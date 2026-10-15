# LLD information: AI Resume-Grounded Interview Preparation Platform

Everything an LLM needs to write the project's **Low-Level Design**. The content is taken from the code on branch `ninad_latest` (2026-10-01): names, fields, endpoints, formulas and thresholds are exact. Python modules live in `main_cap/cap/` unless a path is given.

## Prompt to give the LLM

> Using only the information below, write the Low-Level Design for this project. Structure it as:
> 1. Module decomposition
> 2. Class design (per module: classes, key attributes, methods, relationships)
> 3. Database design (tables, keys, relationships)
> 4. API design (endpoint, request, response, errors)
> 5. Core algorithms (step by step, with the formulas and thresholds given)
> 6. State machines
> 7. Error handling
> 8. Configuration
> 9. Design patterns
>
> Do not invent classes, endpoints, fields or numbers. Keep each module to about half a page, and use tables where possible. Where a diagram helps (class, state, sequence), give it as PlantUML.

---

## 1. Module decomposition

| # | Module | Owner | Files | Responsibility |
|---|---|---|---|---|
| M1 | Resume Intelligence & Resume Discussion | Mayuran | `resume_engine/`, `candidate_profile_generator.py`, `planner.py`, `topic_pool.py`, `question_specification.py`, `question_families.py`, `question_realizer.py`, `discussion_policy.py`, `conversation_memory.py`, `interview_question.py`, `conversation_engine.py` | Parse the resume into a Candidate Profile; plan and phrase 10 traceable Round 1 questions; run the Round 1 session |
| M2 | RAG, Technical Interview & Answer Evaluation | Ninad | `rag_system/rag_tester/slide_rag/`, `question_bank/`, `tech_interview/`, `evaluator.py`, `evaluator_registry.py`, `evaluation_request.py`, `evaluation_result.py`, `evaluation_engine.py`, `heuristic_evaluator.py`, `overall_single_evaluator.py`, `averaged_evaluator.py`, `answer_gate.py`, `deployment_evaluator.py`, `interview_feedback.py` | Offline: slides → 422-question bank. Runtime: select, grade and follow up Round 2 questions; score Round 1 answers |
| M3 | Webcam Monitoring & Proctoring | Surya | Webcam, camera-check and session-integrity code in `templates/index.html`; `static/models/face_landmarker.task` | Camera check, attention, liveness, second-person/lighting alerts, full-screen / tab / copy-paste rules |
| M4 | Accounts, Data & UI | Nandagopal | `app.py`, `account_routes.py`, `account_schemas.py`, `resume_store.py`, `avatar_store.py`, `database.py`, `models.py`, `migrations/`, `session_history.py`, `session_routes.py`, `insights.py`, rest of `templates/index.html` | Auth, profiles, resumes, persistence, history, Home insights, all screens and reports |

**Layering:** Browser (`index.html`) → Flask routes (`app.py`, `account_routes`, `session_routes`) → domain modules (M1, M2) → persistence (`session_history`, `models`) → SQLite.

**Hard boundary:** planning modules (`planner`, `topic_pool`, `question_realizer`, `discussion_policy`, `conversation_memory`) must not import evaluation modules. This is enforced by AST tests; only `conversation_engine` touches both.

---

## 2. Class design (key classes per module)

### M1: Resume engine
| Class | Kind | Key attributes | Key methods |
|---|---|---|---|
| `ResumePipeline` | dataclass, 8 injected stages | extractor, layout_reconstructor, section_detector, parser_runner, cross_reference_engine, normalizer, validation_engine, confidence_engine | `run(file_path, source_format, trace=None) -> AnnotatedCandidateProfile` |
| `DocumentModel` | dataclass | spans: list[TextSpan], page_count, source_format, body_font_size, layout_mode, layout_confidence | — |
| `TextSpan` | dataclass | text, bbox, font_size, is_bold, page_num, column_index | — |
| `Section` | dataclass | label, raw_header_text, spans, header_confidence | — |
| `ParserResult` | dataclass | entities, confidences: list[Confidence], observations: list[Observation] | — |
| `EntityParser` | Protocol | entity_name, required_sections, version | `parse(sections, doc, trace) -> ParserResult` |
| Parsers | implement `EntityParser` | ContactParser, ExperienceParser, ProjectParser, EducationParser, SkillsParser, CertificationParser | `parse(...)` |
| `AnnotatedCandidateProfile` | dataclass | parser_results, observations, overall_confidence: Confidence(score, reasons) | — |
| `CandidateProfile` | Pydantic | candidate_name, contact_details, skills, education[], experience[], projects[ProjectEntry(title, summary, technologies, concepts, interview_seeds)], certifications, predicted_domain, experience_level, confidence, interview_blueprint, resume_summary | — |

