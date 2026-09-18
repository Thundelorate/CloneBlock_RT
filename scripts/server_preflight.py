#!/usr/bin/env python3
"""Local environment diagnostic. Does not download models or start training."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGES = {"numpy": "numpy", "scipy": "scipy", "soundfile": "soundfile", "librosa": "librosa",
            "PyYAML": "yaml", "jiwer": "jiwer", "pystoi": "pystoi", "torch": "torch",
            "torchaudio": "torchaudio", "speechbrain": "speechbrain", "huggingface-hub": "huggingface_hub",
            "matplotlib": "matplotlib", "pandas": "pandas"}


def inspect_environment(repo, require_gpu=False):
    errors, packages = [], {}
    for distribution, module in PACKAGES.items():
        try:
            importlib.import_module(module)
            packages[distribution] = {"version": importlib.metadata.version(distribution), "import_ok": True}
        except Exception as exc:
            packages[distribution] = {"import_ok": False, "error": str(exc)}
            errors.append(f"Cannot import {distribution}")
    gpu = {"available": False}
    if packages["torch"]["import_ok"]:
        import torch
        gpu["available"] = torch.cuda.is_available()
        gpu["torch_cuda_build"] = torch.version.cuda
        try:
            if gpu["available"]:
                gpu["devices"] = [{"name": torch.cuda.get_device_name(i),
                                   "memory_gib": torch.cuda.get_device_properties(i).total_memory / 1024**3}
                                  for i in range(torch.cuda.device_count())]
            device = "cuda" if gpu["available"] else "cpu"
            value = torch.ones(16, device=device, requires_grad=True)
            value.square().sum().backward()
            if not torch.allclose(value.grad, torch.full_like(value, 2)):
                raise RuntimeError("Autograd smoke test returned incorrect gradients")
            gpu["tensor_backward_device"] = device
        except Exception as exc:
            errors.append(f"Tensor/GPU smoke test failed: {exc}")
    if require_gpu and (platform.system() != "Linux" or not gpu["available"]):
        errors.append("This stage requires Linux with a usable CUDA GPU")
    if packages["torch"]["import_ok"] and packages["torchaudio"]["import_ok"]:
        if packages["torch"]["version"].split("+")[0] != packages["torchaudio"]["version"].split("+")[0]:
            errors.append("torch and torchaudio release versions must match")

    codecs = {"ffmpeg": shutil.which("ffmpeg"), "libopus": False, "pcm_mulaw": False}
    if codecs["ffmpeg"]:
        try:
            result = subprocess.run([codecs["ffmpeg"], "-hide_banner", "-encoders"],
                                    capture_output=True, text=True, timeout=15, check=True)
            names = {line.split()[1] for line in result.stdout.splitlines() if len(line.split()) >= 2}
            for encoder in ("libopus", "pcm_mulaw"):
                codecs[encoder] = encoder in names
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"FFmpeg inspection failed: {exc}")
    if not all(codecs.values()):
        errors.append("FFmpeg must expose libopus and pcm_mulaw encoders")
    assets = {"raw_vctk": (repo / "data/raw/VCTK-Corpus-0.92").is_dir(),
              "test_split": (repo / "data/splits/vctk/test.csv").is_file(),
              "test_session_pool": (repo / "data/splits/session_pool_v3_test.csv").is_file(),
              "defense_checkpoints": [str(p.relative_to(repo)) for p in (repo / "checkpoints/defense").glob("*.pt")]}
    versions = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}
    return {"ok": not errors, "created_utc": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(), "python": sys.version, "python_executable": sys.executable,
            "packages": packages, "gpu": gpu, "codecs": codecs, "assets": assets,
            "free_disk_gib": shutil.disk_usage(repo).free / 1024**3,
            "installed_distribution_versions": dict(sorted(versions.items())), "errors": errors,
            "scope": "Environment imports, tensor backward and codec presence only. Missing research assets are reported separately. No model inference, downloads or training."}


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require_gpu", action="store_true")
    parser.add_argument("--output", type=Path, default=repo / "artifacts/env/server_preflight.json")
    args = parser.parse_args()
    report = inspect_environment(repo, args.require_gpu)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "errors": report["errors"], "output": str(args.output)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
