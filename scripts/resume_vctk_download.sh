#!/usr/bin/env bash
# Resumable official VCTK 0.92 download; completion includes MD5 verification.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw artifacts/logs
exec aria2c \
  --continue=true \
  --max-connection-per-server=4 \
  --split=4 \
  --min-split-size=16M \
  --file-allocation=none \
  --auto-file-renaming=false \
  --allow-overwrite=false \
  --max-tries=0 \
  --retry-wait=10 \
  --connect-timeout=30 \
  --timeout=120 \
  --lowest-speed-limit=0 \
  --summary-interval=30 \
  --console-log-level=warn \
  --checksum=md5=8a6ba2946b36fcbef0212cad601f4bfa \
  --dir=data/raw \
  --out=VCTK-Corpus-0.92.zip.part \
  https://datashare.ed.ac.uk/server/api/core/bitstreams/535f4286-e54c-4038-838c-a02285e32cb2/content