The 8 stages, in order: **1** extract (PDF/DOCX/TXT spans) → **2** layout (1 or 2 columns) → **3** section detection (fuzzy header match + SBERT fallback) → **4** entity parsers → **5** cross-reference + interview-seed synthesis → **6** normalization → **7** validation (observations; never blocks) → **8** confidence. Then `candidate_profile_mapper.map_to_candidate_profile()` builds the `CandidateProfile`.

### M1: Round 1 planning and session
| Class / module | Kind | Key attributes | Key methods |
|---|---|---|---|
| `QuestionSpecification` | frozen Pydantic | id, category: QuestionCategory, text_seed, grounding (Project / Experience / Certification, exactly one), priority_boost, source_type, source_id, source_field, reason | — |
| `TopicPool` | class | specs, lifecycle per spec, rejected topics | `get`, `lifecycle_of`, `mark_active`, `mark_covered`, `remaining`, `total` |
| `Planner` | facade over TopicPool | — | `plan_next(state: ConversationState) -> QuestionSpecification \| None`, `advance(spec_id, outcome)` |
| `ConversationState` | frozen dataclass | last_category, recent_source_ids | — |
| `InterviewQuestion` | frozen Pydantic | question_text, transition_text, specification, family, reasoning_type, project_reference, turn_number | — |
| `ConversationMemory` | class | timeline, families, transitions, answer metadata (never evaluation data) | `record_turn`, `recent_source_ids`, `is_family_recently_used`, `turn_count` |
| `question_realizer` | module | — | `realize(spec, memory, turn_number) -> (InterviewQuestion, variant_idx)` |
| `conversation_engine` | module (session facade) | in-memory `_conversations[conv_<hex12>]` = {planner, memory, pinned evaluator, ledger, current question, answer history} | `start_conversation(profile)`, `advance_conversation(id, answer)`, `end_conversation(id, integrity)`, `sanitize_integrity(raw)` |

Enums:
- `QuestionCategory`: project_deep_dive, project_overview, experience, certification, skill_in_context.
- `ReasoningType`: RECALL, EXPLANATION, APPLICATION, TRADE_OFF_ANALYSIS, DEBUGGING, DESIGN, OPTIMIZATION, REFLECTION, OWNERSHIP, DECISION_MAKING.

### M2: Evaluation (Round 1)
| Class | Kind | Notes |
|---|---|---|
| `Evaluator` | Protocol | attrs name, version, declared_dimensions, declared_reasoning_types, requires_network; `evaluate(EvaluationRequest) -> EvaluationResult` |
| `HeuristicEvaluator` | implements Evaluator | "heuristic-v1": SBERT similarity + lexical markers + NLI contradiction flag |
| `OverallSingleEvaluator` | implements Evaluator | fine-tuned DeBERTa-v3 `overall_single_v5_1088` (one overall score) |
| `AveragedEvaluator(heuristic, model)` | implements Evaluator (composite) | **production**: blends the two; keeps the heuristic's dimensions/feedback |
| `HybridEvaluator(heuristic, trained)` / `TrainedEvaluator` | implement Evaluator | older tiers (fallback) |
| `evaluator_registry` | module | `register_evaluator(e, make_active)`, `get_active_evaluator()`; one active; each session pins its evaluator |
| `EvaluationRequest` | frozen Pydantic | request_id, specification, question_text, reasoning_type, answer_text, conversation_context (turn, prior answers, projects/technologies so far), expected_concepts |
| `EvaluationResult` | frozen Pydantic | result_id, request_id, evaluator_name/version, dimensions[DimensionScore(name, raw_score, weight_used, confidence, contributes_to_overall)], overall_score, grade, confidence, reasoning, strengths/weaknesses[EvidenceLinkedClaim], missing_reasoning[], concept_coverage[], suggested_improvements, contradiction_detected, recommended_action |
| `EvaluationLedger` | class | `append(result)`, `all()`, `for_specification(id)`: append-only per session |
| `answer_gate` | module | `gate(request, result) -> EvaluationResult` |
| `interview_feedback` | module | `build_feedback(evaluations) -> {headline, summary, strengths, focus_areas, scope_note, stats}` |

