#!/usr/bin/env python3
"""Freeze ASV acceptance thresholds from validation-only natural-speech trials."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def calibrate(rows: list[dict[str, str]], method: str, target_far: float) -> dict[str, float | int | str]:
    selected = [row for row in rows if row["method"] == method]
    target = [float(row["score"]) for row in selected if row["label"] == "target"]
    impostor = [float(row["score"]) for row in selected if row["label"] == "impostor"]
    if not target or not impostor:
        raise ValueError("Calibration needs target and impostor validation trials")
    candidates = sorted(set(impostor))
    eligible = []
    for threshold in candidates:
        far = sum(score >= threshold for score in impostor) / len(impostor)
        if far <= target_far:
            eligible.append((threshold, far))
    if not eligible:
        threshold = max(impostor) + 1e-12
        far = 0.0
    else:
        threshold, far = min(eligible, key=lambda item: item[0])
    tar = sum(score >= threshold for score in target) / len(target)
    return {
        "method": method,
        "threshold": threshold,
        "target_far": target_far,
        "achieved_far": far,
        "target_accept_rate": tar,
        "n_target": len(target),
        "n_impostor": len(impostor),
        "far_resolution": 1.0 / len(impostor),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", nargs="+", required=True, type=Path)
    parser.add_argument("--method", default="no_defense")
    parser.add_argument("--target_far", type=float, default=0.01)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 0.0 <= args.target_far <= 1.0:
        raise ValueError("target_far must be in [0, 1]")

    results = []
    inputs = []
    for path in args.trials:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        result = calibrate(rows, args.method, args.target_far)
        encoders = {row["encoder"] for row in rows}
        if len(encoders) != 1:
            raise ValueError(f"Expected one encoder in {path}")
        result["encoder"] = next(iter(encoders))
        results.append(result)
        inputs.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})

    payload = {
        "protocol": "validation_natural_speech_operating_point_v1",
        "split": "validation",
        "comparison": "accept if cosine >= threshold",
        "inputs": inputs,
        "thresholds": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
