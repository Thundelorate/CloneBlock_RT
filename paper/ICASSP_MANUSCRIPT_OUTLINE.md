# ICASSP Manuscript Reconstruction Outline

This is a scientific-writing scaffold, not submission-ready prose. Authors remain responsible for the final claims, interpretation, citations, and wording.

## Working Framing

**Problem:** A phone-call attacker can collect many short speech windows, select useful windows, and pool them before zero-shot cloning.

**Primary contribution:** A session-level, aggregation-aware evaluation protocol with explicit attacker information boundaries.

**Method contribution:** CloneBlock-RT, a causal STFT gain-mask defense retrained with a realistic self-consistency aggregation objective.

**Evidence stance:** Realistic `tele_defended` is primary. Pre-channel `defended` is an ablation. Clean-reference selection is an information-privileged oracle reference, not a certified upper bound.

## Four-Page Technical Budget

1. **Abstract (120-150 words):** State problem, protocol, method, and one restrained result sentence. Avoid AUCK/EER/STOI acronyms unless essential.
2. **Introduction and related work (0.65 page):** Motivate multi-window call capture; identify the information-leakage problem in prior evaluation; state three contributions.
3. **Threat model and protocol (0.8 page):** Define attacker observations, candidate windows, K-window pooling, realistic self-consistency, oracle reference, MeanSim@K, AUCK, standard ASV EER/margin.
4. **CloneBlock-RT (0.65 page):** Causal STFT gain mask, bounded alpha, realistic aggregation-aware training objective, streaming implementation.
5. **Experimental setup (0.55 page):** VCTK 0.92, speaker-disjoint sessions, K grid, codecs, ECAPA/x-vector, official transcripts, bootstrap unit, XTTS scope.
6. **Results and limitations (1.05 pages):** Main realistic table; compact codec/ASV table; quality/XTTS/latency table; honest mixed-result analysis.
7. **Conclusion (0.2 page):** Reiterate the protocol and bounded empirical findings without introducing new metrics.

## Required Definitions

- $x_i$: clean candidate waveform window.
- $D$: causal defense.
- $T(\cdot;\theta)$: telephone channel with sampled parameter set $\theta$.
- `clean`, `defended`, `tele_clean`, `tele_defended`: name these four waveform states once and reuse them.
- $f$: speaker encoder; every output is L2-normalized.
- $K$: number of distinct selected windows, $K \in \{1,2,4,8,16\}$.
- MeanSim@K: mean cosine similarity between pooled attack and evaluator reference embeddings.
- AUCK: arithmetic mean of MeanSim@K over the declared K grid.
- Target-impostor margin: target score minus the maximum score over the fixed impostor set.
- EER, WER, and STOI: spell out at first use and state backend/reference pair.

## Planned Tables And Figure

1. **Figure 1:** Full-bleed protocol diagram showing waveform states and information access. The clean scoring reference must be visibly evaluator-only.
2. **Table 1:** ECAPA realistic main result with MeanSim@1, MeanSim@16, AUCK, K16-K1, and 95% CIs. Include no defense, reference objective, and realistic retraining.
3. **Table 2:** Compact robustness panel: codecs, x-vector transfer, independent-session EER/margin, and defended-source ablation.
4. **Table 3:** Utility and practical evidence: perturbation budget, official-transcript WER delta, three STOI pairs, latency, and XTTS paired margins.

## Result Interpretation Guardrails

- Lower MeanSim and AUCK mean weaker identity recovery, but they do not directly equal cloning failure.
- ECAPA EER saturation at zero is a sample-size/operating-regime result; use target-impostor margin for sensitivity.
- The x-vector XTTS margin reductions are small but their speaker-bootstrap CIs are below zero; ECAPA XTTS intervals cross zero.
- Absolute WER is poor even on original clean audio with the chosen ASR backend. Discuss paired defense deltas, not apparent absolute quality.
- The current evidence supports a protocol contribution and a measured defense trade-off. It does not support universal superiority over unreproduced external baselines.

## Author Decisions Needed Before Submission

- Confirm title, author list, affiliations, ORCIDs, and previous submission/publication status.
- Decide whether to request reproducibility assets or permission from the ClearMask/Enkidu authors.
- Write the final scientific interpretation in the authors' own voice and obtain coauthor approval.
- Confirm which result tables fit the official ICASSP page limit after typesetting.
