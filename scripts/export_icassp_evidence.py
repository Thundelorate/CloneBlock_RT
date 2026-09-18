#!/usr/bin/env python3
"""Export verified ICASSP evidence tables from the frozen 2026-09-19 runs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "artifacts" / "tables"
OUT = TABLES / "paper_icassp"
METHODS = ("no_defense", "reference_v0p2", "realistic_selected")
SOURCES: set[Path] = set()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    SOURCES.add(path)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, str]], fields: list[str]) -> Path:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metric_map(rows: list[dict[str, str]], method: str, strategy: str) -> dict[str, dict[str, str]]:
    selected = [
        row for row in rows
        if row["kind"] == "absolute"
        and row["method"] == method
        and row["strategy"] == strategy
    ]
    return {row["metric"]: row for row in selected}


def pack_metric(output: dict[str, str], prefix: str, row: dict[str, str]) -> None:
    output[prefix] = row["estimate"]
    output[f"{prefix}_ci_low"] = row["ci_low"]
    output[f"{prefix}_ci_high"] = row["ci_high"]


def export_security() -> list[Path]:
    outputs: list[Path] = []
    main_path = TABLES / "bootstrap_ci_vctk_test_ecapa_none_20260919.csv"
    main_rows = read_csv(main_path)
    result = []
    strategies = (
        ("bestK_by_self_consistency", "realistic"),
        ("bestK_by_clean_consistency", "oracle_reference"),
    )
    for strategy, view in strategies:
        for method in METHODS:
            metrics = metric_map(main_rows, method, strategy)
            row = {
                "encoder": "speechbrain_ecapa",
                "method": method,
                "view": view,
                "strategy": strategy,
                "selection_source": metrics["AUCK"]["selection_source"],
                "n_speakers": metrics["AUCK"]["n_speakers"],
                "n_sessions": metrics["AUCK"]["n_sessions"],
            }
            for metric, prefix in (
                ("MeanSim@1", "meansim_k1"),
                ("MeanSim@16", "meansim_k16"),
                ("AUCK", "auck"),
                ("slope_16_1", "slope_k16_k1"),
            ):
                pack_metric(row, prefix, metrics[metric])
            result.append(row)
    fields = [
        "encoder", "method", "view", "strategy", "selection_source",
        "meansim_k1", "meansim_k1_ci_low", "meansim_k1_ci_high",
        "meansim_k16", "meansim_k16_ci_low", "meansim_k16_ci_high",
        "auck", "auck_ci_low", "auck_ci_high",
        "slope_k16_k1", "slope_k16_k1_ci_low", "slope_k16_k1_ci_high",
        "n_speakers", "n_sessions",
    ]
    outputs.append(write_csv("main_security_ecapa.csv", result, fields))

    codec_rows = []
    for codec, tag in (("none", "none"), ("opus16k", "opus16k"), ("g711", "g711")):
        rows = read_csv(TABLES / f"bootstrap_ci_vctk_test_ecapa_{tag}_20260919.csv")
        for method in METHODS:
            metrics = metric_map(rows, method, "bestK_by_self_consistency")
            row = {
                "codec": codec,
                "encoder": "speechbrain_ecapa",
                "method": method,
                "selection_source": "tele_defended",
                "n_speakers": metrics["AUCK"]["n_speakers"],
                "n_sessions": metrics["AUCK"]["n_sessions"],
            }
            pack_metric(row, "meansim_k16", metrics["MeanSim@16"])
            pack_metric(row, "auck", metrics["AUCK"])
            codec_rows.append(row)
    outputs.append(write_csv(
        "codec_security_ecapa.csv",
        codec_rows,
        [
            "codec", "encoder", "method", "selection_source",
            "meansim_k16", "meansim_k16_ci_low", "meansim_k16_ci_high",
            "auck", "auck_ci_low", "auck_ci_high", "n_speakers", "n_sessions",
        ],
    ))
    return outputs


def combine_asv(prefix: str, filename: str) -> Path:
    rows = []
    for encoder_tag, encoder in (("ecapa", "speechbrain_ecapa"), ("xvector", "speechbrain_xvector")):
        eer_path = TABLES / f"{prefix}_{encoder_tag}_{filename}_eer.csv"
        margin_path = TABLES / f"{prefix}_{encoder_tag}_{filename}_margin.csv"
        eers = read_csv(eer_path)
        margins = {row["method"]: row for row in read_csv(margin_path)}
        for row in eers:
            margin = margins[row["method"]]
            rows.append({
                "encoder": encoder,
                "method": row["method"],
                "eer": row["eer"],
                "target_impostor_margin": margin["margin_mean"],
                "n_target": row["n_target"],
                "n_impostor": row["n_impostor"],
            })
    return write_csv(
        f"{prefix}_{filename}_asv.csv",
        rows,
        ["encoder", "method", "eer", "target_impostor_margin", "n_target", "n_impostor"],
    )


def export_supporting() -> list[Path]:
    outputs = []
    outputs.append(combine_asv("vctk_test", "none_20260919"))

    official_quality_path = OUT / "quality_official_bootstrap.csv"
    if not official_quality_path.is_file():
        raise FileNotFoundError(official_quality_path)
    quality = read_csv(official_quality_path)
    outputs.append(write_csv(
        "quality_summary.csv", quality,
        [
            "telephony", "metric", "estimate", "ci_low", "ci_high",
            "n_speakers", "n_utterances", "bootstrap_draws", "bootstrap_seed",
        ],
    ))
    budget = read_csv(TABLES / "vctk_test_budget_20260919_summary.csv")
    outputs.append(write_csv(
        "perturbation_budget.csv", budget,
        list(budget[0].keys()),
    ))
    latency = read_csv(TABLES / "latency_v0p1_B_v2.csv")
    outputs.append(write_csv("streaming_latency.csv", latency, list(latency[0].keys())))

    xtts = read_csv(TABLES / "vctk_xtts_summary_20260919.csv")
    xtts = [
        row for row in xtts
        if row["metric"] in {
            "target_impostor_margin",
            "paired_target_impostor_margin_delta",
            "cosine",
            "paired_cosine_delta",
        }
    ]
    outputs.append(write_csv(
        "xtts_summary.csv", xtts,
        [
            "encoder", "K", "condition", "metric", "estimate", "ci_low", "ci_high",
            "n_speakers", "n_rows", "bootstrap_draws", "bootstrap_seed",
        ],
    ))
    return outputs


def export_optional_selection_ablation() -> list[Path]:
    required = [
        TABLES / f"bootstrap_ci_vctk_ablation_{tag}_defended_20260919.csv"
        for tag in ("ecapa", "xvector")
    ]
    if not all(path.is_file() for path in required):
        return []

    result = []
    for encoder_tag, encoder in (("ecapa", "speechbrain_ecapa"), ("xvector", "speechbrain_xvector")):
        sources = (
            ("tele_defended", TABLES / f"bootstrap_ci_vctk_test_{encoder_tag}_none_20260919.csv"),
            ("defended", TABLES / f"bootstrap_ci_vctk_ablation_{encoder_tag}_defended_20260919.csv"),
        )
        for source, path in sources:
            rows = read_csv(path)
            metrics = metric_map(rows, "realistic_selected", "bestK_by_self_consistency")
            row = {
                "encoder": encoder,
                "selection_source": source,
                "method": "realistic_selected",
                "n_speakers": metrics["AUCK"]["n_speakers"],
                "n_sessions": metrics["AUCK"]["n_sessions"],
            }
            pack_metric(row, "meansim_k16", metrics["MeanSim@16"])
            pack_metric(row, "auck", metrics["AUCK"])
            result.append(row)
    outputs = [write_csv(
        "selection_source_ablation.csv",
        result,
        [
            "encoder", "selection_source", "method",
            "meansim_k16", "meansim_k16_ci_low", "meansim_k16_ci_high",
            "auck", "auck_ci_low", "auck_ci_high", "n_speakers", "n_sessions",
        ],
    )]

    oracle_required = [
        TABLES / f"vctk_oracle_{tag}_none_20260919_eer.csv"
        for tag in ("ecapa", "xvector")
    ]
    if all(path.is_file() for path in oracle_required):
        outputs.append(combine_asv("vctk_oracle", "none_20260919"))
    return outputs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = export_security() + export_supporting() + export_optional_selection_ablation()
    manifest = {
        "protocol": "icassp_evidence_export_v1",
        "sources": {
            str(path.relative_to(ROOT)): {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(SOURCES)
        },
        "outputs": {
            str(path.relative_to(ROOT)): {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(outputs)
        },
    }
    manifest_path = OUT / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": str(OUT),
        "n_sources": len(SOURCES),
        "n_outputs": len(outputs),
        "manifest": str(manifest_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
