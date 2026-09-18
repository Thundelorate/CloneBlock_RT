#!/usr/bin/env bash
# Engineering pilot on validation speakers only; never tune on test speakers.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONUNBUFFERED=1
mkdir -p artifacts/logs
exec > >(tee -a artifacts/logs/librispeech_validation_pilot_20260918.log) 2>&1
python scripts/check_training_run.py --run_name reference_librispeech_v0p2_seed42_20260918 --steps 1000
python scripts/build_session_pool_v3.py --dataset librispeech --seed 42 --isolate_dataset
exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
common=(--dataset librispeech --session_pool_csv data/splits/librispeech/session_pool_v3_val.csv
        --speaker_checkpoint_dir checkpoints/speaker_encoders/speechbrain_ecapa
        --strategies random_K,bestK_by_self_consistency --targeted_selection_source tele_defended
        --sanity_n_sessions 0 --seed 42 --output_tag libri_val_pilot_20260918)
python scripts/run_session_pool_eval.py "${common[@]}" --method_name no_defense
python scripts/run_session_pool_eval.py "${common[@]}" --method_name reference_v0p2 \
  --defense_checkpoint checkpoints/defense/reference_librispeech_v0p2_seed42_20260918_best.pt
echo "VALIDATION_PILOT_COMPLETE $(date -Is)"
