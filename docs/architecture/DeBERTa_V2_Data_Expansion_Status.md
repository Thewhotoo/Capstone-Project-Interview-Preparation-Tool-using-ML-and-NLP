# DeBERTa V2 Data Expansion Status

**Last updated: 2026-09-08.** This is a data-collection-only checkpoint. No
training, no model changes, no merge into any experiment split.

## Trigger
V1's real 22-example held-out test evaluation (base `microsoft/deberta-v3-base`,
128/20/22 group-aware split, seed `four_dim_experiment_v1_41`, best epoch 8,
val mean QWK 0.5982) surfaced two concrete weaknesses:
- **technical_correctness**: QWK 0.0902 despite MAE 0.409 / within-1
  95.45% — a gold-3→predicted-4 collapse at the 3/4 boundary.
- **relevance_completeness**: QWK 0.2787, MAE 1.000 — systematic
  over-prediction toward tiers 3–4 on answers that are detailed/technical
  but don't actually satisfy the specific question asked.

depth_specificity (QWK 0.8526) and grounding_ownership (QWK 0.8655) were
already strong and were deliberately NOT the focus of this batch.

## What was created
`main_cap/cap/artifacts/v2_targeted_50/` — 50 new, original, hand-authored
examples. Full detail in that directory's own `README.md`; this document
summarizes for the cross-session status trail.

### Exact counts
| Category | Count | Requested |
|---|---|---|
| Technical Correctness boundary | 25 | 25 |
| Relevance & Completeness boundary | 20 | 20 |
| Grounding & Ownership boundary | 5 | 5 |
| **Total** | **50** | **50** |

