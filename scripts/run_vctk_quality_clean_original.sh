#!/usr/bin/env bash
# Add original-clean ASR WER and re-bootstrap quality deltas.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export PYTHONUNBUFFERED=1
status=artifacts/logs/vctk_quality_clean_original_20260919.status
log=artifacts/logs/vctk_quality_clean_original_20260919.log
mkdir -p artifacts/logs artifacts/tables/quality_official artifacts/tables/paper_icassp
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

printf 'WAITING_OFFICIAL_QUALITY %s\n' "$(date -Is)" > "$status"
while true; do
  upstream="$(cat artifacts/logs/vctk_quality_official_20260919.status 2>/dev/null || true)"
  [[ "$upstream" == QUALITY_OFFICIAL_COMPLETE* ]] && break
  [[ "$upstream" == FAILED* ]] && { echo "Official quality failed: $upstream"; false; }
  sleep 15
done

exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
printf 'CLEAN_ORIGINAL_ASR %s\n' "$(date -Is)" > "$status"
python scripts/run_quality_clean_asr.py \
  --manifest data/splits/vctk/quality_test_official.csv --device cuda \
  --output artifacts/tables/quality_official/vctk_quality_original_clean_20260919.csv

printf 'QUALITY_BOOTSTRAP_WITH_CLEAN %s\n' "$(date -Is)" > "$status"
python scripts/bootstrap_quality_ci.py \
  --inputs \
    artifacts/tables/quality_official/vctk_quality_none_20260919.csv \
    artifacts/tables/quality_official/vctk_quality_opus16k_20260919.csv \
    artifacts/tables/quality_official/vctk_quality_g711_20260919.csv \
  --clean_input artifacts/tables/quality_official/vctk_quality_original_clean_20260919.csv \
  --draws 2000 --seed 42 \
  --output artifacts/tables/paper_icassp/quality_official_bootstrap.csv

printf 'QUALITY_CLEAN_ORIGINAL_COMPLETE %s\n' "$(date -Is)" > "$status"
echo "Original-clean WER and augmented quality bootstrap complete."
