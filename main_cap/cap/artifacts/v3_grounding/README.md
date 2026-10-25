# V3 Data Repair — Grounding Enrichment + Expected-Concepts Repairs

**Status: DATA REPAIR ONLY. No training. No architecture/hyperparameter
changes. No question/answer text changes. No gold-label changes. No V2
split changes.** This is a versioned, separate artifact — the training
JSONLs were touched only for the 3 explicitly-approved `expected_concepts`
repairs (Phase 1); grounding itself lives entirely in this directory and is
not yet wired into the training/inference input builders.

## What changed vs. what didn't

**Changed (3 files, 1 field, 3 examples total):**
| File | example_id | Field |
|---|---|---|
| `artifacts/hand_authored_50/hand_authored_50_v1.jsonl` | `hand50_v1_020` | `expected_concepts` |
| `artifacts/v2_targeted_50/v2_targeted_50_v1.jsonl` | `v2t50_v1_041` | `expected_concepts` |
| `artifacts/seed_dataset_v1/seed_v1_3_repaired.jsonl` | `seed_v1_089` | `expected_concepts` |

Verified by `validate_grounding_proposals.py` check
`only_expected_concepts_changed_in_pool_files` (field-level diff, not just
file-level) and `exactly_the_3_approved_examples_changed`.

**Not changed:** `gap20_v1_008`, `seed_v1_057`, `gap20_v1_005` (explicitly
held per instruction); all question/answer text; all gold `target_profile`
labels; `source_id`/group assignments; `artifacts/four_dim_experiment_v2/split.json`
(170/220 pool counts and the 166/27/27 split are untouched — re-verified
programmatically, not assumed).

## Files in this directory

- `build_grounding_proposals.py` — the fragment library (project-specific
  facts, one entry per `(source_id, topic)`) and the example→fragment
  assignment table. Running it regenerates `grounding_proposals.jsonl` from
  scratch, deterministically, from the hand-curated data inside the script —
  it does not re-derive facts from the answer text at runtime, so every
  fragment's wording was authored and evidence-checked by hand (Task 1/3 of
  the prior read-only audit), not generated.
- `grounding_proposals.jsonl` — 42 proposals, one per enriched example. Schema:
  `example_id, source_id, grounding_text, evidence_example_ids, grounding_scope, confidence`.
- `expected_concepts_repairs.json` — the 3 applied Phase-1 repairs plus the
  regenerated 5-item Phase-2 mismatch audit (2 HIGH-confidence, 2 MEDIUM,
  1 project-wide MEDIUM) — **all 5 are `status: "pending_approval"`, none applied.**
- `validate_grounding_proposals.py` — the Phase 5 validation suite (16 checks).
- `validation_report.json` — machine-readable output of the last validation run.

## Methodology (question-topic-scoped grounding)

For each of the 46 multi-example projects, examples were grouped by
`source_id` and clustered by the specific sub-topic their *question* asks
about (not by project as a whole). A grounding fragment for a topic was only
built when **at least two siblings on that exact sub-topic** exist and at
least one of them is a reliable, project-specific, non-generic,
non-contradicted account. An example's own answer is **never** used as
evidence for its own grounding (`no_self_sourcing` check) — every fragment
assigned to example X is built exclusively from what X's *siblings* say, so
the grounding cannot be a near-restatement of the very answer being judged.

This is stricter than simply "one summary per project": several projects
with rich, detailed answers (SentinelAuth, SupportBot, RaftKeeper, and 20
others) ended up with **zero** enrichable examples, because every one of
their answers addresses a *different* sub-topic — richness without
topic-repetition provides no valid cross-sibling evidence under this rule.
See `validation_report.json`'s
`multi_example_projects_with_zero_safe_grounding_list` for the full set (23
of the 46).

Grounding text is deliberately neutral ("X uses...", "X was chosen
because...") — no first-person or attributional language anywhere (enforced
by the `no_first_person_in_grounding` check), so it can never influence or
be mistaken for corroboration of the `grounding_ownership` dimension.

Misconception/contradicted-sibling examples (11 flagged, e.g. MeshRouter's
wrong "circuit opens permanently" claim, VaultGuard's wrong
symmetric-cipher claim) and vague unsupported-ownership examples (5 flagged)
were excluded as **evidence sources** everywhere (`no_misconception_evidence`,
`no_unsupported_ownership_evidence` checks). Misconception examples *can*
still **receive** correct grounding from their reliable siblings (this is
intended — it's what lets the technical_correctness dimension be judged
against a stated truth); unsupported-ownership examples receive no
grounding at all, per the Phase-3 instruction and the earlier hard-case
safety review's "omit" recommendation for that category.

Irrelevant-but-detailed examples (answer talks about a different topic than
the question asked) are grounded on their **own question's** topic, not on
whatever their answer happens to discuss — this is what preserves the
irrelevance signal instead of accidentally validating the off-topic content.

## Results summary (from `validation_report.json`)

- 220 V2 pool examples total.
- **42 examples received a grounding proposal; 178 are left unchanged**
  (title + technologies only, same as the current V1/V2 baseline).
- Confidence: **19 HIGH, 23 MEDIUM, 0 LOW.**
- 46 multi-example projects; **23 have zero safe grounding fragment for any
  of their examples** (single-topic-per-example, no cross-sibling
  corroboration available) — listed in the report.
- All 18 single-example projects: **0 enriched**, as required.
- **All 16 validation checks pass** — see `validation_report.json` →
  `all_checks_passed: true`. This includes an SBERT cosine-similarity check
  (`all-MiniLM-L6-v2`, same model/threshold as every prior batch's
  near-duplicate check) between each proposed grounding text and the
  *receiving* example's own answer — 0.92 threshold, 0 violations.

## What this artifact does NOT do

- Does not modify `four_dim_experiment_split.py` / `four_dim_experiment_v2_split.py`
  / `model_dataset.py` / `model_evaluator.py` — `ProjectGrounding.summary`
  is still `""` for every example when loaded through the existing pipeline.
  Wiring `grounding_proposals.jsonl` into the actual training/inference
  input (`RELEVANT CONTEXT`) is a separate, not-yet-approved step.
- Does not retrain or evaluate any model.
- Does not apply the 5 regenerated Phase-2 `expected_concepts` mismatch
  corrections — those remain `pending_approval` in
  `expected_concepts_repairs.json` per your instruction to hold them for
  review.

## Next step (not taken)

Pending your review of the Phase 2 mismatch audit and this grounding
artifact: (a) approve/reject the 5 pending `expected_concepts` corrections,
(b) approve wiring `grounding_proposals.jsonl` into a new `summary`-bearing
`ProjectGrounding` construction path for the 42 enriched examples only
(178 unchanged examples would continue exactly as today), (c) only then
consider a V3 training run — still not requested or performed here.
