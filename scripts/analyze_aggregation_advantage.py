#!/usr/bin/env python3
"""Summarize and plot single-window versus multi-window attack strength."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


KEY_FIELDS = ("speaker_id", "session_id", "path")
STRATEGIES = ("random_K", "bestK_by_self_consistency")


def load_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            current = list(csv.DictReader(handle))
        if not current:
            raise ValueError(f"Empty result file: {path}")
        rows.extend(current)
    return rows


def _cluster_samples(
    values: np.ndarray,
    speaker_indices: np.ndarray,
    n_speakers: int,
    sampled_speakers: np.ndarray,
) -> np.ndarray:
    sums = np.zeros(n_speakers, dtype=np.float64)
    counts = np.zeros(n_speakers, dtype=np.float64)
    np.add.at(sums, speaker_indices, values)
    np.add.at(counts, speaker_indices, 1.0)
    numerator = sums[sampled_speakers].sum(axis=1)
    denominator = counts[sampled_speakers].sum(axis=1)
    return numerator / denominator


def summarize(
    rows: list[dict[str, str]],
    draws: int = 2000,
    seed: int = 42,
    confidence: float = 0.95,
) -> list[dict[str, object]]:
    if draws < 2 or not 0.0 < confidence < 1.0:
        raise ValueError("Invalid bootstrap configuration")
    methods = sorted({row["method"] for row in rows})
    ks = sorted({int(row["K"]) for row in rows})
    if 1 not in ks:
        raise ValueError("K=1 is required for aggregation-gain contrasts")

    table: dict[tuple[str, str, tuple[str, str, str], int], float] = {}
    for row in rows:
        strategy = row["strategy"]
        if strategy not in STRATEGIES:
            continue
        session = tuple(row[field] for field in KEY_FIELDS)
        key = (row["method"], strategy, session, int(row["K"]))
        if key in table:
            raise ValueError(f"Duplicate result row: {key}")
        value = float(row["cos"])
        if not np.isfinite(value) or not -1.000001 <= value <= 1.000001:
            raise ValueError(f"Invalid cosine score: {value}")
        table[key] = value

    sessions = sorted({key[2] for key in table})
    expected = {
        (method, strategy, session, k)
        for method in methods
        for strategy in STRATEGIES
        for session in sessions
        for k in ks
    }
    missing = expected - set(table)
    if missing:
        raise ValueError(f"Incomplete method/strategy/session/K grid; missing {len(missing)} rows")

    speakers = sorted({session[0] for session in sessions})
    speaker_to_index = {speaker: index for index, speaker in enumerate(speakers)}
    session_speaker = np.asarray([speaker_to_index[session[0]] for session in sessions], dtype=np.int64)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(speakers), size=(draws, len(speakers)))
    tail = (1.0 - confidence) / 2.0
    output: list[dict[str, object]] = []

    def add_row(method: str, contrast: str, strategy: str, k: int, values: np.ndarray) -> None:
        boot = _cluster_samples(values, session_speaker, len(speakers), sampled)
        low, high = np.quantile(boot, [tail, 1.0 - tail])
        output.append(
            {
                "method": method,
                "contrast": contrast,
                "strategy": strategy,
                "K": k,
                "estimate": float(values.mean()),
                "ci_low": float(low),
                "ci_high": float(high),
                "n_speakers": len(speakers),
                "n_sessions": len(sessions),
                "bootstrap_draws": draws,
                "bootstrap_seed": seed,
            }
        )

    for method in methods:
        arrays: dict[tuple[str, int], np.ndarray] = {}
        for strategy in STRATEGIES:
            for k in ks:
                values = np.asarray([table[(method, strategy, session, k)] for session in sessions])
                arrays[(strategy, k)] = values
                add_row(method, "absolute", strategy, k, values)
                if k != 1:
                    add_row(method, "aggregation_gain_vs_k1", strategy, k, values - arrays[(strategy, 1)])
        for k in ks:
            selection_gain = arrays[("bestK_by_self_consistency", k)] - arrays[("random_K", k)]
            add_row(method, "selection_gain_vs_random", "bestK_by_self_consistency", k, selection_gain)
    return output


def write_figure(rows: list[dict[str, object]], output: Path) -> None:
    import matplotlib.pyplot as plt

    absolute = [row for row in rows if row["contrast"] == "absolute"]
    methods = sorted({str(row["method"]) for row in absolute})
    labels = {
        "no_defense": "No defense",
        "reference_v0p2": "Previous defense",
        "realistic_selected": "Realistic defense",
        "random_K": "Random aggregation",
        "bestK_by_self_consistency": "Self-consistency aggregation",
    }
    fig, axes = plt.subplots(1, len(methods), figsize=(4.2 * len(methods), 3.25), sharey=True)
    axes = np.atleast_1d(axes)
    colors = {"random_K": "#3569a8", "bestK_by_self_consistency": "#c64f3d"}
    markers = {"random_K": "o", "bestK_by_self_consistency": "s"}
    for axis, method in zip(axes, methods):
        for strategy in STRATEGIES:
            subset = sorted(
                [row for row in absolute if row["method"] == method and row["strategy"] == strategy],
                key=lambda row: int(row["K"]),
            )
            x = np.asarray([int(row["K"]) for row in subset])
            y = np.asarray([float(row["estimate"]) for row in subset])
            low = np.asarray([float(row["ci_low"]) for row in subset])
            high = np.asarray([float(row["ci_high"]) for row in subset])
            axis.plot(x, y, color=colors[strategy], marker=markers[strategy], label=labels[strategy])
            axis.fill_between(x, low, high, color=colors[strategy], alpha=0.15, linewidth=0)
        axis.set_xscale("log", base=2)
        axis.set_xticks([1, 2, 4, 8, 16], labels=["1", "2", "4", "8", "16"])
        axis.set_ylim(0.45, 1.01)
        axis.set_title(labels.get(method, method))
        axis.set_xlabel("Aggregated windows K")
        axis.grid(True, alpha=0.25)
    axes[0].set_ylabel("Recovery similarity")
    axes[-1].legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=220, bbox_inches="tight")
    if output.suffix.lower() != ".pdf":
        fig.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--figure", type=Path)
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = summarize(load_rows(args.inputs), draws=args.draws, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    metadata = {
        "inputs": [str(path) for path in args.inputs],
        "output": str(args.output),
        "figure": str(args.figure) if args.figure else "",
        "bootstrap": {"unit": "speaker", "draws": args.draws, "seed": args.seed, "confidence": 0.95},
        "contrasts": {
            "aggregation_gain_vs_k1": "MeanSim@K minus MeanSim@1 within the same strategy",
            "selection_gain_vs_random": "Self-consistency minus random aggregation at the same K",
        },
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if args.figure:
        write_figure(result, args.figure)
    print(f"Wrote {len(result)} rows to {args.output}")


if __name__ == "__main__":
    main()
