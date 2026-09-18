#!/usr/bin/env python3
"""Select a validation-sweep model under an explicit intelligibility constraint."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def security_rows(paths: list[Path]) -> dict[str, dict[str, str]]:
    output = {}
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["strategy"] == "bestK_by_self_consistency":
                    output[row["method"]] = row
    return output


def budget_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["method"]: row for row in csv.DictReader(handle)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security_csv", type=Path, nargs="+", required=True)
    parser.add_argument("--budget_csv", type=Path, required=True)
    parser.add_argument("--checkpoint_dir", type=Path, required=True)
    parser.add_argument("--stoi_floor", type=float, default=0.95)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    security = security_rows(args.security_csv)
    budget = budget_rows(args.budget_csv)
    candidates = []
    for method in sorted(set(security) & set(budget)):
        if not method.startswith("realistic_a"):
            continue
        alpha = float(method.removeprefix("realistic_a").replace("p", "."))
        candidates.append({
            "method": method, "alpha": alpha,
            "k16": float(security[method]["K16_mean"]),
            "auck": float(security[method]["AUCK"]),
            "stoi": float(budget[method]["stoi_tele_clean_vs_tele_defended_mean"]),
            "relative_l2": float(budget[method]["relative_l2_mean"]),
        })
    if not candidates:
        raise ValueError("No matching realistic sweep methods")
    feasible = [row for row in candidates if row["stoi"] >= args.stoi_floor]
    pool = feasible or candidates
    if feasible:
        selected = min(pool, key=lambda row: (row["k16"], row["auck"], row["alpha"]))
        rule = "minimum validation K16, then AUCK and alpha, among models meeting STOI floor"
    else:
        selected = max(pool, key=lambda row: (row["stoi"], -row["k16"], -row["alpha"]))
        rule = "fallback: maximum validation STOI because no model met the floor"
    selected["checkpoint"] = str(args.checkpoint_dir / f"{selected['method']}_best.pt")
    payload = {"split": "validation", "stoi_floor": args.stoi_floor, "rule": rule,
               "candidates": candidates, "selected": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    args.output.with_suffix(".txt").write_text(
        f"{selected['alpha']} {selected['checkpoint']}\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
