# DeBERTa Dataset Expansion Checkpoint

**Status: read-only checkpoint, end of session.** No examples created or modified, no production code touched, no training run. This document records the current state and the open decision points for the next session.

## Current Dataset

**100 seed + 50 hand-authored = 150 examples**

- Original validated 100-example seed: `main_cap/cap/artifacts/seed_dataset_v1/seed_v1_3_repaired.jsonl` (the final repaired/judged version) — **unchanged since the last checkpoint**, confirmed by direct inspection (100 records, same content).
- New 50-example hand-authored batch: `main_cap/cap/artifacts/hand_authored_50/hand_authored_50_v1.jsonl` + judged companion `hand_authored_50_v1_judged.jsonl` — **unchanged since authored**, confirmed by direct inspection (50 records each).
- Both artifact sets live under `main_cap/cap/artifacts/`, which is gitignored — neither is committed, and neither should be until a deliberate decision to do so.

## Validation Status

**100-example seed** (from the prior repair/judging checkpoints):
- Schema-valid, all 12 approved hard cases (A–L) present and matching their current (repaired) target vectors
- Production SBERT near-duplicate check: 0 pairs
- `target_vs_judge_agreement`: 0 residual mismatches (fully resolved as of the last repair pass)
- `grounding_fidelity`: 1 flag, the one intentional genuine contradiction (`seed_v1_037`) — working as designed, not a defect

**50-example hand-authored batch** (this session):
- Schema validation: 50/50 valid
- Profile-blind judging: 50/50 judged, judge saw only question+grounding+expected_concepts+answer, never `target_profile`
- Target-vs-judge agreement: 50/50 within tolerance (after one example repair — `hand50_v1_005`'s grounding language was thin relative to its intended target; the *answer* was repaired, not the label)
- Exact duplicates: 0 (within the 50, and against the 100-seed)
- SBERT near-duplicates: 0 pairs across the **combined 150-example pool**
- Banned quality phrases: 0
- Grounding fidelity: 0 flags (1 found and repaired pre-judging — a technology mention added to its project's grounding list rather than removed from the answer, since it was a plausible real dependency)
- Source-ID collisions with the seed's 12 projects: 0 (14 new, distinct source IDs)

**Combined 150-example pool:**
- Total examples: 150
- Unique answers: 150 (0 exact duplicates)
- Unique questions: 145 (5 exact repeats — all pre-existing, intentional reuse across different hard-case profiles within the original seed's own design, not a new issue)
- Distinct source/group IDs: 26 (the seed's original 12 + this session's 14 new)

## Current Coverage

- **Domains:** 26 total source groups across 26 distinct projects, spanning the seed's original 12 domains plus 14 new ones added this session (frontend, DevOps, standalone security, standalone mobile, embedded/systems, backend/web, distributed systems, databases, networking, ML, computer vision, NLP, data engineering, cloud).
- **Reasoning types:** all 10 `ReasoningType` values represented across the 50 new examples (explanation 12, trade_off_analysis 6, debugging 6, design 5, reflection 5, application 5, decision_making 4, recall 3, optimization 2, ownership 2).
- **Question types:** 48 `project_deep_dive` / 2 `project_overview` in the new batch; combined with the seed's own 88/12 split.
- **Dimension distributions (new 50, judged):** technical_correctness mean 3.50, depth_specificity mean 2.64, relevance_completeness mean 3.42, grounding_ownership mean 2.36 — full 0–4 range represented on every dimension, no collapse.

## Known Gaps

Recorded for a future targeted batch — **not treated as acceptance failures**:

1. **Detailed + irrelevant** (off-topic) — 0 examples in the new 50 batch.
2. **Project/resume contradiction** — 0 examples in the new 50 batch.
3. **Strong ownership + weak technical correctness** — 0 clean examples (two "unsupported ownership" examples exist, but neither pairs strong genuine ownership with an actual wrong technical claim).
4. **Clean textbook-vs-project-specific pairing** — only partial coverage; a few vague/generic answers exist, but none cleanly mirror the seed's own textbook-recitation pattern (describing the general concept without ever committing to what the specific project did).

**Reasoning-type imbalance:**
- `explanation` is relatively overrepresented (12/50).
- `optimization` and `ownership` are relatively thin (2/50 each).

## Important Finding

The existing deterministic rewrite pipeline (`deterministic_rewrite.py` / `deterministic_rewrite_pipeline.py`) currently produces **near-zero useful yield** against naturalistic seed/hand-authored prose — a real dry-run (18 attempts across 6 diverse seed examples × 3 styles) produced **0 accepted rewrites**, almost entirely rejected for exceeding the near-duplicate similarity ceiling (0.97). The transforms were built for, and validated against, an earlier templated synthetic corpus (Experiment 1/2), not naturalistic hand-authored prose. **This pipeline should NOT be used for bulk expansion without dedicated engineering work on the transform library first** — see the Phase C audit for full detail. Mechanically (label/grounding/lineage preservation) the pipeline is sound; the yield problem is structural, not a bug to patch trivially.

## Current Decision

**Stop expansion for today.** No further examples will be created or modified this session.

## Next Decision Point

Tomorrow, decide whether to:

**A.** Create a small targeted coverage batch addressing the four known gaps and the reasoning-type imbalance above.

**B.** Run a small legally-usable TechQA pilot (per the Phase C audit's recommendation: hand-inspect ~20–30 rows for format/domain fit before any bulk decision).

**C.** Invest in improving the deterministic rewrite engine's transform library so it can produce meaningful yield against naturalistic prose.

**D.** Some combination of the above.

**This decision is not made here — it is recorded as an open choice for the next session.**

## Training Status

**The 150-example pool is NOT yet the final DeBERTa training dataset.** It is an expansion/curation pool. Before any training run, the following still need to happen:

- Decide the final dataset size (the original 1,500–2,500 target vs. a revised, evidence-based number — see the Phase C audit's honest recalculation)
- Potentially add targeted examples for the four known coverage gaps
- Potentially evaluate legally usable real technical data such as TechQA (small pilot only, not bulk import)
- Establish final train/validation/test grouping (group-aware, by `source_id`, per the existing `split_dataset_by_group` mechanism)
- Perform final leakage checks on the assembled dataset
- Finalize dataset composition (original / hand-authored / public-real / rewrite strata, clearly tagged and never silently merged)
- Build and freeze the training split
- Train the new DeBERTa-v3-base four-head model **from scratch** (the current deployed checkpoint was trained on the old 12-dimension scheme and (question, answer)-only input — it is not compatible with the four-dimension, context-aware scheme this whole workstream has built)
- Evaluate against a held-out benchmark

**None of these steps were performed tonight.**
