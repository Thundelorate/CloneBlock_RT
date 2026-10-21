#!/usr/bin/env bash
# Non-destructive range probes for VCTK 0.92 sources and representations.
set -u

RANGE_END="${RANGE_END:-8388607}"
MAX_TIME="${MAX_TIME:-20}"

probe() {
  local label="$1"
  local kind="$2"
  local url="$3"
  printf 'SOURCE\t%s\t%s\n' "$label" "$kind"
  curl --max-time "$MAX_TIME" --location --range "0-$RANGE_END" \
    --output /dev/null --silent --show-error \
    --write-out $'RESULT\tcode=%{http_code}\tbytes=%{size_download}\tspeed_Bps=%{speed_download}\ttime_s=%{time_total}\tfinal=%{url_effective}\n' \
    "$url" || true
}

probe \
  "edinburgh-api" \
  "exact-archive-md5-8a6ba2946b36fcbef0212cad601f4bfa" \
  "https://datashare.ed.ac.uk/server/api/core/bitstreams/535f4286-e54c-4038-838c-a02285e32cb2/content"

probe \
  "edinburgh-legacy" \
  "exact-archive-sha256-f96258be9fdc2cbff6559541aae7ea4f59df3fcaf5cf963aae5ca647357e359c" \
  "https://datashare.is.ed.ac.uk/bitstream/handle/10283/3443/VCTK-Corpus-0.92.zip"

probe \
  "zenodo-10691876" \
  "exact-archive-md5-8a6ba2946b36fcbef0212cad601f4bfa" \
  "https://zenodo.org/records/10691876/files/VCTK-Corpus-0.92.zip?download=1"

probe \
  "kaggle-kynthesis" \
  "vctk-0.92-repack-requires-content-audit" \
  "https://www.kaggle.com/api/v1/datasets/download/kynthesis/vctk-corpus"

probe \
  "hf-mirror-parquet" \
  "standard-vctk-parquet-requires-byte-audit" \
  "https://hf-mirror.com/datasets/sanchit-gandhi/vctk/resolve/main/data/train-00000-of-00027-ff24600f70f7ff75.parquet"

echo "Exact-archive sources may resume the official payload only after matching size and checksum."
echo "Repacked or Parquet sources require an audio/transcript content audit before use."
