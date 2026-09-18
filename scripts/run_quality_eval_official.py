#!/usr/bin/env python3
"""Evaluate WER and STOI on full VCTK utterances with official transcripts."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from jiwer import wer as jiwer_wer
from pystoi import stoi as pystoi_stoi

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics.asr import ASRMetric
from src.models.defense_stftmask import STFTMaskDefense
from src.transforms.telephony import TelephonyTransform


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def stoi(reference: np.ndarray, degraded: np.ndarray, sample_rate: int) -> float:
    length = min(len(reference), len(degraded))
    if length <= 0:
        return float("nan")
    return float(pystoi_stoi(reference[:length], degraded[:length], sample_rate, extended=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--defense_checkpoint", required=True, type=Path)
    parser.add_argument("--defense_name", default="realistic_selected")
    parser.add_argument("--telephony_codec", choices=["none", "opus", "g711"], required=True)
    parser.add_argument("--telephony_codec_bitrate", default="16k")
    parser.add_argument("--telephony_config", type=Path, default=ROOT / "configs/telephony.yaml")
    parser.add_argument("--eval_config", type=Path, default=ROOT / "configs/eval.yaml")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    with args.manifest.open(newline="", encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    if not manifest or any(row.get("is_full_utterance") != "1" for row in manifest):
        raise ValueError("Quality manifest must contain full utterances only")

    import yaml
    telephony_payload = yaml.safe_load(args.telephony_config.read_text(encoding="utf-8")) or {}
    telephony_config = copy.deepcopy(telephony_payload.get("telephony", telephony_payload))
    telephony_config.setdefault("codec", {})
    telephony_config["codec"]["enabled"] = args.telephony_codec != "none"
    telephony_config["codec"]["name"] = args.telephony_codec
    if args.telephony_codec == "opus":
        telephony_config["codec"]["bitrate"] = args.telephony_codec_bitrate
    telephony = TelephonyTransform(telephony_config, seed=args.seed)

    eval_payload = yaml.safe_load(args.eval_config.read_text(encoding="utf-8")) or {}
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    asr_config = eval_payload.get("asr_metric", eval_payload.get("asr", {})) or {}
    asr_config["device"] = str(device)
    asr = ASRMetric(asr_config)

    checkpoint = torch.load(args.defense_checkpoint, map_location=device)
    defense = STFTMaskDefense(checkpoint.get("model_config", {})).to(device).eval()
    defense.load_state_dict(checkpoint["model_state_dict"], strict=True)

    sample_rate = 16000
    output_rows = []
    for index, row in enumerate(manifest):
        audio_path = ROOT / row["path"]
        transcript_path = ROOT / row["transcript_path"]
        if not audio_path.is_file() or not transcript_path.is_file():
            raise FileNotFoundError(audio_path if not audio_path.is_file() else transcript_path)
        clean = load_wav(audio_path, sample_rate)
        transcript = transcript_path.read_text(encoding="utf-8", errors="replace").strip()
        if not transcript:
            raise ValueError(f"Empty official transcript: {transcript_path}")

        params = telephony.sample_params()
        tele_clean = telephony.apply_with_params(clean, sample_rate=sample_rate, params=params)
        with torch.inference_mode():
            defended = defense(torch.from_numpy(clean).to(device)).detach().cpu().numpy().astype(np.float32)
        tele_defended = telephony.apply_with_params(
            defended, sample_rate=sample_rate, params=params
        )
        hypothesis_clean = asr.transcribe(torch.from_numpy(tele_clean).unsqueeze(0), sample_rate)
        hypothesis_defended = asr.transcribe(
            torch.from_numpy(tele_defended).unsqueeze(0), sample_rate
        )
        wer_clean = float(jiwer_wer(transcript, hypothesis_clean))
        wer_defended = float(jiwer_wer(transcript, hypothesis_defended))
        output_rows.append({
            "order": index,
            "utter_id": row["utter_id"],
            "speaker_id": row["speaker_id"],
            "telephony": "opus16k" if args.telephony_codec == "opus" else args.telephony_codec,
            "defense": args.defense_name,
            "reference_source": "vctk_official_transcript",
            "wer_tele_clean": f"{wer_clean:.9f}",
            "wer_tele_defended": f"{wer_defended:.9f}",
            "wer_delta": f"{wer_defended - wer_clean:.9f}",
            "stoi_tele_clean_vs_tele_defended": f"{stoi(tele_clean, tele_defended, sample_rate):.9f}",
            "stoi_clean_vs_tele_clean": f"{stoi(clean, tele_clean, sample_rate):.9f}",
            "stoi_clean_vs_tele_defended": f"{stoi(clean, tele_defended, sample_rate):.9f}",
            "audio_path": row["path"],
            "transcript_path": row["transcript_path"],
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    metadata = {
        "protocol": "vctk_official_full_utterance_quality_v1",
        "telephony_codec": args.telephony_codec,
        "telephony_codec_bitrate": args.telephony_codec_bitrate,
        "reference_source": "vctk_official_transcript",
        "stoi_primary_pair": "tele_clean_vs_tele_defended",
        "shared_channel_draws": True,
        "manifest_sha256": sha256(args.manifest),
        "defense_checkpoint_sha256": sha256(args.defense_checkpoint),
        "n_utterances": len(output_rows),
        "n_speakers": len({row["speaker_id"] for row in output_rows}),
        "output_sha256": sha256(args.output),
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
