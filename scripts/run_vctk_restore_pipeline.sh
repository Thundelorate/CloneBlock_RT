#!/usr/bin/env bash
# Wait for the runtime and exact VCTK archive, then rebuild the frozen data protocol.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv-main/bin/python"
LOG="$REPO_ROOT/artifacts/logs/vctk_restore_pipeline.log"
STATUS="$REPO_ROOT/artifacts/logs/vctk_restore_pipeline.status"
EXPECTED_BYTES=11747302977

mkdir -p "$REPO_ROOT/artifacts/logs" "$REPO_ROOT/artifacts/audit"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

wait_for_success() {
  local file="$1"
  local label="$2"
  while [[ ! -f "$file" ]]; do
    echo "[$(date --iso-8601=seconds)] waiting for $label"
    sleep 60
  done
  if [[ "$(tr -d '[:space:]' < "$file")" != "0" ]]; then
    echo "$label failed; see its log" >&2
    return 1
  fi
}

cd "$REPO_ROOT"
wait_for_success artifacts/logs/server_runtime.status "server runtime"
wait_for_success artifacts/logs/vctk_download_new.status "VCTK download"

# The resumable downloader may leave the completed payload under its .part name.
if [[ ! -f data/raw/VCTK-Corpus-0.92.zip && -f data/raw/VCTK-Corpus-0.92.zip.part ]]; then
  actual_bytes="$(stat -c %s data/raw/VCTK-Corpus-0.92.zip.part)"
  if [[ "$actual_bytes" != "$EXPECTED_BYTES" || -f data/raw/VCTK-Corpus-0.92.zip.part.aria2 ]]; then
    echo "VCTK partial file is not complete" >&2
    exit 1
  fi
  mv data/raw/VCTK-Corpus-0.92.zip.part data/raw/VCTK-Corpus-0.92.zip
fi

"$PY" -B scripts/verify_extract_corpus.py --dataset vctk
"$PY" -B scripts/prepare_data.py --dataset vctk --seed 42 --microphone mic2
"$PY" -B scripts/audit_experiment_data.py \
  --splits_dir data/splits/vctk \
  --wav_root data/processed/vctk/wav16k \
  --output artifacts/audit/vctk_data_audit_restored.json
"$PY" -B scripts/build_session_pool_v3.py \
  --dataset vctk --seed 42 --isolate_dataset --disjoint_source_utterances

echo "VCTK restore and frozen session-pool build completed."
