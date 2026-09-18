#!/usr/bin/env python3
"""Paired speaker-cluster percentile intervals for session recovery scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


def summarize(rows, ks=(1, 2, 4, 8, 16), reference_method="baseline",
              draws=2000, seed=42, confidence=0.95):
    """Keep session weighting while resampling whole speakers, paired by session."""
    ks = tuple(ks)
    if not ks or any(k < 1 for k in ks) or tuple(sorted(set(ks))) != ks:
        raise ValueError("K values must be distinct, positive, and sorted")
    if draws < 2 or not 0 < confidence < 1:
        raise ValueError("Need at least two draws and confidence in (0, 1)")
    grouped = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        protocol = tuple(row[f] for f in ("strategy", "attacker_view", "selection_source"))
        key = (row["speaker_id"], row["session_id"], row["path"])
        if any(not value for value in (*protocol, *key, row["method"])):
            raise ValueError("Empty method, protocol, or session identity")
        k, value = int(row["K"]), float(row["cos"])
        if k not in ks:
            raise ValueError(f"Unexpected K={k}; specify the exact evaluated grid")
        if not np.isfinite(value) or not -1.000001 <= value <= 1.000001:
            raise ValueError("Cosine scores must be finite and in [-1, 1]")
        entries = grouped[protocol][row["method"]]
        if (key, k) in entries:
            raise ValueError(f"Duplicate session/K row: {key}, K={k}")
        entries[(key, k)] = row
    if not grouped:
        raise ValueError("No session scores")

    output = []
    all_methods = {r["method"] for r in rows}
    for protocol, methods in sorted(grouped.items()):
        if set(methods) != all_methods or reference_method not in methods:
            raise ValueError("Every protocol must have the same methods and reference")
        reference = methods[reference_method]
        keys = sorted({key for key, _ in reference})
        expected = {(key, k) for key in keys for k in ks}
        if set(reference) != expected:
            raise ValueError("Reference has an incomplete K grid")
        speakers = sorted({key[0] for key in keys})
        if len(speakers) < 2:
            raise ValueError("Speaker-cluster CI requires at least two speakers")
        speaker_index = {speaker: i for i, speaker in enumerate(speakers)}
        cluster = np.array([speaker_index[key[0]] for key in keys])
        counts = np.bincount(cluster, minlength=len(speakers))
        rng = np.random.default_rng(seed)
        # The same speaker draws are reused for all methods, K values and deltas.
        sampled = rng.integers(0, len(speakers), size=(draws, len(speakers)))
        denominator = counts[sampled].sum(axis=1, keepdims=True)
        metric_names = [f"MeanSim@{k}" for k in ks] + ["AUCK"]
        if 1 in ks and 16 in ks:
            metric_names.append("slope_16_1")
        estimates, samples = {}, {}
        for method, entries in sorted(methods.items()):
            if set(entries) != expected:
                raise ValueError(f"{method}: sessions or K grid differ from reference")
            for key_k, row in entries.items():
                ref = reference[key_k]
                if any(row[f] != ref[f] for f in ("candidate_count", "seed")):
                    raise ValueError(f"{method}: candidate count or seed differs")
                if int(row["candidate_count"]) < max(ks):
                    raise ValueError("Insufficient candidate windows")
                if protocol[0] == "random_K" and json.loads(row["selected_indices"]) != json.loads(ref["selected_indices"]):
                    raise ValueError("Random-window draws must match across methods")
            values = np.array([[float(entries[(key, k)]["cos"]) for k in ks] for key in keys])
            columns = [values, values.mean(axis=1, keepdims=True)]
            if 1 in ks and 16 in ks:
                columns.append((values[:, ks.index(16)] - values[:, ks.index(1)])[:, None])
            values = np.concatenate(columns, axis=1)
            sums = np.zeros((len(speakers), values.shape[1]))
            np.add.at(sums, cluster, values)
            estimates[method] = values.mean(axis=0)
            samples[method] = sums[sampled].sum(axis=1) / denominator

        tail = (1.0 - confidence) / 2.0
        for method in sorted(methods):
            conditions = [("absolute", estimates[method], samples[method])]
            if method != reference_method:
                conditions.append(("paired_delta", estimates[method] - estimates[reference_method],
                                   samples[method] - samples[reference_method]))
            for kind, point, boot in conditions:
                lo, hi = np.quantile(boot, [tail, 1.0 - tail], axis=0)
                for j, metric in enumerate(metric_names):
                    output.append(dict(
                        method=method, reference_method=reference_method if kind == "paired_delta" else "",
                        strategy=protocol[0], attacker_view=protocol[1], selection_source=protocol[2],
                        kind=kind, metric=metric, estimate=float(point[j]), ci_low=float(lo[j]),
                        ci_high=float(hi[j]), n_speakers=len(speakers), n_sessions=len(keys),
                        confidence=confidence, bootstrap_draws=draws, bootstrap_seed=seed,
                    ))
    return output


def load_runs(paths):
    rows, provenance, signature = [], [], None
    fields = ("protocol_version", "k_list", "seed", "speaker_encoder_name",
              "telephony_codec", "telephony_codec_bitrate", "selection_protocols",
              "session_pool_sha256", "eval_config_sha256", "telephony_config_sha256")
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        metadata = payload["metadata"]
        current = {field: metadata[field] for field in fields}
        if signature is not None and current != signature:
            raise ValueError("Run metadata differ: do not mix datasets, encoders, codecs or protocols")
        signature = current
        if not path.name.startswith("session_attack_eval_"):
            raise ValueError("Expected session_attack_eval_*.json metadata")
        # Resolve beside the JSON so result bundles remain portable across machines.
        csv_path = path.with_name(path.name.replace("session_attack_eval_", "session_attack_per_session_", 1)).with_suffix(".csv")
        with csv_path.open(newline="", encoding="utf-8") as handle:
            run_rows = list(csv.DictReader(handle))
        if not run_rows or {row["method"] for row in run_rows} != {payload["method"]}:
            raise ValueError("Empty CSV or method does not match its metadata")
        for row in run_rows:
            if int(row["seed"]) != metadata["seed"]:
                raise ValueError("CSV seed does not match its metadata")
            protocol = metadata["selection_protocols"][row["strategy"]]
            if any(row[field] != protocol[field] for field in ("attacker_view", "selection_source")):
                raise ValueError("CSV protocol does not match its metadata")
        rows.extend(run_rows)
        provenance.append({"metadata": str(path), "csv": str(csv_path),
                           "metadata_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()})
    return rows, signature, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", required=True, type=Path, help="Evaluation JSON files for one comparison")
    parser.add_argument("--reference_method", default="baseline")
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows, metadata, provenance = load_runs(args.runs)
    result = summarize(rows, ks=metadata["k_list"], reference_method=args.reference_method,
                       draws=args.draws, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    args.output.with_suffix(".json").write_text(json.dumps({
        "inputs": provenance, "evaluation_metadata": metadata,
        "bootstrap": {"unit": "speaker", "interval": "percentile", "confidence": 0.95,
                      "draws": args.draws, "seed": args.seed, "paired": True},
        "estimand": "Session-weighted mean; resample speakers with all their sessions",
        "AUCK": "Equal-weight mean on exactly the recorded K grid",
        "delta": "method minus reference; negative recovery similarity means less identity recovery",
        "limitation": "Conditional on fitted models and fixed evaluation trials; not training-seed uncertainty. Few speakers can give unstable intervals.",
    }, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(result)} metric rows to {args.output}")


if __name__ == "__main__":
    main()
