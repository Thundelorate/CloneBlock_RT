#!/usr/bin/env bash
# Append a compact server/download/pipeline snapshot every two hours.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-7200}"
LOG="$REPO_ROOT/artifacts/logs/server_progress_2h.log"
mkdir -p "$(dirname "$LOG")"

snapshot() {
  {
    echo "===== $(date --iso-8601=seconds) ====="
    echo "host=$(hostname)"
    echo "tmux_sessions:"
    tmux ls 2>&1 || true
    echo "active_processes:"
    pgrep -af 'aria2c|setup_server_runtime|run_vctk_restore_pipeline|prepare_data.py|build_session_pool|run_aggregation' || true
    echo "status_files:"
    for status in \
      artifacts/logs/server_runtime.status \
      artifacts/logs/vctk_download_new.status \
      artifacts/logs/vctk_restore_pipeline.status \
      artifacts/logs/aggregation_advantage.status; do
      if [[ -f "$REPO_ROOT/$status" ]]; then
        printf '%s=' "$status"
        cat "$REPO_ROOT/$status"
      else
        echo "$status=pending"
      fi
    done
    echo "vctk_files:"
    ls -lh "$REPO_ROOT"/data/raw/VCTK-Corpus-0.92.zip* 2>/dev/null || true
    du -h "$REPO_ROOT"/data/raw/VCTK-Corpus-0.92.zip* 2>/dev/null || true
    echo "latest_download_progress:"
    grep -E 'DL:|Download complete' "$REPO_ROOT/artifacts/logs/vctk_download_new.log" 2>/dev/null | tail -1 || true
    echo "latest_experiment_progress:"
    grep '\[aggregation-asv\]' "$REPO_ROOT/artifacts/logs/aggregation_advantage.log" 2>/dev/null | tail -1 || true
    echo "gpu:"
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu \
      --format=csv,noheader 2>/dev/null || true
    echo "disk:"
    df -h /root/autodl-tmp 2>/dev/null || true
    echo
  } >> "$LOG"
}

while true; do
  snapshot
  sleep "$INTERVAL_SECONDS"
done
