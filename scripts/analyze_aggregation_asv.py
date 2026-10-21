#!/usr/bin/env python3
"""Analyze independent-enrollment aggregation attacks with speaker bootstrap CIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


GROUP_COLUMNS = ["method", "encoder", "strategy", "k"]
METRICS = ["target_score", "margin", "acceptance"]


def percentile_interval(values: np.ndarray) -> tuple[float, float]:
    return tuple(float(value) for value in np.percentile(values, [2.5, 97.5]))


def compute_eer(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=np.float64)
    target = scores[labels]
    impostor = scores[~labels]
    if len(target) == 0 or len(impostor) == 0:
        raise ValueError("EER requires both target and impostor trials")
    thresholds = np.r_[np.inf, np.sort(np.unique(scores))[::-1], -np.inf]
    fars = np.asarray([np.mean(impostor >= threshold) for threshold in thresholds])
    frrs = np.asarray([np.mean(target < threshold) for threshold in thresholds])
    index = int(np.argmin(np.abs(fars - frrs)))
    return float((fars[index] + frrs[index]) / 2), float(thresholds[index])


def bootstrap_eers_from_weights(
    frame: pd.DataFrame,
    speakers: list[str],
    weights: np.ndarray,
    max_thresholds: int = 512,
) -> np.ndarray:
    """Vectorized cluster-bootstrap EERs from precomputed speaker counts."""
    scores = frame["score"].to_numpy(dtype=np.float64)
    if len(scores) == 0:
        raise ValueError("Cannot bootstrap EER from an empty trial frame")
    unique = np.unique(scores)
    if len(unique) > max_thresholds:
        unique = np.unique(np.quantile(unique, np.linspace(0, 1, max_thresholds)))
    thresholds = np.r_[np.inf, unique[::-1], -np.inf]
    false_accepts = np.zeros((len(speakers), len(thresholds)), dtype=np.float64)
    false_rejects = np.zeros_like(false_accepts)
    target_counts = np.zeros(len(speakers), dtype=np.float64)
    impostor_counts = np.zeros(len(speakers), dtype=np.float64)

    for index, speaker in enumerate(speakers):
        subset = frame.loc[frame["speaker"].eq(speaker)]
        target = subset.loc[subset["label"].eq("target"), "score"].to_numpy(dtype=np.float64)
        impostor = subset.loc[subset["label"].eq("impostor"), "score"].to_numpy(dtype=np.float64)
        if len(target) == 0 or len(impostor) == 0:
            raise ValueError(f"Speaker {speaker} lacks target or impostor trials")
        target_counts[index] = len(target)
        impostor_counts[index] = len(impostor)
        false_accepts[index] = (impostor[:, None] >= thresholds[None, :]).sum(axis=0)
        false_rejects[index] = (target[:, None] < thresholds[None, :]).sum(axis=0)

    far = (weights @ false_accepts) / (weights @ impostor_counts)[:, None]
    frr = (weights @ false_rejects) / (weights @ target_counts)[:, None]
    closest = np.argmin(np.abs(far - frr), axis=1)
    draw_indices = np.arange(len(weights))
    return (far[draw_indices, closest] + frr[draw_indices, closest]) / 2


def bootstrap_macro(
    speaker_values: pd.Series, draws: int, rng: np.random.Generator
) -> tuple[float, float, float]:
    values = speaker_values.to_numpy(dtype=np.float64)
    if len(values) < 2:
        raise ValueError("Speaker bootstrap requires at least two speakers")
    sampled = values[rng.integers(0, len(values), size=(draws, len(values)))].mean(axis=1)
    low, high = percentile_interval(sampled)
    return float(values.mean()), low, high


def paired_bootstrap(
    left: pd.Series,
    right: pd.Series,
    draws: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, int]:
    joined = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(joined) < 2:
        raise ValueError("Paired bootstrap requires at least two shared speakers")
    differences = (joined["left"] - joined["right"]).to_numpy(dtype=np.float64)
    sampled = differences[
        rng.integers(0, len(differences), size=(draws, len(differences)))
    ].mean(axis=1)
    low, high = percentile_interval(sampled)
    return float(differences.mean()), low, high, len(differences)


def summarize_scalar_metrics(
    aggregates: pd.DataFrame, draws: int, seed: int
) -> pd.DataFrame:
    rows: list[dict] = []
    for group_key, frame in aggregates.groupby(GROUP_COLUMNS, sort=True):
        for metric in METRICS:
            if metric not in frame or frame[metric].isna().all():
                continue
            per_speaker = frame.groupby("speaker")[metric].mean()
            rng = np.random.default_rng(seed + len(rows))
            estimate, low, high = bootstrap_macro(per_speaker, draws, rng)
            rows.append(
                {
                    **dict(zip(GROUP_COLUMNS, group_key)),
                    "metric": metric,
                    "estimate": estimate,
                    "ci_low": low,
                    "ci_high": high,
                    "speakers": len(per_speaker),
                }
            )
    return pd.DataFrame(rows)


def summarize_eer(trials: pd.DataFrame, draws: int, seed: int) -> pd.DataFrame:
    rows: list[dict] = []
    for group_key, frame in trials.groupby(GROUP_COLUMNS, sort=True):
        labels = frame["label"].eq("target").to_numpy()
        estimate, threshold = compute_eer(labels, frame["score"].to_numpy())
        speakers = sorted(frame["speaker"].unique())
        if len(speakers) < 2:
            raise ValueError("EER bootstrap requires at least two speakers")
        rng = np.random.default_rng(seed + 100000 + len(rows))
        weights = rng.multinomial(
            len(speakers), np.full(len(speakers), 1 / len(speakers)), size=draws
        )
        boot = bootstrap_eers_from_weights(frame, speakers, weights)
        low, high = percentile_interval(boot)
        rows.append(
            {
                **dict(zip(GROUP_COLUMNS, group_key)),
                "metric": "eer",
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "speakers": len(speakers),
                "eer_threshold": threshold,
            }
        )
    return pd.DataFrame(rows)


def bootstrap_eer_difference(
    left: pd.DataFrame,
    right: pd.DataFrame,
    draws: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, int]:
    speakers = sorted(set(left["speaker"]) & set(right["speaker"]))
    if len(speakers) < 2:
        raise ValueError("Paired EER bootstrap requires at least two shared speakers")
    left = left.loc[left["speaker"].isin(speakers)]
    right = right.loc[right["speaker"].isin(speakers)]

    def eer(frame: pd.DataFrame) -> float:
        return compute_eer(frame["label"].eq("target").to_numpy(), frame["score"].to_numpy())[0]

    estimate = eer(left) - eer(right)
    weights = rng.multinomial(
        len(speakers), np.full(len(speakers), 1 / len(speakers)), size=draws
    )
    differences = bootstrap_eers_from_weights(left, speakers, weights) - bootstrap_eers_from_weights(
        right, speakers, weights
    )
    low, high = percentile_interval(differences)
    return float(estimate), low, high, len(speakers)


def summarize_eer_contrasts(trials: pd.DataFrame, draws: int, seed: int) -> pd.DataFrame:
    rows: list[dict] = []
    methods = sorted(trials["method"].unique())
    encoders = sorted(trials["encoder"].unique())
    ks = sorted(int(value) for value in trials["k"].unique())
    strategies = sorted(trials["strategy"].unique())

    def select(method: str, encoder: str, strategy: str, k: int) -> pd.DataFrame:
        return trials.loc[
            trials["method"].eq(method)
            & trials["encoder"].eq(encoder)
            & trials["strategy"].eq(strategy)
            & trials["k"].eq(k)
        ]

    def add(contrast: str, method: str, encoder: str, strategy: str, k: int,
            left: pd.DataFrame, right: pd.DataFrame) -> None:
        rng = np.random.default_rng(seed + 300000 + len(rows))
        estimate, low, high, speakers = bootstrap_eer_difference(left, right, draws, rng)
        rows.append(
            {
                "contrast": contrast,
                "method": method,
                "encoder": encoder,
                "strategy": strategy,
                "k": k,
                "metric": "eer",
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "speakers": speakers,
            }
        )

    for method in methods:
        for encoder in encoders:
            for strategy in strategies:
                baseline = select(method, encoder, strategy, 1)
                for k in ks:
                    add(
                        "eer_change_vs_k1",
                        method,
                        encoder,
                        strategy,
                        k,
                        select(method, encoder, strategy, k),
                        baseline,
                    )
            for k in ks:
                random = select(method, encoder, "random_K", k)
                self_consistency = select(method, encoder, "self_consistency_K", k)
                contiguous = select(method, encoder, "contiguous_K", k)
                add(
                    "eer_change_selfcons_vs_random",
                    method,
                    encoder,
                    "self_consistency_K-random_K",
                    k,
                    self_consistency,
                    random,
                )
                add(
                    "eer_change_selfcons_vs_contiguous",
                    method,
                    encoder,
                    "self_consistency_K-contiguous_K",
                    k,
                    self_consistency,
                    contiguous,
                )
    return pd.DataFrame(rows)


def speaker_metric(
    aggregates: pd.DataFrame,
    method: str,
    encoder: str,
    strategy: str,
    k: int,
    metric: str,
) -> pd.Series:
    selected = aggregates.loc[
        aggregates["method"].eq(method)
        & aggregates["encoder"].eq(encoder)
        & aggregates["strategy"].eq(strategy)
        & aggregates["k"].eq(k)
    ]
    return selected.groupby("speaker")[metric].mean()


def summarize_contrasts(
    aggregates: pd.DataFrame, draws: int, seed: int
) -> pd.DataFrame:
    rows: list[dict] = []
    methods = sorted(aggregates["method"].unique())
    encoders = sorted(aggregates["encoder"].unique())
    ks = sorted(int(value) for value in aggregates["k"].unique())
    strategies = sorted(aggregates["strategy"].unique())

    def add(
        contrast: str,
        method: str,
        encoder: str,
        strategy: str,
        k: int,
        metric: str,
        left: pd.Series,
        right: pd.Series,
    ) -> None:
        rng = np.random.default_rng(seed + 200000 + len(rows))
        estimate, low, high, speakers = paired_bootstrap(left, right, draws, rng)
        rows.append(
            {
                "contrast": contrast,
                "method": method,
                "encoder": encoder,
                "strategy": strategy,
                "k": k,
                "metric": metric,
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "speakers": speakers,
            }
        )

    for method in methods:
        for encoder in encoders:
            for metric in METRICS:
                if metric not in aggregates:
                    continue
                for strategy in strategies:
                    baseline = speaker_metric(aggregates, method, encoder, strategy, 1, metric)
                    for k in ks:
                        current = speaker_metric(aggregates, method, encoder, strategy, k, metric)
                        add("aggregation_gain_vs_k1", method, encoder, strategy, k, metric, current, baseline)
                for k in ks:
                    random = speaker_metric(aggregates, method, encoder, "random_K", k, metric)
                    self_consistency = speaker_metric(
                        aggregates, method, encoder, "self_consistency_K", k, metric
                    )
                    contiguous = speaker_metric(
                        aggregates, method, encoder, "contiguous_K", k, metric
                    )
                    add(
                        "selection_gain_selfcons_vs_random",
                        method,
                        encoder,
                        "self_consistency_K-random_K",
                        k,
                        metric,
                        self_consistency,
                        random,
                    )
                    add(
                        "fragmentation_gain_selfcons_vs_contiguous",
                        method,
                        encoder,
                        "self_consistency_K-contiguous_K",
                        k,
                        metric,
                        self_consistency,
                        contiguous,
                    )
    return pd.DataFrame(rows)


def plot_curves(summary: pd.DataFrame, output: Path) -> None:
    methods = [value for value in ("none", "reference", "realistic") if value in set(summary.method)]
    encoders = [value for value in ("ecapa", "xvector") if value in set(summary.encoder)]
    colors = {"random_K": "#3b6fb6", "self_consistency_K": "#c44e52", "contiguous_K": "#3f8f5f"}
    labels = {"random_K": "Random", "self_consistency_K": "Self-consistency", "contiguous_K": "Contiguous control"}
    figure, axes = plt.subplots(
        len(encoders), len(methods), figsize=(4.2 * len(methods), 3.4 * len(encoders)),
        sharex=True, sharey=True, squeeze=False,
    )
    for row_index, encoder in enumerate(encoders):
        for column_index, method in enumerate(methods):
            axis = axes[row_index, column_index]
            frame = summary.loc[
                summary["encoder"].eq(encoder)
                & summary["method"].eq(method)
                & summary["metric"].eq("target_score")
            ]
            for strategy in ("random_K", "self_consistency_K", "contiguous_K"):
                line = frame.loc[frame["strategy"].eq(strategy)].sort_values("k")
                if line.empty:
                    continue
                axis.plot(line["k"], line["estimate"], marker="o", color=colors[strategy], label=labels[strategy])
                axis.fill_between(line["k"], line["ci_low"], line["ci_high"], color=colors[strategy], alpha=0.16)
            axis.set_xscale("log", base=2)
            axis.set_xticks([1, 2, 4, 8, 16], labels=["1", "2", "4", "8", "16"])
            axis.grid(alpha=0.22)
            axis.set_title(f"{method} | {encoder}")
            axis.set_xlabel("Aggregated fragments K")
            if column_index == 0:
                axis.set_ylabel("Target similarity")
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, legend_labels, loc="upper center", ncol=3, frameon=False)
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=220, bbox_inches="tight")
    figure.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregates", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--contrasts", type=Path, required=True)
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    aggregates = pd.read_csv(args.aggregates)
    trials = pd.read_csv(args.trials)
    aggregates["acceptance"] = aggregates["target_score"] >= aggregates["threshold"]
    scalar = summarize_scalar_metrics(aggregates, args.draws, args.seed)
    eer = summarize_eer(trials, args.draws, args.seed)
    summary = pd.concat([scalar, eer], ignore_index=True, sort=False)
    contrasts = pd.concat(
        [
            summarize_contrasts(aggregates, args.draws, args.seed),
            summarize_eer_contrasts(trials, args.draws, args.seed),
        ],
        ignore_index=True,
        sort=False,
    )

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.contrasts.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    contrasts.to_csv(args.contrasts, index=False)
    plot_curves(summary, args.figure)
    metadata = {
        "bootstrap_draws": args.draws,
        "seed": args.seed,
        "aggregate_rows": len(aggregates),
        "trial_rows": len(trials),
        "summary_rows": len(summary),
        "contrast_rows": len(contrasts),
    }
    args.summary.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
