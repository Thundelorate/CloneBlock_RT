# Server shutdown snapshot: 2026-09-19

The experiment branch preserves code, configurations, tests, paper tables,
audit records, environment locks, and all nine trained defense checkpoints.
Raw corpora, public model caches, Python virtual environments, and generated
XTTS WAV files are deliberately excluded from Git.

## Fresh AutoDL server

```bash
git clone --branch experiments/icassp-supplement \
  https://github.com/Thundelorate/CloneBlock_RT.git
cd CloneBlock_RT
bash scripts/restore_autodl_workspace.sh --with-data --with-xtts
```

Omit `--with-xtts` when only the main defense experiments are needed. Use
`--verify-only` to verify all frozen tables and checkpoints without installing
anything. The restore command is idempotent for downloaded/prepared data and
does not retrain or overwrite a defense checkpoint.

## What Git protects

- Source, configurations, tests, deployment helpers and manuscript workspace.
- `artifacts/tables`, `artifacts/audit`, logs and resolved environment records.
- Nine files under `checkpoints/defense`, verified by SHA-256.
- VCTK and LibriSpeech release URLs, archive sizes and checksums.

## Local offline backup

The shutdown-time server archive is intentionally ignored by Git:

```text
.server-backups/cloneblock_server_snapshot_20260919.tar.gz
SHA-256: a09005ecf71ae7088d2e71c14ad1018f9296a7ecd684fc00bd5f6751b53fe737
```

It contains the versionable project, checkpoints, logs, and the generated XTTS
reference/synthesis WAV files. It excludes the 25 GB raw/processed corpus and
the 11 GB of recreatable virtual environments. Preserve this archive on the
workstation or another private storage location; do not publish it without
reviewing the VCTK and XTTS licenses.
