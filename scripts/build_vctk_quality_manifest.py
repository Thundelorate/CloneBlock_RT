#!/usr/bin/env python3
"""Build a speaker-balanced VCTK full-utterance quality manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split_csv", type=Path, default=ROOT / "data/splits/vctk/test.csv")
    parser.add_argument("--max_utts", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "data/splits/vctk/quality_test_official.csv")
    args = parser.parse_args()

    with args.split_csv.open(newline="", encoding="utf-8") as handle:
        split_rows = list(csv.DictReader(handle))
    candidates: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in split_rows:
        speaker = row["speaker_id"]
        utterance = row.get("source_utter_id", "").strip()
        source_path = row.get("source_path", "").strip()
        if not utterance or not source_path:
            continue
        audio_path = ROOT / "data/raw" / source_path
        transcript_path = audio_path.parents[2] / "txt" / speaker / f"{utterance}.txt"
        if not audio_path.is_file() or not transcript_path.is_file():
            continue
        candidates[speaker][utterance] = {
            "utter_id": utterance,
            "speaker_id": speaker,
            "path": str(audio_path.relative_to(ROOT)),
            "source_path": source_path,
            "transcript_path": str(transcript_path.relative_to(ROOT)),
            "is_full_utterance": "1",
            "microphone": row.get("microphone", "mic2"),
        }

    rng = random.Random(args.seed)
    queues = {}
    for speaker, utterances in sorted(candidates.items()):
        queue = list(utterances.values())
        rng.shuffle(queue)
        queues[speaker] = queue

    selected = []
    while len(selected) < args.max_utts:
        progressed = False
        for speaker in sorted(queues):
            if queues[speaker] and len(selected) < args.max_utts:
                selected.append(queues[speaker].pop())
                progressed = True
        if not progressed:
            break
    if not selected:
        raise ValueError("No full utterances with official transcripts were found")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "utter_id", "speaker_id", "path", "source_path",
        "transcript_path", "is_full_utterance", "microphone",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    metadata = {
        "protocol": "vctk_full_utterance_official_transcript_v1",
        "seed": args.seed,
        "max_utts": args.max_utts,
        "n_utts": len(selected),
        "n_speakers": len({row["speaker_id"] for row in selected}),
        "speaker_counts": {
            speaker: sum(row["speaker_id"] == speaker for row in selected)
            for speaker in sorted({row["speaker_id"] for row in selected})
        },
        "source_split": str(args.split_csv),
        "source_split_sha256": sha256(args.split_csv),
        "manifest_sha256": sha256(args.output),
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
