# DeBERTa Dataset Rebuild — Current Status

**Last updated:** 2026-09-04

## Completed
- **Step 1:** four-dimension rubric (`main_cap/cap/evaluation_dimensions.py`, `docs/architecture/FourDimensionRubric.md`)
- **Step 2:** contextual DeBERTa input (`model_backbone.build_dimension_input_text` / `build_dimension_pair`, wired into `model_evaluator.py` and `model_dataset.py`)
- **Step 3:** dataset-generation infrastructure (this document) — **infrastructure only, no data generated**

## Current Four Dimensions
- `technical_correctness`
- `depth_specificity`
- `relevance_completeness`
- `grounding_ownership`

Canonical source: `evaluation_dimensions.EvaluationDimension` / `RUBRICS`.

## Step 3 Infrastructure
All new, additive modules under `main_cap/cap/`. No frozen generation/evaluation module was modified.

| Module | Purpose |
|---|---|
| `dimension_profiles.py` | `DimensionProfile` (4 ordinal tiers 0–4), the 12 approved hard-case vectors (`HARD_CASES` A–L) as data, `coherent_profile`/`sample_profile` for non-hard-case coverage, and `generation_guidance` — deterministic per-dimension generation instructions that describe *content* to produce, never the answer's own quality. |
| `rubric_judge.py` | `JudgeVerdict`, the `RubricJudge` protocol, `build_judge_prompt` (Step-1 rubric + Step-2 context, one dimension per call), `judge_all_dimensions`, `compute_agreement`/`MismatchPolicy`, and `GeminiRubricJudge` (temperature 0, structured output). Judge-only — never the production interview evaluator. |
| `dataset_filters.py` | Reusable leakage/quality checks: exact (q,a) duplicates, duplicate-answer counts, banned self-describing quality phrases, near-duplicate detection (reuses `rewrite_verifier_client`'s SBERT cosine — no new similarity model), answer-per-question caps, malformed-answer detection, grounding-fidelity check (reuses `generation_validation`'s technology vocabulary). |
| `human_benchmark.py` | `HumanBenchmarkItem`/`HumanAnnotation`/`HumanDimensionLabel` schema, namespaced `hb_` ids, `assert_disjoint_from_training` hard guard. Schema only — no data collected. |
| `four_dim_dataset.py` | Orchestration: `assemble_profiled_prompt` (reuses the existing promptbook, appends profile guidance), `generate_and_label` (generate → validate → filter → judge → agreement-gate → `TrainingExample`), `split_labeled` (wires `training_experimentation.split_dataset_by_group`). |
| `dataset_acceptance.py` | `evaluate_dataset` — the 12-point acceptance report (leakage, banned phrases, four-label completeness, tier distributions, hard-case coverage, category/reasoning-type coverage, source diversity, per-question cap, duplicate rate, target-vs-judge agreement, grounding fidelity) plus the four-dimension correlation **diagnostic**. |
| `test_four_dim_dataset_pipeline.py` | 31 tests, fully mocked (no network), including a mocked end-to-end run. |

## Generation Pipeline
```
DimensionProfile (target tiers, metadata only)
      ↓
assemble_profiled_prompt  — reuses the existing promptbook controllers,
                             appends per-dimension generation guidance
      ↓
GenerationClient.generate — REAL LLM (GeminiGenerationClient), injected;
                             FakeGenerationClient is never used here
      ↓
generation_validation.validate_generation — frozen QA gate (grounding
                             fidelity, malformed output, concept/reasoning
                             consistency) — reused unmodified
      ↓
dataset_filters.check_example — banned quality phrases, malformed check,
                             hallucinated-technology check
      ↓
judge_all_dimensions — independent LLM judge, ONE call per canonical
                             dimension, temperature 0
      ↓
compute_agreement — |judged_tier − target_tier| ≤ tolerance per dimension
      ↓
MismatchPolicy: DISCARD (default) or RELABEL_KEEP
      ↓
build_four_dim_example — TrainingExample; labels come from the JUDGE
```

