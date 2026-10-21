# Server Recovery and Experiment Results

## What belongs in Git

- Source code, configuration, tests and protocol documents.
- Defense checkpoints already tracked by the repository.
- Final summary tables, figures, audit reports and experiment manifests.
- `artifacts/bundles/aggregation_advantage_results.tar.gz` and its SHA-256
  sidecar, provided the bundle remains below 95 MiB.

The VCTK corpus, processed waveform cache, SpeechBrain model cache, Python
environment and temporary embedding caches do not belong in Git.

## Restore a new server

1. Clone the experiment branch and checkout the protected experiment commit.
2. Run `scripts/setup_server_runtime.sh` on an AutoDL Linux GPU instance.
3. Download the official VCTK 0.92 archive and verify MD5
   `8a6ba2946b36fcbef0212cad601f4bfa`.
4. Run `scripts/run_vctk_restore_pipeline.sh` to rebuild the seed-42 split and
   session pools.
5. Start `scripts/run_aggregation_advantage_pipeline.sh` only if the experiment
   needs to be recomputed.

When Edinburgh DataShare is slow, run `scripts/probe_vctk_sources.sh` before
changing the active downloader. Zenodo record `10691876` advertises the same
archive MD5 and can be used only after the downloaded payload passes the normal
size, MD5 and SHA-256 checks. Kaggle and Parquet repositories are repackaged
representations; do not substitute them until their extracted FLAC and
transcript content has passed a separate audit.

To restore saved result artifacts without recomputing them:

```bash
.venv-main/bin/python scripts/verify_aggregation_bundle.py \
  --bundle artifacts/bundles/aggregation_advantage_results.tar.gz \
  --restore_to .
```

The verifier checks the bundle sidecar, rejects unsafe archive entries, checks
every file against the internal recovery manifest and does not overwrite a
different existing file unless `--overwrite` is explicitly supplied.

## Before shutting down AutoDL

The final shutdown gate is all of the following:

1. `artifacts/logs/aggregation_advantage.status` contains `0`.
2. `artifacts/audit/aggregation_asv_test_audit.json` contains `"ok": true`.
3. The result bundle passes `scripts/verify_aggregation_bundle.py`.
4. The bundle and paper-facing artifacts have been copied to the local clone.
5. The code and protected result artifacts have been committed and pushed.
