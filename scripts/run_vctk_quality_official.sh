#!/usr/bin/env bash
# Run official-transcript full-utterance VCTK quality evaluation after the selection ablation.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export PYTHONUNBUFFERED=1

run_id=vctk_quality_official_20260919
status="artifacts/logs/${run_id}.status"
log="artifacts/logs/${run_id}.log"
freeze="artifacts/audit/${run_id}_freeze.txt"
mkdir -p artifacts/logs artifacts/audit artifacts/tables/quality_official artifacts/tables/paper_icassp
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

printf 'WAITING_SELECTION_ABLATION %s\n' "$(date -Is)" > "$status"
while true; do
  upstream="$(cat artifacts/logs/vctk_selection_ablation_20260919.status 2>/dev/null || true)"
  [[ "$upstream" == SELECTION_ABLATION_COMPLETE* ]] && break
  [[ "$upstream" == FAILED* ]] && { echo "Selection ablation failed: $upstream"; false; }
  sleep 15
done

manifest=data/splits/vctk/quality_test_official.csv
checkpoint=checkpoints/defense/realistic_vctk_selected_seed42_20260918_best.pt
for required in "$manifest" "$checkpoint"; do
  [[ -s "$required" ]] || { echo "Missing input: $required"; false; }
done

exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
{
  echo "protocol=vctk_official_full_utterance_quality_v1"
  echo "created=$(date -Is)"
  echo "seed=42"
  echo "utterances=200"
  echo "transcript=vctk_official"
  echo "stoi_primary=tele_clean_vs_tele_defended"
  echo "shared_channel_draws=true"
  sha256sum "$manifest" "$checkpoint" scripts/run_quality_eval_official.py scripts/bootstrap_quality_ci.py
} > "$freeze"

for codec in none opus g711; do
  tag="$codec"
  [[ "$codec" == opus ]] && tag=opus16k
  printf 'QUALITY_%s %s\n' "$tag" "$(date -Is)" > "$status"
  python scripts/run_quality_eval_official.py \
    --manifest "$manifest" --defense_checkpoint "$checkpoint" \
    --defense_name realistic_selected --telephony_codec "$codec" \
    --telephony_codec_bitrate 16k --device cuda --seed 42 \
    --output "artifacts/tables/quality_official/vctk_quality_${tag}_20260919.csv"
done

printf 'QUALITY_BOOTSTRAP %s\n' "$(date -Is)" > "$status"
python scripts/bootstrap_quality_ci.py \
  --inputs \
    artifacts/tables/quality_official/vctk_quality_none_20260919.csv \
    artifacts/tables/quality_official/vctk_quality_opus16k_20260919.csv \
    artifacts/tables/quality_official/vctk_quality_g711_20260919.csv \
  --draws 2000 --seed 42 \
  --output artifacts/tables/paper_icassp/quality_official_bootstrap.csv

printf 'QUALITY_OFFICIAL_COMPLETE %s\n' "$(date -Is)" > "$status"
echo "Official-transcript VCTK quality evaluation complete."
