# AutoDL deployment: 2026-09-18

## Connection and workspace

- SSH alias on the Windows workstation: `autodl4090`.
- Server project: `/root/autodl-tmp/projects/CloneBlock_RT`.
- Server branch: `experiments/icassp-supplement`.
- Base commit: `d81b461`.
- Current local, uncommitted research changes were transferred as a source snapshot.
  This deployment did not commit or push changes to GitHub.
- The initial source archive SHA-256 is
  `a0c2ec42db5c9e61b992d6b0f21b6c38222dc77435f67cd0e7321ccf732c073e`.
  Deployment helpers added afterwards are present on both machines.

## Environment

- NVIDIA RTX 4090, 24564 MiB; driver 580.105.08.
- Python 3.10.8; dedicated `.venv-main` on the 150 GB data disk.
- PyTorch and TorchAudio 2.5.1+cu121; SpeechBrain 1.0.3.
- System dependencies installed: FFmpeg, libsndfile1, tmux, aria2.
- Base Conda environment remains separate.
- The image's default Aliyun pip mirror was slow; installation completed using
  `https://pypi.org/simple`. The PyTorch wheels use the official cu121 index.
- XTTS is not installed in this environment; use a separate environment later.

In a server terminal:

```bash
cd /root/autodl-tmp/projects/CloneBlock_RT
source scripts/activate_autodl.sh
```

This activates the environment and places Hugging Face, Torch, pip, and temporary
files on the data disk. In VS Code Remote SSH, select this Python interpreter:

```text
/root/autodl-tmp/projects/CloneBlock_RT/.venv-main/bin/python
```

## Verification

- Dependency consistency: `pip check` passed.
- Environment preflight: imports, CUDA backward, and FFmpeg encoders passed.
- Existing unit tests: 16 passed.
- Synthetic defense GPU forward/backward and optimizer update passed.
- Opus and G.711 each completed two FFmpeg operations (encode and decode).
  The check rejects silent codec fallback.
- These checks use synthetic inputs and do not establish speech quality,
  cloning resistance, strict streaming causality, or a realistic training objective.

Reports live in server `artifacts/env/`; a copy is saved locally in
`artifacts/env/autodl4090/`. The resolved version list is
`requirements-resolved-20260918.txt`.

## Real-audio runs (2026-09-18)

- Public SpeechBrain ECAPA model downloaded and successfully used on the GPU.
- LibriSpeech dev-clean downloaded from OpenSLR and verified against the official
  archive MD5. Archive SHA-256 is recorded in `artifacts/audit/librispeech_archive.json`.
- Seed-42 speaker-disjoint preparation: 32/4/4 train/validation/test speakers;
  2783/344/353 crops. The provenance and split-leakage audit passed.
- `pilot_librispeech_seed42_20260918`: 50 steps, 16.87 seconds, peak 6219.83 MiB.
- `reference_librispeech_v0p2_seed42_20260918`: 1000 steps, 287.64 seconds,
  peak 6764.99 MiB, best validation similarity 0.952837 at step 1000.
- These use the existing `train_v0p2_p2_2.yaml` loss family, not the planned new
  realistic aggregation objective. They are new reference runs, not a replication
  of the paper's unavailable original checkpoint.
- Validation-only session evaluation completed: 4 speakers, 12 constructed
  sessions. No test-set model selection or test metrics were performed.
- Self-consistency selection using only `tele_defended` observations:
  no-defense K16 0.986170 / AUCK 0.886022; reference-defense K16 0.948159 /
  AUCK 0.852649. These are same-session recovery similarities, not clone success
  rates or independent enrollment verification. The small validation sample does
  not support a paper-level effectiveness claim.
- Paired speaker-cluster bootstrap (2000 draws) completed; intervals with only
  four speakers are exploratory. Results: `artifacts/tables/libri_val_pilot_20260918_ci.csv`.
- Unit tests: 26 passed, including archive integrity, path traversal rejection,
  numeric training checks, and dataset-isolated session output.

Later validation-pipeline checks increased this to 30 passing tests. SpeechBrain
x-vector was cached and GPU-validated (512-dimensional embeddings). A 20-step
LibriSpeech smoke run of the corrected realistic objective completed in 10.56 s,
used 6117.21 MiB peak GPU memory, and produced a finite validation K16 proxy and
checkpoint. Its 10-utterance perturbation/STOI check is an engineering smoke test,
not a result for the paper.

The session builder now supports `--isolate_dataset`; use it to avoid overwriting
another dataset's session manifests. The validation pilot overrides the original
author's absolute ECAPA cache path with the deployed model path.

## Background VCTK pipeline

The old VCTK download URL now returns HTML. The official archive is being fetched
through the Edinburgh DataShare bitstream API using resumable aria2 downloads.
The complete archive must match both official MD5 and the SHA-256 published in
TorchAudio before extraction. Download speed remains the bottleneck.

- tmux `vctk-download`: download, then aria2 checksum verification.
- tmux `vctk-pilot`: wait for download to finish; independently verify the archive;
  extract; prepare VCTK mic2 data; audit; run 50-step pilot and check finite losses
  and weights; run 1000-step existing-objective reference and check its outputs.
- Status: `artifacts/logs/pilot_vctk_seed42_20260918.status`.
- tmux `vctk-next-stage`: wait for the reference pipeline, build and audit
  source-utterance-disjoint sessions, evaluate realistic and oracle protocols on
  validation, train alpha 0.12/0.18/0.24 sweeps, measure perturbation budget and
  tele-clean-vs-tele-defended STOI, choose under an explicit validation-only STOI
  floor of 0.95, train the selected 1000-step realistic model, then run ECAPA and
  x-vector independent-session validation EER/margin trials.
- The corrected `selfconsistency_hard16_margin` objective selects windows only from
  attacker-visible observed embeddings. Clean embeddings supervise the loss but do
  not determine the selected indices. The legacy clean-reference branch remains an
  explicitly labeled oracle reference.
- Next-stage status: `artifacts/logs/vctk_next_stage_20260918.status`.
- Pipeline log: `artifacts/logs/pilot_vctk_seed42_20260918_pipeline.log`.
- Download log: `artifacts/logs/download-vctk-aria2.log`.
- Failed checks stop the pipeline. Existing checkpoints are never overwritten.
- These tmux jobs survive the workstation terminal closing. They do not survive
  stopping or releasing the rented instance; keep the instance running for now.
- No automatic server shutdown, publication, commit, or GitHub push is configured.
- Once the bounded jobs finish, no unbounded training is started automatically.
- The test split remains sealed throughout this automatic next stage.

Small audit and metric outputs are copied to local `artifacts/runs/autodl4090-20260918/`;
LibriSpeech defense checkpoints are backed up under local `checkpoints/autodl4090/`.

## Next research stage

Complete VCTK verification and reference runs, then implement and test the realistic
training objective against that reference. The review matrix still contains open
work on independent ASV enrollment, full-utterance quality evaluation, cross-encoder
and codec experiments, multiple training seeds, and XTTS. The old five-day schedule
is historical; this deployment is not a completed paper experiment.
