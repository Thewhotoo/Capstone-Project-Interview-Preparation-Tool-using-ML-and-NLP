# Milestone 7 — Validation Report (Cutover)

Status: **Phases 1-3 complete and tested. Phase 4's mechanism is fully implemented and tested (the feature flag already supports it, one env var flip) but the default backend has deliberately NOT been switched to "engine" — its stated precondition (Shadow Mode demonstrating stability across a representative set of real resumes) has not actually been run against live Gemini in this environment, and claiming it had would be reporting a result that doesn't exist. See Section 5.**

---

## 1. Audit recap (done before implementation)

- `AnnotatedCandidateProfile` had six of ten `CandidateProfile` fields available directly from `parser_results` (contact, experience, projects, education, skills, certifications) plus `confidence` (from Stage 8). Four fields (`predicted_domain`, `experience_level`, `interview_blueprint`, `resume_summary`) had no producer anywhere in the engine.
- All four were determined to be deterministically producible from evidence Milestones 1-6 already extracted — no LLM required for any of them (Section 1 of the audit, confirmed correct during implementation).
- Integration path: `app.py:415-421` → `generate_candidate_profile(text)` → `_candidate_profiles[session_id]` → `profile_to_frontend_format`. Both consumers accept plain dicts; `topic_pool.py`/`traceability.py` need zero changes.

## 2. What was implemented

### Phase 1 — `AnnotatedCandidateProfile` → `CandidateProfile` mapper (`resume_engine/candidate_profile_mapper.py`)
- `classify_domain`: gazetteer-keyword scoring (new `domain_gazetteer.py`, keyed to the exact `DOMAIN_LABELS` list) against skills/technologies/concepts/role text. Defaults to `"Software Engineering"` (matching the Gemini path's own default) when nothing scores.
- `infer_experience_level`: total years from `experience[].duration` (regex, same technique `candidate_profile_generator._calculate_total_years` already uses) + seniority keywords already present in `role` text.
- `build_technical_topics`: reuses `projects[].technologies`/`concepts` directly as `TechnicalTopic`-shaped evidence (zero new extraction); only scans `experience[].summary` (same gazetteer-matching technique `ProjectParser` already established) when the project-derived topics don't fill the cap. Every topic cites exactly one origin (enforced by construction, matching the schema's XOR requirement) and `evidence` is always a literal substring of the source entry's own text.
- `estimate_weaknesses`: **direct reuse** of the Validation Layer's already-computed `Observation`s (Milestone 6) — zero new heuristic.
- `estimate_strengths`: frequency count of technologies across projects + skills — direct reuse of already-extracted data.
- `build_resume_summary`: a grounded template (never freeform generation), empty when there's no real evidence (graceful degradation, same permanent rule `seed_synthesis.py` established).
- The mapper constructs an actual `candidate_profile_generator.CandidateProfile` Pydantic instance (catching any shape mistake at translation time) and returns `.model_dump()` — the exact same return convention `generate_candidate_profile` already uses.
- **A real bug was found and fixed during this phase**: the initial `_YEAR_PATTERN` regex used a capturing group (`(19|20)\d{2}`), which would have made every `.findall()` call silently return only `"19"`/`"20"` instead of full years — caught before it shipped, via test-writing discipline (write the test, watch it exercise the code path, notice the extracted years were wrong), not via a separate review pass. Fixed to a non-capturing group.
- 21 unit tests (`test_candidate_profile_mapper.py`), including a full round-trip through the unmodified `topic_pool.py`/`profile_to_frontend_format` — the actual downstream-compatibility check.

### Phase 2 — Feature flag (`candidate_profile_generator.py`, `app.py`)
- `get_active_parser_backend()`: reads `CAP_RESUME_PARSER` (`"engine"` or default `"gemini"`), case-insensitive, unrecognized values fall back to `"gemini"` (never silently selects the untested path on a typo).
- `engine_supports_format()`: the engine's Document Extraction stage only handles PDF/DOCX — `.doc`/`.txt` always use Gemini regardless of the flag, a documented limitation, not a silent gap.
- `generate_candidate_profile_via_engine(file_path)`: the engine-path wrapper — runs `default_pipeline().run(...)` then `map_to_candidate_profile(...)`. Lazy imports so a Gemini-only process never pays the engine's model-loading cost.
- `app.py`'s `/api/classify-resume` route branches on the flag before text extraction (the engine does its own extraction internally) — Gemini remains the default, unchanged behavior for every existing deployment until the flag is explicitly set.
- 8 unit tests (`test_engine_backend_selector.py`), including one that runs the real engine path end-to-end against a golden-corpus PDF and round-trips it through `CandidateProfile(**profile_dict)`.

