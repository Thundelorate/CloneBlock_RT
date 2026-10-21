#!/usr/bin/env python3
"""Build deterministic, source-disjoint three-session pools for aggregation ASV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

REPO = Path(__file__).resolve().parents[1]
VAL_SPEAKERS = ("p229", "p237", "p254", "p256", "p282", "p295", "p301", "p307", "p343", "p351", "p374")
TEST_SPEAKERS = ("p228", "p239", "p240", "p244", "p255", "p258", "p262", "p314", "p326", "p340", "p364")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_seed(seed: int, *parts: object) -> int:
    payload = "\x1f".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def read_mono(path: Path, sample_rate: int) -> np.ndarray:
    signal, source_rate = sf.read(path, dtype="float32", always_2d=True)
    signal = signal.mean(axis=1)
    if source_rate != sample_rate:
        divisor = math.gcd(source_rate, sample_rate)
        signal = resample_poly(signal, sample_rate // divisor, source_rate // divisor).astype(np.float32)
    if not len(signal) or not np.all(np.isfinite(signal)):
        raise ValueError(f"Invalid audio: {path}")
    return signal.astype(np.float32, copy=False)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_split(
    split: str,
    speakers: tuple[str, ...],
    corpus_root: Path,
    output_dir: Path,
    sample_rate: int,
    session_seconds: int,
    seed: int,
) -> dict[str, object]:
    audio_root = corpus_root / "wav48_silence_trimmed"
    text_root = corpus_root / "txt"
    session_root = output_dir / "audio" / split
    session_root.mkdir(parents=True, exist_ok=True)
    pool_rows: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    audio_hashes: dict[str, str] = {}
    selected_by_speaker: dict[str, set[str]] = {}
    required_samples = sample_rate * session_seconds

    for speaker in speakers:
        files = sorted((audio_root / speaker).glob(f"{speaker}_*_mic2.flac"))
        if len(files) < 3:
            raise ValueError(f"Too few mic2 files for {speaker}: {len(files)}")
        rng = np.random.default_rng(stable_seed(seed, split, speaker))
        order = rng.permutation(len(files))
        buckets = [[files[int(index)] for index in order[offset::3]] for offset in range(3)]
        used: set[str] = set()
        session_source_sets: list[set[str]] = []

        for session_index, bucket in enumerate(buckets):
            chunks: list[np.ndarray] = []
            source_samples = 0
            source_records: list[tuple[Path, Path, int, int, str, str]] = []
            session_sources: set[str] = set()
            for source in bucket:
                transcript = text_root / speaker / f"{source.name.split('_mic2')[0]}.txt"
                if not transcript.is_file():
                    raise FileNotFoundError(transcript)
                signal = read_mono(source, sample_rate)
                begin = source_samples
                chunks.append(signal)
                source_samples += len(signal)
                resolved = str(source.resolve())
                source_records.append(
                    (source, transcript, begin, source_samples, sha256(source), sha256(transcript))
                )
                session_sources.add(resolved)
                used.add(resolved)
                if source_samples >= required_samples:
                    break
            if source_samples < required_samples:
                raise ValueError(f"{speaker} session {session_index} has only {source_samples / sample_rate:.1f}s")

            session = f"{speaker}_s{session_index:03d}"
            session_path = session_root / f"session_{session}.wav"
            waveform = np.concatenate(chunks)[:required_samples]
            sf.write(session_path, waveform, sample_rate, subtype="PCM_16")
            audio_hashes[str(session_path.relative_to(REPO)).replace("\\", "/")] = sha256(session_path)

            for window_index in range(session_seconds):
                pool_rows.append(
                    {
                        "speaker_id": speaker,
                        "session_id": session,
                        "path": str(session_path.relative_to(REPO)).replace("\\", "/"),
                        "start_sec": float(window_index),
                        "end_sec": float(window_index + 1),
                        "window_index": window_index,
                    }
                )
            session_source_sets.append(session_sources)
            for source, transcript, begin, end, source_hash, transcript_hash in source_records:
                source_rows.append(
                    {
                        "split": split,
                        "speaker_id": speaker,
                        "session_id": session,
                        "source_path": str(source.relative_to(corpus_root)).replace("\\", "/"),
                        "source_sha256": source_hash,
                        "transcript_path": str(transcript.relative_to(corpus_root)).replace("\\", "/"),
                        "transcript_sha256": transcript_hash,
                        "stitched_start_sec": begin / sample_rate,
                        "stitched_end_sec": min(end, required_samples) / sample_rate,
                    }
                )
        for left in range(3):
            for right in range(left + 1, 3):
                overlap = session_source_sets[left] & session_source_sets[right]
                if overlap:
                    raise AssertionError(f"{speaker} has enrollment/attack source leakage: {sorted(overlap)[:3]}")
        selected_by_speaker[speaker] = used

    pool_path = output_dir / f"session_pool_aggregation_{split}.csv"
    source_path = output_dir / f"session_pool_aggregation_{split}_sources.csv"
    write_csv(pool_path, pool_rows)
    write_csv(source_path, source_rows)
    expected_rows = len(speakers) * 3 * session_seconds
    if len(pool_rows) != expected_rows:
        raise AssertionError((len(pool_rows), expected_rows))
    return {
        "split": split,
        "speakers": list(speakers),
        "sessions": len(speakers) * 3,
        "windows": len(pool_rows),
        "session_seconds": session_seconds,
        "pool_csv": str(pool_path.relative_to(REPO)).replace("\\", "/"),
        "pool_sha256": sha256(pool_path),
        "sources_csv": str(source_path.relative_to(REPO)).replace("\\", "/"),
        "sources_sha256": sha256(source_path),
        "session_audio_sha256": audio_hashes,
        "source_disjoint_across_sessions": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus_root", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, default=REPO / "data/splits/vctk")
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--session_seconds", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--source_kind",
        choices=("official_archive", "pinned_git_mirror_subset"),
        required=True,
    )
    parser.add_argument("--source_commit", default="unknown")
    parser.add_argument("--source_archive_md5", default=None)
    parser.add_argument("--source_audit", type=Path, required=True)
    args = parser.parse_args()
    corpus_root = args.corpus_root.resolve()
    output_dir = args.output_dir.resolve()
    if args.session_seconds < 16:
        parser.error("--session_seconds must be at least 16 for K=16")

    summaries = [
        build_split("validation", VAL_SPEAKERS, corpus_root, output_dir, args.sample_rate, args.session_seconds, args.seed),
        build_split("test", TEST_SPEAKERS, corpus_root, output_dir, args.sample_rate, args.session_seconds, args.seed),
    ]
    manifest = {
        "protocol": "aggregation-independent-enrollment-v1",
        "corpus_root": str(corpus_root),
        "source_kind": args.source_kind,
        "source_commit": args.source_commit,
        "source_archive_md5": args.source_archive_md5,
        "source_audit": str(args.source_audit.resolve()),
        "source_audit_sha256": sha256(args.source_audit.resolve()),
        "sample_rate": args.sample_rate,
        "seed": args.seed,
        "session_assignment": "speaker-specific seeded shuffle, disjoint three-way stride",
        "enrollment_session": "lexicographically first session (s000)",
        "attack_sessions": ["s001", "s002"],
        "splits": summaries,
    }
    manifest_path = output_dir / "aggregation_session_pool_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

