#!/usr/bin/env bash
# Install XTTS in a dedicated environment without downloading licensed weights.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/logs /root/autodl-tmp/cache/xtts/models

python_bin=/root/miniconda3/bin/python
[[ -x "$python_bin" ]]
[[ -d .venv-xtts ]] || "$python_bin" -m venv .venv-xtts
source .venv-xtts/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install \
  torch==2.5.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121
python -m pip install coqui-tts==0.27.5 transformers==4.57.6

source scripts/activate_xtts.sh
mkdir -p artifacts/env
python -m pip check
python -m pip freeze > artifacts/env/requirements-xtts-resolved-20260919.txt
python scripts/check_xtts_env.py
