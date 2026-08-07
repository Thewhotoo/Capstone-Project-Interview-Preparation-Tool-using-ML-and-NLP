# Experiment 2 vs. Experiment 3 (Relabeled) — Detailed Comparison

All numbers below are computed directly from `artifacts/experiment_2/dataset.jsonl` and
`artifacts/experiment_3_relabeled/dataset.jsonl` (2,479 examples each, identical
`example_id` set, identical train/val/test split). Full machine-readable version:
[`statistics.json`](statistics.json).

## 1. What is identical between the two datasets

| Property | Experiment 2 | Experiment 3 (Relabeled) |
|---|---|---|
| Example count | 2,479 | 2,479 |
| `example_id` set | — | **identical** |
| Train/val/test split | 1,738 / 379 / 362 | **identical, reused unchanged** |
| Tier distribution | excellent 445, good 449, adequate 446, weak 443, poor 448, contradictory 123, off_topic 125 | **identical** |
| `answer_text`, `provenance`, `concept_labels`, `missing_reasoning_labels`, `contradiction_label`, `overall_label`, `metadata` | — | **identical, byte-for-byte** |
| `technical_accuracy`, `technical_depth`, `resume_grounding` scores | — | **identical** — Stage 1A deliberately does not touch these three (no recipe-derived signal exists for them; inventing one was explicitly rejected) |

