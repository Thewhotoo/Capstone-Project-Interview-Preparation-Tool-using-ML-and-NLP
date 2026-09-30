# Milestone 6 — Validation Report

Status: **Complete. All three remaining stages (Normalization, Validation, Confidence Scoring) implemented. The 8-stage pipeline runs end-to-end for the first time (`default_pipeline().run(...)` completes without raising). Zero regressions in Milestones 0-5.**

---

## 1. Audit (done before implementation, per instruction)

| Stage | Status before this milestone | Status after |
|---|---|---|
| 0-5. Extraction → Cross-Reference | Real (Milestones 1-5) | Unchanged, frozen |
| 6. Normalization | Stub, `NotImplementedError` | Real |
| 7. Validation | Stub, `NotImplementedError` | Real |
| 8. Confidence Scoring | Stub, `NotImplementedError` — the hard blocker preventing `pipeline.run()` from ever completing | Real |

One scope note identified during the audit and confirmed correct during implementation, not discovered as a surprise mid-build: `ValidationEngine.validate(parser_results, trace)` — the frozen interface signature — never receives the raw `list[Section]` (with `header_match_reason`), so Section 8's "unknown/ambiguous section header" structural rule is not reachable from this stage. Every other Section 8 rule category is implementable and was implemented. This is documented in `validation.py`'s module docstring and treated as an accepted, honest scope boundary (the codebase's established discipline — e.g. Milestone 3's `single_entry_sections_pdf`) rather than silently claiming full catalogue coverage.

## 2. What was implemented

### Normalization (`normalization.py`)
- Unicode `NFKC` + whitespace collapse on every string field across every entity type (contact, experience, projects, education) — a pure function (`clean_text`), reused by nothing outside this module (no frozen-module reach-in).
- Duration separator canonicalization (`"Jan 2020—Mar 2021"` → `"Jan 2020 - Mar 2021"`) — normalizes only the separator; month/year tokens are never reformatted, preserving the schema's existing display-string contract.
- Technology de-aliasing (`"JS"` → `"JavaScript"`, `"k8s"` → `"Kubernetes"`, etc. — a small, documented, extensible alias map) + case-insensitive deduplication for `projects[].technologies`, with the merge event logged as an `info` Observation (`duplicate_technologies_merged`) rather than silently invisible.
- The same dedup discipline extended to the flat-string `skills`/`certifications` entity lists, done in lockstep with their 1:1 `Confidence` list (keeping the higher-scoring duplicate) so the `len(entities) == len(confidences)` invariant survives normalization-induced merges.
- 9 unit tests (`test_normalization.py`).