### M2: Technical interview (Round 2)
| Class / module | Kind | Key attributes / signature |
|---|---|---|
| `KeyPoint` | frozen dataclass | point, followup, followup_answer, variants, followup_replies |
| `Question` | frozen dataclass | id, subject, topic_id, topic, difficulty, text, reference_answer, key_points (2–5), confidence, source_pages, curated, interview_priority |
| `Clarity` | dataclass | words, fillers, filler_ratio, dont_know, too_short, vague, repetitive; `unclear()` |
| `Grade` | dataclass | score, keypoint_score, reference_similarity, covered, partial, missing, point_scores, clarity |
| `Decision` | frozen dataclass | kind (next / clarify / probe), text, key_point, reason |
| `TechInterview` | class | `TechInterview(questions, mode)`; `prompt() -> dict`; `submit(answer) -> {record, prompt, finished}`; `summary() -> dict`; `finished` |
| `bank` | module | `load_bank(directory, enriched, curated) -> tuple[Question]`, `question_by_id(id)` |
| `selector` | module | `select_questions(bank, n, seen_ids, topic_scores, rng) -> list[Question]`, `difficulty_plan(n)` |
| `grader` | module | `grade_answer(question, answer) -> Grade`, `followup_covers(key_point, answer) -> (verdict, scores)`, `analyse_clarity(answer) -> Clarity` |
| `followup` | module | `decide(question, grade, followups_used, clarified, asked_points, clarify_count) -> Decision` |

### M4: Persistence and services
| Class / module | Notes |
|---|---|
| `User`, `StudentProfile`, `Resume`, `InterviewSession`, `SessionTurn` | SQLAlchemy models (section 3) |
| `session_history` | `begin_resume_discussion`, `record_resume_discussion_turn`, `finish_resume_discussion`, `begin_tech_interview`, `record_tech_interview_turn`, `finish_tech_interview`, `technical_history(user) -> (seen_ids, topic_scores)`, `abandon_in_progress_sessions`, `abandon_stale_sessions`, `abandon_all_open_sessions`, `delete_session` |
| `insights` | `build_insights(user_id) -> {stats, last_session, trend, focus}` |
| `resume_store` | save file (random name, SHA-256), `parse_resume(path)` |
| `avatar_store` | `process_avatar(file) -> bytes` (256×256 JPEG) |

### M3: Frontend proctoring (JavaScript, `index.html`)
| Unit | Functions |
|---|---|
| Camera setup check | `showCameraSetup(onProceed)`, `_csRender`, `_csFaceLuma`, `camFaceSharpness` |
| Monitoring | `initializeGazeMonitoring()`, `startGazeDetectionLoop()`, `stopGazeMonitoring()`, `setAttentionState()`, `computeAttentionScore(metrics)`, `attentionSnapshot()`, `camAlertUpdate(kind, condition, now)` |
| Session integrity | `showInterviewRules(mode)`, `acceptInterviewRules(mode)`, `proctorArm()`, `proctorViolation(type)`, `proctorIntegrityPayload()`, `proctorDisarm()` |

---

## 3. Database design (SQLite via SQLAlchemy; Alembic migrations applied at startup)

