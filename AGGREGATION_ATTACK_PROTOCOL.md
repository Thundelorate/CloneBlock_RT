# Aggregation Attack Advantage Experiment

## Claim

The experiment tests one narrow claim: an attacker that combines multiple
speech fragments obtains a stronger speaker representation than an otherwise
matched single-fragment attacker. It does not use stronger cloning results as
an indirect proxy for this claim.

The outcomes are speaker-representation and ASV attack proxies. They quantify
identity recovery available to a downstream cloning attacker, but they are not
reported as direct evidence of synthesized-speech naturalness or cloning
quality.

## Frozen data protocol

- Corpus: official VCTK 0.92, microphone `mic2`, exact archive MD5
  `8a6ba2946b36fcbef0212cad601f4bfa`.
- Split and session pool: seed 42, speaker-disjoint train/validation/test split,
  three sessions per speaker, disjoint source utterances.
- Evaluation unit: speaker. Validation is used for thresholds and protocol
  choices; test is read once for the final report.
- Enrollment: the first deterministically sorted session of each test speaker.
  Its clean windows form the enrollment centroid.
- Attack: the other two sessions. No attack window may be used for enrollment.
- Windows: 1.0 s. A greedy chronological filter retains only non-overlapping
  windows before an attack condition is sampled.

## Systems

1. `none`: no defense.
2. `reference`: the previous single-fragment-oriented checkpoint.
3. `realistic`: the selected realistic-objective checkpoint.

Random attack indices, telephony parameters, speaker encoder and enrollment
centroids are shared for paired comparisons between systems. Self-consistency
and contiguous selections are recomputed from each system's attacker-visible
embeddings, because the realistic attacker adapts to the defended signal; those
conditions remain paired by speaker and attack session rather than by index.

## Attack conditions

For each attack session and `K in {1, 2, 4, 8, 16}`:

- `random_K`: uniformly sample K non-overlapping windows without replacement.
  Use 100 deterministic repeats per speaker/session/K.
- `self_consistency_K`: select K windows whose embeddings are most consistent
  with the attacker-visible session centroid. This is the realistic targeted
  aggregation strategy.
- `contiguous_K`: select a chronological K-window block using the same
  self-consistency score, concatenate those windows into one `K`-second
  waveform, and invoke the speaker encoder once. It matches total speech
  duration while removing both cross-session selection and fragment-embedding
  averaging from the control condition.

`K=1` is evaluated separately for every strategy. Therefore the experiment
does not compare a hand-picked multi-fragment attack only against a random
single fragment.

## Speaker encoders

- Primary: ECAPA-TDNN.
- Secondary robustness check: x-vector.

All embeddings are L2-normalized before aggregation. The aggregate is the
L2-normalized mean of the selected embeddings.

## Outcomes

- Target similarity: cosine similarity to the independent clean enrollment.
- Target-impostor margin: target similarity minus the maximum similarity to
  another speaker's enrollment.
- EER: equal-error rate over target and impostor trials.
- Attack acceptance rate: fraction of target trials above a threshold fixed on
  validation at 1% false-accept rate.

Report two distinct paired contrasts:

- Aggregation gain: metric at K minus the same strategy's metric at K=1.
- Selection gain: self-consistency metric minus random metric at the same K.

The first contrast quantifies whether stronger aggregation-aware defense is needed. The
second measures the additional benefit of realistic targeted fragment
selection and must not be described as aggregation gain.

For target similarity, margin and acceptance, a positive `K - K1` change means
a stronger attack. For EER, the direction is reversed: lower EER means the
aggregated representation separates the victim from impostors more reliably,
so report `EER(K) - EER(K1)` explicitly rather than relabeling its sign.

## Statistics and artifacts

- Point estimates are macro-averaged over speakers.
- Use a paired speaker-cluster bootstrap with 2,000 draws and seed 42.
- Report 95% percentile confidence intervals for absolute metrics and both
  paired contrasts.
- Save raw per-trial rows, per-speaker summaries, aggregate tables, JSON
  manifests, and PNG/PDF figures.
- Every manifest records the Git commit, checkpoint SHA-256, session-pool
  SHA-256, encoder, codec, seed, K values, repeats and bootstrap draws.

## Decision rule

The primary claim is supported only if, for the no-defense ECAPA condition on
the held-out test speakers, the K=16 aggregation gain over K=1 is positive and
its paired 95% confidence interval excludes zero. Defense effectiveness is a
separate comparison of that curve and its final attack outcomes across systems.
