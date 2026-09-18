#!/usr/bin/env bash
# Download the user-authorized XTTS-v2 model and preserve a file manifest.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/logs artifacts/audit

status=artifacts/logs/xtts_model_download_20260919.status
log=artifacts/logs/xtts_model_download_20260919.log
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

source /etc/network_turbo 2>/dev/null || true
source scripts/activate_xtts.sh
export COQUI_TOS_AGREED=1
printf 'DOWNLOADING_MODEL %s\n' "$(date -Is)" > "$status"
python scripts/download_xtts_model.py \
  --model_name tts_models/multilingual/multi-dataset/xtts_v2 \
  --output artifacts/audit/xtts_model_manifest_20260919.json
printf 'MODEL_DOWNLOAD_COMPLETE %s\n' "$(date -Is)" > "$status"