### Target vs. judged label distributions
Identical (see artifact README's dimension-distribution table) — 50/50
target-vs-judge agreement within tolerance, mean max-delta 0.0, maximum
delta 0. Two targets were corrected against the rubric's own tier text
*before* judging (relevance 2→1 on one general-not-specific example;
grounding 1→2 on one team-vs-personal example) — see the artifact README's
"Validation performed" section for the specific rubric citations.

### Phenomenon coverage (all requested phenomena represented)
- TC: 7 shallow-but-correct, 9 solid-but-missing-a-qualification (post-finalization; one example was reclassified between these two buckets — see "Finalization pass" below), 6
  genuinely excellent, 3 plausible-but-meaningfully-wrong.
- Relevance: all 8 requested phenomena present (detailed+irrelevant,
  one-part-of-multipart, general-not-specific, textbook-vs-project,
  partial+missing-component, fully-complete, overly-narrow,
  strong-info-wrong-ask).
- Grounding: all 5 requested boundary types present.

### Reasoning-type distribution
explanation 12, design 10, decision_making 9, trade_off_analysis 7,
debugging 5, optimization 3, reflection 3, recall 1. (`application`/
`ownership` not used — this batch targets dimension boundaries, not
reasoning-type diversity, which the existing 170-pool already covers.)

### Domain/source distribution
13 requested TC topics all represented (backend 7, databases 6,
distributed_systems 6, system_design 4, ml 4, security 4, networking 3,
caching 3, concurrency 3, deployment 3, performance 3, testing 2, mobile 2).
21 new distinct source/project groundings, 0 collisions with the existing
43 across the frozen 170-pool.

### Duplicate results
0 exact (question, answer) duplicates within the 50, and 0 against the
combined 220 (170 frozen + 50 new).

### SBERT results
0 near-duplicate pairs (threshold 0.92, `all-MiniLM-L6-v2`) in both scoped
checks: 50-internal (1,225 pairs) and 50-vs-existing-170 (8,500 pairs).

### Grounding fidelity results
1 raw flag found during authoring (QuickLookup's abbreviated 2-item tech
list didn't include Postgres, which one answer legitimately references as
the cache's source-of-truth DB) — repaired by completing the grounding's
technology list (same precedent as the seed dataset's postgres/node.js
alias repairs), **not** by removing content from the answer. **0 flags on
the final batch.**

### Repaired examples
2 target-label corrections (both against the rubric's own tier text, before
judging — see above); 1 grounding-fidelity repair (tech-list completion).
No answer content was rewritten to force label agreement.

### Remaining limitations
- This batch is deliberately narrow (TC/relevance boundary + a handful of
  grounding cases) — it does not address the V1 finding that
  `technical_correctness` tier 2 was nearly absent pool-wide before this
  batch (now partially addressed: 3 new tier-2 examples), nor does it
  attempt to rebalance reasoning-type or domain coverage generally.
- Not yet merged into any split, group-checked against V1's train/val/test
  boundaries, or evaluated in a real training run — that is explicitly the
  next phase, not this one.
- SBERT near-duplicate checks used the production `all-MiniLM-L6-v2`
  cosine model (same as every prior batch), not a semantic-equivalence or
  entailment check — a genuinely paraphrased near-duplicate outside the
  0.92 cosine threshold would not be caught by this check alone.

## Validation test suite
Ran the existing `dataset_filters`/`dataset_acceptance`/schema validation
functions directly against the batch (see artifact README); no new pytest
file was added for this data-only batch (consistent with the `gap_coverage_20`
precedent, which also validated via direct function calls rather than a
dedicated test file, since these are hand-authored data artifacts, not
production code paths). Relevant existing test suites
(`test_dataset_filters_grounding.py`, `test_evaluation_dimensions.py`,
`test_four_dim_experiment_split.py`, `test_four_dim_migration.py`) were not
modified and are unaffected by this data-only addition.

## Finalization pass (2026-09-08, after human review)

A full 50-example human review flagged 7 examples for judgment-call
scrutiny plus 2 systemic gaps. Per explicit instruction, only a **narrow**
set of changes was made — no regeneration, no broad rewrite:

| Example | Change | Type |
|---|---|---|
| `v2t50_v1_007` | `coverage_category`: `tc_boundary_shallow` → `tc_boundary_missing_qualification` | Taxonomy/metadata only — all 4 dimension labels unchanged |
| `v2t50_v1_032` | `depth_specificity`: `0` → `1` | Label correction against the rubric's own tier text (tier 1 = "names things but no mechanism"; the answer names a real, if generic, mechanism) |
| `v2t50_v1_028`, `_029`, `_030`, `_036`, `_037`, `_038` | `expected_concepts` populated (2 entries each, exactly the two things the question asks for) | New field population, no other field touched |
| `v2t50_v1_022`, `_023`, `_024`, `_042`, `_043` | **No change** | Reviewed, left as defensible judgment calls |

**Zero `answer` or `question` text changed anywhere in the batch** —
verified by an exhaustive field-by-field diff over all 50 records (not
assumed). Final count: **50/50, unchanged.**

### Re-validation after finalization
- Schema: 50/50 valid.
- Exact duplicates: 0 (within 50, vs. combined 220).
- Duplicate answer strings: 0.
- Banned phrases: 0.
- Grounding fidelity: 0.
- SBERT near-duplicates: prior result (0/0, both scopes) **remains valid
  unchanged** — proven via the same diff (no answer/question text differs
  anywhere), not re-run redundantly against an identical text corpus.
- Target-vs-judged consistency: **50/50 within tolerance, mean max-delta
  0.0, maximum delta 0.** This is a profile-blind **self-consistency
  check performed in the same authoring session**, not independent
  second-rater validation — stated explicitly per review feedback, not
  described as "independent judging" or "inter-rater agreement" anywhere
  in this document.
- Frozen 170-example core pool: confirmed still exactly 170
  (`four_dim_experiment_split.load_core_pool()` reloaded and counted).
- Frozen V1 split (`four_dim_experiment_v1/split.json`): confirmed
  untouched — 128/20/22, seed `four_dim_experiment_v1_41`.
- Relevant test suite (82 tests) + full repository suite: **1713 passed,
  33 subtests passed, 0 failed** — unchanged from before this pass (no
  test files were added or modified; this was a data-only finalization).

## Phase 5 — V2 experiment pool + split (2026-09-08)

**This section describes a NEW, separate experiment from V1.** V1's pool
(170), split (`four_dim_experiment_v1/split.json`, 128/20/22, seed
`four_dim_experiment_v1_41`), and trained checkpoint are all frozen and
untouched. V2 is a distinct 220-example pool with its own split, built by
`build_four_dim_v2_split.py` via the new `four_dim_experiment_v2_split.py`
adapter and the existing, unmodified `training_experimentation.split_dataset_by_group`.

### 220-example V2 pool
170 frozen V1 core (unchanged, confirmed byte-identical by test) + 50
finalized `v2_targeted_50` = **220**. See `main_cap/cap/artifacts/four_dim_experiment_v2/README.md`
for the full report.

### V2 split
| Split | Count | % | Groups | v2_targeted_50 examples |
|---|---|---|---|---|
| train | 166 | 75.5% | 47 | 33 |
| val | 27 | 12.3% | 7 | 9 |
| test | 27 | 12.3% | 10 | 8 |

Seed: `four_dim_v2_split_348`, chosen from 800 deterministic candidates,
scored on val and test **independently** (not combined) for
technical_correctness/relevance_completeness tier diversity and
v2_targeted_50 representation — see the artifact README's "Seed selection"
for why this mattered (an earlier top-combined-scoring candidate put only
3/50 targeted examples and 0 TC-tier-2 examples in test specifically).

### Label distributions
Full 0–4 tables in the artifact README. Summary: test set has
technical_correctness {0:1, 1:1, 2:1, 3:8, 4:16} (tier-4 is 59%, not
dominant) and relevance_completeness spanning the full 0–4 range
(3/2/3/4/15). val has technical_correctness concentrated at tier 3/4 only
(0/0/0/10/17) — a real limitation, see below.

### Hard-case coverage
train: all 12 (A–L). val: B, F, H, J (4). test: A, D, I, L (4) — includes
D (relevant-but-incomplete) and I (unsupported-ownership), directly
relevant to this experiment.

### Leakage checks: **PASS**
0 source_id overlap, 0 group_key overlap, 0 exact question/answer overlap,
0 rewrite-lineage leakage, 0 examples missing a canonical label, 0
out-of-range labels — all asserted programmatically across train/val/test
pairwise.

### Limitations
1. val has zero technical_correctness tier-0/1/2 (all tier-3/4) — test
   alone carries tier-2 representation for that dimension.
2. 6 of 17 v2_targeted_50 coverage categories (each with only 1–2 total
   examples batch-wide) landed entirely in train, absent from val+test.
3. SBERT near-duplicate checks were not re-run for this split-construction
   step, since no answer/question text was created or modified here —
   only already-individually-validated examples were partitioned.

### Tests
19 new (`test_four_dim_v2_split.py`) + 68 relevant existing (`test_four_dim_experiment_split.py`,
`test_four_dim_migration.py`, `test_four_dim_training_entrypoint.py`, `test_four_dim_v2_split.py`)
all passed. Full repository suite: **1732 passed, 33 subtests passed, 0
failed** (up from 1713 — exactly the 19 new tests).

### READY FOR V2 TRAINING: the split is validated. Training itself was explicitly NOT started this phase.

---

## [Historical, pre-Phase-5] Batch validation status of v2_targeted_50 alone

The 50 examples pass every hard validation check (schema, exact-duplicate,
SBERT near-duplicate, banned-phrase, grounding-fidelity, target-vs-judge
agreement). At the time this was written, they had not yet been merged
into a V2 split — Phase 5 (above) has since built and validated that
split. This section is kept for the historical record of the batch's own
validation, prior to merging.

## Protected / untouched
Rubric, model, rewrite pipeline, RAG, planner/specification/realizer, UI,
resume parser, interview runtime, the frozen 170-example core pool, and the
frozen V1 split/checkpoint are all unmodified.
