# 02 — Round 1: planning, phrasing, session orchestration

Files (main_cap/cap/): `conversation_engine.py` (orchestrator), `planner.py`, `topic_pool.py`, `coverage_tracker.py`,
`question_specification.py`, `traceability.py`, `question_realizer.py`, `question_families.py`, `discussion_policy.py`,
`conversation_memory.py`, `interview_question.py`. Original spec: `docs/architecture/ResumeDiscussion_v2.md` (describes some v1 behaviour — stale).

## Pipeline
`CandidateProfile dict → Planner(TopicPool) → QuestionSpecification → question_realizer.realize → InterviewQuestion → answer → evaluate (see 03)`

## TopicPool (`topic_pool.py`) — what to ask
Built once from the profile; one immutable `QuestionSpecification` per discussable fact, ids `topic_0..N` in build order.
Build priorities (and `CATEGORY_PRIORITY` tier, question_specification.py:84):
| # | Category | Source | tier |
|---|---|---|---|
| 1 | `PROJECT_DEEP_DIVE` | each `projects[].interview_seeds` (deduped by (title, seed)); `text_seed_is_sentence=True` | 5 |
| 2 | `PROJECT_OVERVIEW` | each project with a title | 4 |
| 3 | `EXPERIENCE` | each experience with role or company; source_id `"role at company"` | 3 |
| 4 | `CERTIFICATION` | each cert name | 2 |
| 5 | `SKILL_IN_CONTEXT` | `interview_blueprint.technical_topics` whose origin project/experience exists (traceability gate; failures → `pool.rejected`) | 1 |
`priority_boost` when title/seed/topic touches `interview_blueprint.estimated_weaknesses`.

`select_next(last_category, recent_source_ids)` score = `tier*10 + 100 if category not yet covered + 2 if boost + 1 if category != last − 3 if source_id recent (_RECENT_SOURCE_PENALTY)`; tie → earliest build order. Pure read; lifecycle changes via `mark_active/covered/skipped` (state machine in `UnitLifecycleState`, invalid transitions raise).
Note: diversity bonus can never change a selection across categories (tiers differ by ≥10).

`Planner` is a thin facade: `plan_next(ConversationState(last_category, recent_source_ids))`, `advance(spec_id, UnitStatus.X)`, `total()`, `rejected`.

## QuestionSpecification (`question_specification.py`)
Frozen pydantic: `id, category, text_seed, text_seed_is_sentence, grounding (exactly one of project/experience/certification), priority_boost, source_type, source_id, source_field, reason`. Validators: grounding has exactly one entity; source_type matches grounding; provenance non-empty.
`ProjectGrounding(title, summary, technologies, concepts)`, `ExperienceGrounding(role, company, duration, summary)`, `CertificationGrounding(name)`.

## Realizer — how to phrase it (`question_realizer.py`)
`realize(spec, memory, turn_number) -> (InterviewQuestion, variant_idx)` (annotated as returning InterviewQuestion — it returns a tuple). Pure; caller must `memory.record_turn(...)`.
- First touch on a source_id → `discussion_policy.select_family` (forces "overview").
- A validated candidate-facing seed sentence is used VERBATIM (`_SEED_VERBATIM_FAMILY`) unless first touch or previous turn was also verbatim (no two in a row). `_name_the_project` inserts the project name.
- Else family template, variant chosen by `_stable_index` = `zlib.crc32(...) % n` (deterministic across processes).
- Transition prefix from `discussion_policy.select_transition` (same_topic / new_project / returning_project / new_experience / new_certification, 2 variants each, rotation avoids recent reuse).
- `realize_followup(spec, memory, turn, followups_used_on_this_spec, angle, focus_hint)` — same spec, `is_followup=True`, no transition. Angles: tradeoff_probing→tradeoffs, design_justification→decision_making, debugging_decisions→debugging, ownership, reflection, + template-only clarification / more_detail / alternative_approaches. `tradeoff_probing` excluded for SKILL_IN_CONTEXT.

