#!/usr/bin/env python3
"""Validate a bounded training run before chaining the next GPU job."""
import argparse
import csv
import json
import math
from pathlib import Path

import torch


def check_run(root: Path, run_name: str, steps: int) -> dict:
    curve = root / "artifacts/tables" / f"train_{run_name}_curve.csv"
    checkpoint = root / "checkpoints/defense" / f"{run_name}_best.pt"
    with curve.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if [int(row["step"]) for row in rows] != list(range(1, steps + 1)):
        raise ValueError("Training curve is incomplete or has duplicate steps")
    for row in rows:
        for key in ("loss_total", "loss_spk_global", "loss_rec", "loss_energy"):
            if not math.isfinite(float(row[key])):
                raise ValueError(f"Non-finite {key} at step {row['step']}")
    validations = [float(row["val_speaker_sim_tel"]) for row in rows
                   if math.isfinite(float(row["val_speaker_sim_tel"]))]
    if not validations:
        raise ValueError("No finite validation measurement")
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = payload["model_state_dict"]
    if not state or any(not torch.isfinite(tensor).all().item() for tensor in state.values()):
        raise ValueError("Missing or non-finite checkpoint weights")
    if payload["run_name"] != run_name or not 1 <= int(payload["step"]) <= steps:
        raise ValueError("Checkpoint identity does not match this run")
    return {"ok": True, "run_name": run_name, "steps": steps,
            "dataset": payload["dataset"], "best_step": int(payload["step"]),
            "best_val_speaker_sim_tel": float(payload["best_val_speaker_sim_tel"]),
            "final_loss": float(rows[-1]["loss_total"]),
            "checkpoint": str(checkpoint),
            "scope": "Numerical and artifact integrity only; not a defense-efficacy claim."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run_name", required=True)
    parser.add_argument("--steps", type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = check_run(root, args.run_name, args.steps)
    output = root / "artifacts/audit" / f"{args.run_name}_training.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
