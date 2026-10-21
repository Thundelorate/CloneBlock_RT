#!/usr/bin/env python3
"""Export paper-facing LaTeX tables for the aggregation ASV experiment."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


METHOD_LABELS = {
    "none": "No defense",
    "reference": "Reference defense",
    "realistic": "Realistic defense",
}
STRATEGY_LABELS = {
    "random_K": "Random",
    "self_consistency_K": "Self-consistency",
    "contiguous_K": "Contiguous",
}


def scalar(summary: pd.DataFrame, method: str, encoder: str, strategy: str, k: int, metric: str) -> pd.Series:
    selected = summary.loc[
        summary["method"].eq(method)
        & summary["encoder"].eq(encoder)
        & summary["strategy"].eq(strategy)
        & summary["k"].eq(k)
        & summary["metric"].eq(metric)
    ]
    if len(selected) != 1:
        raise ValueError(
            f"Expected one summary row for {(method, encoder, strategy, k, metric)}, found {len(selected)}"
        )
    return selected.iloc[0]


def contrast(
    contrasts: pd.DataFrame,
    name: str,
    method: str,
    encoder: str,
    strategy: str,
    k: int,
    metric: str,
) -> pd.Series:
    selected = contrasts.loc[
        contrasts["contrast"].eq(name)
        & contrasts["method"].eq(method)
        & contrasts["encoder"].eq(encoder)
        & contrasts["strategy"].eq(strategy)
        & contrasts["k"].eq(k)
        & contrasts["metric"].eq(metric)
    ]
    if len(selected) != 1:
        raise ValueError(
            f"Expected one contrast row for {(name, method, encoder, strategy, k, metric)}, "
            f"found {len(selected)}"
        )
    return selected.iloc[0]


def number(row: pd.Series, percent: bool = False, with_ci: bool = False) -> str:
    scale = 100 if percent else 1
    digits = 2 if percent else 3
    estimate = float(row["estimate"]) * scale
    value = f"{estimate:.{digits}f}"
    if with_ci:
        low = float(row["ci_low"]) * scale
        high = float(row["ci_high"]) * scale
        value += f" [{low:.{digits}f}, {high:.{digits}f}]"
    return value


def write_strength_table(summary: pd.DataFrame, output: Path) -> None:
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Attack strategy & Metric & $K{=}1$ & $K{=}2$ & $K{=}4$ & $K{=}8$ & $K{=}16$ \\",
        r"\midrule",
    ]
    for strategy in ("random_K", "self_consistency_K", "contiguous_K"):
        for metric, label, percent in (
            ("target_score", r"Target similarity $\uparrow$", False),
            ("margin", r"Target--impostor margin $\uparrow$", False),
            ("eer", r"EER (\%) $\downarrow$", True),
        ):
            values = [
                number(scalar(summary, "none", "ecapa", strategy, k, metric), percent=percent)
                for k in (1, 2, 4, 8, 16)
            ]
            lines.append(
                f"{STRATEGY_LABELS[strategy]} & {label} & " + " & ".join(values) + r" \\" 
            )
        lines.append(r"\addlinespace")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_defense_table(summary: pd.DataFrame, output: Path) -> None:
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"System & Encoder & Target sim. $\uparrow$ & Margin $\uparrow$ & EER (\%) $\downarrow$ & Accept. (\%) $\uparrow$ \\",
        r"\midrule",
    ]
    for method in ("none", "reference", "realistic"):
        for encoder in ("ecapa", "xvector"):
            values = [
                number(scalar(summary, method, encoder, "self_consistency_K", 16, "target_score")),
                number(scalar(summary, method, encoder, "self_consistency_K", 16, "margin")),
                number(scalar(summary, method, encoder, "self_consistency_K", 16, "eer"), percent=True),
                number(scalar(summary, method, encoder, "self_consistency_K", 16, "acceptance"), percent=True),
            ]
            lines.append(
                f"{METHOD_LABELS[method]} & {encoder.upper()} & " + " & ".join(values) + r" \\" 
            )
        lines.append(r"\addlinespace")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contrast_table(contrasts: pd.DataFrame, output: Path) -> None:
    lines = [
        r"\begin{tabular}{lllrrr}",
        r"\toprule",
        r"System & Encoder & Attack & $\Delta$ target sim. & $\Delta$ margin & $\Delta$ EER (pp) \\",
        r"\midrule",
    ]
    for method in ("none", "reference", "realistic"):
        for encoder in ("ecapa", "xvector"):
            for strategy in ("random_K", "self_consistency_K", "contiguous_K"):
                similarity = contrast(
                    contrasts, "aggregation_gain_vs_k1", method, encoder, strategy, 16, "target_score"
                )
                margin = contrast(
                    contrasts, "aggregation_gain_vs_k1", method, encoder, strategy, 16, "margin"
                )
                eer = contrast(
                    contrasts, "eer_change_vs_k1", method, encoder, strategy, 16, "eer"
                )
                lines.append(
                    f"{METHOD_LABELS[method]} & {encoder.upper()} & {STRATEGY_LABELS[strategy]} & "
                    + " & ".join(
                        [
                            number(similarity, with_ci=True),
                            number(margin, with_ci=True),
                            number(eer, percent=True, with_ci=True),
                        ]
                    )
                    + r" \\" 
                )
        lines.append(r"\addlinespace")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_fragmentation_table(contrasts: pd.DataFrame, output: Path) -> None:
    """Export the equal-duration fragmented-vs-contiguous control at K=16."""
    lines = [
        r"\begin{tabular}{llrrr}",
        r"\toprule",
        r"System & Encoder & $\Delta$ target sim. & $\Delta$ margin & $\Delta$ EER (pp) \\",
        r"\midrule",
    ]
    strategy = "self_consistency_K-contiguous_K"
    for method in ("none", "reference", "realistic"):
        for encoder in ("ecapa", "xvector"):
            similarity = contrast(
                contrasts, "fragmentation_gain_selfcons_vs_contiguous",
                method, encoder, strategy, 16, "target_score"
            )
            margin = contrast(
                contrasts, "fragmentation_gain_selfcons_vs_contiguous",
                method, encoder, strategy, 16, "margin"
            )
            eer = contrast(
                contrasts, "eer_change_selfcons_vs_contiguous",
                method, encoder, strategy, 16, "eer"
            )
            lines.append(
                f"{METHOD_LABELS[method]} & {encoder.upper()} & "
                + " & ".join([
                    number(similarity, with_ci=True),
                    number(margin, with_ci=True),
                    number(eer, percent=True, with_ci=True),
                ])
                + r" \\" 
            )
        lines.append(r"\addlinespace")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--contrasts", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    args = parser.parse_args()
    summary = pd.read_csv(args.summary)
    contrasts = pd.read_csv(args.contrasts)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_strength_table(summary, args.output_dir / "aggregation_attack_strength.tex")
    write_defense_table(summary, args.output_dir / "aggregation_defense_comparison.tex")
    write_contrast_table(contrasts, args.output_dir / "aggregation_contrasts.tex")
    write_fragmentation_table(
        contrasts, args.output_dir / "aggregation_fragmentation_control.tex"
    )


if __name__ == "__main__":
    main()
