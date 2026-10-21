#!/usr/bin/env bash
# Cache both public speaker encoders with an auditable exit status.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv-main/bin/python"
LOG="$REPO_ROOT/artifacts/logs/aggregation_model_prefetch.log"
STATUS="$REPO_ROOT/artifacts/logs/aggregation_model_prefetch.status"

mkdir -p "$REPO_ROOT/artifacts/logs" "$REPO_ROOT/models"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

cd "$REPO_ROOT"
source /etc/network_turbo >/dev/null 2>&1 || true
"$PY" -B scripts/download_models.py \
  --speaker_encoder speechbrain_ecapa \
  --speaker_savedir "$REPO_ROOT/models/spkrec-ecapa-voxceleb"
"$PY" -B scripts/download_models.py \
  --speaker_encoder speechbrain_xvector \
  --speaker_savedir "$REPO_ROOT/models/spkrec-xvect-voxceleb"

echo "ECAPA and x-vector caches are ready."
