#!/usr/bin/env python3
"""Speaker-cluster bootstrap for official-transcript VCTK quality metrics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


METRICS = (
    "wer_tele_clean",
    "wer_tele_defended",
    "wer_delta",
    "stoi_tele_clean_vs_tele_defended",
    "stoi_clean_vs_tele_clean",
    "stoi_clean_vs_tele_defended",
)


def interval(rows: list[dict[str, str]], metric: str, draws: int, seed: int) -> tuple[float, float, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["speaker_id"]].append(float(row[metric]))
    speakers = sorted(grouped)
    if len(speakers) < 2:
        raise ValueError("Speaker bootstrap requires at least two speakers")
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(draws):
        picked = rng.integers(0, len(speakers), size=len(speakers))
        values = [value for index in picked for value in grouped[speakers[index]]]
        samples.append(float(np.mean(values)))
    estimate = float(np.mean([float(row[metric]) for row in rows]))
    low, high = np.quantile(np.asarray(samples), [0.025, 0.975])
    return estimate, float(low), float(high)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, nargs="+", type=Path)
    parser.add_argument("--clean_input", type=Path)
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    summary = []
    clean_by_utterance = {}
    if args.clean_input:
        with args.clean_input.open(newline="", encoding="utf-8") as handle:
            clean_rows = list(csv.DictReader(handle))
        if not clean_rows:
            raise ValueError("Clean original quality input is empty")
        clean_by_utterance = {row["utter_id"]: row for row in clean_rows}
        estimate, low, high = interval(clean_rows, "wer_clean_original", args.draws, args.seed)
        summary.append({
            "telephony": "original_clean",
            "metric": "wer_clean_original",
            "estimate": estimate,
            "ci_low": low,
            "ci_high": high,
            "n_speakers": len({row["speaker_id"] for row in clean_rows}),
            "n_utterances": len(clean_rows),
            "bootstrap_draws": args.draws,
            "bootstrap_seed": args.seed,
        })

    for path in args.inputs:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or any(row["reference_source"] != "vctk_official_transcript" for row in rows):
            raise ValueError(f"Invalid official quality rows: {path}")
        codec = rows[0]["telephony"]
        metrics = list(METRICS)
        if clean_by_utterance:
            for row in rows:
                clean = clean_by_utterance.get(row["utter_id"])
                if clean is None:
                    raise ValueError(f"Missing clean-original row for {row['utter_id']}")
                original = float(clean["wer_clean_original"])
                row["wer_channel_delta"] = str(float(row["wer_tele_clean"]) - original)
                row["wer_total_delta"] = str(float(row["wer_tele_defended"]) - original)
            metrics.extend(("wer_channel_delta", "wer_total_delta"))
        for metric in metrics:
            estimate, low, high = interval(rows, metric, args.draws, args.seed)
            summary.append({
                "telephony": codec,
                "metric": metric,
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "n_speakers": len({row["speaker_id"] for row in rows}),
                "n_utterances": len(rows),
                "bootstrap_draws": args.draws,
                "bootstrap_seed": args.seed,
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    args.output.with_suffix(".json").write_text(json.dumps({
        "protocol": "speaker_cluster_bootstrap_quality_v1",
        "confidence": 0.95,
        "draws": args.draws,
        "seed": args.seed,
        "inputs": [str(path) for path in args.inputs],
        "clean_input": str(args.clean_input) if args.clean_input else None,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(summary), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