### Phase 3 — Shadow Mode (`resume_engine/devtools/shadow_mode.py`, `shadow_mode_batch.py`)
- Rewrote the Milestone 0 placeholder (which compared `AnnotatedCandidateProfile`'s raw internal shape — impossible to interpret meaningfully) to use the new mapper, producing a genuine apples-to-apples `CandidateProfile`-vs-`CandidateProfile` diff for the first time.
- `compare_profiles` is type-aware per field: scalars (direct equality), flat string lists (order-independent set diff — `skills`/`certifications`), structured entity lists (`education`/`experience`/`projects`, matched by a natural key, diffed field-by-field). Every discrepancy is categorized (`missing_in_engine` / `missing_in_gemini` / `different_value` / `count_mismatch`) — never a verdict on which side is "correct," confirmed by a dedicated test (`test_shadow_mode_never_labels_a_side_as_ground_truth`).
- `shadow_mode_batch.py`: the comparison tooling for inspecting differences across a whole directory of resumes at once — one bad/corrupt fixture is recorded as an error entry, never aborts the batch; produces a human-reviewable JSON report with batch-level category totals.
- Both modules remain exactly what Section 2.2 of the architecture doc requires: developer/test tooling only, never imported by `app.py`, never a code path a real user request can reach.
- 16 unit tests (`test_shadow_mode.py`, `test_shadow_mode_batch.py`) — all with Gemini's call mocked (no real API calls from the test suite), engine-side and file-I/O logic exercised for real.

### Phase 4 — mechanism ready, default not switched
See Section 5.

## 3. M0-6 boundary check

Modified: `app.py`, `candidate_profile_generator.py` (the cutover integration points themselves — this milestone's whole purpose), `confidence.py`/`cross_reference.py`/`factory.py`/`normalization.py`/`validation.py`/the three Milestone 5 parsers (already-modified in prior milestones, untouched further here — confirmed via `git status`, no new diffs beyond what Milestones 4-6 already introduced), `shadow_mode.py` (Milestone 0's own explicitly-temporary scaffolding, rewritten as designed). **Zero changes** to `extractor.py`, `layout.py`, `sections.py`, `document_model.py`, `interfaces.py`, `registry.py`, `contact_parser.py`, `experience_parser.py`, `project_parser.py`, `seed_synthesis.py`, `dates.py`, or `topic_pool.py`/`traceability.py`/`discussion_engine.py`/`planner.py`/any frontend file.

## 4. Test count

`python -m pytest resume_engine/tests/ -q` from `main_cap/cap`: **359 passed** (up from 322 at the Milestone 6 freeze — 37 new tests: 21 mapper, 10 Shadow Mode comparison, 6 Shadow Mode batch tooling).

Root-level app tests (`test_engine_backend_selector.py` [new, 8 tests] + the existing `test_candidate_profile_generator.py` + `test_e2e.py`, confirming zero regression in the Gemini path): **57 passed, 19 subtests passed**.

**Combined: 416 passed, 19 subtests passed, zero failures, zero regressions anywhere.**

## 5. Can Gemini be fully removed, or does it still have responsibilities?

**Gemini cannot be removed yet — not because the engine is deficient, but because the validation Phase 4 requires hasn't actually been run.**

What's genuinely true right now:
- The engine is feature-complete, schema-compatible (verified by construction — every mapper output round-trips through the real Pydantic `CandidateProfile` model and the real, unmodified `topic_pool.py`), and the flag to switch to it (`CAP_RESUME_PARSER=engine`) is fully implemented, tested, and already usable today by anyone who sets that environment variable.
- Everything Milestone 7 asked to be *built* is built: the mapper, the flag, Shadow Mode, and batch comparison tooling.
- What is **not** true, and I want to be explicit about this rather than let the phase numbering imply otherwise: Phase 4's own stated precondition — "once Shadow Mode demonstrates that the deterministic engine is stable and downstream-compatible" across "a representative set of real resumes" — has not been satisfied, because doing so requires a live `GEMINI_API_KEY` and a batch of real resumes, neither of which exist in this environment, and calling a paid external API on your behalf without being asked isn't something I'll do unprompted. All Shadow Mode tests in this milestone mock Gemini's response; none of them constitute the real-world comparison Phase 4 is gated on.

**Recommendation**: keep Gemini as the default and available as a fallback (exactly as Phase 4 specifies), and do **not** flip `CAP_RESUME_PARSER`'s default to `"engine"` yet. The concrete next step, when you're ready: run `python -m resume_engine.devtools.shadow_mode_batch --dir <folder of real/realistic resumes> --report shadow_report.json` with `GEMINI_API_KEY` set, review the category-totals summary and the per-resume discrepancy list it produces, and only then decide whether to flip the default — a one-line change (`get_active_parser_backend`'s fallback value) once that evidence exists. This is a data-gathering step, not an engineering one; nothing about the engine's architecture or this milestone's code is blocking it.

Gemini's actual remaining responsibilities, until that review happens: the sole PDF/DOCX parsing path in production (default), and the only path at all for `.doc`/`.txt` resumes (the engine has no extractor for those formats — a known, documented, non-blocking gap, since almost all real-world resume uploads are PDF/DOCX).
