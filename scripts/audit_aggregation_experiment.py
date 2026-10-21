#!/usr/bin/env python3
"""Audit completeness and leakage controls for aggregation-attack outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


EXPECTED_METHODS = {"none", "reference", "realistic"}
EXPECTED_ENCODERS = {"ecapa", "xvector"}
EXPECTED_STRATEGIES = {"random_K", "self_consistency_K", "contiguous_K"}
EXPECTED_K = {1, 2, 4, 8, 16}
REQUIRED_COLUMNS = {
    "method",
    "encoder",
    "speaker",
    "enrollment_session",
    "attack_session",
    "strategy",
    "representation",
    "k",
    "repeat",
    "selection_id",
    "selected_indices",
    "selected_intervals",
    "selected_duration_sec",
    "selection_span_sec",
    "target_score",
    "max_impostor_score",
    "margin",
}
TRIAL_REQUIRED_COLUMNS = {
    "method",
    "encoder",
    "speaker",
    "enrollment_speaker",
    "enrollment_session",
    "attack_session",
    "strategy",
    "representation",
    "k",
    "repeat",
    "selection_id",
    "label",
    "score",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_indices(value: str) -> tuple[int, ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = [part for part in value.split(";") if part]
    if not isinstance(parsed, list):
        raise ValueError("selected_indices must encode a list")
    return tuple(int(item) for item in parsed)


def parse_intervals(value: str) -> tuple[tuple[float, float], ...]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("selected_intervals must encode a list")
    intervals = []
    for item in parsed:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Every selected interval must be [start, end]")
        start, end = map(float, item)
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise ValueError("Selected interval boundaries must be finite and increasing")
        intervals.append((start, end))
    return tuple(intervals)


def load_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            errors.append(f"Missing CSV columns: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        errors.append("Aggregate-row CSV is empty")
    return rows, errors


def load_trial_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = TRIAL_REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            errors.append(f"Missing trial CSV columns: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        errors.append("Trial-row CSV is empty")
    return rows, errors


def result_key(row: dict[str, str]) -> tuple[str, str, str, str, str, int, int, str]:
    return (
        row["method"],
        row["encoder"],
        row["speaker"],
        row["attack_session"],
        row["strategy"],
        int(row["k"]),
        int(row["repeat"]),
        row["selection_id"],
    )


def audit_trials(
    manifest: dict, aggregates: list[dict[str, str]], trials: list[dict[str, str]]
) -> list[str]:
    errors: list[str] = []
    expected_speakers = set(manifest.get("speakers", []))
    aggregate_by_key: dict[tuple[str, str, str, str, str, int, int, str], dict[str, str]] = {}
    for row in aggregates:
        try:
            key = result_key(row)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"Cannot key aggregate row for trial audit: {exc}")
            continue
        if key in aggregate_by_key:
            errors.append(f"Duplicate aggregate selection key: {key}")
        aggregate_by_key[key] = row

    trials_by_key: dict[
        tuple[str, str, str, str, str, int, int, str], list[dict[str, str]]
    ] = defaultdict(list)
    for line_number, row in enumerate(trials, start=2):
        try:
            key = result_key(row)
            score = float(row["score"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"trial row {line_number}: cannot parse row: {exc}")
            continue
        if not math.isfinite(score) or not -1.000001 <= score <= 1.000001:
            errors.append(f"trial row {line_number}: invalid cosine score")
        expected_label = (
            "target" if row["enrollment_speaker"] == row["speaker"] else "impostor"
        )
        if row["label"] != expected_label:
            errors.append(f"trial row {line_number}: label disagrees with speaker IDs")
        trials_by_key[key].append(row)

    missing = set(aggregate_by_key) - set(trials_by_key)
    extra = set(trials_by_key) - set(aggregate_by_key)
    if missing:
        errors.append(f"Trials missing {len(missing)} aggregate selections")
    if extra:
        errors.append(f"Trials contain {len(extra)} unknown aggregate selections")

    for key in sorted(set(aggregate_by_key) & set(trials_by_key)):
        aggregate = aggregate_by_key[key]
        selected_trials = trials_by_key[key]
        enrollment_speakers = {row["enrollment_speaker"] for row in selected_trials}
        if expected_speakers and enrollment_speakers != expected_speakers:
            errors.append(f"Trial enrollment cohort mismatch for {key}")
        target_rows = [row for row in selected_trials if row["label"] == "target"]
        impostor_rows = [row for row in selected_trials if row["label"] == "impostor"]
        if len(target_rows) != 1 or not impostor_rows:
            errors.append(f"Trial target/impostor coverage mismatch for {key}")
            continue
        target = float(target_rows[0]["score"])
        max_impostor = max(float(row["score"]) for row in impostor_rows)
        expected_target = float(aggregate["target_score"])
        expected_impostor = float(aggregate["max_impostor_score"])
        expected_margin = float(aggregate["margin"])
        if not math.isclose(target, expected_target, rel_tol=1e-7, abs_tol=1e-8):
            errors.append(f"Trial target score disagrees with aggregate row for {key}")
        if not math.isclose(
            max_impostor, expected_impostor, rel_tol=1e-7, abs_tol=1e-8
        ):
            errors.append(f"Trial max impostor disagrees with aggregate row for {key}")
        if not math.isclose(
            target - max_impostor, expected_margin, rel_tol=1e-7, abs_tol=1e-8
        ):
            errors.append(f"Trial-derived margin disagrees with aggregate row for {key}")
    return errors


def audit(manifest: dict, rows: list[dict[str, str]]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    protocol = manifest.get("protocol", {})

    if protocol.get("dataset") != "VCTK-0.92-mic2":
        errors.append("Manifest must identify VCTK-0.92-mic2")
    if protocol.get("dataset_archive_md5") != "8a6ba2946b36fcbef0212cad601f4bfa":
        errors.append("Official VCTK archive MD5 is missing or incorrect")
    if protocol.get("dataset_archive_md5_verified") is not True:
        errors.append("Official VCTK archive MD5 was not verified for this run")
    if int(protocol.get("seed", -1)) != 42:
        errors.append("Protocol seed must be 42")
    if set(map(int, protocol.get("k_values", []))) != EXPECTED_K:
        errors.append("Manifest K grid must be [1, 2, 4, 8, 16]")
    if int(protocol.get("random_repeats", 0)) < 100:
        errors.append("At least 100 random repeats are required")
    if int(protocol.get("bootstrap_draws", 0)) < 2000:
        errors.append("At least 2000 bootstrap draws are required")
    for flag in (
        "independent_enrollment",
        "non_overlapping_attack_windows",
        "same_total_duration_control",
        "validation_threshold_frozen_before_test",
    ):
        if protocol.get(flag) is not True:
            errors.append(f"Manifest protocol flag must be true: {flag}")
    if protocol.get("same_total_duration_control_representation") != (
        "single encoder pass over one contiguous K-second waveform"
    ):
        errors.append("Contiguous control must use one encoder pass over a K-second waveform")

    methods = {row.get("method", "") for row in rows}
    encoders = {row.get("encoder", "") for row in rows}
    strategies = {row.get("strategy", "") for row in rows}
    if methods != EXPECTED_METHODS:
        errors.append(f"Method coverage mismatch: {sorted(methods)}")
    if encoders != EXPECTED_ENCODERS:
        errors.append(f"Encoder coverage mismatch: {sorted(encoders)}")
    if strategies != EXPECTED_STRATEGIES:
        errors.append(f"Strategy coverage mismatch: {sorted(strategies)}")

    coverage: dict[tuple[str, str, str, str, str], dict[int, set[int]]] = defaultdict(
        lambda: defaultdict(set)
    )
    random_pairing: dict[tuple[str, str, str, int, int], dict[str, tuple[str, tuple[int, ...]]]] = (
        defaultdict(dict)
    )
    speakers: set[str] = set()
    k1_controls: dict[
        tuple[str, str, str, str], dict[str, tuple[tuple[int, ...], float, float, float]]
    ] = defaultdict(dict)

    for line_number, row in enumerate(rows, start=2):
        prefix = f"row {line_number}"
        try:
            method = row["method"]
            encoder = row["encoder"]
            speaker = row["speaker"]
            enrollment_session = row["enrollment_session"]
            attack_session = row["attack_session"]
            strategy = row["strategy"]
            representation = row["representation"]
            k = int(row["k"])
            repeat = int(row["repeat"])
            indices = parse_indices(row["selected_indices"])
            intervals = parse_intervals(row["selected_intervals"])
            duration = float(row["selected_duration_sec"])
            span = float(row["selection_span_sec"])
            target = float(row["target_score"])
            impostor = float(row["max_impostor_score"])
            margin = float(row["margin"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{prefix}: cannot parse row: {exc}")
            continue

        speakers.add(speaker)
        if enrollment_session == attack_session:
            errors.append(f"{prefix}: enrollment leaks into the attack session")
        if k not in EXPECTED_K:
            errors.append(f"{prefix}: unexpected K={k}")
        if len(indices) != k or len(set(indices)) != k:
            errors.append(f"{prefix}: selected_indices must contain K unique windows")
        if len(intervals) != k:
            errors.append(f"{prefix}: selected_intervals must contain K windows")
        ordered_intervals = sorted(intervals)
        if any(
            ordered_intervals[index][0] < ordered_intervals[index - 1][1] - 1e-8
            for index in range(1, len(ordered_intervals))
        ):
            errors.append(f"{prefix}: selected attack windows overlap")
        interval_duration = sum(end - start for start, end in intervals)
        if not math.isclose(duration, interval_duration, abs_tol=1e-8):
            errors.append(f"{prefix}: selected_duration_sec disagrees with intervals")
        interval_span = max(end for _, end in intervals) - min(start for start, _ in intervals)
        if not math.isclose(span, interval_span, abs_tol=1e-8):
            errors.append(f"{prefix}: selection_span_sec disagrees with intervals")
        if not math.isclose(duration, float(k), abs_tol=0.05):
            errors.append(f"{prefix}: selected duration is not K seconds")
        if strategy == "contiguous_K":
            if representation != "single_contiguous_waveform":
                errors.append(f"{prefix}: contiguous control is not a single waveform encoding")
            if not math.isclose(span, float(k), abs_tol=0.05):
                errors.append(f"{prefix}: contiguous control span is not K seconds")
            if any(
                not math.isclose(
                    ordered_intervals[index][0], ordered_intervals[index - 1][1], abs_tol=0.02
                )
                for index in range(1, len(ordered_intervals))
            ):
                errors.append(f"{prefix}: contiguous control contains a time gap")
        elif representation != "fragment_embedding_mean":
            errors.append(f"{prefix}: fragment attack must aggregate fragment embeddings")
        if not all(math.isfinite(value) for value in (target, impostor, margin)):
            errors.append(f"{prefix}: score is nonfinite")
        if not -1.000001 <= target <= 1.000001 or not -1.000001 <= impostor <= 1.000001:
            errors.append(f"{prefix}: cosine score outside [-1, 1]")
        if not math.isclose(margin, target - impostor, abs_tol=1e-8):
            errors.append(f"{prefix}: margin does not equal target minus impostor")

        coverage[(method, encoder, speaker, attack_session, strategy)][k].add(repeat)
        if k == 1 and repeat == 0 and strategy in {
            "self_consistency_K",
            "contiguous_K",
        }:
            k1_controls[(method, encoder, speaker, attack_session)][strategy] = (
                indices,
                target,
                impostor,
                margin,
            )
        if strategy == "random_K":
            pairing_key = (encoder, speaker, attack_session, k, repeat)
            random_pairing[pairing_key][method] = (row["selection_id"], indices)

    if len(speakers) < 2:
        errors.append("At least two speakers are required")

    required_random_repeats = int(protocol.get("random_repeats", 100))
    for key, by_k in coverage.items():
        missing_k = EXPECTED_K - set(by_k)
        if missing_k:
            errors.append(f"Incomplete K grid for {key}: missing {sorted(missing_k)}")
            continue
        strategy = key[-1]
        for k, repeats in by_k.items():
            if strategy == "random_K":
                expected = set(range(required_random_repeats))
                if repeats != expected:
                    errors.append(
                        f"Random repeats incomplete for {key}, K={k}: "
                        f"found {len(repeats)}, expected {required_random_repeats}"
                    )
            elif repeats != {0}:
                errors.append(f"Deterministic strategy must use repeat=0 for {key}, K={k}")

    for key, by_method in random_pairing.items():
        if set(by_method) != EXPECTED_METHODS:
            errors.append(f"Random selection lacks all methods for {key}")
            continue
        selections = set(by_method.values())
        if len(selections) != 1:
            errors.append(f"Random selection is not paired across methods for {key}")

    for key, controls in k1_controls.items():
        if set(controls) != {"self_consistency_K", "contiguous_K"}:
            errors.append(f"K=1 control pair is incomplete for {key}")
            continue
        selfcons = controls["self_consistency_K"]
        contiguous = controls["contiguous_K"]
        if selfcons[0] != contiguous[0]:
            errors.append(f"K=1 self-consistency and contiguous controls select different windows for {key}")
        if any(
            not math.isclose(left, right, rel_tol=1e-5, abs_tol=1e-6)
            for left, right in zip(selfcons[1:], contiguous[1:])
        ):
            errors.append(f"K=1 self-consistency and contiguous scores disagree for {key}")

    if not manifest.get("session_pool_sha256"):
        errors.append("Manifest lacks session_pool_sha256")
    if not manifest.get("session_pool_manifest_sha256"):
        errors.append("Manifest lacks session_pool_manifest_sha256")
    source_kind = manifest.get("session_pool_source_kind")
    if source_kind not in {"official_archive", "pinned_git_mirror_subset"}:
        errors.append("Manifest lacks a recognized session-pool source kind")
    if source_kind == "official_archive":
        if manifest.get("session_pool_source_archive_md5") != (
            "8a6ba2946b36fcbef0212cad601f4bfa"
        ):
            errors.append("Official session-pool source MD5 is missing or incorrect")
    elif not manifest.get("session_pool_source_commit"):
        errors.append("Manifest lacks the pinned session-pool source commit")
    if not manifest.get("session_pool_source_audit_sha256"):
        errors.append("Manifest lacks the source-subset audit SHA-256")
    if not manifest.get("telephony_config_sha256"):
        errors.append("Manifest lacks telephony_config_sha256")
    checkpoint_hashes = manifest.get("checkpoint_sha256", {})
    if set(checkpoint_hashes) != {"reference", "realistic"}:
        errors.append("Manifest must contain both defense checkpoint SHA-256 values")
    encoder_hashes = manifest.get("encoder_model_sha256", {})
    if set(encoder_hashes) != EXPECTED_ENCODERS or not all(encoder_hashes.values()):
        errors.append("Manifest must contain ECAPA and x-vector model SHA-256 values")
    source_hashes = manifest.get("source_file_sha256", {})
    expected_sources = {
        "scripts/run_aggregation_advantage_asv.py",
        "src/metrics/aggregation_protocol.py",
        "src/models/defense_stftmask.py",
        "src/transforms/telephony.py",
    }
    if set(source_hashes) != expected_sources or not all(
        isinstance(value, str) and len(value) == 64 for value in source_hashes.values()
    ):
        errors.append("Manifest must contain SHA-256 values for all runtime source files")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "rows": len(rows),
        "speakers": len(speakers),
        "methods": sorted(methods),
        "encoders": sorted(encoders),
        "strategies": sorted(strategies),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows, errors = load_rows(args.rows)
    trials, trial_load_errors = load_trial_rows(args.trials)
    report = audit(manifest, rows)
    report["errors"] = (
        errors + trial_load_errors + report["errors"] + audit_trials(manifest, rows, trials)
    )
    report["ok"] = not report["errors"]
    report["manifest_sha256"] = sha256(args.manifest)
    report["rows_sha256"] = sha256(args.rows)
    report["trials_sha256"] = sha256(args.trials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
