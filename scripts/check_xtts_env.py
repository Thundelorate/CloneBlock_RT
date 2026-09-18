#!/usr/bin/env python3
"""Validate and snapshot the isolated XTTS runtime without downloading weights."""

import importlib.metadata
import json
from pathlib import Path

import torch
import torchaudio
from TTS.api import TTS


snapshot = {
    "coqui_tts": importlib.metadata.version("coqui-tts"),
    "transformers": importlib.metadata.version("transformers"),
    "torch": torch.__version__,
    "torch_cuda": torch.version.cuda,
    "torchaudio": torchaudio.__version__,
    "cuda_available": torch.cuda.is_available(),
    "tts_import": TTS.__module__,
}
print(json.dumps(snapshot, indent=2))
output = Path("artifacts/env/xtts-environment-20260919.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
