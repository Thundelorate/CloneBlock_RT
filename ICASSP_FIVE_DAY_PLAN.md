# ICASSP Five-Day Revision Plan

Owner authorization: 2026-09-11. All remaining methodological choices delegated to the assistant, subject to later owner changes.

Internal deadline: 2026-09-15 22:00 Asia/Shanghai. This is a delivery target, not a guarantee that experiments will support improved performance.

## Submission Target

- Target: ICASSP 2027 regular paper, assuming the previous manuscript is rejected/withdrawn and unpublished. Owner must confirm its actual publication/submission status.
- Official submission page currently lists Beijing 2026-09-17 20:00. Keep the internal deadline unchanged.
- Use the 2027 template: at most four technical-content pages plus an optional fifth page for permitted back matter. Do not plan a technical appendix on page five.
- Every author needs an ORCID. Owner coordinates authorship, affiliations, coauthor approval and submission.
- The conference permits assistance with code, ideation and editing, but prohibits entire LLM-produced manuscript sections. Authors provide and take ownership of the scientific prose; assistance focuses on reviewing, clarifying and editing it. Verify generated code and all citations.
- Sources checked 2026-09-11: https://cmsworkshops.com/ICASSP2027/papers.php and https://cmsworkshops.com/ICASSP2027/papers/paper_kit.php

## Scientific Scope

The intended contribution is a session-level aggregation-aware evaluation protocol and a streaming defense trained/evaluated under an explicit phone-call attacker model. Statistical intervals, notation repairs and additional standard metrics strengthen evidence but are not standalone algorithmic innovations. Realistic training is a candidate method contribution whose value must be measured.

Main attacker observations: `tele_defended`, meaning defense output after the telephone channel. `defended` means defense output before the channel and is a diagnostic ablation. An embedding is a numerical speaker representation extracted from either waveform.

Main selection: random windows plus self-consistency, which selects windows whose pooled speaker embedding matches the observed recording's own centroid. The existing observed-centroid implementation is not an independently targeted attack. A separate realistic targeted condition requires a specified independently obtainable victim reference; do not invent access to clean evaluation audio.

Oracle: retain legacy clean-reference selection as an information-privileged reference. It does not guarantee a numerical upper bound. If adding a greedy attack scored directly against the clean reference, call it an oracle attack estimate. A finite maximum over evaluated attacks is an observed attack envelope, not a certified global bound.

The evaluator may use clean audio for scoring without disclosing it to the realistic attacker. Same-session recovery similarity and standard ASV with independent enrollment/test utterances are different experiments. The current ASV script uses same-session references; correct or explicitly qualify that protocol before presenting standard verification claims.

## Daily Deliverables

| Date (Asia/Shanghai) | Assistant work | Owner contribution | Completion gate |
|---|---|---|---|
| Sep 11 | Correct selection boundary; freeze metric definitions and experiment manifest; add tests; audit data, checkpoints and baseline implementations; run a tiny server pilot | Supply server access through local SSH configuration, asset paths and manuscript source; confirm previous paper status | No clean leakage in realistic selection; runnable pilot; measured throughput and revised compute estimate |
| Sep 12 | Main old-checkpoint and baseline evaluation; speaker-cluster bootstrap; independent ASV trials; fix transcript mapping; small alpha validation sweep; start realistic retraining | Resolve missing assets; review threat-model and contribution notes with supervisor | Protocol/configuration frozen; training running; initial main table from corrected evaluation |
| Sep 13 | Evaluate retrained checkpoint; Opus/G.711 and ECAPA/x-vector checks; WER/STOI and perturbation measurements; small XTTS pilot and batch | Review representative audio and preliminary mixed results; supply author-written method/results notes | Primary security, usability and transfer evidence produced; XTTS pipeline functioning |
| Sep 14 | Finish planned jobs by 18:00; freeze numerical results; generate tables/curves; reconcile every review item; edit author draft into four-page technical budget | Deliver scientific draft sections and coauthor feedback | Every claim linked to evidence or softened/removed; manuscript complete for review |
| Sep 15 | Morning: fix correctness/reproducibility issues and layout; afternoon: final citation/number checks; by 22:00 deliver PDF, sources, configurations and evidence ledger | Coauthors approve final text, author details and submission form; submit | Submission-ready package with no placeholder numbers, missing mandatory results or unsupported claims |