| Table | Key columns | Keys / relations |
|---|---|---|
| `users` | id, email (unique), password_hash (scrypt), email_verified, role, is_active, consent_data, consent_training, consent_version, consented_at, avatar (BLOB), avatar_updated_at, created_at, last_login_at | PK id |
| `student_profiles` | id, user_id, full_name, date_of_birth, phone, class10_board/score/score_type/year, higher_secondary_type/board/score/score_type/year, college, degree, branch, cgpa, cgpa_scale, graduation_year, updated_at | FK user_id → users (unique, 1:1, ON DELETE CASCADE) |
| `resumes` | id, user_id, file_path, original_filename, content_type, size_bytes, sha256, parsed_profile (JSON = CandidateProfile), is_current, uploaded_at | FK user_id → users (1:N, CASCADE) |
| `interview_sessions` | id, user_id, resume_id, session_type (resume_discussion \| technical), status (in_progress \| completed \| terminated \| abandoned), started_at, ended_at, last_activity_at, overall_score, overall_grade, questions_answered, evaluator_name, evaluator_version, integrity (JSON), attention_metrics (JSON), summary (JSON) | FK user_id → users (1:N, CASCADE); FK resume_id → resumes (N:1, SET NULL) |
| `session_turns` | id, session_id, turn_number (unique per session), question_text, category, family, reasoning_type, project_reference, source_id, is_followup, answer_text, answered_at, overall_score, grade, evaluation (JSON) | FK session_id → interview_sessions (1:N, CASCADE) |

- **Migrations:** `ee1633ec7576` (initial schema), `eeeb3959ae84` (last_activity_at), `a7c3e91f2b40` (profile photo).
- **Pragmas:** `foreign_keys=ON`, WAL mode.
- **Files on disk:** resumes under `instance/uploads/resumes/<user_id>/<uuid>.<ext>`; the database at `instance/app.db`.

---

## 4. API design (JSON over HTTP; every `/api/*` route except login/signup needs a session cookie, else 401)

| Method & path | Request | Response | Errors |
|---|---|---|---|
| POST `/api/auth/signup` | multipart: email, password, profile + academic fields, consent_data, consent_training, `resume` file, optional `avatar` | 201 `{user, profile, current_resume}` (logged in) | 400 field errors `[{field, message}]`; 400 unreadable resume; 409 duplicate email; 413 > 10 MB |
| POST `/api/auth/login` | `{email, password, remember}` | 200 `{user}` | 401 (same message for wrong password or unknown email); 403 disabled |
| POST `/api/auth/logout` · GET `/api/auth/me` | — | `{user, profile, current_resume}` | 401 |
| PATCH `/api/profile` · POST `/api/auth/change-password` · PATCH `/api/auth/consent` · DELETE `/api/auth/account` | field changes / passwords / `{consent_training}` / `{password}` | 200 | 400, 401 |
| GET/POST/DELETE `/api/auth/avatar` | multipart `avatar` (POST) | image / 200 | 400 not an image; 404 none |
| GET/POST `/api/resumes`; POST `/api/resumes/<id>/make-current`; DELETE `/api/resumes/<id>` | multipart `file` (POST) | resume list / resume | 404 other user's id; 409 deleting the only resume |
| POST `/api/resumes/<id>/use` | — | `{session_id: "profile_<hex>", name, projects, skills, …}` | 404 |
| POST `/api/classify-resume` | multipart `file` | same as `/use` (also saved as the current resume) | 400 unreadable |
| POST `/api/resume-discussion-v2/start` | `{session_id}` (profile session) | 200 `{status, conversation_id, question: {text, transition_text, …}, total_questions}` | 400 no questions possible; 404 |
| POST `/api/resume-discussion-v2/reply` | `{session_id: conversation_id, answer}` | 200 `{status, evaluation: {overall_score, grade, dimensions, strengths, weaknesses, …}, next_question \| null, is_completed, turn_number}` | 404 unknown/other user's conversation |
| POST `/api/resume-discussion-v2/end` | `{session_id, integrity, attention_metrics}` | 200 summary `{total_questions, timeline, evaluations, feedback, integrity, …}` | 404 |
| POST `/api/tech-interview/start` | `{mode: "standalone" (10) \| "round2" (8)}` | 201 `{session, prompt}` | 400 unknown mode; 503 bank unavailable |
| POST `/api/tech-interview/<id>/answer` | `{answer}` (≤ 5,000 chars) | 200 `{prompt, finished, questions_answered}` | 400 not a string; 404; 409 already finished |
| POST `/api/tech-interview/<id>/end` | `{attention_metrics, integrity}` | 200 `{session, summary, questions: [per-question record]}` | 404 |
| GET `/api/sessions[?type=]` · GET/DELETE `/api/sessions/<id>` | — | session list / session with turns | 404 |
| GET `/api/insights` | — | `{stats, last_session, trend, focus}` | — |

**Technical `prompt` object:**

