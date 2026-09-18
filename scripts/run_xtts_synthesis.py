#!/usr/bin/env python3
"""Synthesize fixed texts from frozen XTTS reference waveforms."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path


TEXTS = (
    ("t0", "The quick brown fox jumps over the lazy dog."),
    ("t1", "She sells seashells by the seashore."),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audio_dir", required=True, type=Path)
    parser.add_argument("--model_name", default="tts_models/multilingual/multi-dataset/xtts_v2")
    parser.add_argument("--language", default="en")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--ks", default="1,16")
    parser.add_argument("--max_reference_sec", type=float, default=30.0)
    parser.add_argument("--recommended_min_reference_sec", type=float, default=3.0)
    args = parser.parse_args()

    with args.references.open(newline="", encoding="utf-8") as handle:
        references = list(csv.DictReader(handle))
    ks = {int(value) for value in args.ks.split(",") if value.strip()}
    references = [row for row in references if int(row["K"]) in ks]
    if not references:
        raise ValueError("Reference manifest is empty")
    too_long = [row for row in references if float(row["reference_duration_sec"]) > args.max_reference_sec]
    if too_long:
        raise ValueError("A selected reference exceeds XTTS max_reference_sec")

    from TTS.api import TTS
    model = TTS(args.model_name).to(args.device)
    args.audio_dir.mkdir(parents=True, exist_ok=True)
    output_rows = []
    for row in references:
        reference_path = Path(row["reference_path"])
        if not reference_path.is_file():
            raise FileNotFoundError(reference_path)
        for text_id, text in TEXTS:
            filename = f"{int(row['order']):02d}_{row['speaker_id']}_{row['condition']}_K{row['K']}_{text_id}.wav"
            output_path = args.audio_dir / filename
            if output_path.exists():
                raise FileExistsError(f"Refusing to overwrite {output_path}")
            model.tts_to_file(
                text=text,
                speaker_wav=str(reference_path),
                language=args.language,
                file_path=str(output_path),
            )
            output_rows.append({
                **row,
                "text_id": text_id,
                "text": text,
                "model_name": args.model_name,
                "reference_below_recommended_duration": str(
                    float(row["reference_duration_sec"]) < args.recommended_min_reference_sec
                ).lower(),
                "synth_path": str(output_path),
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    metadata = {
        "protocol": "xtts_fixed_text_synthesis_v1",
        "model_name": args.model_name,
        "coqui_tts_version": importlib.metadata.version("coqui-tts"),
        "references_sha256": hashlib.sha256(args.references.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "n_syntheses": len(output_rows),
        "ks": sorted(ks),
        "max_reference_sec": args.max_reference_sec,
        "recommended_min_reference_sec": args.recommended_min_reference_sec,
        "excluded_k64_reason": "K64 concatenation exceeds the default 30-second per-reference limit",
        "texts": dict(TEXTS),
        "license_acceptance_env_present": os.environ.get("COQUI_TOS_AGREED") == "1",
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
