# Review Response Matrix

This matrix tracks every actionable reviewer concern for CloneBlock-RT and maps it to a response plan, code or experiment target, owner decision, missing inputs, and priority.

## Current Owner Decisions

| Decision Area | Current Choice |
|---|---|
| Paper framing | Realistic attacker plus oracle upper-bound dual view |
| Protocol contribution | Explicitly frame as a session-level aggregation-aware protocol |
| Main selection source | Confirmed 2026-09-11: tele_defended main; defended pre-channel ablation |
| Selection strategy update | Add realistic targeted and self-consistency strategies |
| Oracle issue | Acknowledge and reclassify clean-reference targeted selection as oracle upper bound |
| AUCK | Equal-weight arithmetic mean over the declared discrete K grid; not linear-K trapezoidal area |
| Standard ASV metrics | Add EER plus target-impostor margin |
| Uncertainty | Bootstrap 95 percent CI |
| Perturbation budget | Report CloneBlock perturbation budget |
| Alpha choice | Justify by validation sweep |
| Training plan | Retrain with realistic objective |
| WER reference | Use official VCTK transcripts |
| STOI definition | Report STOI as tele_clean vs tele_defended |
| PESQ/DNSMOS | Do not add for now |
| Codec security | Run K16/AUCK/EER under Opus and G.711 |
| Cross encoder | ECAPA plus x-vector |
| E2E cloning | Small-scale XTTS |
| Compute platform | Linux GPU server |
| Result narrative | Acknowledge mixed results and explain metric meanings |
| Abstract | Fewer unexplained metrics, clearer problem/result framing |

## Matrix

