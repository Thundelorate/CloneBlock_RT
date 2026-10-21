#!/usr/bin/env bash
# End-to-end aggregation advantage experiment after VCTK restoration.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_ROOT/.venv-main/bin/python"
LOG="$REPO_ROOT/artifacts/logs/aggregation_advantage.log"
STATUS="$REPO_ROOT/artifacts/logs/aggregation_advantage.status"
OUTPUT="$REPO_ROOT/artifacts/experiments/aggregation_advantage"
TABLES="$REPO_ROOT/artifacts/tables/paper_icassp"
FIGURES="$REPO_ROOT/artifacts/figures"

REFERENCE_CHECKPOINT="${REFERENCE_CHECKPOINT:-$REPO_ROOT/checkpoints/defense/reference_vctk_v0p2_seed42_20260918_best.pt}"
REALISTIC_CHECKPOINT="${REALISTIC_CHECKPOINT:-$REPO_ROOT/checkpoints/defense/realistic_vctk_selected_seed42_20260918_best.pt}"
VAL_POOL="${VAL_POOL:-$REPO_ROOT/data/splits/vctk/session_pool_v3_val.csv}"
TEST_POOL="${TEST_POOL:-$REPO_ROOT/data/splits/vctk/session_pool_v3_test.csv}"
DATA_READY_STATUS="${DATA_READY_STATUS:-$REPO_ROOT/artifacts/logs/vctk_restore_pipeline.status}"

mkdir -p "$REPO_ROOT/artifacts/logs" "$OUTPUT" "$TABLES" "$FIGURES"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

wait_for_success() {
  local file="$1"
  local label="$2"
  while [[ ! -f "$file" ]]; do
    echo "[$(date --iso-8601=seconds)] waiting for $label"
    sleep 60
  done
  if [[ "$(tr -d '[:space:]' < "$file")" != "0" ]]; then
    echo "$label failed; see its log" >&2
    return 1
  fi
}

cd "$REPO_ROOT"
export HF_HOME="${HF_HOME:-/root/autodl-tmp/cache/huggingface}"
export TORCH_HOME="${TORCH_HOME:-/root/autodl-tmp/cache/torch}"
export TMPDIR="${TMPDIR:-/root/autodl-tmp/tmp}"

wait_for_success artifacts/logs/server_runtime.status "server runtime"
wait_for_success "$DATA_READY_STATUS" "VCTK data/session-pool restore"

# Fail before model downloads or GPU work if the protocol/analysis contract is broken.
"$PY" -B -m unittest discover -s tests -v

if [[ ! -f "$REFERENCE_CHECKPOINT" || ! -f "$REALISTIC_CHECKPOINT" ]]; then
  echo "Required defense checkpoint is missing" >&2
  exit 1
fi
if [[ ! -f "$VAL_POOL" || ! -f "$TEST_POOL" ]]; then
  echo "Validation or test session pool is missing" >&2
  exit 1
fi

# This is idempotent; already cached SpeechBrain files are reused.
bash scripts/prefetch_aggregation_models.sh

COMMON=(
  --checkpoint "reference=$REFERENCE_CHECKPOINT"
  --checkpoint "realistic=$REALISTIC_CHECKPOINT"
  --random_repeats 100
  --bootstrap_draws 2000
  --seed 42
  --device cuda
)

"$PY" -B scripts/run_aggregation_advantage_asv.py \
  --session_pool "$VAL_POOL" \
  --split validation \
  --output_dir "$OUTPUT" \
  "${COMMON[@]}"

"$PY" -B scripts/run_aggregation_advantage_asv.py \
  --session_pool "$TEST_POOL" \
  --split test \
  --thresholds "$OUTPUT/aggregation_asv_validation_thresholds.json" \
  --output_dir "$OUTPUT" \
  "${COMMON[@]}"

"$PY" -B scripts/analyze_aggregation_asv.py \
  --aggregates "$OUTPUT/aggregation_asv_test_aggregates.csv" \
  --trials "$OUTPUT/aggregation_asv_test_trials.csv" \
  --summary "$TABLES/aggregation_asv_summary.csv" \
  --contrasts "$TABLES/aggregation_asv_contrasts.csv" \
  --figure "$FIGURES/aggregation_asv_curves.png" \
  --draws 2000 \
  --seed 42

"$PY" -B scripts/export_aggregation_latex.py \
  --summary "$TABLES/aggregation_asv_summary.csv" \
  --contrasts "$TABLES/aggregation_asv_contrasts.csv" \
  --output_dir "$TABLES"

"$PY" -B scripts/summarize_aggregation_claim.py \
  --contrasts "$TABLES/aggregation_asv_contrasts.csv" \
  --output "$TABLES/aggregation_claim_decision.json"

"$PY" -B scripts/audit_aggregation_experiment.py \
  --manifest "$OUTPUT/aggregation_asv_test_manifest.json" \
  --rows "$OUTPUT/aggregation_asv_test_aggregates.csv" \
  --trials "$OUTPUT/aggregation_asv_test_trials.csv" \
  --output "$REPO_ROOT/artifacts/audit/aggregation_asv_test_audit.json"

"$PY" -B scripts/package_aggregation_results.py \
  --repo "$REPO_ROOT" \
  --output "$REPO_ROOT/artifacts/bundles/aggregation_advantage_results.tar.gz" \
  --max_mib 95

"$PY" -B scripts/verify_aggregation_bundle.py \
  --bundle "$REPO_ROOT/artifacts/bundles/aggregation_advantage_results.tar.gz"

echo "Aggregation advantage experiment, analysis, audit and recovery bundle completed."