Writing starts Sep 11 alongside code work. Do not wait until all experiments finish to organize the manuscript.

## Fixed Experiment Defaults

| Item | Default and rationale |
|---|---|
| Baselines | Preserve all original baselines for which actual implementation/weights are recoverable, including the strongest reported comparison. Never combine old oracle numbers with new realistic numbers in the same comparison. Flag missing baselines immediately. |
| Main K grid | 1, 2, 4, 8, 16; K is the number of selected windows. Use identical eligible sessions across K/methods. Report window duration, overlap and unique audio coverage. |
| AUCK | Arithmetic mean of MeanSim@K on that exact grid. Changing the grid changes the metric. Do not describe it as a linear-K integral. |
| Confidence intervals | 95% paired speaker-cluster bootstrap, initially 2000 resamples. Resample speakers with all their sessions; overlapping windows are not independent samples. Record seed and number of speakers. Single-seed intervals do not measure training-seed variability. |
| ASV | Automatic speaker verification: ECAPA and x-vector speaker encoders; EER is equal error rate. Margin is target score minus the strongest score in a fixed impostor set. Reuse trial lists across methods. Separate independent ASV from same-session recovery. |
| Channel checks | No codec, Opus at 16 kbps, G.711. Share channel draws and noise seeds across methods; record actual backend and fail clearly on unavailable codecs. |
| Perturbation | Report alpha (STFT gain limit), actual waveform SNR, RMS and maximum absolute change, plus clipping fraction. Alpha is not a universal waveform distortion budget. Compare baselines at documented budgets; add a limited matched-distortion comparison if feasible, otherwise explicitly limit fairness claims. |
| Alpha selection | Initial validation-only grid 0.09, 0.18, 0.27, including old 0.18. First measure the quality/security tradeoff with the old checkpoint as a screening ablation; use validation-only criteria to fix the retraining setting. Changing alpha at inference is not three independent training runs. Freeze selection criterion before test evaluation. |
| Retraining | One realistic-objective retraining or explicitly labeled fine-tuning, depending checkpoint recovery and pilot throughput. Keep old checkpoint as reference. Do not choose whether to report the new model based on test gains. |
| Quality | Official VCTK transcripts matched to complete original utterances, or correctly aligned segments. Never score a 2-6 second crop against the whole utterance transcript. WER = word error rate; report ASR model and defense-induced change. |
| STOI | Short-Time Objective Intelligibility. Primary pair: channel-processed clean audio vs channel-processed defended audio, with shared channel draws. Add original-clean vs channel-output column to expose channel damage; self-comparison baseline of 1 is then explained. No PESQ/DNSMOS. |
| XTTS | Small end-to-end speech-cloning check: default 20 held-out sessions covering as many distinct speakers as possible, K=1/16/64 when feasible, fixed synthesis texts/seeds and reference-duration policy. Compare unprotected vs final defended reference. Verify actual model reference truncation before claiming multi-K coverage. |
| XTTS ASV decision | Report attack acceptance at a threshold calibrated on held-out natural-speech validation trials (target FAR=1% if sample size supports it), plus target margin and uncertainty. FAR = false acceptance rate. Never choose threshold using cloned test scores. |
| Compute | One Linux NVIDIA GPU server initially; 24 GB VRAM is a planning target, actual fit/throughput determined by pilot. No reliable GPU-hour total before measuring data loading, encoding, training and synthesis. Owner controls spending ceiling. |

## Five-Day Scope Controls

