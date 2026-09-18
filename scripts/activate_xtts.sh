#!/usr/bin/env bash
# Shared environment for the isolated XTTS evaluator.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repo_root/.venv-xtts/bin/activate"
export TTS_HOME=/root/autodl-tmp/cache/xtts/models
export HF_HOME=/root/autodl-tmp/cache/huggingface
export TORCH_HOME=/root/autodl-tmp/cache/torch
export XDG_CACHE_HOME=/root/autodl-tmp/cache
mkdir -p "$TTS_HOME" "$HF_HOME" "$TORCH_HOME"
