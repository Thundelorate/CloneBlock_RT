#!/usr/bin/env bash
# Install the candidate main environment into a dedicated venv, then validate it.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
ENV_DIR="${ENV_DIR:-$REPO_ROOT/.venv-main}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
export HF_HOME="${HF_HOME:-/root/autodl-tmp/cache/huggingface}"
export TORCH_HOME="${TORCH_HOME:-/root/autodl-tmp/cache/torch}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/root/autodl-tmp/cache/pip}"
export TMPDIR="${TMPDIR:-/root/autodl-tmp/tmp}"

if [[ "$(uname -s)" != Linux ]]; then
  echo "Run this script on the Linux GPU server." >&2
  exit 1
fi
mkdir -p "$HF_HOME" "$TORCH_HOME" "$PIP_CACHE_DIR" "$TMPDIR"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:2] in ((3,10), (3,11)), "Use Python 3.10 or 3.11"'
if ! command -v ffmpeg >/dev/null; then
  echo "Install ffmpeg first (on Ubuntu: apt-get update && apt-get install -y ffmpeg libsndfile1)." >&2
  exit 1
fi
if [[ ! -e "$ENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$ENV_DIR"
fi
if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  echo "ENV_DIR exists but is not a Python venv: $ENV_DIR" >&2
  exit 1
fi
"$ENV_DIR/bin/python" -c 'import sys; assert sys.version_info[:2] in ((3,10), (3,11)), "Existing venv has an unsupported Python version"'
"$ENV_DIR/bin/python" -m pip install 'pip<26'
"$ENV_DIR/bin/python" -m pip install torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
"$ENV_DIR/bin/python" -m pip install -r "$REPO_ROOT/requirements-server.txt"
"$ENV_DIR/bin/python" -m pip check
cd "$REPO_ROOT"
"$ENV_DIR/bin/python" -B scripts/server_preflight.py --require_gpu
"$ENV_DIR/bin/python" -B -m unittest discover -s tests -v
"$ENV_DIR/bin/python" -B scripts/server_smoke.py
echo "Environment ready for an audio/model pilot. Activate: source $REPO_ROOT/scripts/activate_autodl.sh"
echo "No corpus, pretrained model, or experiment has been downloaded or run by this script."
