#!/usr/bin/env python3
"""Apply the predeclared aggregation-advantage decision rule."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def select(
    contrasts: pd.DataFrame, contrast_name: str, strategy: str, metric: str
) -> dict:
    rows = contrasts.loc[
        contrasts["contrast"].eq(contrast_name)
        & contrasts["method"].eq("none")
        & contrasts["encoder"].eq("ecapa")
        & contrasts["strategy"].eq(strategy)
        & contrasts["k"].eq(16)
        & contrasts["metric"].eq(metric)
    ]
    if len(rows) != 1:
        raise ValueError(
            "Expected exactly one no-defense ECAPA K=16 row for "
            f"{contrast_name}/{strategy}/{metric}; found {len(rows)}"
        )
    row = rows.iloc[0]
    return {
        "estimate": float(row["estimate"]),
        "ci_low": float(row["ci_low"]),
        "ci_high": float(row["ci_high"]),
        "n_speakers": int(row["speakers"]),
    }


def build_decision(contrasts: pd.DataFrame) -> dict:
    primary = select(
        contrasts, "aggregation_gain_vs_k1", "random_K", "target_score"
    )
    targeted = select(
        contrasts, "aggregation_gain_vs_k1", "self_consistency_K", "target_score"
    )
    fragmentation = select(
        contrasts,
        "fragmentation_gain_selfcons_vs_contiguous",
        "self_consistency_K-contiguous_K",
        "target_score",
    )
    return {
        "decision_rule_version": "aggregation-advantage-v1",
        "scope": "No-defense ECAPA speaker-similarity proxy on held-out test speakers.",
        "primary_claim": {
            "description": "Random K=16 aggregation improves target similarity over K=1.",
            "contrast": primary,
            "criterion": "estimate > 0 and bootstrap 95% CI lower bound > 0",
            "supported": primary["estimate"] > 0 and primary["ci_low"] > 0,
        },
        "secondary_evidence": {
            "self_consistency_k16_vs_k1_target_similarity": targeted,
            "self_consistency_k16_vs_contiguous_k16_target_similarity": fragmentation,
        },
        "interpretation_guardrail": (
            "This ASV/speaker-representation result measures identity recovery, not "
            "end-to-end cloned-speech quality. Secondary results do not override the "
            "predeclared primary decision rule."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contrasts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    decision = build_decision(pd.read_csv(args.contrasts))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(decision, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
