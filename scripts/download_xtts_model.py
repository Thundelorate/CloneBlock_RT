#!/usr/bin/env python3
"""Download the licensed XTTS-v2 model and record a reproducibility manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from TTS.utils.manage import ModelManager


MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model_name", default=MODEL_NAME)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if os.environ.get("COQUI_TOS_AGREED") != "1":
        raise RuntimeError("COQUI_TOS_AGREED=1 is required after explicit CPML acceptance")

    model_path, config_path, model_item = ModelManager(progress_bar=True).download_model(args.model_name)
    model_path = Path(model_path).resolve()
    config_path = Path(config_path).resolve() if config_path else None
    model_dir = model_path if model_path.is_dir() else model_path.parent
    files = []
    for path in sorted(item for item in model_dir.rglob("*") if item.is_file()):
        files.append({
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    payload = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": args.model_name,
        "model_path": str(model_path),
        "config_path": str(config_path) if config_path else None,
        "license": model_item.get("license"),
        "tos_required": model_item.get("tos_required"),
        "commit": model_item.get("commit"),
        "model_hash": model_item.get("model_hash"),
        "files": files,
        "total_size_bytes": sum(item["size_bytes"] for item in files),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