```
{number, total, subject, subject_label, topic, difficulty, question_id,
 kind: "question" | "followup" | "clarify",
 text,
 main_question}        // main_question: only when kind is followup or clarify
```

---

## 5. Core algorithms (formulas and thresholds)

**A1. Round 1 question selection (`TopicPool.select_next`, deterministic, no randomness).**
1. Build one specification per resume fact: deep-dive (per interview seed), overview (per project), experience, certification, skill-in-context.
2. Skill topics must pass the traceability gate; topics that fail go to `rejected`.
3. Score each candidate and pick the highest:

```
score = CATEGORY_PRIORITY × 10
      + 100 if the category is not yet covered
      + 2   if priority_boost
      + 1   if the category differs from the last one
      − 3 if its project/job was used in the last few turns
```

`CATEGORY_PRIORITY`: deep_dive 5, overview 4, experience 3, certification 2, skill 1. Ties go to the earlier-built specification. The budget is 10 questions.

**A2. Phrasing (`question_realizer.realize`).**
- **Family:** 21 families × 2 variants. The family comes from a per-category arc and avoids families used in the last 3 turns; a project's first question is forced to "overview".
- **Variant:** `variant = crc32(spec.id + "::" + family) % 2`, flipped if it would repeat the last one.
- **Transition phrase:** avoids the last 3 used.
- **Seed questions:** asked verbatim with the project named, never two in a row.

**A3. Round 1 scoring.**
1. **Production score:** `overall = 0.8 × DeBERTa(overall_single_v5_1088) + 0.2 × heuristic`.
2. **Heuristic accuracy:** `0.85 × grounding similarity + 0.15 × question similarity` (SBERT cosine, rescaled).
3. **Heuristic dimension weights:** 1.5 for always-relevant dimensions, 1.0 for the rest.
4. **Grades:** ≥ 0.90 excellent, ≥ 0.75 good, ≥ 0.55 adequate, ≥ 0.30 weak, else poor.
5. **Non-answer gate:** "idk" replies, < 3 words, keyword dumps, comma term lists, gibberish, repetition and pasted code are capped at **0.1 / poor**.
6. **Contradiction flag:** NLI contradiction probability ≥ 0.5.

**A4. Round 2 question selection (`select_questions`).**
1. Difficulty plan for n questions:
   - easy = max(1, round(0.2n));
   - hard = max(1, round(0.15n));
   - medium = the rest.

   So n = 8 gives 2 easy / 5 medium / 1 hard, and n = 10 gives 2 / 6 / 2.
2. Subjects rotate (shuffled round-robin); every question comes from a different topic.
3. Questions this user has already been asked are skipped.
4. Weight for each candidate:

```
w = (0.5 + confidence) × PRIORITY[tier] × (1 + 2.0 × (1 − topic_avg))
```

   - `PRIORITY` = {3: 6.0, 2: 1.0, 1: 0.2} (interview-frequency tier).
   - The last factor applies only to topics the user has answered before.
5. When a slot has no candidate, constraints relax in this order: difficulty → subject → already-seen.
6. Only `curated` questions are served (`CAP_CURATED_ONLY=1`).

**A5. Round 2 grading (`grade_answer`).**
1. Split the answer into sentences, sentence pairs and 20/40-word windows.
2. For each key point:
   - entailment = max NLI entailment(chunk ⇒ point) with `cross-encoder/nli-deberta-v3-base`;
   - sim = max MiniLM cosine.
3. Classify each point:
   - **covered** if entail ≥ 0.60, or entail ≥ 0.20 and sim ≥ 0.80;
   - **partial** if entail ≥ 0.05 and (sim ≥ 0.60 or entail ≥ 0.30);
   - otherwise **missing**.
4. `keypoint_score = (covered + 0.5 × partial) / number of points`.
5. `score = 0.85 × keypoint_score + 0.15 × reference_similarity`. The reference term counts fully only once half the points are met.
6. Fillers are stripped before grading but counted for clarity.

**A6. Follow-up policy (`followup.decide`).** Rules are checked in order:
1. "I don't know" → **next**.
2. Follow-ups used ≥ 2 → **next**.
3. score ≥ 0.70 and the answer is clear → **next**.
4. Answer unclear and not yet clarified → **clarify** (a template question).
5. A missing/partial key point with a prepared follow-up, not asked yet → **probe** (ask that follow-up).
6. Otherwise → **next**.

