#!/usr/bin/env bash
# Start after the named download session; stop immediately on a failed stage.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export PYTHONUNBUFFERED=1
dataset="${1:?dataset is required}"
case "$dataset" in
  librispeech) download_session=libri-download ;;
  vctk) download_session=vctk-download ;;
  *) echo "Unsupported dataset: $dataset" >&2; exit 2 ;;
esac
mkdir -p artifacts/logs artifacts/audit
run_name="pilot_${dataset}_seed42_20260918"
status="artifacts/logs/${run_name}.status"
exec > >(tee -a "artifacts/logs/${run_name}_pipeline.log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR
printf 'WAITING_DOWNLOAD %s\n' "$(date -Is)" > "$status"
while tmux has-session -t "$download_session" 2>/dev/null; do sleep 10; done
printf 'VERIFYING_ARCHIVE %s\n' "$(date -Is)" > "$status"
python scripts/verify_extract_corpus.py --dataset "$dataset"
printf 'PREPARING_DATA %s\n' "$(date -Is)" > "$status"
if [[ -e "data/splits/$dataset/preparation.json" ]]; then
  echo "Using existing prepared data; audit must pass before training."
else
  python scripts/prepare_data.py --dataset "$dataset" --seed 42 --microphone mic2
fi
python scripts/audit_experiment_data.py \
  --splits_dir "data/splits/$dataset" \
  --wav_root "data/processed/$dataset/wav16k" \
  --output "artifacts/audit/${dataset}_data_audit.json"
printf 'WAITING_GPU %s\n' "$(date -Is)" > "$status"
# Serialize our own pilots without taking over any unrelated GPU jobs.
exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
if [[ -e "checkpoints/defense/${run_name}_best.pt" ]]; then
  echo "Refusing to overwrite an existing pilot checkpoint." >&2
  false
fi
printf 'TRAINING_PILOT %s\n' "$(date -Is)" > "$status"
python scripts/run_train.py --config configs/train_server_pilot.yaml \
  --dataset "$dataset" --run_name "$run_name" --train_objective rank
test -s "checkpoints/defense/${run_name}_best.pt"
python scripts/check_training_run.py --run_name "$run_name" --steps 50
printf 'PILOT_COMPLETE %s\n' "$(date -Is)" > "$status"
reference_name="reference_${dataset}_v0p2_seed42_20260918"
if [[ -e "checkpoints/defense/${reference_name}_best.pt" ]]; then
  echo "Refusing to overwrite an existing reference checkpoint." >&2
  false
fi
printf 'TRAINING_REFERENCE %s\n' "$(date -Is)" > "$status"
python scripts/run_train.py --config configs/train_v0p2_p2_2.yaml \
  --dataset "$dataset" --run_name "$reference_name" --max_steps 1000 --train_objective rank
python scripts/check_training_run.py --run_name "$reference_name" --steps 1000
printf 'REFERENCE_COMPLETE %s\n' "$(date -Is)" > "$status"
