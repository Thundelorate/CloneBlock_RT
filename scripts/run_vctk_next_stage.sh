#!/usr/bin/env bash
# Validation-only continuation after the bounded VCTK reference pipeline.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/activate_autodl.sh
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONUNBUFFERED=1
mkdir -p artifacts/logs artifacts/audit artifacts/tables
status=artifacts/logs/vctk_next_stage_20260918.status
exec > >(tee -a artifacts/logs/vctk_next_stage_20260918.log) 2>&1
trap 'code=$?; printf "FAILED exit=%s time=%s\n" "$code" "$(date -Is)" > "$status"; exit "$code"' ERR

printf 'WAITING_REFERENCE %s\n' "$(date -Is)" > "$status"
while true; do
  reference_status="$(cat artifacts/logs/pilot_vctk_seed42_20260918.status 2>/dev/null || true)"
  [[ "$reference_status" == REFERENCE_COMPLETE* ]] && break
  [[ "$reference_status" == FAILED* ]] && { echo "VCTK reference pipeline failed: $reference_status"; false; }
  sleep 15
done

reference=checkpoints/defense/reference_vctk_v0p2_seed42_20260918_best.pt
python scripts/check_training_run.py --run_name reference_vctk_v0p2_seed42_20260918 --steps 1000
printf 'BUILDING_SESSIONS %s\n' "$(date -Is)" > "$status"
python scripts/build_session_pool_v3.py --dataset vctk --seed 42 --isolate_dataset \
  --disjoint_source_utterances
for split in train val test; do
  python scripts/audit_session_pool.py \
    --session_pool_csv "data/splits/vctk/session_pool_v3_${split}.csv" \
    --output "artifacts/audit/vctk_session_pool_${split}_20260918.json"
done

exec 9>/root/autodl-tmp/cloneblock-training.lock
flock 9
common_eval=(--dataset vctk --session_pool_csv data/splits/vctk/session_pool_v3_val.csv
             --speaker_checkpoint_dir checkpoints/speaker_encoders/speechbrain_ecapa
             --strategies random_K,bestK_by_self_consistency,bestK_by_clean_consistency
             --targeted_selection_source tele_defended --sanity_n_sessions 0 --seed 42)

printf 'EVALUATING_REFERENCE %s\n' "$(date -Is)" > "$status"
python scripts/run_session_pool_eval.py "${common_eval[@]}" --method_name no_defense \
  --output_tag vctk_val_20260918
python scripts/run_session_pool_eval.py "${common_eval[@]}" --method_name reference_v0p2 \
  --defense_checkpoint "$reference" --output_tag vctk_val_20260918

printf 'TRAINING_SWEEP %s\n' "$(date -Is)" > "$status"
sweep_security=()
budget_specs=()
for alpha in 0.12 0.18 0.24; do
  alpha_tag="${alpha/./p}"
  run_name="realistic_a${alpha_tag}"
  checkpoint="checkpoints/defense/${run_name}_best.pt"
  [[ ! -e "$checkpoint" ]] || { echo "Refusing to overwrite $checkpoint"; false; }
  python scripts/run_train.py --config configs/train_realistic_sweep.yaml --dataset vctk \
    --run_name "$run_name" --max_steps 300 --alpha "$alpha" \
    --init_checkpoint "$reference" --train_objective selfconsistency_hard16_margin \
    --session_pool_train_csv data/splits/vctk/session_pool_v3_train.csv \
    --val_session_pool_csv data/splits/vctk/session_pool_v3_val.csv \
    --att_selection_source tele_defended --val_proxy_selection_source tele_defended \
    --best_metric val_k16_proxy --att_candidate_windows 48 --att_tau 0.85 \
    --att_margin_mode hinge
  python scripts/check_training_run.py --run_name "$run_name" --steps 300
  python scripts/run_session_pool_eval.py "${common_eval[@]}" --method_name "$run_name" \
    --defense_checkpoint "$checkpoint" --output_tag vctk_val_sweep_20260918
  sweep_security+=("artifacts/tables/session_attack_summary_abs_${run_name}_vctk_val_sweep_20260918.csv")
  budget_specs+=("${run_name}:${checkpoint}")
done

method_specs="$(IFS=,; printf '%s' "${budget_specs[*]}")"
python scripts/eval_perturbation_budget.py --dataset vctk --split val --max_utts 100 \
  --method_specs "$method_specs" --output_prefix artifacts/tables/vctk_val_sweep_budget_20260918
python scripts/select_realistic_sweep.py --security_csv "${sweep_security[@]}" \
  --budget_csv artifacts/tables/vctk_val_sweep_budget_20260918_summary.csv \
  --checkpoint_dir checkpoints/defense --stoi_floor 0.95 \
  --output artifacts/audit/vctk_realistic_sweep_selection_20260918.json

read -r selected_alpha selected_checkpoint < artifacts/audit/vctk_realistic_sweep_selection_20260918.txt
full_name=realistic_vctk_selected_seed42_20260918
[[ ! -e "checkpoints/defense/${full_name}_best.pt" ]] || { echo "Refusing to overwrite full run"; false; }
printf 'TRAINING_SELECTED alpha=%s time=%s\n' "$selected_alpha" "$(date -Is)" > "$status"
python scripts/run_train.py --config configs/train_realistic_full.yaml --dataset vctk \
  --run_name "$full_name" --max_steps 1000 --alpha "$selected_alpha" \
  --init_checkpoint "$reference" --train_objective selfconsistency_hard16_margin \
  --session_pool_train_csv data/splits/vctk/session_pool_v3_train.csv \
  --val_session_pool_csv data/splits/vctk/session_pool_v3_val.csv \
  --att_selection_source tele_defended --val_proxy_selection_source tele_defended \
  --best_metric val_k16_proxy --att_candidate_windows 48 --att_tau 0.85 \
  --att_margin_mode hinge
python scripts/check_training_run.py --run_name "$full_name" --steps 1000
python scripts/run_session_pool_eval.py "${common_eval[@]}" --method_name realistic_selected \
  --defense_checkpoint "checkpoints/defense/${full_name}_best.pt" --output_tag vctk_val_20260918
method_specs="no_defense:,reference_v0p2:${reference},realistic_selected:checkpoints/defense/${full_name}_best.pt"
for encoder in speechbrain_ecapa speechbrain_xvector; do
  encoder_args=(--speaker_encoder_name "$encoder"
                --speaker_checkpoint_dir checkpoints/speaker_encoders/speechbrain_ecapa
                --speaker_checkpoint_dir_xvector checkpoints/speaker_encoders/speechbrain_xvector)
  python scripts/run_asv_eer_eval.py --dataset vctk \
    --session_pool_csv data/splits/vctk/session_pool_v3_val.csv \
    --method_specs "$method_specs" "${encoder_args[@]}" \
    --selection_strategy self_consistency --selection_source tele_defended --k 16 --seed 42 \
    --output_csv "artifacts/tables/vctk_val_${encoder}_eer_20260918.csv" \
    --output_margin_csv "artifacts/tables/vctk_val_${encoder}_margin_20260918.csv" \
    --output_trials_csv "artifacts/tables/vctk_val_${encoder}_trials_20260918.csv"
done
printf 'VALIDATION_STAGE_COMPLETE %s\n' "$(date -Is)" > "$status"
