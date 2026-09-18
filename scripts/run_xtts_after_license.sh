#!/usr/bin/env bash
# Run frozen XTTS synthesis only after explicit user license acceptance.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/logs artifacts/audit artifacts/xtts/syntheses/20260919 artifacts/tables

status=artifacts/logs/xtts_final_20260919.status
log=artifacts/logs/xtts_final_20260919.log
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

[[ "$(cat artifacts/logs/xtts_prepare_20260919.status)" == WAITING_MODEL_LICENSE* ]]
[[ "${COQUI_TOS_AGREED:-}" == "1" ]] || {
  echo "Set COQUI_TOS_AGREED=1 only after reviewing and accepting the XTTS model license." >&2
  false
}

references=artifacts/xtts/vctk_xtts_references_20260919.csv
syntheses=artifacts/xtts/vctk_xtts_syntheses_20260919.csv
thresholds=artifacts/audit/vctk_xtts_asv_thresholds_20260919.json
[[ -s "$references" ]]
[[ -s "$thresholds" ]]
[[ ! -e "$syntheses" ]]

exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
source scripts/activate_xtts.sh
printf 'XTTS_SYNTHESIS %s\n' "$(date -Is)" > "$status"
python scripts/run_xtts_synthesis.py \
  --references "$references" --ks 1,16 \
  --output "$syntheses" --audio_dir artifacts/xtts/syntheses/20260919 \
  --model_name tts_models/multilingual/multi-dataset/xtts_v2 \
  --language en --device cuda

printf 'HASHING_MODEL %s\n' "$(date -Is)" > "$status"
find "$TTS_HOME" -type f -print0 | sort -z | xargs -0 sha256sum \
  > artifacts/audit/xtts_model_files_sha256_20260919.txt

source scripts/activate_autodl.sh
printf 'SCORING_XTTS %s\n' "$(date -Is)" > "$status"
python scripts/score_xtts_outputs.py \
  --syntheses "$syntheses" --thresholds "$thresholds" \
  --speaker_checkpoint_dir checkpoints/speaker_encoders/speechbrain_ecapa \
  --speaker_checkpoint_dir_xvector checkpoints/speaker_encoders/speechbrain_xvector \
  --device cuda --draws 2000 --seed 42 \
  --output artifacts/tables/vctk_xtts_scores_20260919.csv \
  --summary_output artifacts/tables/vctk_xtts_summary_20260919.csv

printf 'XTTS_COMPLETE %s\n' "$(date -Is)" > "$status"
echo "Frozen XTTS evaluation complete."
