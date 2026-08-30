# Experiment 3 (`v_experiment_3_relabeled_dimensions`) — Reproducibility Package

This package documents exactly how `v_experiment_3_relabeled_dimensions` differs from
`v_experiment_2_scaled_library`, and how to reproduce it, **without needing to read the
implementation**. It exists to give Colab (or anyone else) everything needed to trust and
reproduce this dataset.

**Status**: Stage 1A (deterministic per-dimension relabeling) is complete and approved,
including two fixes applied after an initial statistical verification found issues. This is
the final state of Experiment 3 — no further changes are planned to this dataset version.

## What Experiment 3 is, in one paragraph

Experiment 2's synthetic training examples scored every relevant evaluation dimension
(`communication`, `completeness`, `architecture`, `tradeoffs`, `ownership`, `testing`, plus
3 others) with the exact same value per example, driven purely by a coarse `quality_tier`
label — a model trained on it could never learn that `technical_accuracy` and
`communication` can diverge within one answer. Experiment 3 recomputes those per-dimension
scores from data the generation recipe *already sampled but never used for labeling* —
per-category reasoning-gap presence/severity, and per-concept inclusion status — with **zero
new text generation, zero new API calls, and zero new randomness**. It is a pure relabeling
pass on top of Experiment 2's existing answer text.

## What changed — the short version

1. **Per-dimension scores are now independently derived** instead of copying the tier value,
   for 8 of 11 dimensions (3 — `technical_accuracy`, `technical_depth`, `resume_grounding` —
   are deliberately left untouched; no recipe-derived signal exists for them).
2. **Two issues found during verification were fixed** before this dataset was approved:
   - `completeness` no longer silently falls back to the flat tier value for the ~46% of
     examples with no checkable concepts — it now derives a score from reasoning-target
     coverage instead.
   - `communication`/`architecture`/`tradeoffs`/`ownership`/`testing` no longer saturate to a
     hard `0.0` for 65–92% of WEAK/POOR-tier examples — severity is now interpreted as a
     proportional reduction of the tier ceiling, not an absolute point deduction.

Full detail, with real numbers before/after each fix: **[`COMPARISON.md`](COMPARISON.md)**.

## What did NOT change

- Example count (2,479), `example_id` set, and the train/val/test split (1,738/379/362) —
  all identical to Experiment 2, reused unchanged.
- `answer_text`, `provenance`, `concept_labels`, `missing_reasoning_labels`,
  `contradiction_label`, `overall_label`, `metadata` — untouched on every example.
- `technical_accuracy`, `technical_depth`, `resume_grounding` scores — untouched.
- The upstream generation pipeline (`generation_recipe.py`'s `_REASONING_GAP_PROFILE` and
  everything else in that module) — relabeling reads it, never writes to it. Both fixes were
  implemented purely in the interpretation layer (`dataset_relabeling.py`), per this
  project's "don't modify upstream generation unless downstream interpretation cannot solve
  the problem" rule.

## Package contents

| File | What it is |
|---|---|
| [`README.md`](README.md) | This file — the narrative entry point. |
| [`COMPARISON.md`](COMPARISON.md) | The full before/after comparison: aggregate correlation, exact-tie rate, both fixes' measured effect, per-dimension mean/stdev, a note on a pre-existing dataset property unrelated to either fix. |
| [`REPRODUCE.md`](REPRODUCE.md) | Exact commands to regenerate this dataset from Experiment 2, and how to verify your reproduction matches. |
| [`manifest.json`](manifest.json) | The real `DatasetManifest` produced by this dataset's generation — version, parent lineage, all 2,479 `example_id`s, tier distribution, label-source distribution. |
| [`statistics.json`](statistics.json) | Machine-readable version of every number in `COMPARISON.md`: full pairwise correlation matrices (both datasets), per-dimension mean/stdev/min/max, 10-bin histograms per dimension per dataset, both fixes' before/after counts. |
| [`change_summary.json`](change_summary.json) | The relabeling script's own change log: which dimensions changed for how many examples, and a 20-example sample of individual score changes (old value → new value). |
| [`provenance.json`](provenance.json) | Exact code state that produced this dataset: git commit/working-tree state, SHA-256 hashes of every file that influenced the output, the determinism guarantee, and the test-suite result at generation time. |

## Reading order for someone new to this

1. This README (you're here).
2. [`COMPARISON.md`](COMPARISON.md) for the substance — what changed and why, with numbers.
3. [`manifest.json`](manifest.json) if you need the exact example-id list or lineage metadata.
4. [`REPRODUCE.md`](REPRODUCE.md) only if you intend to actually regenerate the dataset
   yourself.

## Scope note

This package documents a **dataset**, not a model. No training, evaluation, or checkpoint
work happened as part of producing it — per this repository's current scope (dataset
generation pipeline only; all model training happens on Google Colab). The actual
`dataset.jsonl` file itself is not included in this package (2,479 examples, ~8.5MB) — it
lives at `artifacts/experiment_3_relabeled/dataset.jsonl`, gitignored, same convention as
every other experiment's generated output, and is reproducible byte-for-byte via
[`REPRODUCE.md`](REPRODUCE.md).
