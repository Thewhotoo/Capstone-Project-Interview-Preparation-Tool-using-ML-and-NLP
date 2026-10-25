# V4 Diagnostic Dataset

**Status: implemented, validated, isolated diagnostic benchmark. NOT wired
into any training pipeline. No training has been run against it.**

This directory implements the 58-example V4 diagnostic design proposed in
`docs/architecture/V3_Forensic_Analysis_and_V4_Diagnostic_Design.md`
(Section 6). Its purpose is to determine, via **read-only inference against
the existing V3 checkpoint** (not done in this pass — building and
validating the dataset is), whether the evaluator can distinguish:

1. detailed ≠ relevant
2. technical vocabulary ≠ technically correct
3. relevant ≠ complete
4. shallow ≠ incomplete
5. technically correct ≠ personally grounded
6. project-specific ≠ personally owned

## Files

- `build_v4_diagnostic.py` — the 58 examples as an in-file literal, plus the
  script that writes `v4_diagnostic_58.jsonl` + `manifest.json`. Re-run with
  `python build_v4_diagnostic.py` to regenerate after any edit.
- `v4_diagnostic_58.jsonl` — the dataset, one JSON object per line.
- `v4_input_builder.py` — the one sanctioned function
  (`build_v4_model_input`) for turning a V4 record into the (text_a, text_b)
  pair a real model call would see. Mirrors `model_backbone.
  build_dimension_input_text`/`build_dimension_pair`'s shape without
  importing production code, so V4 stays decoupled while still being
  checked against the real input contract.
- `validate_v4_diagnostic.py` — runs every requested validation check plus
  an SBERT near-duplicate check (`all-MiniLM-L6-v2`, cosine 0.92 threshold,
  same model/threshold as every prior batch in this project) against V4
  internally and V4 vs. the frozen 220-example pool. Writes
  `validation_report.json`.
- `validation_report.json` — the last validation run's full output.
- `manifest.json` — category/pair-group/source_id summary, written by the
  builder.

## Isolation guarantees (by construction, not just convention)

- Every `source_id` is prefixed `v4h_` (19 distinct hypothetical projects,
  none overlapping any of the 64 real `source_id`s across the frozen
  170/220-example pool).
- Every example carries `"hypothetical_source": true` and an
  `isolation_note` explaining it is not derived from any real candidate.
- `grounding.summary` is `""` for all 58 examples — no enrichment wiring, no
  path for an answer or a first-person claim to leak into the grounding
  channel.
- **No file in this directory is imported by `four_dim_experiment_split.py`,
  `four_dim_experiment_v2_split.py`, `CORE_POOLS`, or
  `run_four_dim_training.py`.** Verified both by `validate_v4_diagnostic.py`
  (greps those two files for `v4_diagnostic`/`v4h_` — 0 hits) and by
  `test_v4_diagnostic.py::TestV4NotWiredIntoTrainingPipeline`.
- The dataset is **not** in any `CORE_POOLS`-style tuple, has no split.json,
  and is not referenced by any experiment name in `run_four_dim_training.py`
  (`v1`, `v2`, `v3`). Using it for training would require a deliberate,
  separate, future change — it cannot happen by accident.

## Rationale metadata

Every example has a `rationale` object (one string per dimension) recording
*why* the gold label was assigned. This is for human review only.
`v4_input_builder.build_v4_model_input` reads only
`question`/`grounding.title`/`grounding.technologies`/`grounding.summary`/
`expected_concepts`/`answer` — `validate_v4_diagnostic.py`'s
`rationale_never_in_model_input` check confirms none of `rationale`,
`gold_labels`, `diagnostic_category`, `pair_group_id`, `hypothetical_source`,
or `isolation_note` ever appears in the built model-input text, for all 58
examples.

## Design summary

20 pair/contrast groups, 58 examples:

| diagnostic_category | count | groups |
|---|---|---|
| relevance_alignment | 16 | REL-1..8 (2 each: off-topic/generic vs. directly relevant) |
| multipart_completeness | 9 | MP-1..3 (3 each: both parts / one part / neither-or-one-wrong) |
| technical_correctness | 12 | TC-1..3 (4 each: concise-correct / detailed-correct+mechanism / detailed-subtly-incorrect / confident misconception) |
| depth_control | 6 | DEP-1..2 (3 each: shallow / +mechanism / +mechanism+tradeoff) |
| grounding_ownership | 9 | GRD-1 (5: generic / project-specific-no-ownership / explicit-ownership / unsupported-ownership-claim / ownership+tradeoff), GRD-2 (4, same shape minus the 5th) |
| cross_dimension | 6 | XD-1 (3: ownership framing swings, everything else held constant), XD-2 (3: relevance swings, everything else held roughly constant) |