| ID | Reviewer Concern | Response Strategy | Code / Experiment Target | Output Artifact | Needs User Input? | Compute Need | Priority |
|---|---|---|---|---|---|---|---|
| R1-01 | Main targeted best-K attack may use clean/oracle information unavailable to a realistic attacker. | Split evaluation into realistic attacker and oracle upper bound. Make tele_defended or defended selection the main result. | `src/metrics/session_attack.py`, `scripts/run_session_pool_eval.py`, `scripts/run_asv_eer_eval.py` | Main security table with explicit `selection_source`; oracle appendix table | Yes: choose primary between `defended` and `tele_defended` | Existing checkpoint evaluation first; retraining later | P0 |
| R1-02 | Claims that selection uses only telephony-captured signals are overstated. | Revise terminology: clean-reference selection is oracle; defended-stream selection is realistic. | Paper text, README, script help strings, output metadata | Threat-model paragraph; table captions | No, unless paper tone changes | None | P0 |
| R1-03 | AUCK is underspecified. | Define AUCK formula over discrete K set, normalization, and lower-is-better interpretation. | `scripts/run_session_pool_eval.py`, `scripts/csv_to_latex.py`, paper equations | CSV fields `AUCK`, table notes, formula in method section | No | None | P0 |
| R1-04 | Codec-specific security results are claimed but not visible. | Add security tables for Opus 16 kbps and G.711, not only usability tables. | `scripts/run_session_pool_eval.py`, `scripts/reproduce_paper.sh`, `scripts/export_paper_artifacts.py` | `codec_robustness_targeted_teledef.csv`, LaTeX table, figure | No | GPU useful for speed | P0 |
| R1-05 | Cross-encoder ASV margin reductions are claimed but not visible. | Add ECAPA and x-vector EER plus target-impostor margin table. | `scripts/run_asv_eer_eval.py`, `scripts/export_paper_artifacts.py`, `scripts/csv_to_latex.py` | `cross_encoder_asv_eer.csv`, margin table | No, unless adding more encoders | GPU useful | P0 |
| R1-06 | STOI baseline exactly 1.0000 under codecs is unclear or implausible. | State STOI reference is `tele_clean` vs processed condition; optionally add clean-original vs tele-output metric. | `scripts/run_quality_eval.py`, paper quality section | Quality table with explicit reference definition | Yes: decide whether to add extra clean-original STOI column | CPU/GPU depending ASR | P0 |
| R1-07 | WER values are high and small differences are hard to interpret. | Use official VCTK transcript where available; report ASR model; present defense-induced delta and CI. | `scripts/prepare_data.py`, `scripts/run_quality_eval.py` | Quality summary with transcript source and WER CI | Possibly: confirm VCTK raw transcript path on server | ASR inference, GPU useful | P0 |
| R1-08 | Main result is mixed; another baseline wins MeanSim@16. | Present mixed results honestly and explain metric roles: point metric vs curve robustness vs aggregation slope. | Paper result section | Revised narrative and table captions | Yes: decide final rhetorical stance | None | P0 |
| R1-09 | No uncertainty estimates for main security metrics. | Add bootstrap 95 percent CI and paired delta CI. | `scripts/run_session_pool_eval.py`, possibly helper module | Security tables with CI columns | No | Low | P0 |
| R1-10 | Perturbation budget and matched-budget comparisons are under-justified. | Report actual perturbation metrics; run alpha validation sweep; later decide matched-budget baseline. | New or updated eval script; `scripts/run_train.py`; `scripts/export_paper_artifacts.py` | Perturbation budget table; alpha sweep table/plot | Yes: choose budget metric and baseline set | Alpha sweep may require GPU; matched baselines may be high cost | P1 |
| R1-11 | XTTS evaluation would be stronger with operating-point results or perceptual evidence. | Run small-scale XTTS and optionally add ASV accept-rate at fixed threshold; no PESQ/DNSMOS for now. | `scripts/run_e2e_cloning_eval.py`, `scripts/reproduce_paper.sh` | `e2e_cloning_summary.csv`, optional accept-rate table | Yes: choose sample size and whether threshold comes from validation ASV | GPU server | P1 |
| R2-01 | Lack of standard metrics makes comparison hard. | Add EER and target-impostor margin alongside custom session metrics. | `scripts/run_asv_eer_eval.py` | ASV table | No | GPU useful | P0 |
| R2-02 | Proposed metrics need critical analysis. | Add a subsection explaining what MeanSim@K, AUCK, and slope capture and what they do not capture. | Paper text, README notes | Metric interpretation section | Yes: final contribution framing | None | P0 |
| R2-03 | Paper is difficult to follow due to many acronyms. | Reduce acronyms in abstract; define all acronyms on first use. | Paper text | Revised abstract and notation paragraph | No | None | P0 |
| R2-04 | Equations 1-3 have undefined symbols such as theta, y, superscript c, and S. | Add notation table and define each symbol before equations. | Paper text | Notation table or paragraph | No | None | P0 |
| R2-05 | Equation 5 inner product/cosine is not explicit. | State embeddings are L2-normalized, so dot product equals cosine similarity. | Paper text | Updated equation explanation | No | None | P0 |
| R2-06 | Sections 2.4 and 2.5 are overly complex for speaker-verification-style enrollment averaging. | Rewrite with standard ASV terms: enrollment windows, embedding pooling, cosine scoring. | Paper text | Simplified protocol section | Yes: decide whether to call it a protocol contribution or evaluation adaptation | None | P0 |
| R2-07 | Cross-encoder ASV risk is referenced but not reported. | Add table and cite it in intro/conclusion only if present. | `scripts/run_asv_eer_eval.py`, paper result section | Cross-encoder table | No | GPU useful | P0 |
| R2-08 | STOI and WER are not introduced or defined. | Define WER, STOI, ASR backend, transcript source, and reference audio pair. | `scripts/run_quality_eval.py`, paper text | Quality-method paragraph and table notes | No | None for writing; GPU for rerun | P0 |
| R2-09 | The method appears to have limited improvement over baselines. | Use corrected realistic/oracle tables, CI, matched-budget or budget reporting, and mixed-result narrative. | Main eval scripts and paper text | Revised main table and discussion | Yes: decide which baselines remain central | Evaluation plus possible retraining | P1 |
| R2-10 | Minor grammar and typo issues, including LibriSpeech spelling. | Fix typos and awkward sentence construction. | Paper text, README if needed | Clean final manuscript | No | None | P2 |
| R4-01 | Positive review supports the live telephony and aggregation-aware framing. | Preserve this framing but make the attacker-information boundary precise. | Paper intro and method | Revised contribution bullets | No | None | P0 |
| R4-02 | Positive review says selection strategies are clear. | Keep random, consistency, and targeted categories, but label realistic vs oracle explicitly. | Paper text and table labels | Cleaner protocol taxonomy | No | None | P0 |

## Earlier Decision Options (Resolved By Delegation On 2026-09-11)

The owner accepted the recommended defaults and selected ICASSP 2027, with an internal delivery deadline of 2026-09-15 evening (Asia/Shanghai). See `ICASSP_FIVE_DAY_PLAN.md` for the execution schedule and remaining resource inputs. Decisions in this historical table are no longer pending approval; server availability and existing assets still need to be supplied. Earlier 'Needs User Input?' cells concerning methodological preferences are superseded by this delegation.