1. Sep 11: benchmark two sessions and a short training run, plus one XTTS synthesis if weights are ready. Estimate full-job time from measurements and leave at least 30% recovery margin.
2. Priority order: protocol correctness and standard metrics; actual baseline comparisons; realistic retraining; channel/encoder transfer; quality/budget; small XTTS. Prepare dependencies concurrently so long-running work can start early.
3. First reductions if throughput is low: broad alpha grids, multiple training seeds, expanded XTTS speakers/K and pre-channel ablations. Keep all exclusions and changes in the evidence ledger. Do not silently declare omitted review items solved.
4. Missing old weights or the strongest baseline by Sep 11 evening is a critical schedule risk. Recover from the original author immediately; cold-start reproduction can exceed five days.
5. Sep 13 evening: if retraining is unstable, preserve logs and report the corrected old-model evaluation as such. Discuss the weaker method claim with the owner. Do not replace failed runs with invented or cherry-picked outcomes.
6. Sep 14 18:00: freeze planned numerical results. After that, rerun only to fix demonstrated correctness issues, not to chase better test scores.
7. Each review row needs: action, evidence path, manuscript location, limitation if any, and status (open/implemented/verified/closed). Lack of improvement can be an honest scientific result; it is not proof of superiority.

## Required Owner Inputs

- Server availability, GPU/VRAM, allowed duration and spending cap. Configure SSH locally; never paste passwords or private keys into chat.
- Owner has supplied all available materials. Real VCTK audio/transcripts, original splits/session manifests, defense weights and baseline artifacts are absent; download the official corpus and regenerate fixed manifests. Old weights may require contacting the original author or replacing old-model evaluation with an explicitly documented retraining.
- Manuscript source is unavailable: the owner has only the supplied PDF. Reconstruct the editable project from that PDF and the official conference template; do not ask for unavailable LaTeX again.
- Original manuscript publication/review status, intended coauthors and supervisor review times. An already published paper requires a different novelty/submission assessment from a rejected manuscript.
- Daily author-written scientific notes and draft text: what problem matters, why this threat model is justified, and what the measured results support. Assistance can organize evidence, review reasoning and improve wording; authors own the scientific narrative.

## Code Map For The Next Steps

| File | Technical role | Status |
|---|---|---|
| src/metrics/session_attack.py | Choose K reference windows; separate attacker observations from scoring reference | First patch implemented; six selection unit tests passed on CPU |
| scripts/run_session_pool_eval.py | Run pooled-window similarity curves and save per-session evidence | Realistic default, AUCK label, protocol metadata and raw records implemented; audio smoke test pending |
| tests/test_session_attack.py | Verify clean-value independence, protocol labels and distinct-window checks | Six tests passed; no pretrained audio models needed |
| scripts/run_asv_eer_eval.py | Speaker-verification trials, EER and target/impostor margins | Next: independent trials, source labels, shared trials/channel draws, CI and codec controls |
| scripts/run_quality_eval.py; scripts/prepare_data.py | Transcript alignment, word errors and intelligibility | Pending |
| scripts/run_train.py | Optimize defense parameters; alpha controls STFT gain range | Pending realistic loss audit and retraining config |
| scripts/run_e2e_cloning_eval.py | Synthesize speech with XTTS and test impersonation | Pending |
| scripts/reproduce_paper.sh; scripts/export_paper_artifacts.py; scripts/csv_to_latex.py | Reproduce experiments and turn verified outputs into paper tables | Pending; old one-shot runner is not yet updated for the revised protocol |
| scripts/bootstrap_session_ci.py | Paired speaker-cluster intervals for the recovery curve, AUCK and K16-K1 | Implemented with known-answer tests; real results pending |
| scripts/audit_experiment_data.py | Check speaker disjointness, crop provenance and manifest hashes | Implemented with audio fixtures; full VCTK audit pending |
| scripts/setup_autodl.sh; scripts/server_preflight.py | Prepare candidate GPU environment and capture installed package versions | Bash syntax/local diagnostic checked; server install and GPU pilot pending |

## Delivery Package

- Author-approved ICASSP PDF and editable source, with verified references and no unsupported performance claims.
- Revised code, focused tests, pinned environment information and exact run commands.
- Speaker/session splits, trial lists, seeds, checkpoint identity, codec configuration, raw metrics and regenerated tables/figures.
- Review-response matrix with evidence links and explicitly acknowledged limitations; use it as the internal revision checklist, not an assumed rebuttal attachment for a new submission.