Within every group, the question and `grounding.title`/`source_id` are held
identical (validated programmatically) — only the answer varies, and it
varies specifically along the one dimension the group targets.

## Gold label distributions (58 examples)

| dim | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| technical_correctness | 3 | 2 | 5 | 6 | 42 |
| depth_specificity | 5 | 3 | 10 | 32 | 8 |
| relevance_completeness | 5 | 8 | 3 | 6 | 36 |
| grounding_ownership | 8 | 3 | 29 | 8 | 10 |

Unlike the naturalistic V1–V3 pool, TC and relevance are still skewed toward
4 here because most groups include a "correct/relevant" reference answer
per contrast pair, not because V4 avoids low-tier cases — every TC and
relevance group has at least one deliberately low-tier member (0 or 1),
which is what makes the pairs diagnostic. Depth is deliberately kept small
and mid-weighted (32/58 at tier 3) since V3 already handles it well; it is
a sanity-check baseline, not a focus.

## Known review notes (not defects, flagged for transparency)

1. **`v4_diag_dep1_b` vs `v4_diag_dep1_c`** — SBERT cosine 0.9342, just above
   the project's usual 0.92 near-duplicate threshold. This is intentional:
   (c) is (b)'s exact mechanism sentence plus one added tradeoff sentence,
   by design (the "correct+mechanism" → "correct+mechanism+tradeoff" depth
   progression). Reviewed and accepted, not reworded, because the intended
   diagnostic signal specifically requires (c) to be recognizable as "the
   same mechanism, plus more" — rewording to reduce similarity would blur
   the exact contrast being tested. `DEP-2`'s equivalent pair (b/c) stayed
   under threshold without any special-casing.
2. **An earlier draft of 5 examples (`rel1_a`, `rel4_a`, `mp1_b`, `dep1_a`,
   `dep2_b`) accidentally reused answer text verbatim from the real V3
   failure examples quoted in the forensic-analysis request** (cosine 1.0
   against `v2t50_v1_027`, `v2t50_v1_032`, `seed_v1_015`, `hand50_v1_047`,
   `v2t50_v1_011` respectively) — caught by the SBERT-vs-frozen-pool check
   in this same implementation pass, before any commit. All 5 were rewritten
   with original phrasing preserving the same diagnostic intent/gold labels
   and re-validated at 0 cross-pool near-duplicates. See git-free session
   history; nothing was ever committed with the duplicate text.
3. **`v4_diag_grd1_d` and `v4_diag_grd2_d`** (the two "unsupported ownership
   claim" examples) are the most subjective labels in the set — they hinge
   on the judgment call that first-person phrasing without any verifiable
   specific detail should NOT be scored as ownership, which is explicitly
   the point being tested (per the task's "do not reward first-person
   wording by itself" instruction) but is inherently a closer call than the
   other, more mechanically clear-cut examples. Flagged for extra scrutiny
   if V4 results for these two are surprising.
4. **`v4_diag_xd2_b`/`v4_diag_xd2_c`** hold grounding/TC constant while
   relevance swings, but depth also drifts down slightly (3→2) alongside
   relevance in both variants, since the off-topic/adjacent answers are
   naturally somewhat less mechanistic than the on-topic reference answer.
   This is disclosed in each example's own `rationale.depth_specificity`
   rather than treated as a clean, single-dimension swing — XD-2 tests
   relevance isolation less perfectly than XD-1 tests ownership isolation.

## Running validation

```
cd main_cap/cap/artifacts/v4_diagnostic
python build_v4_diagnostic.py        # regenerate v4_diagnostic_58.jsonl + manifest.json
python validate_v4_diagnostic.py     # run all checks + SBERT, write validation_report.json
```

Or via the test suite: `python -m pytest test_v4_diagnostic.py -q` from
`main_cap/cap/`.

## Explicitly NOT done in this pass

- No training run of any kind.
- No change to `model_backbone.py`, `model_heads.py`, `model_dataset.py`,
  or any other production/architecture file.
- No change to `four_dim_experiment_split.py`, `CORE_POOLS`, or either V2
  split (`four_dim_experiment_v2/split.json`).
- No modification to any file under `seed_dataset_v1/`, `hand_authored_50/`,
  `gap_coverage_20/`, `v2_targeted_50/`, `v3_grounding/`,
  `four_dim_experiment_v1/`, or `four_dim_experiment_v2/`.
- V4 has not been run through inference against the V3 checkpoint yet —
  that is the explicit next step (Phase 7 of the forensic-analysis report),
  not part of this dataset-implementation pass.
- Nothing in this session was committed or pushed.
