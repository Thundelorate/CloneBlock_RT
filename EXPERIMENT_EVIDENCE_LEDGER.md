# ICASSP Experiment Evidence Ledger

Updated: 2026-09-19 (Asia/Shanghai)

This ledger separates verified evidence, manuscript-only work, and unresolved limitations. A code change is not marked verified unless a frozen run produced an auditable artifact.

## Protocol And Security

| Review ID | Status | Resolution | Evidence | Limitation |
|---|---|---|---|---|
| R1-01, R1-02, R4-02 | Verified experiment; wording pending | Main attacker selects from `tele_defended` observations using self-consistency. `defended` is a pre-channel ablation. Clean selection is an information-privileged oracle reference. | `artifacts/tables/paper_icassp/main_security_ecapa.csv`; `selection_source_ablation.csv` | The clean oracle is not a certified numerical upper bound. |
| R1-03 | Verified | AUCK is the equal-weight arithmetic mean over K={1,2,4,8,16}. | `main_security_ecapa.csv`; `scripts/bootstrap_session_ci.py` | AUCK changes if the K grid changes. |
| R1-04 | Verified | ECAPA session security reported for none, Opus 16 kbps, and G.711. | `codec_security_ecapa.csv` | Only the frozen telephony configuration was tested. |
| R1-05, R2-01, R2-07 | Verified | Independent-session ASV uses ECAPA and x-vector, EER, and target-impostor margin. | `vctk_test_none_20260919_asv.csv`; `vctk_oracle_none_20260919_asv.csv` | ECAPA EER is zero on the small test set; margin is more informative. |
| R1-09 | Verified | 95% paired speaker-cluster bootstrap, 2,000 draws, seed 42. | `bootstrap_ci_*.csv`; paper ICASSP tables | Eleven test speakers limit interval precision. |
| R1-10 | Partly verified | Actual RMS, SNR, relative L2, L-infinity, and STOI budget are reported. Alpha was selected on validation and the realistic objective was retrained before frozen test evaluation. | `perturbation_budget.csv`; validation sweep artifacts; checkpoint freeze records | No matched-budget ClearMask comparison. ClearMask code was not found; Enkidu's public repository has no explicit license file. |
| R2-02 | Evidence ready; prose pending | MeanSim@K is a point risk measure, AUCK summarizes the declared K grid, and K16-K1 describes aggregation gain. | `main_security_ecapa.csv` | These are protocol diagnostics, not replacements for standard ASV metrics. |

## Quality, Deployment, And Cloning

| Review ID | Status | Resolution | Evidence | Limitation |
|---|---|---|---|---|
| R1-06, R2-08 | Verified | Primary STOI is `tele_clean` versus `tele_defended`; clean-to-channel STOI is reported separately. | `quality_summary.csv`; `scripts/run_quality_eval_official.py` | STOI does not measure speaker identity. |
| R1-07 | Verified with explicit negative finding | WER uses 200 full VCTK utterances and official transcripts. Original-clean, tele-clean, tele-defended, channel delta, and defense delta receive speaker-cluster CIs. | `quality_summary.csv`; `quality_test_official.csv` | Absolute WER is about 1.0 with the current ASR backend; only paired deltas are interpretable. |
| R1-11 | Verified small-scale experiment | XTTS-v2: 20 sessions, 11 speakers, K=1 exploratory and K=16 primary, two texts, independent enrollment, ECAPA/x-vector margins and bootstrap CIs. | `xtts_summary.csv`; XTTS protocol and license audit files | Natural-speech thresholds reject both baseline and defended clones; acceptance rate is uninformative. K=64 synthesis was excluded because the concatenated reference exceeds XTTS's default 30-second limit. |
| R4-01 | Verified | Streaming latency and causal deployment measurements are retained. | `streaming_latency.csv` | Benchmark is for the tested hardware/software stack. |

## Manuscript Work Still Open

| Review ID | Status | Required manuscript action |
|---|---|---|
| R1-08, R2-09 | Open writing | Report mixed results: strong embedding-curve reductions, saturated ECAPA EER, small x-vector/XTTS margins, and quality trade-offs. |
| R2-03 | Open writing | Reduce abstract acronyms and omit a list of unexplained metric values. |
| R2-04, R2-05 | Open writing | Define every symbol before use and state explicitly that normalized embedding dot products are cosine similarity. |
| R2-06 | Open writing | Rewrite the protocol in standard ASV terms: candidate windows, embedding pooling, independent enrollment, cosine scoring. |
| R2-10 | Open writing | Correct LibriSpeech and perform a final grammar pass. |

## Claims That Must Not Be Reused From The Old PDF

- Do not reuse the old ClearMask or Enkidu numbers: no corresponding implementation, weights, raw outputs, or provenance exist in this repository.
- Do not call clean-reference selection a guaranteed upper bound.
- Do not claim a realistic targeted attack unless an attacker-obtainable external target reference is explicitly defined and evaluated.
- Do not reuse the old crop-based pseudo-ASR WER table.
- Do not claim statistically significant XTTS improvement for ECAPA; its paired confidence intervals cross zero.
