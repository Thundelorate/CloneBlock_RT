#!/usr/bin/env bash
# Restore only the frozen validation/test speakers while the official archive continues.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIRROR_ROOT="${MIRROR_ROOT:-/root/autodl-tmp/vctk-github-mirror}"
SOURCE_REPO="${SOURCE_REPO:-https://github.com/milletyann/VCTK-Corpus-0.92.git}"
EXPECTED_COMMIT="${EXPECTED_COMMIT:-4af5c66fddca9cde5ec24e5359929e5a7e7c953f}"
CORPUS_ROOT="$MIRROR_ROOT/VCTK-Corpus-0.92"
LINK_PATH="$REPO_ROOT/data/raw/VCTK-Corpus-0.92-github-subset"
LOG="$REPO_ROOT/artifacts/logs/vctk_subset_git.log"
STATUS="$REPO_ROOT/artifacts/logs/vctk_subset_git.status"

VAL_SPEAKERS=(p229 p237 p254 p256 p282 p295 p301 p307 p343 p351 p374)
TEST_SPEAKERS=(p228 p239 p240 p244 p255 p258 p262 p314 p326 p340 p364)
SPEAKERS=("${VAL_SPEAKERS[@]}" "${TEST_SPEAKERS[@]}")

mkdir -p "$REPO_ROOT/artifacts/logs" "$REPO_ROOT/artifacts/audit" "$REPO_ROOT/data/raw"
exec > >(tee -a "$LOG") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$STATUS"; exit "$rc"' EXIT

source /etc/network_turbo >/dev/null 2>&1 || true
if [[ ! -d "$MIRROR_ROOT/.git" ]]; then
  git clone --depth 1 --filter=blob:none --sparse --no-checkout "$SOURCE_REPO" "$MIRROR_ROOT"
fi

actual_commit="$(git -C "$MIRROR_ROOT" rev-parse HEAD)"
if [[ "$actual_commit" != "$EXPECTED_COMMIT" ]]; then
  echo "Unexpected mirror commit: $actual_commit" >&2
  exit 1
fi

patterns=("VCTK-Corpus-0.92/speaker-info.txt")
for speaker in "${SPEAKERS[@]}"; do
  patterns+=("VCTK-Corpus-0.92/txt/$speaker")
  patterns+=("VCTK-Corpus-0.92/wav48_silence_trimmed/$speaker")
done
git -C "$MIRROR_ROOT" sparse-checkout set --no-cone "${patterns[@]}"
git -C "$MIRROR_ROOT" checkout

manifest="$REPO_ROOT/artifacts/audit/vctk_aggregation_subset_source.tsv"
printf "speaker\tmic2_files\ttranscripts\tbytes\n" > "$manifest"
for speaker in "${SPEAKERS[@]}"; do
  audio_dir="$CORPUS_ROOT/wav48_silence_trimmed/$speaker"
  text_dir="$CORPUS_ROOT/txt/$speaker"
  audio_count="$(find "$audio_dir" -maxdepth 1 -type f -name '*_mic2.flac' | wc -l)"
  text_count="$(find "$text_dir" -maxdepth 1 -type f -name '*.txt' | wc -l)"
  if (( audio_count < 300 || text_count < 300 )); then
    echo "Incomplete speaker $speaker: mic2=$audio_count transcripts=$text_count" >&2
    exit 1
  fi
  bytes="$(du -sb "$audio_dir" "$text_dir" | awk '{sum += $1} END {print sum}')"
  printf "%s\t%s\t%s\t%s\n" "$speaker" "$audio_count" "$text_count" "$bytes" >> "$manifest"
done

if [[ -e "$LINK_PATH" && ! -L "$LINK_PATH" ]]; then
  echo "Refusing to replace non-symlink path: $LINK_PATH" >&2
  exit 1
fi
ln -sfn "$CORPUS_ROOT" "$LINK_PATH"
printf "commit\t%s\nsource\t%s\n" "$actual_commit" "$SOURCE_REPO" >> "$manifest"
echo "VCTK aggregation subset ready at $LINK_PATH"

