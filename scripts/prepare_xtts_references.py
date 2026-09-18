#!/usr/bin/env python3
"""Prepare frozen realistic XTTS references from a score-independent manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.metrics.session_attack import pick_indices
from src.metrics.speaker import SpeakerMetric
from src.models.defense_stftmask import STFTMaskDefense
from src.transforms.telephony import TelephonyTransform


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, dtype="float32")
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32), int(sample_rate)


def concat_segments(segments: list[np.ndarray], sample_rate: int, silence_sec: float = 0.1) -> np.ndarray:
    if not segments:
        raise ValueError("Cannot concatenate an empty reference")
    silence = np.zeros(int(round(sample_rate * silence_sec)), dtype=np.float32)
    parts = []
    for index, segment in enumerate(segments):
        if index:
            parts.append(silence)
        parts.append(segment)
    return np.concatenate(parts).astype(np.float32)


def resolve_audio(path_value: str) -> Path:
    path = REPO_ROOT / path_value
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--session_pool_csv", required=True, type=Path)
    parser.add_argument("--defense_checkpoint", required=True, type=Path)
    parser.add_argument("--speaker_checkpoint_dir", required=True)
    parser.add_argument("--telephony_config", default=str(REPO_ROOT / "configs/telephony.yaml"))
    parser.add_argument("--ks", default="1,16,64")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audio_dir", required=True, type=Path)
    args = parser.parse_args()

    if not args.audio_dir.is_absolute():
        args.audio_dir = (REPO_ROOT / args.audio_dir).resolve()
    if not args.output.is_absolute():
        args.output = (REPO_ROOT / args.output).resolve()

    ks = sorted({int(value) for value in args.ks.split(",") if value.strip()})
    if not ks or any(value < 1 for value in ks):
        raise ValueError("ks must contain positive integers")
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    with args.manifest.open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    with args.session_pool_csv.open(newline="", encoding="utf-8") as handle:
        pool_rows = list(csv.DictReader(handle))
    by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pool_rows:
        by_session[row["session_id"]].append(row)

    import yaml
    telephony_payload = yaml.safe_load(Path(args.telephony_config).read_text(encoding="utf-8")) or {}
    telephony = TelephonyTransform(telephony_payload.get("telephony", telephony_payload), seed=args.seed)
    selector = SpeakerMetric({
        "encoder_name": "speechbrain_ecapa",
        "checkpoint_dir": args.speaker_checkpoint_dir,
        "device": str(device),
    })
    payload = torch.load(args.defense_checkpoint, map_location=device)
    defense = STFTMaskDefense(payload.get("model_config", {})).to(device).eval()
    defense.load_state_dict(payload["model_state_dict"], strict=True)

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    output_rows = []
    for item in manifest:
        attack_session = item["attack_session_id"]
        windows = sorted(by_session[attack_session], key=lambda row: row["chunk_id"])
        if len(windows) < max(ks):
            raise ValueError(f"{attack_session} has {len(windows)} windows, need {max(ks)}")
        full_audio, sample_rate = load_wav(resolve_audio(item["attack_path"]))
        with torch.inference_mode():
            defended = defense(torch.from_numpy(full_audio).to(device)).detach().cpu().numpy().astype(np.float32)
        params = telephony.sample_params()
        tele_clean = telephony.apply_with_params(full_audio, sample_rate=sample_rate, params=params)
        tele_defended = telephony.apply_with_params(defended, sample_rate=sample_rate, params=params)

        clean_segments = []
        defended_segments = []
        clean_embeddings = []
        defended_embeddings = []
        for window in windows:
            start = int(round(float(window["start_sec"]) * sample_rate))
            duration = int(round(float(window["dur_sec"]) * sample_rate))
            clean_segment = tele_clean[start : start + duration]
            defended_segment = tele_defended[start : start + duration]
            if len(clean_segment) != duration or len(defended_segment) != duration:
                raise ValueError(f"Incomplete window in {attack_session}: {window['chunk_id']}")
            clean_segments.append(clean_segment)
            defended_segments.append(defended_segment)
            clean_embeddings.append(selector.embed(torch.from_numpy(clean_segment), sample_rate))
            defended_embeddings.append(selector.embed(torch.from_numpy(defended_segment), sample_rate))
        clean_z = F.normalize(torch.stack(clean_embeddings), dim=-1)
        defended_z = F.normalize(torch.stack(defended_embeddings), dim=-1)

        for condition, visible_z, segments in (
            ("baseline_ref", clean_z, clean_segments),
            ("defended_ref", defended_z, defended_segments),
        ):
            for k in ks:
                indices = pick_indices(
                    "bestK_by_self_consistency", visible_z, k, random.Random(args.seed), selection_z=visible_z
                )
                reference = concat_segments([segments[index] for index in indices], sample_rate)
                relative = Path(f"{int(item['order']):02d}_{item['speaker_id']}_{attack_session}_{condition}_K{k}.wav")
                output_path = args.audio_dir / relative
                sf.write(output_path, reference, sample_rate)
                output_rows.append({
                    **item,
                    "condition": condition,
                    "K": str(k),
                    "selection_strategy": "bestK_by_self_consistency",
                    "selection_source": "tele_clean" if condition == "baseline_ref" else "tele_defended",
                    "candidate_count": str(len(windows)),
                    "selected_indices": json.dumps(indices),
                    "reference_duration_sec": f"{len(reference) / sample_rate:.6f}",
                    "reference_path": str(output_path.relative_to(REPO_ROOT)),
                })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    metadata = {
        "protocol": "xtts_realistic_self_consistency_v1",
        "attacker_view": "realistic",
        "selection_encoder": "speechbrain_ecapa",
        "ks": ks,
        "n_manifest_sessions": len(manifest),
        "n_reference_rows": len(output_rows),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "session_pool_sha256": hashlib.sha256(args.session_pool_csv.read_bytes()).hexdigest(),
        "defense_checkpoint_sha256": hashlib.sha256(args.defense_checkpoint.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
