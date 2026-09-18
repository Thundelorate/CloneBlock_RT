#!/usr/bin/env python3
"""Check split isolation, source provenance and PCM headers without loading models."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import wave
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Manifest path escapes its data root: {relative}")
    return path


def audit(splits_dir, wav_root, raw_root):
    errors, split_stats = [], {}
    seen_speakers, seen_audio, seen_sources = {}, {}, {}
    for split in ("train", "val", "test"):
        manifest = splits_dir / f"{split}.csv"
        if not manifest.is_file():
            errors.append(f"Missing split: {manifest}")
            continue
        with manifest.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            errors.append(f"Empty split: {split}")
        speakers, duration, identities = set(), 0.0, set()
        missing_transcripts = set()
        for i, row in enumerate(rows, start=2):
            try:
                speaker = row["speaker_id"]
                if not speaker or not row["path"] or not row["source_path"] or not row["source_utter_id"]:
                    raise ValueError("Empty speaker, audio path or source identity")
                speakers.add(speaker)
                if speaker in seen_speakers and seen_speakers[speaker] != split:
                    raise ValueError(f"Speaker {speaker} leaks across splits")
                seen_speakers[speaker] = split
                identity = (speaker, row["utter_id"])
                if identity in identities:
                    raise ValueError(f"Duplicate crop identity {identity}")
                identities.add(identity)
                audio = inside(wav_root, row["path"])
                if audio in seen_audio:
                    raise ValueError(f"Processed audio appears more than once: {row['path']}")
                seen_audio[audio] = split
                source = inside(raw_root, row["source_path"])
                if not source.is_file():
                    raise ValueError(f"Missing source: {source}")
                if source in seen_sources and seen_sources[source] != split:
                    raise ValueError(f"Source recording reused across splits: {source}")
                seen_sources[source] = split
                start, end, sr = (int(row[f]) for f in ("source_start_sample", "source_end_sample", "sample_rate"))
                if not 0 <= start < end or sr != 16000:
                    raise ValueError("Invalid source offsets or sample rate")
                with wave.open(str(audio), "rb") as handle:
                    if handle.getnchannels() != 1 or handle.getframerate() != sr or handle.getsampwidth() != 2:
                        raise ValueError("Expected mono PCM16 at 16 kHz")
                    frames = handle.getnframes()
                if frames != end - start or abs(float(row["duration"]) - frames / sr) > 0.001:
                    raise ValueError("PCM length disagrees with crop provenance")
                duration += frames / sr
                # For VCTK the source folder is <corpus>/<wav-folder>/<speaker>/<file>.
                if row.get("microphone") in ("mic1", "mic2"):
                    transcript = source.parents[2] / "txt" / speaker / (row["source_utter_id"] + ".txt")
                    if not transcript.is_file() or not transcript.read_text(encoding="utf-8").strip():
                        missing_transcripts.add(row["source_utter_id"])
            except (KeyError, ValueError, OSError, wave.Error) as exc:
                errors.append(f"{split}.csv:{i}: {exc}")
        split_stats[split] = {"speakers": len(speakers), "crops": len(rows),
                              "duration_sec": duration, "manifest_sha256": sha256_file(manifest),
                              "source_utterances_without_transcript": sorted(missing_transcripts)}
    preparation = splits_dir / "preparation.json"
    if not preparation.is_file():
        errors.append("Missing preparation.json; legacy splits lack verified provenance")
    else:
        try:
            metadata = json.loads(preparation.read_text(encoding="utf-8"))
            for split, stats in split_stats.items():
                if metadata["split_sha256"][split] != stats["manifest_sha256"]:
                    errors.append(f"{split}: manifest changed since preparation")
        except (KeyError, ValueError, OSError) as exc:
            errors.append(f"Invalid preparation.json: {exc}")
    return {"ok": not errors, "splits": split_stats, "errors": errors,
            "limitations": ["Source audio content is not hashed by this audit; preserve the downloaded archive checksum.",
                            "Crop provenance does not align words. Official-reference WER must use complete source utterances or verified word alignment."]}


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits_dir", type=Path, default=repo / "data/splits/vctk")
    parser.add_argument("--wav_root", type=Path, default=repo / "data/processed/vctk/wav16k")
    parser.add_argument("--raw_root", type=Path, default=repo / "data/raw")
    parser.add_argument("--archive", type=Path, help="Optionally hash the official downloaded archive (can take minutes)")
    parser.add_argument("--output", type=Path, default=repo / "artifacts/audit/data_audit.json")
    args = parser.parse_args()
    report = audit(args.splits_dir, args.wav_root, args.raw_root)
    if args.archive is not None:
        report["archive"] = {"path": str(args.archive), "sha256": sha256_file(args.archive)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "error_count": len(report["errors"]), "output": str(args.output)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
