#!/usr/bin/env bash
# Source this file from an SSH or VS Code terminal.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Use: source scripts/activate_autodl.sh" >&2
  exit 1
fi
CLONEBLOCK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$CLONEBLOCK_ROOT/.venv-main/bin/activate" ]]; then
  echo "Missing .venv-main; run scripts/setup_autodl.sh first." >&2
  return 1
fi
export HF_HOME=/root/autodl-tmp/cache/huggingface
export TORCH_HOME=/root/autodl-tmp/cache/torch
export PIP_CACHE_DIR=/root/autodl-tmp/cache/pip
export XDG_CACHE_HOME=/root/autodl-tmp/cache
export TMPDIR=/root/autodl-tmp/tmp
mkdir -p "$HF_HOME" "$TORCH_HOME" "$PIP_CACHE_DIR" "$TMPDIR"
source "$CLONEBLOCK_ROOT/.venv-main/bin/activate"
