#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

with_data=0
with_xtts=0
verify_only=0
for arg in "$@"; do
  case "$arg" in
    --with-data) with_data=1 ;;
    --with-xtts) with_xtts=1 ;;
    --verify-only) verify_only=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

python_bin="${PYTHON_BIN:-/root/miniconda3/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$(command -v python3)"
"$python_bin" scripts/verify_frozen_snapshot.py
if (( verify_only )); then
  exit 0
fi

if ! command -v ffmpeg >/dev/null || ! command -v aria2c >/dev/null; then
  if [[ "$(id -u)" != 0 ]]; then
    echo "Install ffmpeg, libsndfile1, aria2, tmux and unzip as root first." >&2
    exit 1
  fi
  apt-get update
  apt-get install -y ffmpeg libsndfile1 aria2 tmux unzip
fi

PYTHON_BIN="$python_bin" bash scripts/setup_autodl.sh
source scripts/activate_autodl.sh
python scripts/verify_frozen_snapshot.py

if (( with_data )); then
  bash scripts/download_data.sh librispeech
  python scripts/verify_extract_corpus.py --dataset librispeech

  if [[ ! -d data/raw/VCTK-Corpus-0.92 ]]; then
    bash scripts/resume_vctk_download.sh
  fi
  python scripts/verify_extract_corpus.py --dataset vctk

  for dataset in librispeech vctk; do
    if [[ ! -f "data/splits/$dataset/preparation.json" ]]; then
      python scripts/prepare_data.py --dataset "$dataset" --seed 42 --microphone mic2
    fi
    python scripts/audit_experiment_data.py \
      --splits_dir "data/splits/$dataset" \
      --wav_root "data/processed/$dataset/wav16k" \
      --output "artifacts/audit/${dataset}_data_audit_restored.json"
  done

  python scripts/build_session_pool_v3.py --dataset vctk --seed 42 \
    --isolate_dataset --disjoint_source_utterances
  python scripts/download_models.py --speaker_encoder speechbrain_ecapa \
    --speaker_savedir checkpoints/speaker_encoders/speechbrain_ecapa --device cuda
  python scripts/download_models.py --speaker_encoder speechbrain_xvector \
    --speaker_savedir checkpoints/speaker_encoders/speechbrain_xvector --device cuda
fi

if (( with_xtts )); then
  bash scripts/setup_xtts.sh
  COQUI_TOS_AGREED=1 bash scripts/run_xtts_model_download.sh
fi

python -m unittest discover -s tests -v
echo "RESTORE_COMPLETE repo=$repo_root data=$with_data xtts=$with_xtts"
