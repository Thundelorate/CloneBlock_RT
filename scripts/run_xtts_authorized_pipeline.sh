#!/usr/bin/env bash
# Start the frozen XTTS experiment as soon as references and weights are ready.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/logs

status=artifacts/logs/xtts_pipeline_20260919.status
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR
printf 'WAITING_PREREQUISITES %s\n' "$(date -Is)" > "$status"

while true; do
  prep="$(cat artifacts/logs/xtts_prepare_20260919.status 2>/dev/null || true)"
  model="$(cat artifacts/logs/xtts_model_download_20260919.status 2>/dev/null || true)"
  [[ "$prep" == FAILED* ]] && { echo "XTTS reference preparation failed: $prep"; false; }
  [[ "$model" == FAILED* ]] && { echo "XTTS model download failed: $model"; false; }
  if [[ "$prep" == WAITING_MODEL_LICENSE* && "$model" == MODEL_DOWNLOAD_COMPLETE* ]]; then
    break
  fi
  sleep 10
done

printf 'STARTING_FROZEN_XTTS %s\n' "$(date -Is)" > "$status"
export COQUI_TOS_AGREED=1
bash scripts/run_xtts_after_license.sh
printf 'PIPELINE_COMPLETE %s\n' "$(date -Is)" > "$status"