## Families (`question_families.py`, registry via `register_family`)
21 families: overview, architecture, implementation, skill_application, skill_context, tradeoffs, decision_making, debugging, optimization, scaling, testing, deployment, failures, lessons_learned, future_improvements, reflection, responsibilities, team_collaboration, ownership, motivation, application(cert). Each: `name, reasoning_type (ReasoningType enum: recall/explanation/application/trade_off_analysis/debugging/design/optimization/reflection/ownership/decision_making), applicable_categories, variants (callables on PhrasingContext)`.
`discussion_policy._ARC` per category = order families progress through as a source is revisited (e.g. DEEP_DIVE: implementation→architecture→tradeoffs→decision_making→debugging→…). SKILL_IN_CONTEXT deliberately avoids "implementation"/"tradeoffs" (evidence doesn't support ownership/comparison claims). A test asserts every `_ARC` name is a registered family.

## ConversationMemory (`conversation_memory.py`)
Evaluation-free record of turns: timeline, projects/skills/technologies discussed, reasoning types covered, family/transition recency (`_RECENCY_WINDOW`), `recent_source_ids()`, `turn_count()`. Only answer-length metadata, never scores.

## Orchestration (`conversation_engine.py`)
- `RESUME_DISCUSSION_QUESTION_BUDGET = 10` (stop calling plan_next after 10 recorded turns).
- Adaptive follow-ups (live app opts in): `_answer_warrants_followup` ⇔ `0.15 < overall_score < 0.60`; `MAX_FOLLOWUPS_PER_PROJECT = 1`, `MAX_FOLLOWUPS_PER_SESSION = 2`; only within budget. Follow-up uses angle `more_detail`, focus = project title head before " — ". Spec NOT advanced (next answer evaluated against the same spec). Counts tracked in `followups_by_source` (not pool lifecycle, since specs never go ACTIVE).
- Record/replay: only the JSON record is stored; `_rebuild` replays turns through the same planner/realizer, restoring evaluations from the record and using the STORED `followup` decision. If replay doesn't reproduce `current_question.text` → conversation dropped (404). So: **any change to planning/phrasing invalidates in-flight Redis conversations** (fine; they expire in 2 h).
- `advance_conversation` (under store lock) → `_advance`: build_request (prior answers only) → `evaluate` → `ledger.append` → `_queue_regrade` → `check_tech_consistency` (informational) → `memory.record_turn` → decide follow-up → append turn → payload with `_result_payload(result)` + `improved_answer`, `coaching_note` (strong_answer.py), `concept_coverage_pct` (concept_analysis.py), `tech_consistency`.
- `_result_payload`: only `DISPLAYED_DIMENSIONS = {technical_depth, completeness, ownership, resume_grounding}` shown (others are gameable keyword heuristics).
- `end_conversation(conv_id, integrity, wait_for_regrades)`: deletes record, `_final_results` (swap finished re-grades), summary {total_questions, projects/skills/technologies discussed, timeline, evaluations, regraded_turns, integrity: `sanitize_integrity(...)`, feedback: `interview_feedback.build_feedback(...)`}.
- `sanitize_integrity`: allowed types `tab_switch, window_switch, fullscreen_exit, copy, cut, paste, drop`; else "unknown"; label ≤120 chars.

## Recipes
- **Change question count**: `RESUME_DISCUSSION_QUESTION_BUDGET`. Frontend shows `total_questions = min(planner.total(), budget)`.
- **Add a phrasing family**: `register_family(FamilyDefinition(...))` in question_families.py, add to `_ARC` in discussion_policy.py; tests in `test_question_families.py`, `test_discussion_policy.py`, `test_round1_question_quality.py`.
- **Change follow-up policy**: `_answer_warrants_followup`, `MAX_FOLLOWUPS_*`, `_realize_followup`. Tests: `test_adaptive_followups.py`.
- Keep everything deterministic — `test_conversation_engine.py` checks replay across hash seeds.