## Leakage Protection
- **Exact (question, answer) duplicates** — `exact_qa_duplicate_indices`.
- **Duplicate answer strings** — `duplicate_answer_counts`; enforced as `duplicate_answer_rate` in the acceptance gate.
- **Near-duplicate answers** — `near_duplicate_pairs`, reusing the existing SBERT cosine accessor (`rewrite_verifier_client._semantic_similarity`) — no second similarity implementation.
- **Banned self-describing quality phrases** — regex bank in `dataset_filters.BANNED_QUALITY_PATTERNS` (covers "mentioned briefly", "demonstrated with concrete...", "generated to target", "target tier", "<tier> answer", etc.), enforced per-example and again corpus-wide in the acceptance gate.
- **Question/source grouping** — `four_dim_dataset.split_labeled` uses `training_experimentation.split_dataset_by_group`, keyed on the grounding `source_id` (the row-level `split_dataset` is not used for this pipeline).
- **Cross-split leakage assertions** — `dataset_acceptance.evaluate_dataset` checks no answer, no question, and no `source_id` spans more than one split; verified by test (`test_group_split_keeps_sources_and_answers_within_one_split`).
- **Answer-per-question cap** — `questions_over_cap`, enforced in the gate.
- **Rewrites** — deterministic rewrites are not used as an independent source in this pipeline; if ever reintroduced, they must share their origin's group key (documented decision, not yet needed since `deterministic_rewrite` isn't wired into `four_dim_dataset.py`).

## Labeling
**Final training labels come from the independent rubric judge, never from the generation target.** The `DimensionProfile` only steers what kind of answer the LLM is asked to produce; `build_four_dim_example` builds every `DimensionLabel` from `JudgeVerdict.score`, confirmed by test (`test_labels_come_from_judge_not_target_on_accept`, `test_mismatch_kept_under_relabel_keep_with_judge_labels`). The `MismatchPolicy` only decides whether a mismatched example is kept or discarded — it never substitutes the target for the judge's score.

## Human Benchmark
Schema-only (`human_benchmark.py`). Deliberately a distinct Pydantic type from `TrainingExample`, namespaced with `hb_` ids, with `assert_disjoint_from_training` as a hard guard against accidental leakage into training data. No collection, no annotation, no data yet. Intended as the **authoritative, frozen, held-out** evaluation set once populated (~150–300 real answers, per the Step-3 design report) — never used for training or hyperparameter tuning.

## Not Yet Done
- Actual dataset generation (the 1,500–2,500 training examples)
- Validation dataset generation
- Human benchmark collection (150–300 real answers, annotation, adjudication)
- DeBERTa 12→4 head migration
- DeBERTa fine-tuning
- Colab T4 training run
- Human benchmark evaluation / promotion decision
- Adaptive follow-up / Planner controller changes (explicitly out of scope for this entire workstream so far)

## Important Decisions
- **`FakeGenerationClient` is not used** anywhere in `four_dim_dataset.py` — verified by an AST-based test (`test_pipeline_does_not_reference_fake_generation_client`) that checks actual imports/usage, not just prose mentions.
- **Deterministic rewrites are not treated as an independent data source** in this pipeline.
- **Group-aware splitting is required** — `split_dataset_by_group`, never the row-level `split_dataset`, for the four-dimension dataset.
- **Dimension correlation is a diagnostic, not a hard acceptance failure.** `dataset_acceptance.evaluate_dataset` reports `four_dimension_correlation_DIAGNOSTIC` with `passed=None` unconditionally — hard-case coverage and per-dimension tier distributions are the acceptance criteria that actually gate the dataset.
- **No frozen module was modified.** `generation_recipe.py`, `prompt_controllers.py`, `prompt_assembler.py`, `generation_client.py`, `generation_validation.py`, `training_example.py`, `training_example_assembler.py`, `dataset_manifest.py`, `coverage_strategy.py`, and `training_experimentation.py` are all reused as-is.

## Verification
- New Step-3 tests: **31 passed** (`test_four_dim_dataset_pipeline.py`).
- Relevant evaluation/dataset-generation suite (Step-1/2/3 tests + generation_recipe, generation_validation, training_example, training_example_assembler, dataset_manifest, labeling_operations, coverage_strategy, synthetic_generation_pipeline, rewrite_validation, rewrite_verifier_client, deterministic_rewrite(_pipeline), dataset_relabeling, run_experiment_4_prepare_training_data, training_experimentation): **348 passed**.
- **Full repository test suite: 1614 passed, 33 subtests passed, 0 failed** (only pre-existing torch deprecation warnings).
- `git status`: 7 new Step-3 files under `main_cap/cap/`; the only *modified* files are the Step-1/2 files already accepted in prior sessions (`model_backbone.py`, `model_evaluator.py`, `model_dataset.py`) and the Phase-1 resume-parser files from an earlier workstream — nothing from this step touched them.

## Tomorrow's Next Step (superseded — see Checkpoint below)
**Code review of the Step-3 implementation first.** Only after the infrastructure is reviewed and approved should a **small pilot dataset generation** (a few dozen examples, real Gemini calls, real judge calls, full acceptance-gate report) be run to validate the pipeline against real model output before committing to the full 1,500–2,500-example generation. Do not jump directly to full-scale generation.

