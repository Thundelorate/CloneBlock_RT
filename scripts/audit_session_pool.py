#!/usr/bin/env python3
"""Audit session windows and source-utterance isolation before ASV evaluation."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def audit(path: Path, repo_root: Path, min_windows: int = 16) -> dict:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    errors = []
    sessions = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        try:
            key = (row["speaker_id"], row["session_id"])
            sessions[key].append(row)
            audio = (repo_root / row["path"]).resolve()
            if not audio.is_relative_to(repo_root.resolve()) or not audio.is_file():
                raise ValueError(f"missing or unsafe audio path: {row['path']}")
            if float(row["dur_sec"]) <= 0 or float(row["start_sec"]) < 0:
                raise ValueError("invalid window times")
        except (KeyError, ValueError, OSError) as exc:
            errors.append(f"line {line}: {exc}")
    session_sources = {}
    for key, values in sessions.items():
        if len(values) < min_windows:
            errors.append(f"{key}: only {len(values)} windows")
        source_sets = {tuple(sorted(json.loads(row["source_utter_ids"]))) for row in values}
        if len(source_sets) != 1 or not source_sets:
            errors.append(f"{key}: inconsistent or empty source provenance")
            continue
        session_sources[key] = set(next(iter(source_sets)))
    by_speaker = defaultdict(list)
    for (speaker, session), sources in session_sources.items():
        by_speaker[speaker].append((session, sources))
    for speaker, entries in by_speaker.items():
        if len(entries) < 2:
            errors.append(f"{speaker}: independent enrollment requires at least two sessions")
        for i, (left_name, left) in enumerate(entries):
            for right_name, right in entries[i + 1:]:
                overlap = left & right
                if overlap:
                    errors.append(f"{speaker}: {left_name}/{right_name} share {len(overlap)} source utterances")
    return {"ok": not errors, "csv": str(path), "rows": len(rows),
            "speakers": len(by_speaker), "sessions": len(sessions), "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session_pool_csv", type=Path, required=True)
    parser.add_argument("--min_windows", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    result = audit(args.session_pool_csv, repo_root, args.min_windows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
