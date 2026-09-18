#!/usr/bin/env bash
# Frozen pre-channel selection ablation and clean-information oracle ASV evaluation.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export PYTHONUNBUFFERED=1

run_id=vctk_selection_ablation_20260919
status="artifacts/logs/${run_id}.status"
log="artifacts/logs/${run_id}.log"
freeze="artifacts/audit/${run_id}_freeze.txt"
mkdir -p artifacts/logs artifacts/audit artifacts/tables
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

reference=checkpoints/defense/reference_vctk_v0p2_seed42_20260918_best.pt
selected=checkpoints/defense/realistic_vctk_selected_seed42_20260918_best.pt
pool=data/splits/vctk/session_pool_v3_test.csv
ecapa=checkpoints/speaker_encoders/speechbrain_ecapa
xvector=checkpoints/speaker_encoders/speechbrain_xvector
methods=(no_defense reference_v0p2 realistic_selected)
checkpoints=("" "$reference" "$selected")
encoder_names=(speechbrain_ecapa speechbrain_xvector)
encoder_tags=(ecapa xvector)
method_specs="no_defense:,reference_v0p2:$reference,realistic_selected:$selected"

for required in "$reference" "$selected" "$pool" "$ecapa" "$xvector"; do
  [[ -e "$required" ]] || { echo "Missing required input: $required" >&2; false; }
done

exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
printf 'FREEZING_INPUTS %s\n' "$(date -Is)" > "$status"
{
  echo "protocol=pre_channel_ablation_plus_oracle_asv"
  echo "created=$(date -Is)"
  echo "dataset=vctk"
  echo "split=test"
  echo "seed=42"
  echo "K=16"
  echo "codec=none"
  echo "main_protocol=tele_defended_results_from_vctk_final_test_20260919"
  sha256sum "$reference" "$selected" "$pool" scripts/run_session_pool_eval.py \
    scripts/run_asv_eer_eval.py scripts/bootstrap_session_ci.py
} > "$freeze"

printf 'DEFENDED_SESSION_EVAL %s\n' "$(date -Is)" > "$status"
for ei in "${!encoder_names[@]}"; do
  encoder="${encoder_names[$ei]}"
  encoder_tag="${encoder_tags[$ei]}"
  tag="vctk_ablation_${encoder_tag}_defended_20260919"
  for mi in "${!methods[@]}"; do
    method="${methods[$mi]}"
    checkpoint="${checkpoints[$mi]}"
    checkpoint_args=()
    [[ -z "$checkpoint" ]] || checkpoint_args=(--defense_checkpoint "$checkpoint")
    python scripts/run_session_pool_eval.py \
      --dataset vctk --session_pool_csv "$pool" --method_name "$method" \
      --group_key session_id \
      --strategies random_K,bestK_by_self_consistency,bestK_by_clean_consistency \
      --targeted_selection_source defended \
      --speaker_encoder_name "$encoder" \
      --speaker_checkpoint_dir "$ecapa" \
      --speaker_checkpoint_dir_xvector "$xvector" \
      --telephony_codec none --sanity_n_sessions 0 --seed 42 --output_tag "$tag" \
      "${checkpoint_args[@]}"
  done
  python scripts/bootstrap_session_ci.py \
    --runs \
      "artifacts/tables/session_attack_eval_no_defense_${tag}.json" \
      "artifacts/tables/session_attack_eval_reference_v0p2_${tag}.json" \
      "artifacts/tables/session_attack_eval_realistic_selected_${tag}.json" \
    --reference_method no_defense --draws 2000 --seed 42 \
    --output "artifacts/tables/bootstrap_ci_${tag}.csv"
done

printf 'DEFENDED_ASV %s\n' "$(date -Is)" > "$status"
for ei in "${!encoder_names[@]}"; do
  encoder="${encoder_names[$ei]}"
  encoder_tag="${encoder_tags[$ei]}"
  tag="vctk_ablation_${encoder_tag}_defended_20260919"
  python scripts/run_asv_eer_eval.py \
    --dataset vctk --session_pool_csv "$pool" --method_specs "$method_specs" \
    --speaker_encoder_name "$encoder" \
    --speaker_checkpoint_dir "$ecapa" --speaker_checkpoint_dir_xvector "$xvector" \
    --selection_strategy self_consistency --selection_source defended \
    --telephony_codec none --k 16 --impostors_per_target 10 --seed 42 \
    --output_csv "artifacts/tables/${tag}_eer.csv" \
    --output_margin_csv "artifacts/tables/${tag}_margin.csv" \
    --output_trials_csv "artifacts/tables/${tag}_trials.csv"
done

printf 'ORACLE_ASV %s\n' "$(date -Is)" > "$status"
for ei in "${!encoder_names[@]}"; do
  encoder="${encoder_names[$ei]}"
  encoder_tag="${encoder_tags[$ei]}"
  tag="vctk_oracle_${encoder_tag}_none_20260919"
  python scripts/run_asv_eer_eval.py \
    --dataset vctk --session_pool_csv "$pool" --method_specs "$method_specs" \
    --speaker_encoder_name "$encoder" \
    --speaker_checkpoint_dir "$ecapa" --speaker_checkpoint_dir_xvector "$xvector" \
    --selection_strategy oracle_clean --selection_source clean \
    --telephony_codec none --k 16 --impostors_per_target 10 --seed 42 \
    --output_csv "artifacts/tables/${tag}_eer.csv" \
    --output_margin_csv "artifacts/tables/${tag}_margin.csv" \
    --output_trials_csv "artifacts/tables/${tag}_trials.csv"
done

printf 'SELECTION_ABLATION_COMPLETE %s\n' "$(date -Is)" > "$status"
echo "Pre-channel selection ablation and oracle ASV complete."