A follow-up reply is judged by `followup_covers`. A recovered point earns **0.75** credit, and the question's score is recombined.

**A7. Attention score (browser).**

```
score = 100 − 4 × warnings − 6 × face_absent − 5 × liveness_failures − min(20, 0.25 × seconds_away)
```

Bands: **FOCUSED** ≥ 85, **MOSTLY FOCUSED** ≥ 65, otherwise **DISTRACTED**.

**A8. Gaze/head fusion (browser).**
- Head pose: yaw/pitch from the face transformation matrix, smoothed with EMA 0.30; beyond 26° counts as away.
- Iris gaze: offset normalised by eye size, thresholds |x| 0.44 and |y| 0.60, 5 confirming frames.
- Fusion: `raw = 0.35 × head + 0.55 × gaze + 0.10 (if head and gaze agree)`, then EMA.
- A deviation starts at ≥ 0.50 and ends < 0.34.

**A9. Camera alerts.**
- **Second person:** a second face for 0.6 s shows the alert; it clears after 1.2 s without one.
- **Too dark or blurry:** face brightness < 65, whole-frame brightness < 40 with no face, or face sharpness (Laplacian variance) < 15. Sampled every 500 ms, smoothed, shown/cleared after 2.5 s.

**A10. Question-bank generation (offline).**
1. Per topic: retrieve the slide sections (hybrid FAISS + BM25, α = 0.6, MiniLM reranker).
2. Qwen3-8B writes a question with 2–5 key points, each with a slide quote.
3. Code checks:
   - the quote is in the slide text (fuzzy ≥ 88) and relates to its point (cosine ≥ 0.35);
   - at least 2 verified points;
   - no trivia.
4. Qwen3 judge: on topic, and the reference answer is correct.
5. Distinctness: < 0.85 within a topic, < 0.90 across the bank.
6. Confidence ranking from 6 signals: ≥ 0.75 → active (282).
7. Hand review: score ≥ 8 (or ≥ 7 on a most-asked topic) → curated (132).

---

## 6. State machines

**S1. Interview session status (`interview_sessions.status`).**
- `in_progress` → `completed` on a normal /end.
- `in_progress` → `terminated` on a proctoring violation.
- `in_progress` → `abandoned` when a new interview starts, after 2 h idle, or on server restart.
- `completed`, `terminated` and `abandoned` are terminal.

**S2. Question unit lifecycle (`UnitLifecycleState`).**
- `UNASKED` → `ACTIVE` → `COVERED` | `SKIPPED`; `UNASKED` → `COVERED` | `SKIPPED` directly is also allowed.
- Terminal states stay terminal. Any other transition raises `InvalidLifecycleTransitionError`.

**S3. Technical question (`TechInterview`, per main question).**
- `ASKED` → (answer) → `GRADED`.
- `GRADED` → `CLARIFY_PENDING` | `FOLLOWUP_PENDING` (at most 2 in total) → (reply) → `GRADED` again.
- `GRADED` → `CLOSED` when the decision is "next". `CLOSED` writes the record and moves to the next question; after the last question the interview is `FINISHED`.

**S4. Attention (browser).**
- `NORMAL` → `CAUTION` after 3.5 s looking away → `WARNING` after 8.5 s (visual banner + spoken message unless a mic is on).
- `FACE_ABSENT` after 7.5 s without a face.
- 45 s cooldown per warning type.

**S5. Liveness (browser).**
- `NO_FACE` → `FACE_DETECTED` → (after 2.5 s) `LIVENESS_CHECKING` (random head-turn left/right, 13° yaw, 12 s timeout) → `LIVE_PERSON_CONFIRMED`.
- Re-check after 35 s with no natural facial activity.

**S6. Interview flow (browser `interviewFlow.phase`).**
- `resume` → `between` → `technical` → `ended` (Full Interview); the standalone Technical Interview runs `technical` → `ended`.
- A violation in any phase → `ended`, with the integrity record set to terminated.

---

## 7. Error handling

