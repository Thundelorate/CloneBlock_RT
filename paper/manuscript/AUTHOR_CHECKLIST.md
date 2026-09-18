# Author decisions before submission

## Required immediately

- Confirm the exact title and whether `CloneBlock` or `CloneBlockRT` is the
  public method name.
- Supply author order, affiliations, email addresses, and ORCIDs.
- Confirm which prior manuscript authors qualify for this substantially revised
  submission.
- Verify the live submission deadline in the paper-management system because
  the two official ICASSP pages currently display different dates.

## Scientific ownership

- Write and approve the 100--150 word abstract.
- State the contribution without calling the clean-information oracle a
  certified upper bound.
- Approve the interpretation of the mixed XTTS result and the weak absolute
  WER backend.
- Decide whether the missing ClearMask and Enkidu reruns are framed as a scope
  limitation or completed after obtaining auditable implementations.
- Confirm that the threat model is session-level and aggregation-aware, and
  that `tele_defended` is the primary realistic embedding source.

## Final audit

- Re-run `python scripts/export_icassp_evidence.py` after any experiment change.
- Ensure every manuscript number occurs in `evidence_manifest.json` or an
  explicitly cited external source.
- Check that quality WER uses official full-utterance VCTK transcripts; do not
  reuse the old crop-level pseudo-reference WER.
- Keep raw datasets, model caches, generated audio, and checkpoints out of Git.
- Archive the exact configuration, seeds, environment, logs, and result tables.
