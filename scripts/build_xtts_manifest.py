#!/usr/bin/env python3
"""Build a deterministic, speaker-stratified XTTS attack/enrollment manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path


def build_manifest(rows: list[dict[str, str]], n_sessions: int, seed: int) -> list[dict[str, str]]:
    paths: dict[tuple[str, str], str] = {}
    by_speaker: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        speaker = row["speaker_id"]
        session = row["session_id"]
        path = row["path"]
        key = (speaker, session)
        if key in paths and paths[key] != path:
            raise ValueError(f"Session has multiple paths: {key}")
        paths[key] = path
        by_speaker[speaker].add(session)
    if not by_speaker:
        raise ValueError("Session pool is empty")

    rng = random.Random(seed)
    speakers = sorted(by_speaker)
    rng.shuffle(speakers)
    attacks: dict[str, list[str]] = {}
    enrollment: dict[str, str] = {}
    for speaker in speakers:
        sessions = sorted(by_speaker[speaker])
        rng.shuffle(sessions)
        if len(sessions) < 2:
            raise ValueError(f"Speaker {speaker} needs at least two independent sessions")
        enrollment[speaker] = sessions[0]
        attacks[speaker] = sessions[1:]

    available = sum(len(items) for items in attacks.values())
    if not 1 <= n_sessions <= available:
        raise ValueError(f"n_sessions must be in [1, {available}]")

    chosen: list[tuple[str, str]] = []
    round_index = 0
    while len(chosen) < n_sessions:
        added = False
        for speaker in speakers:
            if round_index < len(attacks[speaker]):
                chosen.append((speaker, attacks[speaker][round_index]))
                added = True
                if len(chosen) == n_sessions:
                    break
        if not added:
            break
        round_index += 1

    output = []
    for index, (speaker, attack_session) in enumerate(chosen):
        enrollment_session = enrollment[speaker]
        if attack_session == enrollment_session:
            raise AssertionError("Attack and enrollment sessions must be disjoint")
        output.append({
            "order": str(index),
            "speaker_id": speaker,
            "attack_session_id": attack_session,
            "enrollment_session_id": enrollment_session,
            "attack_path": paths[(speaker, attack_session)],
            "enrollment_path": paths[(speaker, enrollment_session)],
            "seed": str(seed),
            "selection_rule": "speaker_stratified_round_robin",
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session_pool_csv", required=True, type=Path)
    parser.add_argument("--n_sessions", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.session_pool_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    manifest = build_manifest(rows, args.n_sessions, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(manifest[0])
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
    metadata = {
        "protocol": "xtts_small_scale_v1",
        "selection_uses_scores": False,
        "n_sessions": len(manifest),
        "n_speakers": len({row["speaker_id"] for row in manifest}),
        "seed": args.seed,
        "session_pool_sha256": hashlib.sha256(args.session_pool_csv.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
