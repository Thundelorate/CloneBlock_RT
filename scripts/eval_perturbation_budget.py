#!/usr/bin/env python3
"""Measure CloneBlock perturbation and telephony-relative STOI on one split."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml
from pystoi import stoi

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.defense_stftmask import STFTMaskDefense
from src.transforms.telephony import TelephonyTransform


def parse_specs(value: str) -> list[tuple[str, Path]]:
    specs = []
    for token in value.split(","):
        name, checkpoint = token.strip().split(":", 1)
        specs.append((name, Path(checkpoint)))
    return specs


def load_model(path: Path, device: torch.device) -> STFTMaskDefense:
    payload = torch.load(path, map_location=device, weights_only=True)
    model = STFTMaskDefense(payload["model_config"]).to(device).eval()
    model.load_state_dict(payload["model_state_dict"], strict=True)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="vctk", choices=["vctk", "librispeech"])
    parser.add_argument("--split", default="val", choices=["train", "val", "test"])
    parser.add_argument("--method_specs", required=True, help="Comma-separated name:checkpoint pairs")
    parser.add_argument("--max_utts", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output_prefix", type=Path, required=True)
    parser.add_argument("--telephony_config", type=Path, default=REPO_ROOT / "configs/telephony.yaml")
    args = parser.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    with (REPO_ROOT / f"data/splits/{args.dataset}/{args.split}.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rng = random.Random(args.seed)
    if args.max_utts > 0 and len(rows) > args.max_utts:
        rows = rng.sample(rows, args.max_utts)
    with args.telephony_config.open(encoding="utf-8") as handle:
        raw_cfg = yaml.safe_load(handle) or {}
    tp_cfg = raw_cfg.get("telephony", raw_cfg)
    tp_cfg.setdefault("codec", {})["enabled"] = False
    param_source = TelephonyTransform(tp_cfg, seed=args.seed)
    channel_params = [param_source.sample_params() for _ in rows]
    detail = []
    for method, checkpoint in parse_specs(args.method_specs):
        model = load_model(checkpoint, device)
        telephony = TelephonyTransform(tp_cfg, seed=args.seed)
        for index, row in enumerate(rows):
            path = REPO_ROOT / f"data/processed/{args.dataset}/wav16k" / row["path"]
            clean, sr = sf.read(path, dtype="float32")
            if clean.ndim == 2:
                clean = clean.mean(axis=1)
            with torch.inference_mode():
                defended = model(torch.from_numpy(clean).to(device)).detach().cpu().numpy().astype(np.float32)
            n = min(len(clean), len(defended))
            clean, defended = clean[:n], defended[:n]
            delta = defended - clean
            signal_rms = float(np.sqrt(np.mean(clean ** 2) + 1e-12))
            perturb_rms = float(np.sqrt(np.mean(delta ** 2) + 1e-12))
            tele_clean = telephony.apply_with_params(clean, sr, channel_params[index])
            tele_defended = telephony.apply_with_params(defended, sr, channel_params[index])
            detail.append({
                "method": method, "speaker_id": row["speaker_id"], "utter_id": row["utter_id"],
                "signal_rms": signal_rms, "perturb_rms": perturb_rms,
                "snr_db": 20.0 * math.log10(signal_rms / perturb_rms),
                "relative_l2": float(np.linalg.norm(delta) / (np.linalg.norm(clean) + 1e-12)),
                "linf": float(np.max(np.abs(delta))),
                "stoi_tele_clean_vs_tele_defended": float(stoi(tele_clean, tele_defended, sr, extended=False)),
            })
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    detail_path = args.output_prefix.with_name(args.output_prefix.name + "_per_utterance.csv")
    with detail_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(detail[0]))
        writer.writeheader()
        writer.writerows(detail)
    summary = []
    for method, _ in parse_specs(args.method_specs):
        subset = [row for row in detail if row["method"] == method]
        out = {"method": method, "n_utterances": len(subset)}
        for field in ("perturb_rms", "snr_db", "relative_l2", "linf", "stoi_tele_clean_vs_tele_defended"):
            values = np.asarray([row[field] for row in subset], dtype=np.float64)
            out[field + "_mean"] = float(values.mean())
            out[field + "_std"] = float(values.std())
        summary.append(out)
    summary_path = args.output_prefix.with_name(args.output_prefix.name + "_summary.csv")
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    args.output_prefix.with_suffix(".json").write_text(json.dumps({
        "dataset": args.dataset, "split": args.split, "seed": args.seed,
        "telephony_pair": "tele_clean vs tele_defended with shared parameters",
        "summary_csv": str(summary_path), "per_utterance_csv": str(detail_path),
        "summary": summary,
    }, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