| Question | Why It Matters | Options | Recommended Default |
|---|---|---|---|
| Should the primary realistic selection source be `tele_defended` or `defended`? | This decides the main table and the training objective. `tele_defended` best matches a phone-call attacker; `defended` isolates defense before channel effects. | `tele_defended` main, `defended` ablation; or `defended` main, `tele_defended` robustness | `tele_defended` main, `defended` ablation |
| Which baselines must remain in the paper? | Matched-budget and mixed-result discussion depend on the baseline set. | Keep all existing baselines; keep only strongest/standard baselines; add new budget-matched baselines | Keep current baselines first, then add budget reporting before deciding matched-budget reruns |
| What is the acceptable GPU budget? | Determines whether we run only existing-checkpoint evaluation, one retraining, alpha sweep, or multi-seed retraining. | Short run; one full retrain; retrain plus alpha sweep; multi-seed | First: existing checkpoint eval; second: one realistic-objective retrain plus small alpha sweep |
| What XTTS scale is acceptable? | E2E cloning can be expensive and slow. | 10 sessions; 20 sessions; 50 sessions; more | 20 sessions, K in 1/16/64 |
| Should we add a clean-original STOI column? | It directly addresses confusion around baseline STOI=1.0000. | Keep only tele_clean-vs-tele_defended; add clean-original reference column | Add clean-original reference column if implementation time is acceptable |
| What is the final paper target? | Determines how aggressive the revision should be. | Rebuttal only; workshop resubmission; full conference resubmission | Build for full resubmission-quality evidence, but stage work for fast rebuttal first |

## Recommended Execution Order

1. Freeze terminology: define realistic vs oracle and choose table labels.
2. Update session selection code to support realistic targeted and self-consistency strategies without clean-oracle leakage.
3. Add AUCK, per-session raw outputs, bootstrap CI, and paired deltas.
4. Rerun existing-checkpoint main evaluation under `tele_defended` and `defended`.
5. Add codec security evaluation for Opus 16 kbps and G.711.
6. Add ECAPA and x-vector EER plus margin outputs.
7. Repair VCTK transcript tracking and rerun WER/STOI quality evaluation.
8. Report perturbation budget metrics and run a small alpha validation sweep.
9. Run the planned realistic-objective retraining after the validation sweep; report it even if it does not improve on the old checkpoint.
10. Run small-scale XTTS E2E cloning on Linux GPU.
11. Update export and LaTeX scripts so all evidence is visible in paper artifacts.
12. Rewrite abstract, threat model, metric definitions, equations, and results narrative.

## Implementation Status (2026-09-11)

- R1-01/R1-02/R4-02: first protocol patch implemented. Main defaults use observed-stream self-consistency; CSVs label attacker access. Full audio evaluation remains pending.
- R1-03: AUCK emitted as a discrete equal-weight mean, with AUC retained as a compatibility alias. Paper wording and exports remain pending.
- R1-09: per-session scores and selected indices are saved. `scripts/bootstrap_session_ci.py` now implements paired speaker-cluster 95% percentile intervals for MeanSim@K, AUCK and K16-K1. Known-answer and command-line fixture tests cover the implementation; actual experimental intervals remain pending.
- First-patch verification: six selection unit tests passed in the existing Python 3.10 / PyTorch 2.7.1 CPU environment. Changed Python files passed syntax checks. Audio/model integration and server experiments have not run.
- All review concerns remain open until verified evidence or an explicit limitation and revised claim is linked. A code patch alone does not close an experimental concern.
- Clarification: legacy clean-centroid selection is not a mathematically guaranteed upper bound. Retain it as an oracle reference; any upper-bound wording must specify whether it means an information-privileged stress test or a certified bound.
- Clarification: the legacy observed-pool centroid objective is self-consistency, not targeting an independently known victim embedding. Any separate realistic targeted condition needs an explicit attacker-obtainable target reference.
- R1-07/R2-08: source-file/crop provenance and explicit VCTK microphone selection added to data preparation; split integrity audit added. Whole-utterance quality manifest and WER evaluation repair remain pending. Provenance alone does not provide aligned crop transcripts.
- Server setup and preflight scripts prepared. Candidate dependency versions are not yet validated on the rented GPU server. Local preflight correctly reports missing audio dependencies and codecs.
- See `OVERNIGHT_HANDOFF.md` for the runnable setup sequence, terminology and known blockers. The owner has supplied all currently available materials; there is no LaTeX source or local experiment asset bundle to request again.