*(This plan changed after today's real-Gemini smoke test — see the dated checkpoint below for the current plan.)*

---

## Checkpoint — End of Day (2026-09-04)

**Current phase:** Step 3 dataset-generation infrastructure is implemented and audited. Dataset generation strategy pivoted away from Gemini today. A 100-example hand-authored seed dataset exists in the Claude Code scratchpad (not yet in the repo, not yet labeled). **No DeBERTa training has happened at any point in this workstream.**

### What was completed today
1. **Step 3 implementation audit (read-only)** — inspected `dimension_profiles.py`, `rubric_judge.py`, `dataset_filters.py`, `human_benchmark.py`, `four_dim_dataset.py`, `dataset_acceptance.py`, `test_four_dim_dataset_pipeline.py` against the 12 approved Step 3 design requirements.
   - **Result: 12/12 requirements PASS.** No modifications made, no bugs found that block proceeding.
   - **70 relevant tests passed** (`test_four_dim_dataset_pipeline.py`'s 31 + `test_evaluation_dimensions.py`/`test_dimension_input.py`'s 39, confirming Step-2 contextual-input compatibility still holds).
   - The specific concern about the `FakeGenerationClient`-exclusion test was verified: it uses real AST inspection (`ast.Name`/`ast.Attribute`/import nodes) via `test_pipeline_does_not_reference_fake_generation_client`, not a substring/string check.
   - Two minor, non-blocking findings recorded (not fixed, per read-only scope): `dataset_filters.near_duplicate_pairs` (SBERT) exists but isn't wired into `dataset_acceptance.evaluate_dataset`'s hard checks; the banned-phrase guidance test doesn't cover `technical_correctness`/`depth_specificity` tier 0 specifically.

2. **Real Gemini smoke test — FAILED, root cause identified.**
   - Ran `four_dim_dataset.generate_and_label()` wired to the real `GeminiGenerationClient` + real `GeminiRubricJudge` (no `FakeGenerationClient`) against 8 hand-built realistic recipes (4 hard cases + 4 coherent profiles, 8 distinct groundings).
   - **0/8 examples completed the pipeline.** All 8 failed at the network-call layer: `429 RESOURCE_EXHAUSTED` (Gemini free-tier quota — explicitly `generativelanguage.googleapis.com/generate_content_free_tier_requests`, **limit 5 requests/minute**) and `"no parsed GenerationOutput/verdict"` errors consistent with the same quota pressure.
   - **Root cause:** `generate_and_label` costs **~5 Gemini calls per example** (1 generation + 4 independent per-dimension judge calls). A single example alone saturates the free-tier 5 RPM budget.
   - **Secondary finding:** `rubric_judge.GeminiRubricJudge` has **no retry/backoff** (unlike `GeminiGenerationClient`, which does) — a real robustness gap if Gemini is used again later.
   - No thresholds, prompts, filters, or rubrics were changed to force a pass. The failure was reported as-is.

3. **Decision: do NOT depend on Gemini for dataset generation.** At ~7,500–12,500 total LLM calls needed for a 1,500–2,500-example dataset, no free/local path exists that produces that volume automatically — so the chosen strategy is a **hybrid**, not a Gemini scale-up:
   - Claude Code hand-authors a small, high-quality **seed set** (this document's seed dataset, below).
   - A separate, **profile-blind independent judging pass** (not yet run) produces the actual training labels — judging must never see the target profile, only the rubric + question + grounding + answer, exactly as `rubric_judge.build_judge_prompt` already guarantees structurally.
   - The existing, already-tested, **fully API-free** `deterministic_rewrite_pipeline.py` / `deterministic_rewrite.py` (precedent: Experiment 4, 2,479 + 3,185 examples) is the planned mechanism to later expand the trusted, judged seed set toward the 1,500–2,500 target, without further LLM-judging cost for the multiplied examples (style rewrites carry the source's judged labels forward verbatim since they never change claims/content).

### The 100-example seed dataset
**Status: created, schema-validated, NOT labeled.** `target_profile` on every record is **generation intent only — it is explicitly NOT a ground-truth label.** No independent judging has been run against this seed set.

**Location (scratchpad only — NOT in the repository, NOT committed):**
```
C:\Users\mayur\AppData\Local\Temp\claude\C--Users-mayur-capstone\74985d8c-d674-45a4-b586-386b83ef043c\scratchpad\deberta_seed_dataset_v1.jsonl
C:\Users\mayur\AppData\Local\Temp\claude\C--Users-mayur-capstone\74985d8c-d674-45a4-b586-386b83ef043c\scratchpad\deberta_seed_dataset_v1_manifest.json
C:\Users\mayur\AppData\Local\Temp\claude\C--Users-mayur-capstone\74985d8c-d674-45a4-b586-386b83ef043c\scratchpad\build_seed_dataset.py   (generator script, reproducible)
```
⚠️ This is a **session-scoped Claude Code scratchpad path**, not durable repository storage. If a future session's scratchpad directory differs, these files may not be reachable by path — the seed set should be moved into the repo (e.g. `main_cap/cap/artifacts/seed_dataset_v1/`, gitignored like other experiment artifacts) as an early step once judging begins, so it survives independently of any one scratchpad.

**Exact counts:**
- 100 examples total (`seed_v1_000`–`seed_v1_099`)
- 48 hard-case examples — **exactly 4 per approved hard case A–L, all 12 covered, none missing**
- 52 coherent-profile examples (10 each at tiers 0/1/2/3/4, +2 extra at tiers 1/2)
- 12 fictional-but-plausible project groundings (web app, distributed system, ML system, security system, database, networking, backend, cloud, mobile, data pipeline, computer vision, NLP), 7–9 examples each
- All 10 `ReasoningType` values represented; `QuestionCategory` split 88 `project_deep_dive` / 12 `project_overview`
- Per-dimension target-tier histograms show real spread across all 5 tiers for all four canonical dimensions (no dimension collapsed to one score) — full histogram is in the manifest JSON

**Validation completed (read-only, using existing repo functions, no repo modification):**
- 100/100 schema-valid (`DimensionProfile` + `QuestionSpecification` construction, both passed for every record)
- Hard-case vectors verified to match `dimension_profiles.HARD_CASES` exactly
- 0 exact (question, answer) duplicates (`dataset_filters.exact_qa_duplicate_indices`)
- 0 duplicate answer strings (`dataset_filters.duplicate_answer_counts`)
- 0 banned self-describing quality phrases (`dataset_filters.find_banned_phrases`)
- 0 near-duplicates found via a **cheap `difflib` proxy** (0.75 threshold) — **NOT** the production SBERT check
- 5 questions intentionally reused across two different hard cases each (deliberate design — same question, contrasting profile/answer — not a defect)
- The `J` hard case (4 examples) intentionally contains grounding-contradicting content (that's the case's definition); all other 96 examples are grounding-faithful

**Outstanding validation before this seed set is treated as final:**
- **Re-run the real production SBERT near-duplicate check** (`rewrite_verifier_client._semantic_similarity` via `dataset_filters.near_duplicate_pairs`), not the difflib proxy used today.

### Explicit non-status reminders
- **No DeBERTa training has happened.** No head migration, no fine-tuning run, no Colab session.
- **No independent judging has happened.** The seed set's `target_profile` values must never be copied into final `dimension_labels` — labels must come only from a profile-blind judging pass, per the Step 3 design already audited today.
- **No Gemini calls were made** during seed authoring or checkpoint work today, only during the earlier, already-reported failed smoke test.
- **No production/application code was modified today.** `git status` at the end of today's session is identical to `git status` at the start — all modified/untracked files pre-date this session (Step 1–3 infra + an earlier, unrelated Phase-1 resume-parser workstream).

### Next step (tomorrow's first action) — superseded, see Checkpoint below
1. ~~Re-run the production SBERT near-duplicate check~~ — **done**, see below.
2. ~~Run the independent, profile-blind judging pass~~ — **done**, see below.
3. ~~Run the acceptance gate~~ — **done**, see below.
4. Begin planning the `deterministic_rewrite_pipeline.py`-based expansion toward the 1,500–2,500-example target — **not yet started**.
5. DeBERTa 4-head migration, fine-tuning, and the Colab T4 training run remain unchanged, later steps — not started.

---

## Checkpoint — Judging + Repair Pass (2026-09-06)

**Current phase:** the 100-example hand-authored seed has been SBERT-validated, independently profile-blind judged (twice — once pre-repair, once post-repair), forensically analyzed, and repaired. **Still no DeBERTa training, no head migration, no dataset expansion, no Gemini/external API calls.**

### 1. SBERT near-duplicate validation
Production path (`dataset_filters.near_duplicate_pairs` → `rewrite_verifier_client._semantic_similarity`, model `all-MiniLM-L6-v2`, threshold 0.92) run against all 100 answers: **0 near-duplicate pairs.** Re-run after the repair pass (below) against the repaired 100 answers: **still 0 pairs.**

### 2. First independent judging pass (pre-repair)
Judge: Claude Code itself (this session), not Gemini — the `RubricJudge` protocol is duck-typed, and `build_judge_prompt` was verified structurally (source inspection) to never reference `target_profile`/`hard_case`/`profile_id`. Scored all 100 examples × 4 dimensions from question + grounding (title+technologies) + expected_concepts + answer only. **100/100 judged, 0 errors.** Acceptance gate (`dataset_acceptance.evaluate_dataset`): 6/9 hard checks passed; failed `grounding_source_diversity` (12 sources vs. default min 20), `target_vs_judge_agreement` (31/100 exceeded tolerance), `grounding_fidelity` (6 flags).

### 3. Forensic analysis (read-only)
Classified all 31 agreement mismatches, all 6 grounding-fidelity flags, and the source-diversity failure. Findings: most agreement mismatches were bad seed content (answers written better/more-grounded than their own target intended) or bad target_profile design (hard cases J and K each coupled two dimensions the rubric's own `must_not_overlap_with` text declares independent); the rubric had a genuine gap for "contentless but not factually false" answers (10 examples, 048–057); 5/6 grounding-fidelity flags were validator false positives (postgres/PostgreSQL spelling variants; technologies mentioned only as a considered-and-rejected alternative), 1/6 (`seed_v1_037`) was a genuine contradiction; source diversity was a pilot-size/config mismatch, not a seed defect; dimension correlations (mean |r| 0.461, max 0.684 depth↔grounding) showed no dimension collapse.

### 4. Repairs applied
- **`main_cap/cap/evaluation_dimensions.py`**: added an explicit Technical Correctness rule distinguishing "no verifiable technical claim" (defaults tier 3, penalized under Depth/Relevance instead) from an actual wrong claim (tier 0-2) — no new dimension, no other rubric change.
- **`main_cap/cap/dimension_profiles.py`**: revised the approved hard-case vectors J `(2,2,3,0)→(4,2,3,0)` and K `(4,1,2,2)→(4,1,4,1)`, decoupling technical_correctness from J's grounding contradiction and relevance_completeness from K's shallow depth, per the rubric's own independence rules. A and the other 9 hard cases are untouched.
- **`main_cap/cap/dataset_filters.py`**: `hallucinated_technologies` is now alias-aware (postgres/postgresql, node.js/nodejs) and ignores a technology mentioned only as a considered-and-rejected alternative (sentence-scoped marker check) — the genuine contradiction case (`seed_v1_037`) is unaffected and still flags.
- **`main_cap/cap/dataset_acceptance.py`**: added `PILOT_SEED_V1_ACCEPTANCE_CONFIG` (`min_distinct_sources=12`) as an explicit, separate, additive constant for this 100-example pilot; the production default (`min_distinct_sources=20`) is untouched.
- **Seed content**: 24 of the 100 examples were rewritten/updated (5 for tone-down of over-strong grounding on off-topic hard case F, 1 rewritten to contain a genuine technical misconception for hard case E, 11 coherent-tier examples dialed back from "excellent" toward their intended mediocre tier, 4 J + 4 K records had only their `target_profile` snapshot refreshed to match the repaired vectors). Original `deberta_seed_dataset_v1.jsonl` in the scratchpad is untouched; the repaired set is a new, separate file.
- **Tests**: `test_evaluation_dimensions.py` (+3 tests pinning the contentless-answer rule), `test_four_dim_dataset_pipeline.py` (updated `test_hard_case_matrix_matches_approved_vectors` to the repaired J/K vectors), `test_dataset_filters_grounding.py` (new, +7 regression tests: 2 alias cases, 2 rejected-alternative cases, 1 genuine-contradiction-still-caught case, 1 mixed-mentions edge case, 1 symmetric alias case).

### 5. Second independent judging pass (post-repair)
Same blind-judging discipline, re-run against the repaired seed. **100/100 judged, 0 errors.**

| Metric | Pre-repair | Post-repair |
|---|---|---|
| target_vs_judge mean max-delta | 1.19 | 1.05 |
| Examples exceeding tolerance | 31 | 11 |
| grounding_fidelity flags | 6 (5 false positive, 1 genuine) | 1 (the genuine one, `seed_v1_037`) |
| grounding_source_diversity | 12 vs. min 20 (FAIL) | 12 vs. pilot min 12 (PASS) |
| Mean \|pairwise dimension correlation\| | 0.461 | 0.380 |

**Acceptance gate (pilot config) result: still FAILS 2/9 hard checks** — `target_vs_judge_agreement` (11 residual mismatches: 10 are the `coherent:0` bucket's per-dimension jitter target, itself out of this repair's authorized scope — only the 12 approved hard-case vectors were revised, not the procedurally-jittered coherent-tier targets; 1 is `seed_v1_075`'s relevance, an accepted rubric-consistent residual since a simple, fully-answered question legitimately scores relevance high regardless of a "shallow" coherent-tier target) and `grounding_fidelity` (the 1 genuine, intentionally-preserved `seed_v1_037` contradiction — working as designed, not a defect).

**Verdict: NOT yet READY FOR EXPANSION.** Smallest next repair: decide whether to also refresh the `coherent:0` bucket's stored `target_profile.technical_correctness` (currently 0) to be consistent with the now-repaired rubric's contentless-answer rule, or explicitly accept these 10 as documented, known residual disagreements before proceeding. This decision was intentionally left to the user rather than made unilaterally, since it involves touching target_profile values outside the explicitly-authorized J/K hard-case scope.

---

## Checkpoint — Option (a) Follow-Up: coherent:0 target_profile Refresh (2026-09-06)

**Chosen:** option (a) — refresh the 10 `coherent:0` records' (048–057) stored `target_profile.technical_correctness` 0 → 3, matching the repaired rubric's contentless-answer rule. **Nothing else touched**: no rubric change, no hard-case vector change, no answer-text rewrite, no judged `dimension_labels` change, no dataset expansion, no Gemini/API calls, no training.

### What changed
New file `seed_v1_2_repaired.jsonl` (built from `seed_v1_1_repaired.jsonl`, which is untouched). Programmatic field-by-field diff confirms **exactly 10 records differ, and each differs in exactly one field** (`target_profile.technical_correctness: 0 → 3`); `depth_specificity`, `relevance_completeness`, `grounding_ownership`, `answer`, and every other field are byte-identical on all 100 records. Recorded in `seed_v1_1_changelog.json`'s `option_a_followup` block (also appended as 10 individual change entries).

### Re-validation performed
1. **Schema validation** — all 100 records reconstruct a valid `DimensionProfile` + `QuestionSpecification` + `ReasoningType`: **100/100 pass**.
2. **Hard-case vector validation** — every `hard_case`-tagged record's `target_profile` matches `dimension_profiles.HARD_CASES[letter]` exactly (A–L, including the J/K repair from the prior checkpoint): **0 mismatches**.
3. **Production SBERT near-duplicate check** — re-run against `seed_v1_2_repaired.jsonl`'s 100 answers (unchanged from `seed_v1_1`): **0 pairs** (threshold 0.92, `all-MiniLM-L6-v2`).
4. **Profile-blind judging** — re-run (judge never saw `target_profile`/`hard_case`/`profile_id`). **Judged `dimension_labels` are byte-identical to the prior pass (0 changes)** — confirmed programmatically, not asserted — since only the target changed, never the judge's inputs. This is the point: the gate result below moved because the *target* got more accurate, not because labels were adjusted to match it.
5. **Pilot acceptance** (`PILOT_SEED_V1_ACCEPTANCE_CONFIG`, `min_distinct_sources=12`; production default unchanged at 20).

### Result

| Metric | Before this follow-up | After |
|---|---|---|
| target_vs_judge mean max-delta | 1.05 | **0.81** |
| Examples exceeding tolerance | 11 | **1** |
| grounding_fidelity flags | 1 (`seed_v1_037`, genuine) | **1** (`seed_v1_037`, still genuine, unchanged) |

**Acceptance gate: still FAILS 2/9 hard checks**, both now fully accounted for:
- `target_vs_judge_agreement` — **1 residual mismatch**: `seed_v1_075` (relevance_completeness target=2, judged=4). Accepted, rubric-consistent residual — a simple, fully-answered question ("what alternatives did you consider") legitimately scores relevance high regardless of its coherent-tier "shallow" target; not touched, since only J/K hard-case vectors and the 048–057 rubric-driven target were in authorized scope this round.
- `grounding_fidelity` — **1 flag**, `seed_v1_037`, the genuine AWS/SageMaker-vs-Airflow contradiction. **Confirmed still flagged** — working as designed, per the CRITICAL instruction that this must remain caught.
- `grounding_source_diversity` — **passes** (12 sources vs. pilot min 12; production default remains 20, untouched).

### READY FOR EXPANSION: **NO**

Smallest remaining substantive dataset-quality issue: **`seed_v1_075`'s relevance_completeness target (2) is inconsistent with its own answer content** (a simple, single-part question that the answer fully and directly addresses) — the same class of issue already fixed for hard cases J and K (a coherent-tier profile assigning a low relevance target to an answer that, on the rubric's own terms, fully answers its question). This is the one remaining place a stored target still disagrees with the rubric's independence rule in a way that's traceable to a specific, nameable defect rather than an inherent judge/target divergence. Everything else (1 genuine grounding contradiction, correlation levels, source diversity, duplicate/leakage/banned-phrase/hard-case-coverage checks) is either passing or a working-as-intended diagnostic.

---

## Checkpoint — Final Residual Repair: seed_v1_075 (2026-09-06)

**Fixed the one remaining item from the prior checkpoint.** Inspected `seed_v1_075` directly: question ("What alternatives to Vault did you consider for secret storage?") is single-part with zero expected concepts; the answer names the one alternative considered (AWS Secrets Manager), states why it lost (single-cloud vs. the project's actual multi-cloud need), and explicitly scopes the comparison depth. Confirmed: this fully and directly answers the literal question. Stored `target_profile.relevance_completeness: 2` was inconsistent with the rubric's tier-4 definition and its shallow≠incomplete independence rule (judged value was already 4).

**Change:** `seed_v1_075.target_profile.relevance_completeness: 2 → 4`, on `seed_v1_3_repaired.jsonl` (built from the untouched `seed_v1_2_repaired.jsonl`). Field-by-field diff over all 100 records confirms **exactly 1 record differs, in exactly 1 field**. No answer text, no other target dimension, no other record, no rubric/validator/threshold code touched this pass.

**Re-validation:**
- Schema validation: **100/100 valid**.
- Hard-case vector validation: **all 12 (A–L) match `dimension_profiles.HARD_CASES` exactly**, including J `(4,2,3,0)` and K `(4,1,4,1)` from the earlier repair — unchanged.
- SBERT near-duplicate check: **0 pairs** (100 answers, unchanged from prior pass).
- Profile-blind judging: re-run; **judged `dimension_labels` confirmed byte-identical to the prior pass (0 changes)**.
- Pilot acceptance (`PILOT_SEED_V1_ACCEPTANCE_CONFIG`, min_distinct_sources=12): **`target_vs_judge_agreement` now PASSES — 0/100 examples exceed tolerance, mean max-delta 0.80** (down from 1 residual / 0.81).

**Remaining acceptance failure: 1/9 — `grounding_fidelity` (1 flag, `seed_v1_037`).** Confirmed still flagged: the genuine AWS/SageMaker-vs-Airflow contradiction was not suppressed, whitelisted, or weakened. This is intentional, working-as-designed behavior (per repeated explicit instruction), not a defect.

### READY FOR NEXT PHASE: **YES**

Every hard acceptance check now passes except the one that is *supposed* to fail by design — `grounding_fidelity`'s single flag is the deliberately-preserved genuine contradiction example, not a quality defect. Leakage, banned phrases, all-four-dimensions-present, hard-case coverage, source diversity (pilot config), answer-per-question cap, duplicate rate, and target-vs-judge agreement all pass cleanly; dimension correlations show no redundant heads. The 100-example seed is ready to move to the next phase (planning the `deterministic_rewrite_pipeline.py`-based expansion toward 1,500–2,500 examples) — still not started.

### 6. Validation
`test_evaluation_dimensions.py` + `test_dimension_input.py` + `test_four_dim_dataset_pipeline.py` + `test_dataset_filters_grounding.py`: **80 passed.** Full repository suite: **1624 passed, 33 subtests passed, 0 failed** (up from 1614 — the 10 new targeted tests above).

### 7. Artifacts (all under the gitignored `main_cap/cap/artifacts/seed_dataset_v1/`)
`seed_v1_judged.jsonl` / `seed_v1_acceptance_report.json` (pre-repair), `seed_v1_1_repaired.jsonl` / `seed_v1_1_changelog.json` / `seed_v1_1_judged.jsonl` / `seed_v1_1_acceptance_report.json` (post-repair).

### Explicit non-status reminders
- No DeBERTa training, head migration, or dataset expansion has happened.
- No Gemini/external API calls were made.
- No commit or push was made this session.

---

## Checkpoint — Phase 1B: Targeted Coverage Batch (2026-09-08)

**Chosen from yesterday's decision point:** option (a) — a small, targeted
20-example batch addressing the four known coverage gaps and the
reasoning-type imbalance, per `docs/architecture/DeBERTa_Dataset_Expansion_Checkpoint.md`.
No TechQA pilot, no rewrite-engine work, no training this session.

**Result:** 20 new, original examples authored, profile-blind judged (0
mismatches), and validated against the full existing 150-example pool.
Artifact: `main_cap/cap/artifacts/gap_coverage_20/` (gitignored, same
convention as `seed_dataset_v1/` and `hand_authored_50/` — see that
directory's `README.md` for full detail).

**Combined curation/expansion pool: 100 seed + 50 hand-authored + 20 targeted
= 170 examples.** Still NOT the final training dataset — same outstanding
steps as recorded in the Expansion Checkpoint's "Training Status" section.

Coverage: 5 detailed+irrelevant, 5 project/resume contradiction, 4 strong-
ownership+weak-correctness, 6 textbook-vs-project-specific (3 pairs). 17 new
distinct source groundings, 0 collisions with the existing 26. Reasoning-type
representation shifted toward the previously-thin types (debugging 5,
decision_making 3, design 2, optimization 2, ownership 1, reflection 1,
trade_off_analysis 1, recall 1) with explanation deliberately kept to 4/20.

Validation: schema 20/20, exact duplicates 0, SBERT near-duplicates 0 (gap-
internal + gap-vs-existing-150, both scoped checks — the existing 150x150
pairs were already 0 in prior checkpoints and untouched here), banned
phrases 0, malformed 0, target-vs-judge agreement 20/20 within tolerance
(mean/max delta 0.0/0). Grounding-fidelity proxy raised 6 raw flags: 4 are
either the batch's own intentional contradiction content (working as
designed) or genuine contradictions the proxy's vocabulary-membership check
isn't equipped to catch (behavioral swaps, not named-technology swaps); 2 are
checker false positives of the same documented alias class as the seed's
postgres/node.js issue (not patched — no filter code was touched this
session; see the artifact `README.md` for the full breakdown).

No rubric, model, rewrite pipeline, RAG, planner/specification/realizer, UI,
resume parser, or interview-runtime code was touched. No commit or push.

---

## Checkpoint — Phase 4: Colab Training Entry Point Prepared (2026-09-08)

**Attempted a real local training run first; it failed on resource
grounds, not a code defect.** `microsoft/deberta-v3-base` (fresh init) +
four canonical CORAL heads, batch_size=8/max_length=256, on this
machine's CPU: a synthetic single-batch timing probe suggested ~6.5s/batch
(~15 min for 8 epochs), but the REAL run measured >8.9GB private memory
against this machine's 7.5GB total RAM, triggered active disk paging, and
stalled (epoch 1 not complete after ~20 minutes wall time / ~500s CPU
time). The run was killed cleanly (no partial checkpoint written). This is
an environment constraint, not an architecture or dataset problem — the
Phase 2/Phase 3 migration and split are unaffected and unmodified.

**Decision:** move real training to a GPU-backed Google Colab runtime.
Local execution is now `--dry-run`-only (environment report + frozen-pool
sanity check, no download, no training) via a deliberate, explicit hard
gate — `run_four_dim_training.py` refuses to proceed past `train` without
`torch.cuda.is_available() == True`, printing a clear blocker message
rather than silently falling back to CPU (a deviation from this
codebase's existing "Colab-intended, portable" scripts, chosen
specifically because the silent-CPU-fallback pattern is what let the
stalled local attempt happen in the first place).

**Created:**
- `main_cap/cap/run_four_dim_training.py` — the canonical entry point (`--dry-run` / `train`). Reuses `model_dataset.build_dataloaders`, `model_heads.train_model`/`MultiTaskModel`, `model_checkpoint_io.save/load_checkpoint_artifact`, `model_evaluator.TrainedEvaluator`, `training_experimentation.compute_qwk`/`assemble_checkpoint`, `four_dim_experiment_split.load_core_pool` — all unmodified. New code is orchestration + per-dimension (accuracy/within-1/MAE/QWK/confusion-matrix) metric computation only.
- `main_cap/cap/COLAB_RUN.md` — step-by-step Colab instructions.
- `main_cap/cap/test_four_dim_training_entrypoint.py` — 14 new tests (environment report, hard CUDA gate, dry-run safety incl. an AST check that dry-run never touches the real backbone/tokenizer, config sanity, per-dimension metric math) — all passing, no real model involved.

**Validation:** relevant suite (`test_four_dim_training_entrypoint.py` + `test_four_dim_migration.py` + `test_four_dim_experiment_split.py` + `test_model_dataset.py`/`test_model_heads.py`/`test_model_evaluator.py`): 100 passed. Full repository suite: **1713 passed, 33 subtests passed, 0 failed** (up from 1699 — the 14 new tests).

**Explicit non-status reminders:** no real DeBERTa training has completed anywhere yet (the local attempt stalled and was killed before finishing even one epoch; no weights were ever saved from it). The frozen 170-example pool and the Phase 3 split (`artifacts/four_dim_experiment_v1/split.json`, seed `four_dim_experiment_v1_41`) are unmodified. No TechQA, no rewrites, no new examples. No commit, no push.

**Next step:** run `python run_four_dim_training.py train` in a GPU-backed Google Colab runtime per `COLAB_RUN.md`, then copy `artifacts/four_dim_training_v1/` back into the repository for analysis.
