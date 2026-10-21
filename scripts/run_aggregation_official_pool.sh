#!/usr/bin/env bash
# Build the aggregation protocol pools from the checksum-verified official VCTK archive.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv-main/bin/python"
LOG="$REPO_ROOT/artifacts/logs/aggregation_official_pool.log"
STATUS="$REPO_ROOT/artifacts/logs/aggregation_official_pool.status"
RESTORE_STATUS="$REPO_ROOT/artifacts/logs/vctk_restore_pipeline.status"
CORPUS_ROOT="$REPO_ROOT/data/raw/VCTK-Corpus-0.92"
ARCHIVE="$REPO_ROOT/data/raw/VCTK-Corpus-0.92.zip"
SOURCE_AUDIT="$REPO_ROOT/artifacts/audit/vctk_aggregation_official_source.json"
EXPECTED_MD5="8a6ba2946b36fcbef0212cad601f4bfa"

mkdir -p "$REPO_ROOT/artifacts/logs" "$REPO_ROOT/artifacts/audit"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

while [[ ! -f "$RESTORE_STATUS" ]]; do
  echo "[$(date --iso-8601=seconds)] waiting for official VCTK restore"
  sleep 30
done
if [[ "$(tr -d '[:space:]' < "$RESTORE_STATUS")" != "0" ]]; then
  echo "Official VCTK restore failed" >&2
  exit 1
fi

cd "$REPO_ROOT"
"$PY" -B scripts/audit_vctk_aggregation_source.py \
  --corpus_root "$CORPUS_ROOT" \
  --archive "$ARCHIVE" \
  --output "$SOURCE_AUDIT"

"$PY" -B scripts/build_aggregation_session_pool.py \
  --corpus_root "$CORPUS_ROOT" \
  --output_dir data/splits/vctk \
  --sample_rate 16000 \
  --session_seconds 80 \
  --seed 42 \
  --source_kind official_archive \
  --source_archive_md5 "$EXPECTED_MD5" \
  --source_audit "$SOURCE_AUDIT"

echo "Official VCTK aggregation validation/test session pools are ready."
