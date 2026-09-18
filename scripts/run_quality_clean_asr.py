#!/usr/bin/env python3
"""Measure the ASR WER of original clean VCTK utterances against official transcripts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from jiwer import wer as jiwer_wer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics.asr import ASRMetric


def load_wav(path: Path, target_sr: int) -> np.ndarray:
    audio, sample_rate = sf.read(path, dtype="float32")
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if int(sample_rate) != target_sr:
        import librosa
        audio = librosa.resample(
            audio.astype(np.float64), orig_sr=int(sample_rate), target_sr=target_sr
        ).astype(np.float32)
    return audio.astype(np.float32)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--eval_config", type=Path, default=ROOT / "configs/eval.yaml")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    import yaml
    with args.manifest.open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    eval_payload = yaml.safe_load(args.eval_config.read_text(encoding="utf-8")) or {}
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    asr_config = eval_payload.get("asr_metric", eval_payload.get("asr", {})) or {}
    asr_config["device"] = str(device)
    asr = ASRMetric(asr_config)

    rows = []
    for item in manifest:
        audio_path = ROOT / item["path"]
        transcript_path = ROOT / item["transcript_path"]
        clean = load_wav(audio_path, 16000)
        transcript = transcript_path.read_text(encoding="utf-8", errors="replace").strip()
        hypothesis = asr.transcribe(torch.from_numpy(clean).unsqueeze(0), 16000)
        rows.append({
            "utter_id": item["utter_id"],
            "speaker_id": item["speaker_id"],
            "reference_source": "vctk_official_transcript",
            "wer_clean_original": f"{float(jiwer_wer(transcript, hypothesis)):.9f}",
            "audio_path": item["path"],
            "transcript_path": item["transcript_path"],
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.output.with_suffix(".json").write_text(json.dumps({
        "protocol": "vctk_official_original_clean_asr_v1",
        "manifest_sha256": sha256(args.manifest),
        "n_utterances": len(rows),
        "n_speakers": len({row["speaker_id"] for row in rows}),
        "output_sha256": sha256(args.output),
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
