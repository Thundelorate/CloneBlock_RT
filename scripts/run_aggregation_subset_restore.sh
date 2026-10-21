#!/usr/bin/env bash
# Wait for the sparse VCTK subset, then build independent enrollment/attack pools.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv-main/bin/python"
LOG="$REPO_ROOT/artifacts/logs/aggregation_subset_pool.log"
STATUS="$REPO_ROOT/artifacts/logs/aggregation_subset_pool.status"
SOURCE_STATUS="$REPO_ROOT/artifacts/logs/vctk_subset_git.status"
RUNTIME_STATUS="$REPO_ROOT/artifacts/logs/server_runtime.status"
CORPUS_ROOT="$REPO_ROOT/data/raw/VCTK-Corpus-0.92-github-subset"
SOURCE_COMMIT="${SOURCE_COMMIT:-4af5c66fddca9cde5ec24e5359929e5a7e7c953f}"

mkdir -p "$REPO_ROOT/artifacts/logs"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

wait_for_success() {
  local status_file="$1"
  local label="$2"
  while [[ ! -f "$status_file" ]]; do
    echo "[$(date --iso-8601=seconds)] waiting for $label"
    sleep 30
  done
  if [[ "$(tr -d '[:space:]' < "$status_file")" != "0" ]]; then
    echo "$label failed" >&2
    exit 1
  fi
}

wait_for_success "$SOURCE_STATUS" "VCTK sparse subset"
wait_for_success "$RUNTIME_STATUS" "server runtime"

cd "$REPO_ROOT"
"$PY" -B scripts/build_aggregation_session_pool.py \
  --corpus_root "$CORPUS_ROOT" \
  --output_dir data/splits/vctk \
  --sample_rate 16000 \
  --session_seconds 80 \
  --seed 42 \
  --source_kind pinned_git_mirror_subset \
  --source_commit "$SOURCE_COMMIT" \
  --source_audit artifacts/audit/vctk_aggregation_subset_source.tsv

echo "Aggregation validation/test session pools are ready."

