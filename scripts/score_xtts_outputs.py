#!/usr/bin/env python3
"""Score XTTS outputs against independent enrollment and bootstrap speakers."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.metrics.speaker import SpeakerMetric


def load_wav(path: Path) -> tuple[torch.Tensor, int]:
    audio, sample_rate = sf.read(path, dtype="float32")
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    return torch.from_numpy(audio), int(sample_rate)


def cluster_interval(
    rows: list[dict], value_key: str, draws: int, seed: int
) -> tuple[float, float, float]:
    by_speaker: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_speaker[row["speaker_id"]].append(float(row[value_key]))
    speakers = sorted(by_speaker)
    if len(speakers) < 2:
        raise ValueError("Speaker bootstrap requires at least two speakers")
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(draws):
        picked = rng.integers(0, len(speakers), size=len(speakers))
        values = [value for index in picked for value in by_speaker[speakers[index]]]
        samples.append(float(np.mean(values)))
    estimate = float(np.mean([float(row[value_key]) for row in rows]))
    low, high = np.quantile(np.asarray(samples), [0.025, 0.975])
    return estimate, float(low), float(high)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--syntheses", required=True, type=Path)
    parser.add_argument("--thresholds", required=True, type=Path)
    parser.add_argument("--speaker_checkpoint_dir", required=True)
    parser.add_argument("--speaker_checkpoint_dir_xvector", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary_output", required=True, type=Path)
    args = parser.parse_args()

    with args.syntheses.open(newline="", encoding="utf-8") as handle:
        syntheses = list(csv.DictReader(handle))
    threshold_payload = json.loads(args.thresholds.read_text(encoding="utf-8"))
    thresholds = {row["encoder"]: float(row["threshold"]) for row in threshold_payload["thresholds"]}
    device = args.device if torch.cuda.is_available() else "cpu"
    encoder_specs = (
        ("speechbrain_ecapa", {"checkpoint_dir": args.speaker_checkpoint_dir}),
        ("speechbrain_xvector", {"checkpoint_dir_xvector": args.speaker_checkpoint_dir_xvector}),
    )

    scored = []
    for encoder, paths in encoder_specs:
        metric = SpeakerMetric({"encoder_name": encoder, "device": device, **paths})
        enrollment_cache = {}
        enrollment_by_speaker = {}
        enrollment_path_by_speaker = {}
        for row in syntheses:
            enrollment_path = (REPO_ROOT / row["enrollment_path"]).resolve()
            speaker_id = row["speaker_id"]
            previous_path = enrollment_path_by_speaker.get(speaker_id)
            if previous_path is not None and previous_path != enrollment_path:
                raise ValueError(f"Multiple enrollment sessions for {speaker_id}")
            enrollment_path_by_speaker[speaker_id] = enrollment_path
            cache_key = str(enrollment_path)
            if cache_key not in enrollment_cache:
                enrollment_audio, enrollment_sr = load_wav(enrollment_path)
                enrollment_cache[cache_key] = metric.embed(enrollment_audio, enrollment_sr)
            enrollment_by_speaker[speaker_id] = enrollment_cache[cache_key]
        if len(enrollment_by_speaker) < 2:
            raise ValueError("Target-impostor margin requires at least two enrolled speakers")
        for row in syntheses:
            synth_path = Path(row["synth_path"])
            synth_audio, synth_sr = load_wav(synth_path)
            synth_embedding = metric.embed(synth_audio, synth_sr)
            cosine = metric.cosine(synth_embedding, enrollment_by_speaker[row["speaker_id"]])
            impostor_max = max(
                metric.cosine(synth_embedding, enrollment_embedding)
                for speaker_id, enrollment_embedding in enrollment_by_speaker.items()
                if speaker_id != row["speaker_id"]
            )
            threshold = thresholds[encoder]
            scored.append({
                **row,
                "encoder": encoder,
                "enrollment_protocol": "independent_session",
                "cosine": f"{cosine:.9f}",
                "impostor_max": f"{impostor_max:.9f}",
                "target_impostor_margin": f"{cosine - impostor_max:.9f}",
                "threshold": f"{threshold:.9f}",
                "accepted": "1" if cosine >= threshold else "0",
            })
        del metric
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scored[0]))
        writer.writeheader()
        writer.writerows(scored)

    grouped: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    for row in scored:
        grouped[(row["encoder"], int(row["K"]), row["condition"])].append(row)
    summary = []
    for (encoder, k, condition), rows in sorted(grouped.items()):
        for metric_name, key in (
            ("cosine", "cosine"),
            ("target_impostor_margin", "target_impostor_margin"),
            ("acceptance_rate", "accepted"),
        ):
            estimate, low, high = cluster_interval(rows, key, args.draws, args.seed)
            summary.append({
                "encoder": encoder,
                "K": k,
                "condition": condition,
                "metric": metric_name,
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "n_speakers": len({row["speaker_id"] for row in rows}),
                "n_rows": len(rows),
                "bootstrap_draws": args.draws,
                "bootstrap_seed": args.seed,
            })

    # Paired deltas preserve session, text, K, and encoder.
    paired: dict[tuple[str, int, str, str], dict[str, dict]] = defaultdict(dict)
    for row in scored:
        key = (row["encoder"], int(row["K"]), row["order"], row["text_id"])
        paired[key][row["condition"]] = row
    delta_groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for (encoder, k, _, _), conditions in paired.items():
        if set(conditions) != {"baseline_ref", "defended_ref"}:
            raise ValueError("Incomplete baseline/defended XTTS pair")
        baseline = conditions["baseline_ref"]
        defended = conditions["defended_ref"]
        delta_groups[(encoder, k)].append({
            "speaker_id": baseline["speaker_id"],
            "cosine_delta": float(defended["cosine"]) - float(baseline["cosine"]),
            "margin_delta": (
                float(defended["target_impostor_margin"])
                - float(baseline["target_impostor_margin"])
            ),
            "acceptance_delta": float(defended["accepted"]) - float(baseline["accepted"]),
        })
    for (encoder, k), rows in sorted(delta_groups.items()):
        for metric_name, key in (
            ("paired_cosine_delta", "cosine_delta"),
            ("paired_target_impostor_margin_delta", "margin_delta"),
            ("paired_acceptance_delta", "acceptance_delta"),
        ):
            estimate, low, high = cluster_interval(rows, key, args.draws, args.seed)
            summary.append({
                "encoder": encoder,
                "K": k,
                "condition": "defended_minus_baseline",
                "metric": metric_name,
                "estimate": estimate,
                "ci_low": low,
                "ci_high": high,
                "n_speakers": len({row["speaker_id"] for row in rows}),
                "n_rows": len(rows),
                "bootstrap_draws": args.draws,
                "bootstrap_seed": args.seed,
            })

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    args.summary_output.with_suffix(".json").write_text(json.dumps({
        "protocol": "xtts_independent_enrollment_operating_point_v1",
        "syntheses_sha256": hashlib.sha256(args.syntheses.read_bytes()).hexdigest(),
        "thresholds_sha256": hashlib.sha256(args.thresholds.read_bytes()).hexdigest(),
        "bootstrap": {"unit": "speaker", "draws": args.draws, "seed": args.seed, "confidence": 0.95},
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
