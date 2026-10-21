# ICASSP Paper Outline (Final Working Version)

**Status:** outline frozen for first full draft
**Target format:** four pages of technical content, with an optional fifth page restricted to references and allowed acknowledgements/ethics material; use the [official ICASSP paper kit](https://cmsworkshops.com/ICASSP2027/papers/paper_kit.php) for the target edition.

## 1. Recommended Positioning

### Working title

**CloneBlock-RT: Realistic Session-Level Defense Against Voice Cloning in Phone Calls**

Alternative if we want to foreground the training contribution:

**CloneBlock-RT: Aggregation-Aware Streaming Defense Against Voice Cloning in Phone Calls**

The first title is preferred because it makes the repaired threat model the paper's first-viewport contribution and avoids implying a new network architecture.

### Central claim

Existing streaming voice defenses can look effective under single-clip or clean-reference evaluation while weakening when an attacker selects and aggregates multiple intercepted call segments. CloneBlock-RT aligns training and evaluation with this realistic session-level attacker, improving resistance to multi-window aggregation while preserving real-time operation and high paired intelligibility.

### Contribution hierarchy

1. **Protocol contribution:** an attacker-observable, session-level aggregation protocol with explicit `clean`, `defended`, `tele_clean`, and `tele_defended` information boundaries.
2. **Training contribution:** a causal STFT-mask checkpoint retrained with an aggregation-aware self-consistency objective selected on validation data.
3. **Evaluation contribution:** uncertainty-aware results across codecs and speaker encoders, plus perturbation budgets, corrected transcript-aligned quality evaluation, real-time latency, and a small-scale XTTS study.

### Claims to avoid

- Do not call clean-reference evaluation a certified upper bound; use **information-privileged reference**.
- Do not claim universal prevention of voice cloning.
- Do not equate embedding-similarity reduction with end-to-end cloning failure.
- Do not reuse unaudited ClearMask/Enkidu, old WER, or old XTTS/K=64 numbers.
- Do not imply that bootstrap confidence intervals capture training-seed variability.

## 2. Four-Page Content Budget

| Part | Approx. space | Purpose |
| --- | ---: | --- |
| Abstract + index terms | 0.20 page | Problem, protocol, method, main result, qualification |
| 1. Introduction and related work | 0.65 page | Establish aggregation threat and evaluation gap |
| 2. Threat model and protocol | 0.75 page | Define observability, session aggregation, objectives, metrics |
| 3. Aggregation-aware CloneBlock-RT | 0.60 page | Architecture retained; new objective and validation selection |
| 4. Experimental setup | 0.50 page | Data, splits, encoders/codecs, statistics, utility and XTTS setup |
| 5. Results and discussion | 1.10 page | Main security result, robustness, utility, XTTS, limitations |
| 6. Conclusion | 0.20 page | Restrained take-away |

Recommended visual budget: **one two-column protocol figure and two compact two-column tables**. Avoid a third large table unless the first draft leaves room.

## 3. Abstract Plan (100-150 words)

Write five sentences:

1. Streaming perturbation defenses face a multi-window aggregation attack in phone calls.
2. Prior clean-reference/single-view protocols do not match the information available to a realistic interceptor.
3. We introduce a session-level self-consistency protocol and retrain the causal STFT gain-mask model with an aggregation-aware objective.
4. On VCTK, realistic retraining reduces ECAPA MeanSim@16 from 0.9444 to 0.9130 relative to the previous checkpoint, with 95% CI [0.9013, 0.9235], and the trend persists through Opus and G.711 while 20 ms CPU RTF is 0.028.
5. A small XTTS study gives mixed cross-encoder evidence, so the result is framed as stronger resistance rather than universal clone prevention.

Suggested index terms: **voice privacy, voice cloning, streaming defense, speaker verification, adversarial perturbation**.

## 4. Section-by-Section Outline

## 1. Introduction and Related Work

**Paragraph 1: problem and deployment setting.**
Zero-shot cloning systems can collect several fragments from a phone call. A defense that is causal and effective on one clip may degrade when the adversary selects and combines many windows.

**Paragraph 2: gap in prior evaluation.**
Clean target references give the evaluator information that a passive interceptor may not possess. Point estimates from a single speaker encoder also hide uncertainty and model dependence. State that these issues motivated the revised protocol; do not spend space narrating the submission history.

**Paragraph 3: approach.**
Introduce CloneBlock-RT as a causal STFT gain-mask processor whose architecture is retained, then state the new contribution: training and evaluation are aligned with session-level self-consistency selection over attacker-observed telephone audio.

**Paragraph 4: contributions.**
Use three compact bullets matching the contribution hierarchy above. Mention the realistic main result, codec robustness, real-time operation, and qualified XTTS evidence once; avoid an abstract-like metric list.

**Related-work integration.**
In two or three sentences, distinguish offline adversarial audio protection, real-time speech processing, and speaker/voice-cloning evaluation. Discuss ClearMask and Enkidu conceptually, but do not reproduce numerical baselines without auditable, matched-budget implementations.

## 2. Threat Model and Session-Level Protocol

**2.1 Signal states and attacker access.**
Define clean waveform `x`, defended waveform `x_def`, telephony transform `T`, `tele_clean = T(x)`, and `tele_defended = T(x_def)`. The realistic passive attacker observes only `tele_defended` windows from a target session. The defender does not know the attacker's downstream speaker encoder or TTS backend.

**2.2 Window selection and aggregation.**
For session windows `{w_i}`, define speaker embeddings `e_i`. In the realistic strategy, rank/select windows by self-consistency within the intercepted set, then aggregate the selected embeddings or audio for K in `{1, 2, 4, 8, 16}`. Use `tele_defended` as the primary selection source. The pre-channel `defended` source is an ablation.

**2.3 Information-privileged reference.**
Define a separate clean-reference score using a target enrollment embedding. Explain that this setting isolates the value of extra target information, but is neither the primary realistic attacker nor a proven mathematical upper bound.

**2.4 Metrics and uncertainty.**
Define MeanSim@K as the mean cosine similarity after K-window aggregation. Define AUCK explicitly as the normalized mean/area of the fixed K curve. Add ASV EER and target-impostor margin as complementary identity metrics. State that 95% CIs use 2000 paired bootstrap replicates clustered by speaker.

### Figure 1: protocol and method overview

Two-column figure placed at the top of page 2:

- Left-to-right signal path: `clean -> causal STFT mask -> defended -> codec/channel -> tele_defended`.
- Parallel clean channel: `clean -> codec/channel -> tele_clean` for paired quality measurement.
- Attacker box sees only multiple `tele_defended` windows in the realistic protocol.
- Show self-consistency ranking, top-K aggregation, and downstream speaker encoder/TTS.
- Use a dashed privileged path from clean enrollment to the reference-only condition.

The caption must carry the access-control message so the main distinction remains understandable if body text is skimmed.

## 3. Aggregation-Aware CloneBlock-RT

**3.1 Causal gain-mask processor.**
Briefly retain only implementation facts needed for reproducibility: causal framing, STFT-domain gain mask, bounded perturbation, overlap-add reconstruction, and chunk-wise streaming. Do not re-explain generic STFT background.

**3.2 Realistic aggregation-aware objective.**
Write the loss using the exact symbols implemented in the training code. Explain that the previous checkpoint optimized a clean-reference objective, whereas the new checkpoint optimizes an attacker-observable self-consistency/aggregation surrogate over session windows. Preserve any quality or perturbation regularizer in the equation and define every coefficient.

**3.3 Validation-only model selection.**
Report the validation sweep `alpha in {0.12, 0.18, 0.24}` and selection of `alpha=0.24` using realistic MeanSim@16/AUCK. State that the final model is trained for 1000 steps and the test set is not used for selection.

## 4. Experimental Setup

**Data and session pools.**
Use VCTK 0.92 as the final corpus. Report 255/33/33 train/validation/test sessions and 22,203/2,724/2,901 windows, with 11 speakers and 33 sessions in the final test. Mention source/split/session disjointness audits. Label LibriSpeech dev-clean as pilot-only rather than pooling it into final results.

**Security backends and channels.**
ECAPA is the primary speaker encoder; x-vector tests cross-encoder transfer. Evaluate no additional codec, Opus 16 kb/s, and G.711. Report K=16 and AUCK in the compact tables while retaining the full K curve in the figure/artifact if space permits.

**Utility and runtime.**
Use a deterministic 200-utterance VCTK manifest with official transcripts and paired channel draws. Report WER delta rather than absolute WER because the available ASR backend has poor clean accuracy. Define STOI specifically between `tele_clean` and `tele_defended`. State CPU/GPU chunk benchmark settings.

**End-to-end cloning.**
Describe the XTTS subset: 20 sessions, 11 speakers, K in `{1,16}`, two synthesis texts, 160 synthesized samples, independent enrollment, two speaker encoders, and paired speaker-cluster bootstrap. State before results that it is an exploratory scale test.

## 5. Results and Discussion

### Table 1: session-level security and robustness

Use a two-panel table.

**Panel A: primary ECAPA / `tele_defended` / self-consistency result**

| System | MeanSim@1 | MeanSim@16 | AUCK |
| --- | ---: | ---: | ---: |
| No defense | 0.7322 | 0.9873 | 0.8889 |
| Previous reference-objective checkpoint | 0.6987 | 0.9444 | 0.8497 |
| Realistic-objective retraining | **0.6754** | **0.9130** | **0.8208** |

Add `95% CI [0.9013, 0.9235]` for the final MeanSim@16 in the caption or a compact footnote.

**Panel B: channel and encoder sensitivity**

| Evaluation condition | MeanSim@16 | AUCK |
| --- | ---: | ---: |
| ECAPA, Opus 16 kb/s | 0.9096 | 0.8143 |
| ECAPA, G.711 | 0.9111 | 0.8206 |
| ECAPA, pre-channel selection | 0.8986 | 0.7810 |
| x-vector, telephony selection | 0.9963 | 0.9884 |

**Result paragraph 1.**
Lead with the realistic checkpoint improvement over the previous checkpoint, not with comparison to no defense alone. Interpret the remaining K=16 similarity as evidence that aggregation remains a hard failure mode.

**Result paragraph 2.**
State that Opus and G.711 preserve the ECAPA trend, while x-vector exposes limited cross-encoder transfer. This is a central mixed result, not a footnote.

### Table 2: utility, practicality, and end-to-end evidence

Use compact panels or grouped rows:

**Perturbation and quality**

- RMS 0.00884; SNR 14.32 dB; relative L2 0.1925; L-infinity 0.0746.
- STOI: 0.98436 without an added codec, 0.90676 with Opus, 0.97724 with G.711.
- WER delta: +0.00250 `[-0.00200, 0.00710]`, +0.00231 `[-0.00498, 0.01006]`, and +0.00468 `[-0.00315, 0.01231]`, respectively.

**Runtime**

- 20 ms chunks: CPU 0.560 ms / RTF 0.0280; GPU 0.745 ms / RTF 0.0373.

**XTTS target-impostor margin delta**

- x-vector K=1: -0.00246 `[-0.00504, -0.00019]`.
- x-vector K=16: -0.00296 `[-0.00521, -0.00052]`.
- ECAPA point estimates decrease but both confidence intervals cross zero; summarize in text rather than spending two more table rows if space is tight.

**Result paragraph 3.**
Explain that all WER-delta intervals cross zero and STOI remains high in the no-codec/G.711 conditions. The low Opus STOI is mainly a full-channel condition and should not be attributed solely to the defense.

**Result paragraph 4.**
Present XTTS as mixed evidence: x-vector margins decrease consistently but modestly; ECAPA uncertainty includes zero; natural-speech thresholds reject both baseline and defended clones and therefore do not provide a useful acceptance-rate comparison.

**Limitations paragraph.**
One concise paragraph must name: one final training seed, VCTK-centric testing, one small TTS backend study, weak absolute ASR accuracy, no matched-budget external baseline, and strong speaker-encoder dependence. This paragraph is required, not optional.

## 6. Conclusion

Use three restrained sentences:

1. Realistic multi-window aggregation should be part of streaming voice-defense evaluation.
2. Aligning CloneBlock-RT training with that attacker improves ECAPA session-level resistance while retaining real-time operation and paired intelligibility.
3. Cross-encoder and XTTS results remain mixed, motivating multi-backend and multi-seed evaluation rather than a universal prevention claim.

## 7. Exact Terminology to Keep Consistent

| Use | Avoid |
| --- | --- |
| realistic self-consistency protocol | targeted realistic protocol based on clean enrollment |
| information-privileged clean-reference condition | oracle upper bound, unless carefully qualified |
| session-level aggregation-aware objective | generic adversarial training |
| `tele_defended` attacker-observed selection source | defended embedding, when the channel position is ambiguous |
| reduction in aggregation similarity/resistance | guaranteed prevention |
| exploratory small-scale XTTS evaluation | comprehensive end-to-end proof |
| speaker-cluster paired bootstrap CI | training uncertainty CI |

## 8. Writing and Evidence Checklist

- [ ] Copy equations from the implemented loss, not from memory or the old manuscript.
- [ ] Define K, MeanSim@K, AUCK, EER, margin, STOI, WER delta, and RTF at first use.
- [ ] Keep all main comparisons on the same frozen test pools and checkpoint IDs.
- [ ] Cite artifact hashes or experiment IDs in the internal source notes, even if they do not appear in the camera-ready paper.
- [ ] Verify that every number in the draft exists in `EXPERIMENT_EVIDENCE_LEDGER.md` or a frozen artifact.
- [ ] Use the official target-year ICASSP template and recheck page limits, author visibility, and submission deadline before upload.
- [ ] After the first full draft, perform one claim audit against the original PDF and one number audit against exported CSV/JSON artifacts.

## 9. Information Needed Before Camera-Ready Drafting

The outline and first prose draft can proceed now. Before submission, obtain or decide:

1. Author list, affiliations, corresponding author, and contribution statement.
2. Whether original checkpoints/logs can restore a fair external baseline.
3. Whether compute/time permits at least two additional training seeds.
4. Final target ICASSP edition and its current paper-kit rules.
5. Final public artifact URL/commit to cite after anonymization policy is confirmed.
