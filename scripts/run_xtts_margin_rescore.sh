#!/usr/bin/env bash
# Re-score frozen XTTS outputs with target-impostor margins.
set -euo pipefail
cd "$(dirname "$0")/.."
status=artifacts/logs/xtts_final_20260919.status
log=artifacts/logs/xtts_margin_rescore_20260919.log
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED_MARGIN_RESCORE exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

source scripts/activate_autodl.sh
printf 'RESCORING_XTTS_MARGIN %s\n' "$(date -Is)" > "$status"
python scripts/score_xtts_outputs.py \
  --syntheses artifacts/xtts/vctk_xtts_syntheses_20260919.csv \
  --thresholds artifacts/audit/vctk_xtts_asv_thresholds_20260919.json \
  --speaker_checkpoint_dir checkpoints/speaker_encoders/speechbrain_ecapa \
  --speaker_checkpoint_dir_xvector checkpoints/speaker_encoders/speechbrain_xvector \
  --device cuda --draws 2000 --seed 42 \
  --output artifacts/tables/vctk_xtts_scores_20260919.csv \
  --summary_output artifacts/tables/vctk_xtts_summary_20260919.csv
printf 'XTTS_COMPLETE_WITH_MARGIN %s\n' "$(date -Is)" > "$status"