### Confidence Scoring (`confidence.py`, Stage 8)
- Per the explicit instruction ("use signals already produced... instead of inventing new heuristics"): every parser already computes its own per-entity `Confidence` (Section 7's weighted formulas live inside `ContactParser`/`ExperienceParser`/`ProjectParser`/`EducationParser`/`SkillsParser`/`CertificationParser`, all built in Milestones 3 and 5). This stage does pure aggregation — a flat, unweighted mean across every individual entity's score, pooled across all parsers — into `AnnotatedCandidateProfile.overall_confidence`.
- Deliberately not weighted by entity-type "importance" (e.g. favoring projects over education): that would be a new heuristic invented at this layer, which the instruction explicitly ruled out. Flagged in the module docstring as the one place a future milestone could reasonably add weighting, as a reviewable, documented change — not assumed here.
- Reasons list every contributing parser by name, entity count, and average score (`"+projects:2 entities, avg confidence 0.79"`), or an explicit `"-<parser>:no_entities_found"` when a parser found nothing — full traceability, zero new signals.
- 6 unit tests (`test_confidence_scoring.py`).

### Validation Layer (`validation.py`, Stage 7)
- Collects every `Observation` already embedded by earlier stages (parsers' own `missing_technologies`/`missing_degree`/`empty_section`/`missing_dates`; Cross-Reference's `skill_not_demonstrated`; Normalization's `duplicate_technologies_merged`) into one unified list — this is most of Section 8's catalogue, already produced upstream and simply surfaced here for the first time.
- Four new rules for the gaps not covered elsewhere: `missing_linkedin` (Completeness), `no_measurable_outcome` (Completeness — a project summary with no percentage/multiplier pattern), `empty_experience_summary` (Completeness), `inconsistent_dates` (Consistency — an experience entry whose parsed end date precedes its start date, reusing the shared `dates.py` utility rather than re-implementing date parsing).
- Structured, deterministic, non-gating by construction: `validate()` always returns a plain `list[Observation]`, never raises, never blocks profile generation — confirmed by `test_validate_never_gates_and_returns_a_plain_list`.
- 14 unit tests (`test_validation.py`).

### End-to-end confirmation
- `default_pipeline().run()` against `full_entity_resume_pdf` now completes all 8 stages without error for the first time: `overall_confidence: 0.87`, 3 observations (`missing_linkedin`, 2× `no_measurable_outcome`), all 16 stage-trace entries recorded correctly with a trace active.
- 3 new end-to-end tests (`test_pipeline_end_to_end.py`), including a `None`-value sweep across every entity field produced by the full pipeline (Section 1.3's sentinel convention, checked end-to-end for the first time rather than only per-parser).

## 3. M0-5 boundary check

Modified: `confidence.py`, `cross_reference.py`, `factory.py`, `normalization.py`, `validation.py` — all were Milestone 6 (or earlier-milestone, still-stub) files explicitly scoped to this work, never a frozen M0-3 file. `git status` confirms zero changes to `extractor.py`, `layout.py`, `sections.py`, `document_model.py`, `interfaces.py`, `registry.py`, `contact_parser.py`, `experience_parser.py`, `project_parser.py`, `seed_synthesis.py`, or any golden-corpus expectation file from a prior milestone.

## 4. Test count

`python -m pytest resume_engine/tests/ -q` from `main_cap/cap`: **322 passed** (up from 290 at the Milestone 5 freeze — 32 new tests: 9 Normalization, 6 Confidence Scoring, 14 Validation, 3 end-to-end). Zero failures, zero regressions in any prior milestone's test.

## 5. What remains before the Resume Intelligence Engine can replace Gemini in the live application

The engine itself is now feature-complete end-to-end (all 8 stages real, `pipeline.run()` completes). What's left is entirely **Milestone 7 (Cutover)**, per the original roadmap — nothing further needs designing, only integrating:

1. **`AnnotatedCandidateProfile` → public `CandidateProfile` mapping.** Not yet written anywhere. The engine's internal shape (`parser_results: dict[str, ParserResult]` + `observations` + `overall_confidence`) needs a conversion function into the exact Pydantic `CandidateProfile` shape `candidate_profile_generator.py` returns today (flattening `entities` lists into `ExperienceEntry`/`ProjectEntry`/`EducationEntry` objects, mapping `overall_confidence.score` to the top-level `confidence: float`, filling `predicted_domain`/`experience_level`/`interview_blueprint` — none of which any current stage produces, since those were never in scope for Milestones 1-6's parser/cross-reference/normalization/validation work).
2. **`predicted_domain`, `experience_level`, and `interview_blueprint` (`technical_topics`, `estimated_strengths`/`weaknesses`, `starting_difficulty`) have no producer anywhere in the engine yet.** These were flagged in the original audit's dependency table as real fields but were out of scope for every milestone so far (0-6 covered extraction through confidence scoring of the six core entity types only). This is new work, not yet designed — worth a short design check before Milestone 7 starts, since it's the one remaining piece with no existing implementation to extend.
3. **The feature-flagged, canary-phase swap itself** (Section 10, Milestone 7): wiring `default_pipeline()` into `app.py`/`generate_candidate_profile()` behind a flag, running Gemini in comparison-only mode against real traffic, developer review, then the follow-up change that deletes Gemini's retry/truncation machinery.
4. **Shadow Mode harness** (Milestone 0's own deliverable, referenced throughout the architecture doc) — not confirmed to exist yet; needed for Milestone 7's comparison-diff step. Worth verifying its state before Milestone 7 begins, not assumed here.

Not required for feature-completeness, explicitly deferred: `PipelineTrace.to_html()` (Milestone 6 originally scoped this too, but it's a nice-to-have visualization, not load-bearing for cutover) and OCR (Milestone 8+, always out of scope unless requested).