| Area | Behaviour |
|---|---|
| Resume parsing | Missing / corrupt / password-protected / scanned (< 50 characters) → `ExtractionFailure` → 400 with a clear message; at signup nothing is saved (rollback + file removed) |
| Parsers | A missing section gives an empty result plus an observation; date parsing never raises; model-load failures fall back to "unknown" |
| Round 1 | Unknown/finished conversation → 404 / `{"status": "completed"}`; evaluator failure leaves state unchanged (turn can be retried); an evaluator is pinned per session |
| Evaluator startup | `bootstrap_production_evaluator()` never raises. Order: Averaged (v5 weights present and approved) → Hybrid (old weights) → Heuristic |
| Technical interview | Bad mode → 400; bank missing → 503; non-string answer → 400; answers truncated to 5,000 characters; already finished → 409 |
| Auth / ownership | Login guard → 401; another user's resume/session/conversation → 404 (never 403); identical 401 for wrong password vs unknown email (timing-safe dummy hash) |
| Uploads | > 10 MB → JSON 413; only .pdf/.docx/.txt resumes; avatars re-encoded (non-images rejected, EXIF stripped) |
| Integrity record | `sanitize_integrity` whitelists the client record (`terminated` must be literally true; unknown types → "unknown") |
| Frontend | Re-entrancy guards (no double start/end); stale timers check `interviewFlow.phase`; any 401 returns to login; camera denied → "Camera blocked" panel |

---

## 8. Configuration (environment variables and key constants)

| Name | Default | Effect |
|---|---|---|
| `CAP_DATABASE_URL` | `sqlite:///instance/app.db` | Database (any SQLAlchemy URL) |
| `CAP_UPLOAD_DIR` | `instance/uploads` | Resume storage |
| `CAP_SECRET_KEY` | generated into `instance/secret_key` | Session secret |
| `CAP_TRAINED_EVALUATOR` | on | `0` forces the heuristic Round 1 evaluator |
| `CAP_CURATED_ONLY` | `1` | Serve only curated questions (`0` = all 282 active) |
| `CAP_GRADER_ENRICHMENT` | `replies` | off / replies / all |
| `CAP_QUESTION_BANK_DIR` | `rag_system/rag_tester/question_bank` | Bank location |
| `CAP_MODEL_WARMUP` | on | Background model loading at startup |
| `RESUME_DISCUSSION_QUESTION_BUDGET` | 10 | Round 1 length |
| `TECH_INTERVIEW_LENGTHS` | standalone 10, round2 8 | Round 2 length |
| `MAX_FOLLOWUPS` / `GOOD_SCORE` / `RECOVERED_CREDIT` | 2 / 0.70 / 0.75 | Follow-up policy |
| `HEURISTIC_WEIGHT` | 0.2 | Averaged evaluator blend |
| `PROCTOR_BLUR_GRACE_MS` | 1500 | Window-switch grace (permission prompts) |
| `STALE_AFTER` | 2 h | Idle sessions become abandoned |
| Max upload / answer length | 10 MB / 5,000 chars | Limits |

---

## 9. Design patterns

| Pattern | Where |
|---|---|
| Strategy via Protocol | `Evaluator` (Heuristic / OverallSingle / Averaged / Hybrid); resume-engine stage Protocols |
| Composite / decorator | `AveragedEvaluator` and `HybridEvaluator` wrap two evaluators behind the same interface |
| Registry | `evaluator_registry` (active evaluator), `ParserRegistry` (resume parsers), question-family registry |
| Pipeline | `ResumePipeline` (8 stages); offline slide pipeline (extract → classify → vision → sections → index) |
| Facade | `Planner` (over TopicPool), `conversation_engine` (Round 1 session), `TechInterview` (Round 2 session) |
| Adapter | `candidate_profile_mapper` (engine output → CandidateProfile), `evaluation_engine.build_request` |
| Dependency injection + composition root | `resume_engine/factory.py` builds the pipeline from Protocol implementations |
| Immutable value objects | Frozen Pydantic models / dataclasses: QuestionSpecification, InterviewQuestion, EvaluationRequest/Result, Question, KeyPoint |
| State machine | Unit lifecycle, session status, attention, liveness, interview flow |
| Append-only log | `EvaluationLedger` |
| Write-through persistence | Live state in memory; every answered turn written to SQLite immediately |
| Blueprints / app factory | `accounts_bp`, `sessions_bp`, `init_accounts(app)` |
