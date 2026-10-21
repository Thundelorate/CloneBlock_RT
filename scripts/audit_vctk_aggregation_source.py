#!/usr/bin/env python3
"""Verify the official VCTK archive and frozen aggregation speaker subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_aggregation_session_pool import TEST_SPEAKERS, VAL_SPEAKERS


EXPECTED_MD5 = "8a6ba2946b36fcbef0212cad601f4bfa"


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def build_report(corpus_root: Path, archive: Path) -> dict:
    archive_md5 = digest(archive, "md5")
    if archive_md5 != EXPECTED_MD5:
        raise ValueError(f"VCTK archive MD5 mismatch: {archive_md5}")
    speakers = []
    for split, names in (("validation", VAL_SPEAKERS), ("test", TEST_SPEAKERS)):
        for speaker in names:
            audio_dir = corpus_root / "wav48_silence_trimmed" / speaker
            text_dir = corpus_root / "txt" / speaker
            audio = sorted(audio_dir.glob("*_mic2.flac"))
            transcripts = sorted(text_dir.glob("*.txt"))
            if len(audio) < 300 or len(transcripts) < 300:
                raise ValueError(
                    f"Incomplete official VCTK speaker {speaker}: "
                    f"mic2={len(audio)}, transcripts={len(transcripts)}"
                )
            speakers.append(
                {
                    "split": split,
                    "speaker": speaker,
                    "mic2_files": len(audio),
                    "transcripts": len(transcripts),
                    "bytes": sum(path.stat().st_size for path in audio + transcripts),
                }
            )
    return {
        "dataset": "VCTK-0.92-mic2",
        "source_kind": "official_archive",
        "archive": str(archive.resolve()),
        "archive_bytes": archive.stat().st_size,
        "archive_md5": archive_md5,
        "corpus_root": str(corpus_root.resolve()),
        "speakers": speakers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus_root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.corpus_root.resolve(), args.archive.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
