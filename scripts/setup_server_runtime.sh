#!/usr/bin/env bash
# Finish the AutoDL runtime without replacing the CUDA-enabled torch bundled in the image.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="${ENV_DIR:-$REPO_ROOT/.venv-main}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
STATUS="$REPO_ROOT/artifacts/logs/server_runtime.status"
LOG="$REPO_ROOT/artifacts/logs/server_runtime.log"

mkdir -p "$REPO_ROOT/artifacts/logs" /root/autodl-tmp/cache/{huggingface,torch,pip} /root/autodl-tmp/tmp
export HF_HOME=/root/autodl-tmp/cache/huggingface
export TORCH_HOME=/root/autodl-tmp/cache/torch
export PIP_CACHE_DIR=/root/autodl-tmp/cache/pip
export TMPDIR=/root/autodl-tmp/tmp

exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  /root/miniconda3/bin/python -m venv --system-site-packages "$ENV_DIR"
fi

"$ENV_DIR/bin/python" - <<'PY'
import torch
import torchaudio
assert torch.__version__.split("+")[0] == torchaudio.__version__.split("+")[0]
assert torch.cuda.is_available(), "CUDA is not available"
print("Using bundled runtime:", torch.__version__, torchaudio.__version__)
PY

"$ENV_DIR/bin/python" -m pip install \
  --index-url "$PIP_INDEX_URL" --retries 10 --timeout 120 \
  -r "$REPO_ROOT/requirements-server.txt"

# A system-site-packages venv can make old pip report the base Conda
# ruamel.yaml metadata even though Python imports the compatible venv copy.
# Validate the runtime that will actually execute the experiment.
"$ENV_DIR/bin/python" - <<'PY'
import importlib
from importlib import metadata

required = (
    "librosa",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "soundfile",
    "speechbrain",
    "yaml",
)
for name in required:
    module = importlib.import_module(name)
    print(f"{name}: {getattr(module, '__version__', 'imported')}")

import ruamel.yaml

version = tuple(int(part) for part in ruamel.yaml.__version__.split(".")[:3])
assert version >= (0, 17, 28), ruamel.yaml.__version__
print("ruamel.yaml runtime:", ruamel.yaml.__version__, ruamel.yaml.__file__)
print("hyperpyyaml metadata:", metadata.version("hyperpyyaml"))
PY

cd "$REPO_ROOT"
"$ENV_DIR/bin/python" -B scripts/server_preflight.py --require_gpu
"$ENV_DIR/bin/python" -B -m unittest discover -s tests -v
"$ENV_DIR/bin/python" -B scripts/server_smoke.py
echo "Server runtime ready."
