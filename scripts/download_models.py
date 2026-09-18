#!/usr/bin/env python3
"""Download/cache public pretrained models for this repo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.metrics.speaker import SpeakerMetric


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download speaker/ASR models to local checkpoints.")
    p.add_argument(
        "--speaker_savedir",
        type=str,
        default=str(REPO_ROOT / "checkpoints" / "speaker_encoders" / "speechbrain_ecapa"),
        help="Local cache dir for speechbrain ECAPA model",
    )
    p.add_argument("--device", type=str, default="cpu", help="cpu/cuda")
    p.add_argument(
        "--speaker_encoder",
        choices=["speechbrain_ecapa", "speechbrain_xvector"],
        default="speechbrain_ecapa",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    savedir = Path(args.speaker_savedir)
    savedir.mkdir(parents=True, exist_ok=True)

    config = {"encoder_name": args.speaker_encoder, "device": args.device}
    if args.speaker_encoder == "speechbrain_xvector":
        config["checkpoint_dir_xvector"] = str(savedir)
    else:
        config["checkpoint_dir"] = str(savedir)
    speaker = SpeakerMetric(config)

    wav = torch.randn(16000, dtype=torch.float32)
    emb = speaker.embed(wav, sample_rate=16000)
    print(f"[download_models] {args.speaker_encoder} cache={savedir}")
    print(f"[download_models] embedding shape={tuple(emb.shape)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