**Relabeling changes exactly one thing**: `TrainingExample.labels.dimension_labels` for the
8 dimensions Stage 1A does derive a signal for (`communication`, `completeness`,
`architecture`, `tradeoffs`, `ownership`, `testing` — `debugging` and `scalability` have no
examples in this dataset's reasoning-type mix, see Section 5).

## 2. Headline defect this fixes

Experiment 2's dimension scores were **not independently derived** — every relevant
dimension for an example received the exact same value, driven purely by `quality_tier`
(`training_example_assembler._dimension_labels()`). The result: a model trained on
Experiment 2 could never see an example where `technical_accuracy` was high while
`communication` was poor, or `architecture` was strong while `debugging` was weak — every
dimension moved in lockstep with every other one, for every single example.

## 3. Aggregate evidence the defect is reduced

| Metric | Experiment 2 | Experiment 3 (Relabeled) | Change |
|---|---|---|---|
| Mean absolute pairwise correlation, all 11 dimensions | **1.000** | **0.918** | ↓ |
| Mean absolute pairwise correlation, excluding the 3 untouched dims | **1.000** | **0.869** | ↓ |
| Exact-tie rate — how often 2 dimensions in the *same example* land on the literal identical score, across the 8 relabeled dims | **100.0%** (7,850/7,850 pairs) | **16.6%** (1,299/7,850 pairs) | ↓ (the most direct evidence — literal duplication dropped by 60+ points) |

> **Why raw correlation only dropped to 0.918 rather than further**, and a note on
> interpreting it: correlation is dominated by the shared tier-baseline term that's still
> common to every dimension by design (a genuinely bad answer *should* be somewhat
> correlated across dimensions — that's realistic, not a defect). The exact-tie rate is the
> more direct diagnostic for "is this dimension a literal copy of another," and it fell
> sharply. See Section 4 for how the two fixes interact with this number.

## 4. The two fixes implemented this session, and their measured effect

### Fix 1 — `completeness` no longer silently falls back to the flat tier value

**Before**: `completeness` requires `intended_concept_inclusion` targets to compute a
coverage ratio. ~46% of examples (REFLECTION/OWNERSHIP-reasoning-type questions, which have
no checkable technical concepts by design) carried zero concept targets, so `completeness`
silently reverted to the exact pre-relabeling flat tier value for those examples —
defeating Stage 1A's purpose for nearly half the dataset.

**Fix**: when concept targets don't exist, `completeness` is now derived from
`intended_reasoning_category_targets` instead — a presence-weighted average of
`(1 - severity)` across every sampled reasoning category for that example. This measures a
different but equally legitimate notion of breadth ("coverage of the required reasoning"
rather than "coverage of expected concepts"), using the only other already-serialized
evidence the recipe provides. Falls back to the flat tier value only when *both* signals are
absent (true off-topic recipes).

| | Experiment 2 (pre-relabel) | Exp. 3 relabel, before fix | Exp. 3 relabel, after fix |
|---|---|---|---|
| `completeness` == flat tier value | 100% (2,479/2,479, by definition) | **50.4%** (1,250/2,479) | **6.6%** (164/2,479) |

Of the remaining 164: **125 are the legitimate off-topic fallback** (5.0% of the dataset,
by design — off-topic recipes carry no targets of any kind), and **39 are coincidental
numeric ties** (e.g. an ADEQUATE-tier example whose computed concept-coverage ratio happens
to equal 0.50 exactly) — not fallback failures.

### Fix 2 — WEAK/POOR dimension scores no longer saturate to a hard 0.0

**Before**: `communication`/`architecture`/`tradeoffs`/`ownership`/`testing` were scored as
`tier_baseline - severity`, clamped to `[0.0, 1.0]`. Because `_REASONING_GAP_PROFILE`'s
sampled severity floor for WEAK (0.50) and POOR (0.65) already exceeds those tiers' own
dimension baselines (0.30 and 0.12), the subtraction is mathematically guaranteed negative
whenever a gap rolls "present" — **100% of present-case WEAK/POOR scores clamped to exactly
0.0**, collapsing a would-be graded signal into a binary one.

**Fix**: severity is now interpreted as a *proportional* reduction of the tier's own ceiling
(`tier_baseline * (1 - severity)`) rather than an absolute point deduction — applied
entirely in the interpretation layer (`dataset_relabeling.py`). `generation_recipe.py`'s
`_REASONING_GAP_PROFILE` was deliberately left untouched, per this project's "don't modify
upstream generation unless downstream interpretation cannot solve the problem" rule —
several alternative mappings were evaluated against the real sampled severities before this
one was selected (see the module docstring in `dataset_relabeling.py`, "REVISION 2").

| | Exp. 3 relabel, before fix | Exp. 3 relabel, after fix |
|---|---|---|
| WEAK/POOR dimension scores exactly 0.0 | **80.8%** (1,459/1,805) | **0.0%** (0/1,805) |

Verified against the real dataset that the new mapping (a) never produces exactly 0.0 for
any sampled severity (max sampled severity was 0.949, never 1.0), (b) preserves tier
ordering in aggregate (mean present-case score is monotonically
POOR < WEAK < ADEQUATE < GOOD < EXCELLENT across all 5 affected dimensions), and (c) that
per-example score ranges for adjacent tiers still overlap at the boundary in a way that
mirrors — and is actually *smaller than* — the overlap that already existed pre-fix for the
non-saturating tiers (ADEQUATE/GOOD/EXCELLENT); this is judged to be realistic per-example
variance, not a defect (a POOR answer with no reasoning gap and a WEAK answer with a severe
one landing near the same score is the same kind of ambiguity a real interviewer's grading
would show).

## 5. A pre-existing dataset property, unrelated to either fix (observed, not changed)

Experiment 2's underlying `QuestionSpecification` set only samples 6 of the 10
`ReasoningType` values (`recall`, `explanation`, `application`, `reflection`, `ownership`,
`decision_making` — never `debugging`, `design`, `optimization`, `trade_off_analysis`). As a
consequence, the `debugging` and `scalability` dimensions never appear in
`dimension_labels` anywhere in this dataset (0 of 2,479 examples), in both Experiment 2 and
Experiment 3 — this is a property of which questions exist in the synthetic library, not
something Stage 1A introduced or could fix, and not in scope for this session's work.

## 6. Per-dimension mean / stdev, before vs. after

| Dimension | Exp. 2 mean (stdev) | Exp. 3 mean (stdev) |
|---|---|---|
| `technical_accuracy` | 0.4908 (0.2852) | 0.4908 (0.2852) — unchanged |
| `technical_depth` | 0.4922 (0.2863) | 0.4922 (0.2863) — unchanged |
| `resume_grounding` | 0.4908 (0.2852) | 0.4908 (0.2852) — unchanged |
| `communication` | 0.4908 (0.2852) | 0.4065 (0.3194) |
| `completeness` | 0.4908 (0.2852) | 0.6410 (0.3289) |
| `architecture` | 0.4863 (0.2846) | 0.4010 (0.3189) |
| `tradeoffs` | 0.4775 (0.2872) | 0.3932 (0.3201) |
| `ownership` | 0.4954 (0.2823) | 0.4126 (0.3210) |
| `testing` | 0.4751 (0.2896) | 0.3991 (0.3222) |

Full 10-bin histograms for every dimension, both datasets: see `statistics.json` →
`per_dimension_histograms_10bin`.

## 7. Regression check

Full repository test suite: **1,213 passed, 21 subtests passed, 0 failed** — prior baseline
was 1,209 (plus 4 new tests added this session for the two fixes). Zero regressions
anywhere outside `dataset_relabeling.py`/`test_dataset_relabeling.py`.
