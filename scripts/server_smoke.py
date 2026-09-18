#!/usr/bin/env python3
"""Synthetic GPU/codec checks, not speech experiments or quality evidence."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.models.defense_stftmask import STFTMaskDefense
from src.transforms.telephony import TelephonyTransform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "artifacts/env/server_smoke.json")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required")
    torch.manual_seed(42)
    model = STFTMaskDefense().cuda().train()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    before = model.head.weight.detach().clone()
    waveform = torch.randn(2, 16000, device="cuda") * 0.1
    output = model(waveform)
    if output.shape != waveform.shape or not torch.isfinite(output).all():
        raise RuntimeError("Invalid defense output")
    loss = output.square().mean()
    loss.backward()
    gradients = [p.grad for p in model.parameters()]
    if any(g is None or not torch.isfinite(g).all() for g in gradients):
        raise RuntimeError("Missing or nonfinite defense gradients")
    optimizer.step()
    if torch.equal(before, model.head.weight):
        raise RuntimeError("Optimizer did not update defense parameters")
    torch.cuda.synchronize()
    report = {"ok": True, "scope": __doc__, "gpu": torch.cuda.get_device_name(),
              "defense_shape": list(output.shape), "optimizer_update": True,
              "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
              "codecs": {}}
    t = np.arange(16000, dtype=np.float32) / 16000
    signal = (0.15 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    for codec in ("opus", "g711"):
        transform = TelephonyTransform({"codec": {"enabled": True, "name": codec}})
        calls, failures = [], []
        original_run = subprocess.run

        def checked_run(*pos, **kw):
            try:
                result = original_run(*pos, **kw)
            except Exception as exc:
                failures.append(str(exc))
                raise
            calls.append(pos[0])
            return result

        # The transform can silently fall back; count successful FFmpeg operations.
        with patch("src.transforms.telephony.subprocess.run", side_effect=checked_run):
            decoded = transform(signal, sample_rate=16000)
        if failures or len(calls) != 2:
            raise RuntimeError(f"{codec}: FFmpeg encode/decode not completed: {failures}")
        if decoded.shape != signal.shape or not np.isfinite(decoded).all():
            raise RuntimeError(f"{codec}: invalid decoded waveform")
        if not np.any(decoded) or np.array_equal(decoded, signal):
            raise RuntimeError(f"{codec}: empty or unchanged waveform")
        report["codecs"][codec] = {"ffmpeg_operations": len(calls), "samples": len(decoded)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
