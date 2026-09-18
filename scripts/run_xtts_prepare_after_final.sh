#!/usr/bin/env bash
# Wait for the frozen final test, then prepare XTTS references without model weights.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/logs artifacts/audit artifacts/xtts/references

status=artifacts/logs/xtts_prepare_20260919.status
log=artifacts/logs/xtts_prepare_20260919.log
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

printf 'WAITING_FINAL_TEST %s\n' "$(date -Is)" > "$status"
while true; do
  final_status="$(cat artifacts/logs/vctk_final_test_20260919.status 2>/dev/null || true)"
  [[ "$final_status" == FINAL_TEST_COMPLETE* ]] && break
  [[ "$final_status" == FAILED* ]] && { echo "Final test failed: $final_status"; false; }
  sleep 15
done

manifest=artifacts/audit/vctk_xtts_manifest_20260919.csv
thresholds=artifacts/audit/vctk_xtts_asv_thresholds_20260919.json
pool=data/splits/vctk/session_pool_v3_test.csv
checkpoint=checkpoints/defense/realistic_vctk_selected_seed42_20260918_best.pt
references=artifacts/xtts/vctk_xtts_references_20260919.csv
reference_dir=artifacts/xtts/references/20260919
for required in "$manifest" "$thresholds" "$pool" "$checkpoint"; do
  [[ -s "$required" ]] || { echo "Missing required input: $required"; false; }
done
[[ ! -e "$references" ]]
mkdir -p "$reference_dir"

printf 'FREEZING_XTTS_PROTOCOL %s\n' "$(date -Is)" > "$status"
{
  echo "protocol=xtts_small_scale_pre_result_v1"
  echo "created=$(date -Is)"
  echo "sessions=20"
  echo "speakers=11"
  echo "reference_K=1,16,64"
  echo "synthesis_K=1_exploratory,16_primary"
  echo "excluded_K64=concatenated_reference_exceeds_xtts_default_30_second_limit"
  echo "texts=t0,t1"
  echo "selection=bestK_by_self_consistency"
  echo "selection_source=tele_clean_or_tele_defended_by_condition"
  echo "enrollment=independent_session"
  echo "operating_point=validation_natural_speech_far_1pct"
  sha256sum "$manifest" "$thresholds" "$pool" "$checkpoint" \
    scripts/prepare_xtts_references.py scripts/run_xtts_synthesis.py \
    scripts/score_xtts_outputs.py
} > artifacts/audit/vctk_xtts_protocol_freeze_20260919.txt

source scripts/activate_autodl.sh
printf 'PREPARING_REFERENCES %s\n' "$(date -Is)" > "$status"
python scripts/prepare_xtts_references.py \
  --manifest "$manifest" \
  --session_pool_csv "$pool" \
  --defense_checkpoint "$checkpoint" \
  --speaker_checkpoint_dir checkpoints/speaker_encoders/speechbrain_ecapa \
  --ks 1,16,64 --seed 42 --device cuda \
  --output "$references" --audio_dir "$reference_dir"

printf 'WAITING_XTTS_ENV %s\n' "$(date -Is)" > "$status"
while tmux has-session -t xtts-setup 2>/dev/null; do sleep 10; done
source scripts/activate_xtts.sh
python -c 'import torch; from TTS.api import TTS; print(torch.__version__, TTS.__module__)'
printf 'WAITING_MODEL_LICENSE %s\n' "$(date -Is)" > "$status"
echo "References are frozen. Model download requires user acceptance of the XTTS license prompt."
