#!/usr/bin/env bash
# Frozen VCTK test evaluation after validation-only model selection.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export PYTHONUNBUFFERED=1

run_id=vctk_final_test_20260919
status="artifacts/logs/${run_id}.status"
log="artifacts/logs/${run_id}.log"
freeze="artifacts/audit/${run_id}_freeze.txt"
mkdir -p artifacts/logs artifacts/audit artifacts/tables artifacts/tables/quality
exec > >(tee -a "$log") 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

reference=checkpoints/defense/reference_vctk_v0p2_seed42_20260918_best.pt
selected=checkpoints/defense/realistic_vctk_selected_seed42_20260918_best.pt
selected_sweep=checkpoints/defense/realistic_a0p24_best.pt
pool=data/splits/vctk/session_pool_v3_test.csv
selection=artifacts/audit/vctk_realistic_sweep_selection_20260918.txt
ecapa=checkpoints/speaker_encoders/speechbrain_ecapa
xvector=checkpoints/speaker_encoders/speechbrain_xvector

[[ "$(cat artifacts/logs/vctk_next_stage_20260918.status)" == VALIDATION_STAGE_COMPLETE* ]]
read -r selected_alpha selected_sweep_from_file < "$selection"
[[ "$selected_alpha" == "0.24" ]]
[[ "$selected_sweep_from_file" == "$selected_sweep" ]]
for required in "$reference" "$selected" "$selected_sweep" "$pool" "$selection"                 configs/eval.yaml configs/telephony.yaml "$ecapa" "$xvector"; do
  [[ -e "$required" ]] || { echo "Missing required input: $required" >&2; false; }
done

# Prevent concurrent CloneBlock GPU jobs and freeze all test inputs before reading scores.
exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
printf 'FREEZING_INPUTS %s\n' "$(date -Is)" > "$status"
{
  echo "protocol=frozen_test_after_validation"
  echo "created=$(date -Is)"
  echo "dataset=vctk"
  echo "split=test"
  echo "seed=42"
  echo "selected_alpha=$selected_alpha"
  echo "selected_checkpoint=$selected"
  echo "selection_rule=minimum validation K16 then AUCK and alpha subject to STOI>=0.95"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_tracked_diff_sha256=$(git diff --no-ext-diff | sha256sum | cut -d' ' -f1)"
  sha256sum "$reference" "$selected" "$selected_sweep" "$pool" "$selection"             configs/eval.yaml configs/telephony.yaml             scripts/run_session_pool_eval.py scripts/run_asv_eer_eval.py             scripts/bootstrap_session_ci.py scripts/run_quality_eval.py
} > "$freeze"

python scripts/audit_session_pool.py   --session_pool_csv "$pool"   --output artifacts/audit/vctk_session_pool_test_final_20260919.json

methods=(no_defense reference_v0p2 realistic_selected)
checkpoints=("" "$reference" "$selected")
encoder_names=(speechbrain_ecapa speechbrain_xvector)
encoder_tags=(ecapa xvector)
codec_names=(none opus g711)
codec_tags=(none opus16k g711)

printf 'SESSION_EVAL %s\n' "$(date -Is)" > "$status"
for ei in "${!encoder_names[@]}"; do
  encoder="${encoder_names[$ei]}"
  encoder_tag="${encoder_tags[$ei]}"
  for ci in "${!codec_names[@]}"; do
    codec="${codec_names[$ci]}"
    codec_tag="${codec_tags[$ci]}"
    tag="vctk_test_${encoder_tag}_${codec_tag}_20260919"
    for mi in "${!methods[@]}"; do
      method="${methods[$mi]}"
      checkpoint="${checkpoints[$mi]}"
      checkpoint_args=()
      [[ -z "$checkpoint" ]] || checkpoint_args=(--defense_checkpoint "$checkpoint")
      python scripts/run_session_pool_eval.py         --dataset vctk --session_pool_csv "$pool" --method_name "$method"         --group_key session_id         --strategies random_K,bestK_by_self_consistency,bestK_by_clean_consistency         --targeted_selection_source tele_defended         --speaker_encoder_name "$encoder"         --speaker_checkpoint_dir "$ecapa"         --speaker_checkpoint_dir_xvector "$xvector"         --telephony_codec "$codec" --telephony_codec_bitrate 16k         --sanity_n_sessions 0 --seed 42 --output_tag "$tag"         "${checkpoint_args[@]}"
    done
    python scripts/bootstrap_session_ci.py       --runs         "artifacts/tables/session_attack_eval_no_defense_${tag}.json"         "artifacts/tables/session_attack_eval_reference_v0p2_${tag}.json"         "artifacts/tables/session_attack_eval_realistic_selected_${tag}.json"       --reference_method no_defense --draws 2000 --seed 42       --output "artifacts/tables/bootstrap_ci_${tag}.csv"
  done
done

printf 'EER_EVAL %s\n' "$(date -Is)" > "$status"
method_specs="no_defense:,reference_v0p2:$reference,realistic_selected:$selected"
for ei in "${!encoder_names[@]}"; do
  encoder="${encoder_names[$ei]}"
  encoder_tag="${encoder_tags[$ei]}"
  for ci in "${!codec_names[@]}"; do
    codec="${codec_names[$ci]}"
    codec_tag="${codec_tags[$ci]}"
    tag="vctk_test_${encoder_tag}_${codec_tag}_20260919"
    python scripts/run_asv_eer_eval.py       --dataset vctk --session_pool_csv "$pool" --method_specs "$method_specs"       --speaker_encoder_name "$encoder"       --speaker_checkpoint_dir "$ecapa"       --speaker_checkpoint_dir_xvector "$xvector"       --selection_strategy self_consistency --selection_source tele_defended       --telephony_codec "$codec" --telephony_codec_bitrate 16k       --k 16 --impostors_per_target 10 --seed 42       --output_csv "artifacts/tables/${tag}_eer.csv"       --output_margin_csv "artifacts/tables/${tag}_margin.csv"       --output_trials_csv "artifacts/tables/${tag}_trials.csv"
  done
done

printf 'PERTURBATION_BUDGET %s\n' "$(date -Is)" > "$status"
python scripts/eval_perturbation_budget.py   --dataset vctk --split test --max_utts 200   --method_specs "reference_v0p2:$reference,realistic_selected:$selected"   --output_prefix artifacts/tables/vctk_test_budget_20260919

printf 'QUALITY_EVAL %s\n' "$(date -Is)" > "$status"
for codec in none opus g711; do
  python scripts/run_quality_eval.py     --dataset vctk --split test --telephony_codec "$codec"     --telephony_codec_bitrate 16k --max_utts 200 --seed 42     --defense_checkpoint "$selected" --defense_name realistic_selected
done

printf 'LATENCY_EVAL %s\n' "$(date -Is)" > "$status"
python scripts/run_stream_benchmark.py   --dataset vctk --session_pool_csv "$pool"   --defense_checkpoint "$selected" --chunk_ms_list 20,40

printf 'FINAL_TEST_COMPLETE %s\n' "$(date -Is)" > "$status"
echo "Final frozen VCTK test evaluation complete."
