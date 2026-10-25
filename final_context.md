# Final context: AI Resume-Grounded Interview Preparation Platform

Prepared 2026-10-01 from the code on branch `ninad_latest` (commit `59d6c0c`). Every number below was measured on this codebase; where a number was re-run today, it says so. Sources: `PROJECT_DOCUMENTATION.md` (section numbers given as §), `resumeParser_integration.md`, `grader_eval/`, `integration_checks/`, `rag_system/rag_tester/question_bank/quality_review.md`.

How question-bank figures are reported: the bank holds **422 generated questions**. Results "on our best questions" refer to the **curated top tier of 132 questions** (hand-scored 8+/10, or 7+ on a most-asked topic). This is the set the interviews currently draw from by default (`CAP_CURATED_ONLY=1`). A wider tier of **282** passes the automated checks and can be served with `CAP_CURATED_ONLY=0`.

---

## 1. PROJECT SUMMARY

**Abstract.** The platform is a proctored mock-interview system built around the candidate's own resume. A local, deterministic 8-stage Resume Intelligence Engine parses the resume into a structured Candidate Profile. Round 1 then asks 10 questions, each traceable to a specific project, job, certification or skill on that resume, and scores every answer with a fine-tuned DeBERTa-v3 evaluator blended with a heuristic evaluator. Round 2 asks 8 core-CS questions (CN, DBMS, DSA, OOAD, OS) from a 422-question bank generated offline from the faculty lecture slides and checked against them. An NLI grader marks each answer against slide-backed key points, and the interview asks a follow-up or clarification when a point is missing. Throughout, browser-side webcam monitoring (attention, liveness, second person, lighting) and full-screen / tab-switch / copy-paste rules keep the session honest; every turn is saved to SQLite and shown in reports, history and a Home dashboard. Everything that runs during an interview is local: no paid API and no GPU are needed.

**Scope (what the system does):**
- Accounts: signup with academic details, resume and optional profile photo; login, profile and resume management, consent settings, account deletion.
- Resume intelligence: local parsing of PDF/DOCX/TXT resumes into a Candidate Profile (projects, experience, skills, certifications, interview seeds) with explainable confidence.
- Full Interview: Round 1 resume discussion (10 questions) → Round 1 summary → Round 2 technical (8 questions with follow-ups) → combined report; plus a standalone Technical Interview (10 questions).
- Answer evaluation: Round 1 per-dimension scores, strengths, weaknesses, missing reasoning and data-driven feedback; Round 2 key-point grading (covered / partial / missing) with model answers.
- Proctoring: camera setup check, gaze and head-pose attention, head-turn liveness checks, second-person and lighting/blur alerts, zero-tolerance session rules.
- History and insights: every session saved turn by turn, reopenable reports, Home stats, score trend and a "Focus next" list of recurring weaknesses.
- Offline knowledge pipeline: lecture slides → cleaned, sectioned hybrid search index → 422-question bank (generated, verified, ranked, enriched, curated, prioritised by interview frequency).

---

## 2. CHANGES SINCE REVIEW 1

Baseline (Review 1 / Phase 3): resume parsing + resume discussion; a RAG pipeline with Qwen2.5-1.5B and a hardcoded 5-question fill-in-the-blank technical quiz; a DeBERTa/heuristic evaluator; webcam monitoring.

### Features and modules added or replaced
| # | Change | One line |
|---|---|---|
| 1 | **Accounts & database (new)** | Signup (academic details, resume, consents), login, profile, resumes; SQLite + Alembic migrations applied automatically; profile photos. |
| 2 | **Session history & Home insights (new)** | Every interview saved turn by turn (completed / terminated / abandoned); Sessions page reopens exact reports; Home stats, trend and "Focus next". |
| 3 | **Full Interview flow (new)** | One continuous proctored session: Round 1 → summary → Round 2 → combined report with a headline computed from both rounds. |
| 4 | **Technical round replaced** | The 5 hardcoded fill-in-the-blank questions were replaced by the question-bank interview with an NLI grader, follow-ups and clarification requests. |
| 5 | **Slide RAG pipeline (replaces the old RAG)** | Layout-aware slide extraction, cleaning, section grouping, hybrid FAISS + BM25 retrieval with a cross-encoder reranker; vision stage (Qwen3-VL-2B) for diagram/table slides (run on CN). |
| 6 | **422-question bank (new)** | Generated offline with Qwen3-8B (Ollama) from the slides; every key point quote-verified; LLM judge; confidence ranking; follow-up enrichment; hand curation; interview-frequency tiers. |
| 7 | **Qwen2.5-1.5B generation retired** | Replaced by offline Qwen3-8B generation; nothing is generated at interview time. |
| 8 | **Resume engine Phase 1 (upgraded)** | Teammate's rewrite integrated with fixes: better entry boundaries, dates, certifications, contacts (§4.2). |
| 9 | **Round 1 question variety (upgraded)** | Project-specific seed questions, family and item rotation (§4.4). |
| 10 | **Round 1 evaluator (replaced)** | Production scoring = 0.8 × teammate's DeBERTa-v3 `overall_single_v5_1088` + 0.2 × heuristic (`AveragedEvaluator`), replacing the hybrid with the synthetic-data model. |
| 11 | **Non-answer gate (new)** | "idk", keyword dumps, gibberish and pasted code are capped at 0.1 / poor. |
| 12 | **Data-driven feedback (new)** | End-of-round headline, summary, strengths and focus tips computed from the turn results. |
| 13 | **Session integrity rules (new)** | Full screen, no tab/window switch, no copy-paste; the first violation ends the interview; recorded with round and question. |
| 14 | **Webcam upgrades** | Camera setup check before the rules, second-person detection (2 faces), prominent red/amber alerts (second person, too dark or blurry), head-turn liveness (blink challenge disabled as unreliable), spoken warnings muted while a microphone is on. |
| 15 | **Attention in reports** | Per-round attention snapshot saved with each session; "Attention · Whole interview" section in the final report; average attention on Home. |
| 16 | **Voice answers (new, partial)** | Speech-to-text answer input in both rounds (browser Web Speech API). |
| 17 | **Performance** | Offline model loading + background warm-up: server start 6.8 s → 2.1 s; first technical answer 16.2 s → 0.2 s. |
| 18 | **RoBERTa classifier archived** | Never ran in the app (no weights, rule-based fallback only); its routes were removed. |
| 19 | **Repository & docs** | Rewritten README, `SETUP_PREREQUISITES.md`, rebuilt `Requirements_Global.txt`, evaluator weights in Git LFS, personal data scrubbed from tests. |

### Status of the three promised items
| Promised item | Status | Evidence |
|---|---|---|
| (1) Attention metrics in the final dashboard | **Done** | `attentionSnapshot()` saved into `interview_sessions.attention_metrics` for every round; `rdAttentionHtml` renders "Attention · Whole interview" in the combined report (per-round figures totalled by `combineAttention`); Home shows average attention (`insights.py`). Score = 100 − 4·warnings − 6·face-absent − 5·liveness failures − min(20, 0.25·seconds looking away). |
| (2) Voice-based interview | **Partial** | On `ninad_latest`: candidates can answer by voice in both rounds (Web Speech API recognizers `rdRecognition` / `recognition`, Chrome/Edge only); questions are shown as text, not spoken (speech synthesis is used only for proctoring warnings). Branch `Audio` (2026-09-07) has a separate server-side voice pipeline (Whisper speech-to-text `POST /process` in `audio_routes.py`/`audio_processor.py`, text-to-speech `POST /tts` in `tts_routes.py`/`tts_engine.py`) that is **not merged**. |
| (3) Pseudocode evaluator | **Not started** | No pseudocode evaluator exists in the app. The legacy RAG `generate.py` could generate pseudocode *questions* (Qwen2.5), but that pipeline was retired. Recommendation: drop it from the remaining scope ([TEAM INPUT NEEDED]). |

### Do these still exist?
| Item | On `ninad_latest` | Elsewhere |
|---|---|---|
| **CodeBERT** | Only inside the legacy file `rag_system/rag_tester/code_evaluator.py`, which is truncated (SyntaxError) and not imported by the app. | Same legacy file on `main`, `feature/webcam-integration`, `maburan-new`. |
| **Code execution (javac / g++ / node)** | Only in that same broken legacy `code_evaluator.py`; never called. | Same on `main`, `feature/webcam-integration`, `maburan-new`. |
| **BLIP / diagram question generation** | No BLIP anywhere (the only search hit is the word "blips" in a comment). Diagram question generation exists only as legacy stubs (`diagram_*.py`, `call_vlm()` raises `NotImplementedError`; `diagram_question_gen.py` and `diagram_pipeline.py` are missing). Diagram *understanding* for retrieval is now done by Qwen3-VL in the slide pipeline. | Same legacy stubs on `main`, `feature/webcam-integration`, `maburan-new`. |
| **Multi-language support** | None. | None on any branch (search hits only in knowledge-base data files). |
| **RoBERTa** | Archived locally (`archive/Roberta/`, not in the repository); only a comment mentions it. | `Roberta/roberta-multitask-model/` and its routes still exist on `main`, `Audio`, `feature/webcam-integration`, `maburan`, `maburan-new`. |

---

## 3. DESIGN APPROACH

### Major components
| Component | Responsibility |
|---|---|
| Web UI (`templates/index.html`) | Single-page app: auth, Home/Sessions/Profile, interview flow, reports, voice input, webcam monitoring, session rules. |
| Flask API (`app.py`, `account_routes.py`, `session_routes.py`) | Routing, login guard, live interview state, wiring of all modules. |
| Persistence (`database.py`, `models.py`, `migrations/`, `session_history.py`) | SQLite tables, migrations, turn-by-turn recording, abandonment. |
| Resume Intelligence Engine (`resume_engine/`) | File → Candidate Profile in 8 local stages. |
| Planner + Realizer (`planner.py`, `topic_pool.py`, `question_realizer.py`, `discussion_policy.py`) | Decide *what* to ask (traceable specification) and *how* to phrase it. |
| Conversation Engine (`conversation_engine.py`) | Round 1 session lifecycle; the only module that touches both planning and evaluation. |
| Evaluation (`evaluator.py`, `evaluator_registry.py`, `averaged_evaluator.py`, `overall_single_evaluator.py`, `heuristic_evaluator.py`, `answer_gate.py`, `interview_feedback.py`) | Pluggable Round 1 scoring, non-answer gate, feedback. |
| Technical interview (`tech_interview/`) | Question bank loading, selection, NLI grading, follow-up policy, live session. |
| Insights (`insights.py`) | Home stats and "Focus next". |
| Slide RAG + bank tools (`rag_system/rag_tester/slide_rag/`) | Offline: slides → index → question bank (generate, rank, enrich, prioritise). |

### Why this architecture: a modular monolith
One Flask process hosts all modules, each behind a narrow interface (Pydantic contracts, the `Evaluator` Protocol, `session_history` functions). Import boundaries are enforced by AST tests: planning modules may not import evaluation modules.
- **Benefits:** one command to run (`python app.py`); in-process model calls (~0.3 s per answer); one SQLite file; modules developed and tested independently by four people; swappable implementations (three evaluator generations replaced without touching routes or UI).
- **Drawbacks:** live interview state is in memory, so it can't scale across worker processes; one module crash affects the whole app; the frontend is a single 9,300-line HTML file.

### Alternatives considered
| Alternative | Why not chosen |
|---|---|
| **Monolith without module boundaries** (routes calling parsing/scoring code directly) | The evaluator was replaced three times and the resume engine twice; without the Protocol/registry and frozen contracts each swap would have touched routes, session code and UI. Four people working in parallel needed stable interfaces. |
| **Microservices** (parser, evaluator, grader, proctoring as separate services) | Adds network hops, deployment and orchestration for a single-user, single-machine product; models would be loaded per service (RAM); no team capacity for containers/CI. The module boundaries keep a later split possible. |

### Key design decisions
| Decision | Reason |
|---|---|
| Deterministic planner, not an LLM | Guarantees every question traces to a real resume entry; testable; no per-turn latency or cost; no hallucinated topics. |
| Templates for phrasing (21 families × 2 variants) | Earlier generative phrasing (FLAN-T5-small) drifted into "What is X?"; templates keep the senior-interviewer tone. |
| Local resume engine instead of Gemini | No API cost, quota failures or truncated JSON; explainable confidence; works offline. |
| Offline question generation, runtime selection | No GPU or LLM at interview time; every question checked before it is ever asked; instant responses. |
| Local models only at runtime | Privacy (resumes and answers never leave the machine), no API keys, predictable latency. |
| Evaluator interface + registry, evaluator pinned per session | Heuristic → hybrid → averaged evaluators swapped without touching routes or UI; a session is never scored by two model versions. |
| Blend 0.8 model + 0.2 heuristic (not 100% model) | The blend kept QWK 0.86 on the held-out set while removing crushed/inflated cases on the 58-answer stress set; the heuristic also supplies dimension feedback text. |
| NLI entailment per key point for Round 2 | Grades meaning against slide-backed points without an LLM; explainable (✓ / ~ / ✗ per point). |
| Client-side proctoring and webcam analysis | Frames never leave the browser (privacy); a browser can only *detect* leaving full screen, so detection plus zero tolerance is the enforceable policy. |
| SQLite + SQLAlchemy + auto-migrations | Nothing to install; teammates never run schema commands; PostgreSQL is a config change. |
| Parse the resume once at upload | Interviews start instantly; the stored profile is the single source of truth. |

---

## 4. CONSTRAINTS, ASSUMPTIONS, DEPENDENCIES

### Hardware / runtime constraints
- **Runtime (interviews): CPU only.** The server uses ~2.8 GB RAM once models are loaded (measured 2026-09-30); 8 GB minimum. GPU is used automatically if present (~0.1 s vs ~1 s per Round 1 answer).
- **GPU needed only offline:** question-bank generation/enrichment (Qwen3-8B via Ollama, ~6.2 GB VRAM; ~4 h per full pass at ~45 tok/s on an RTX 5050 8 GB), the vision stage (Qwen3-VL-2B, ~10 s/slide), and model training.
- **Single process, in-memory live state:** active conversations and technical sessions live in process memory; answered turns are written to SQLite immediately; unfinished sessions become `abandoned` after restart or 2 h idle.
- Flask development server (no WSGI, no container); port 5000.
- Disk: ~5 GB (packages, ~1.8 GB of Hugging Face models downloaded on first run, 735 MB evaluator weights via Git LFS).

### Assumptions
- **Users:** students / early-career engineers, one interview at a time per account, English answers.
- **Browser:** recent Chrome or Edge (voice input needs Chromium's Web Speech API); full-screen API available; webcam required (microphone optional).
- **Network:** internet on first run (model downloads) and on every page load (MediaPipe from jsDelivr, Google Fonts; Web Speech API uses Google's service).
- **Inputs:** text-based PDF/DOCX/TXT resumes up to 10 MB (scanned/image-only PDFs are rejected with a clear message); lecture slides as one-slide-per-page PDFs (offline pipeline).
- Reasonable lighting and a single person in frame (alerts otherwise).

### Models
| Model | Purpose | When it runs |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | Embeddings: resume section fallback, KeyBERT backbone, heuristic evaluator similarity, technical grader similarity, slide index | **Interview time** (and offline) |
| `cross-encoder/nli-MiniLM2-L6-H768` | Round 1 contradiction flag (heuristic evaluator) | **Interview time** |
| `cross-encoder/nli-deberta-v3-base` | Round 2 key-point entailment (technical grader) | **Interview time** |
| `microsoft/deberta-v3-base` + fine-tuned `overall_single_v5_1088` weights | Round 1 answer score (80% of the blend) | **Interview time** |
| KeyBERT (on MiniLM) | Project concept extraction during resume parsing | **Interview time** (at upload) |
| MediaPipe Face Landmarker (`face_landmarker.task`, 478 landmarks, up to 2 faces) | Gaze, head pose, liveness, second person | **Interview time, in the browser** |
| Web Speech API (browser) | Voice answers (speech-to-text); spoken warnings (synthesis) | **Interview time, in the browser** (optional) |
| `qwen3:8b` (Ollama, Q4_K_M) | Question generation, LLM judge, follow-up enrichment | Offline only |
| `Qwen/Qwen3-VL-2B-Instruct` | Vision stage: diagrams, tables, formulas, picture-only slides | Offline only |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranker in slide retrieval (topic → slides) | Offline only |
| RapidOCR (ONNX) | OCR for picture-only slides | Offline only |
| `BAAI/bge-small-en-v1.5` | Embedding ablation (no gain; not used) | Offline experiment only |
| Old DeBERTa-v3 multi-task model (Experiment 4, CORAL heads) | Earlier Round 1 evaluator (research track; weights not present) | Not used now |
| `Qwen/Qwen2.5-1.5B-Instruct` | Legacy RAG generation | Retired |
| `distilroberta-base`, `bert-base-uncased` | Archived question classifier; untrained legacy resume classifier | Not used |
| Gemini 2.5 Flash | Developer tooling only (parser shadow mode, synthetic data) | Not used by the app |
| Whisper (branch `Audio` only) | Server-side speech-to-text | Not on `ninad_latest` |

**Key libraries:** Flask, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, Pydantic, PyTorch, Hugging Face Transformers, sentence-transformers, PyMuPDF, pdfplumber, python-docx, rapidfuzz, python-dateutil, KeyBERT, FAISS, rank-bm25, RapidOCR, Pillow, NumPy, scikit-learn, pytest; MediaPipe Tasks Vision (JS).

**External services:** Hugging Face Hub (first-run downloads), jsDelivr CDN (MediaPipe), Google Fonts, Web Speech API, GitHub + Git LFS (code and weights). Ollama is a local server used offline only.

---

## 5. DATA FOR UML DIAGRAMS

### a) Class diagram

```
CLASS CandidateProfile  (Pydantic, candidate_profile_generator.py)
  attrs: candidate_name, contact_details: ContactDetails, skills[], education: EducationEntry[],
         experience: ExperienceEntry[], projects: ProjectEntry[], certifications[], predicted_domain,
         experience_level, confidence, interview_blueprint: InterviewBlueprint, resume_summary
  composition: 1 ── * ProjectEntry(title, summary, technologies[], concepts[], interview_seeds[])
               1 ── * ExperienceEntry(company, role, duration, summary)
               1 ── 1 InterviewBlueprint(technical_topics: TechnicalTopic[], estimated_strengths[], estimated_weaknesses[], …)

CLASS AnnotatedCandidateProfile  (resume_engine/confidence.py)   — resume engine output
  attrs: parser_results: dict[str, ParserResult], observations: Observation[], overall_confidence: Confidence(score, reasons)
  relation: ResumePipeline.run() ──creates──> AnnotatedCandidateProfile ──mapped by candidate_profile_mapper──> CandidateProfile (1:1)

CLASS ResumePipeline  (resume_engine/pipeline.py)
  attrs: extractor, layout_reconstructor, section_detector, parser_runner, cross_reference_engine,
         normalizer, validation_engine, confidence_engine   (8 injected Protocol collaborators)
  methods: run(file_path, source_format, trace) -> AnnotatedCandidateProfile
  composition: 1 ── 8 stage objects; uses DocumentModel(spans, page_count, layout_mode, …)

CLASS QuestionSpecification  (Pydantic, frozen, question_specification.py)
  attrs: id, category: QuestionCategory, text_seed, text_seed_is_sentence, grounding, priority_boost,
         source_type, source_id, source_field, reason, schema_version
  grounding: exactly one of ProjectGrounding(title, summary, technologies, concepts) |
             ExperienceGrounding(role, company, duration, summary) | CertificationGrounding(name)
  relation: CandidateProfile 1 ──derives── * QuestionSpecification   (via TopicPool._build)

CLASS TopicPool / Planner  (topic_pool.py, planner.py)
  TopicPool methods: categories_present(), get(id), lifecycle_of(id), remaining(), total(), mark_active(), mark_covered()
  Planner methods: plan_next(state) -> QuestionSpecification|None, advance(spec_id, status), remaining(), total()
  relation: Planner 1 ──facade over── 1 TopicPool;  TopicPool 1 ── * QuestionSpecification (+ UnitLifecycleState each)

CLASS InterviewQuestion  (Pydantic, frozen, interview_question.py)
  attrs: question_text, transition_text, specification: QuestionSpecification, family, reasoning_type,
         project_reference, is_followup, turn_number, metadata
  relation: QuestionSpecification 1 ── * InterviewQuestion (realized by question_realizer.realize)
            ConversationMemory 1 ── * InterviewQuestion (timeline)

CLASS ConversationMemory  (conversation_memory.py)
  methods: record_turn(question, variant), recent_source_ids(), is_family_recently_used(), last_family(), turn_count()

INTERFACE Evaluator  (Protocol, evaluator.py)
  attrs: name, version, declared_dimensions, declared_reasoning_types, requires_network
  methods: evaluate(EvaluationRequest) -> EvaluationResult
  implemented by (realization):
    HeuristicEvaluator   name "heuristic-v1"        — SBERT similarity + lexical markers + NLI contradiction flag
    OverallSingleEvaluator name "overall-single-<model_version>" — fine-tuned DeBERTa-v3 v5_1088
    AveragedEvaluator(heuristic, model)  — composition: 1 HeuristicEvaluator + 1 OverallSingleEvaluator; score = 0.8·model + 0.2·heuristic  [PRODUCTION]
    HybridEvaluator(heuristic, trained)  — composition: HeuristicEvaluator + TrainedEvaluator  [older tier, fallback]
    TrainedEvaluator     name "trained-<model_version>" — old multi-task DeBERTa (CORAL heads)
  registry: EvaluatorRegistry 1 ── * Evaluator (one active); each Round 1 session pins 1 evaluator

CLASS EvaluationRequest  (Pydantic, frozen)
  attrs: request_id, schema_version, requested_at, specification, question_text, reasoning_type, answer_text,
         conversation_context, evaluation_focus, expected_concepts, answer_key

CLASS EvaluationResult  (Pydantic, frozen, evaluation_result.py)
  attrs: result_id, request_id, specification_id, evaluator_name, evaluator_version, dimensions: DimensionScore[],
         overall_score, grade, confidence, reasoning, strengths: EvidenceLinkedClaim[], weaknesses[],
         missing_reasoning: MissingReasoningItem[], concept_coverage[], suggested_improvements[], raw_model_output
  relation: EvaluationRequest 1 ── 1 EvaluationResult (by request_id); EvaluationLedger 1 ── * EvaluationResult (per session)

CLASS tech_interview.Question  (frozen dataclass, tech_interview/bank.py)  — question-bank question
  attrs: id, subject, topic_id, topic, difficulty, text, reference_answer, key_points: KeyPoint[], confidence,
         source_pages[], core_point, curated, interview_priority
  composition: 1 ── 2..5 KeyPoint(point, followup, followup_answer, variants[], followup_replies[])
  methods: subject_label

CLASS TechInterview  (tech_interview/session.py)  — technical interview session
  ctor: TechInterview(questions: Question[], mode)
  attrs (current question state _Current): question, answer, grade: Grade, followups_used, clarified, asked_points, recovered
  methods: prompt(), submit(answer) -> {prompt|record}, summary(), finished
  relations: TechInterview 1 ── 8..10 Question;  uses grade_answer() → Grade(score, keypoint_score,
             reference_similarity, covered[], partial[], missing[], clarity: Clarity) and followup.decide()

SQLAlchemy models (models.py):
  User(id, email, password_hash, role, is_active, consent_data, consent_training, avatar, created_at, last_login_at)
       methods: set_password(), check_password(), current_resume(), to_dict()
  StudentProfile(id, user_id, full_name, date_of_birth, phone, class10_*, higher_secondary_*, college, degree, branch, cgpa, graduation_year)
  Resume(id, user_id, file_path, original_filename, sha256, parsed_profile: JSON(CandidateProfile), is_current, uploaded_at)
  InterviewSession(id, user_id, resume_id, session_type, status, started_at, ended_at, overall_score, overall_grade,
                   questions_answered, evaluator_name, evaluator_version, integrity: JSON, attention_metrics: JSON, summary: JSON)
  SessionTurn(id, session_id, turn_number, question_text, category, source_id, is_followup, answer_text, overall_score, grade, evaluation: JSON)
  associations: User 1 ── 1 StudentProfile;  User 1 ── * Resume;  User 1 ── * InterviewSession;
                Resume 0..1 ── * InterviewSession (SET NULL on delete);  InterviewSession 1 ── * SessionTurn (cascade)
```

### b) Use case diagram
**Actors:** Candidate (primary); Proctor/Monitoring system (secondary, automated, in the browser); Developer (offline: builds the knowledge base and question bank). There is no admin role: `users.role` has `admin`/`annotator` values but no admin feature uses them.

| Use case | Actor | Relationships |
|---|---|---|
| Sign up | Candidate | «include» Upload resume; «extend» Add profile photo |
| Log in / Log out | Candidate | — |
| Manage profile | Candidate | «extend» Change password, Toggle training consent, Delete account, Change/remove profile photo |
| Manage resumes | Candidate | «include» Parse resume (upload); «extend» Make current, Delete, View/download |
| Take Full Interview | Candidate | «include» Camera setup check, Accept session rules, Round 1 Resume Discussion, Round 2 Technical, View combined report |
| Take Technical Interview | Candidate | «include» Camera setup check, Accept session rules, View technical report |
| Answer a question | Candidate | «extend» Answer by voice; «extend» Answer follow-up / clarification (Round 2) |
| View Home insights | Candidate | — |
| Browse / reopen / delete past sessions | Candidate | — |
| Monitor attention (gaze, head pose) | Proctor system | extends every interview use case |
| Verify liveness (head-turn challenge) | Proctor system | «extend» Monitor attention |
| Detect second person / poor lighting | Proctor system | «extend» Monitor attention |
| Enforce session rules → Terminate interview | Proctor system | «extend» Take Full / Technical Interview (on violation) |
| Record session turns; mark abandoned sessions | Proctor system (backend) | «include» in every interview |
| Build slide knowledge base | Developer | — |
| Generate / rank / enrich / curate question bank | Developer | «include» Build slide knowledge base |

### c) Sequence diagram: one Full Interview
Participants: **Browser** (index.html) · **Flask routes** (app.py / account_routes / session_routes) · **ResumeEngine** · **ConversationEngine** (planner, realizer, memory) · **Evaluator** (AveragedEvaluator + answer_gate) · **TechInterview** (selector, grader, followup) · **session_history** · **SQLite**

1. Browser → Flask: `POST /api/auth/login {email, password, remember}` → `User.check_password` → `login_user` → 200 `{user}`; then `GET /api/auth/me` → `{user, profile, current_resume}` → Home.
2. Browser: Full Interview card → `openResumeDiscussionSetup` (saved resume preselected).
3a. (saved resume) Browser → Flask: `POST /api/resumes/<id>/use` → load `Resume.parsed_profile` → `_candidate_profiles[profile_<hex>]` → 200 `profile_to_frontend_format(...) + session_id`.
3b. (new upload) Browser → Flask: `POST /api/classify-resume (file)` → `add_resume_for_user` → `resume_store` saves file → ResumeEngine `generate_candidate_profile_via_engine` → `ResumePipeline.run` → `map_to_candidate_profile` → SQLite INSERT `resumes` (current) → 200 profile + session_id.
4. Browser: Briefing → `rdShowIntegrityRules` → `showCameraSetup` (getUserMedia, FaceLandmarker checks) → `showInterviewRules("full")` → `acceptInterviewRules` → `requestFullscreen` → `startDomainDiscussionFromDashboard` → `initializeGazeMonitoring`.
5. Browser → Flask: `POST /api/resume-discussion-v2/start {session_id}` → ConversationEngine `start_conversation(profile)` → `Planner.plan_next` → `question_realizer.realize` → InterviewQuestion → session_history `begin_resume_discussion` → SQLite INSERT `interview_sessions` (in_progress) → 200 `{conversation_id, question, total_questions}`; Browser `proctorArm()`.
6. Round 1 turn: Browser → Flask: `POST /api/resume-discussion-v2/reply {session_id, answer}` → `owns_conversation` → ConversationEngine `advance_conversation` → `evaluation_engine.build_request` → Evaluator `AveragedEvaluator.evaluate` (OverallSingleEvaluator + HeuristicEvaluator) → `answer_gate.gate` → `EvaluationLedger.append` → `memory.record_turn` → `planner.advance` → `plan_next` → `realize` → session_history `record_resume_discussion_turn` → SQLite INSERT `session_turns` → 200 `{evaluation, next_question, is_completed, turn_number}`. (Repeat up to 10.)
7. Round 1 end: Browser → Flask: `POST /api/resume-discussion-v2/end {session_id, integrity, attention_metrics}` → `end_conversation` → `interview_feedback.build_feedback` → session_history `finish_resume_discussion` → SQLite UPDATE session (completed) → 200 summary; Browser `showRoundTransition` (still full screen, webcam on).
8. Round 2 start: Browser `beginRound2` (attention counters reset) → Flask: `POST /api/tech-interview/start {mode: "round2"}` → `load_bank()` (curated tier) → `technical_history(user)` (seen questions, topic averages) → `select_questions(bank, 8, …)` → `TechInterview(questions)` → session_history `begin_tech_interview` → SQLite INSERT session → 200 `{session, prompt}`.
9. Round 2 answer that triggers a follow-up: Browser → Flask: `POST /api/tech-interview/<id>/answer {answer}` → `TechInterview.submit` → `grade_answer` (NLI DeBERTa entailment + MiniLM similarity per key point) → `followup.decide` → 200 `{prompt: {kind: "followup", text}}`. Browser → Flask: `POST /api/tech-interview/<id>/answer {answer}` (follow-up reply) → `submit` → `followup_covers` → recovered credit → `_close` → session_history `record_tech_interview_turn` → SQLite INSERT `session_turns` → 200 `{prompt: next main question}`.
10. Round 2 end: Browser → Flask: `POST /api/tech-interview/<id>/end {attention_metrics, integrity}` → `TechInterview.summary()` → session_history `finish_tech_interview` → SQLite UPDATE → 200 report.
11. Final report: Browser `showFinalResults` → `rdRenderReport(round1, {combined: {round2, integrity, attention}})` → `rdCombinedVerdict` headline; `stopGazeMonitoring`; exit full screen.
(Violation at any step: Browser `proctorViolation(type)` → `interviewTerminate()` → the active `/end` call with `integrity.terminated = true` → session saved `terminated`.)

### d) Package diagram
| Package | Contains | Depends on |
|---|---|---|
| `main_cap/cap` (app core) | `app.py`, `account_routes.py`, `session_routes.py`, `session_history.py`, `insights.py`, `models.py`, `database.py`, `migrations/` | resume_engine, planning, evaluation, tech_interview, templates/static |
| `main_cap/cap/resume_engine` | 8-stage parser, parsers, gazetteers, mapper | (none of the app packages) |
| planning (logical, `main_cap/cap`) | `planner.py`, `topic_pool.py`, `question_specification.py`, `question_realizer.py`, `question_families.py`, `discussion_policy.py`, `conversation_memory.py` | candidate profile contract only (no evaluation imports, AST-tested) |
| evaluation (logical, `main_cap/cap`) | `evaluator*.py`, `evaluation_*.py`, `averaged_evaluator.py`, `overall_single_evaluator.py`, `heuristic_evaluator.py`, `answer_gate.py`, `interview_feedback.py`, model layer | question_specification (types), model weights |
| `conversation_engine.py` | Round 1 facade | planning + evaluation |
| `main_cap/cap/tech_interview` | `bank.py`, `selector.py`, `grader.py`, `followup.py`, `session.py` | question_bank (data) |
| `main_cap/cap/templates`, `static` | `index.html` (UI, proctoring, webcam), `face_landmarker.task` | Flask API (HTTP), MediaPipe CDN |
| `rag_system/rag_tester/slide_rag` | Offline slide pipeline + bank tools | lecture slides, Ollama, models |
| `rag_system/rag_tester/question_bank` | 5 subject JSON files + quality review | produced by slide_rag; read by tech_interview |
| `resume_classifier` | DOCX/DOC/TXT text extraction | — |
| `grader_eval`, `integration_checks` | Evaluation sets and scripts | tech_interview, evaluation, resume_engine |
| `docs/architecture` | Design documents | — |

### e) Deployment diagram
| Node | Runs | Connects via |
|---|---|---|
| **Candidate's browser** (Chrome/Edge, webcam, mic) | `index.html` SPA; MediaPipe Face Landmarker (WASM); Web Speech API | HTTP/JSON to Flask (localhost:5000); HTTPS to jsDelivr CDN (MediaPipe bundle) and Google Fonts; `/static/models/face_landmarker.task` from Flask |
| **Application server** (any CPU machine) | `python app.py` (Flask, single process); in-process models: MiniLM, nli-MiniLM2, nli-DeBERTa-v3, DeBERTa-v3 v5_1088 | Files: `question_bank/*.json`, weights (`deployed_model_overall_single_v5_1088/`), Hugging Face cache; HTTPS to Hugging Face Hub on first run only |
| **Database** (same machine) | SQLite `instance/app.db` + resume files `instance/uploads/` | File access via SQLAlchemy |
| **Offline GPU machine** (dev laptop, RTX 5050 8 GB) | Ollama `qwen3:8b`, Qwen3-VL-2B, slide pipeline, bank generation/enrichment | Reads slide PDFs; writes `knowledge_base_v2/` and `question_bank/*.json` → committed to Git |
| **GitHub** | Repository (branch `ninad_latest`) + Git LFS (weights) | git over HTTPS |

---

## 6. MODULE-BY-MODULE PROGRESS

### 6.1 Accounts, database, session history, Home insights
- Signup with academic details (Class 10, Class 12/Diploma, college, CGPA), resume and optional photo; per-field validation; consents.
- SQLite with 5 tables and 3 migrations applied automatically at startup; cascade deletes; resume files stored under random names with SHA-256.
- Every interview saved turn by turn; statuses completed / terminated / abandoned; reports rebuilt exactly from saved turns.
- Home: sessions finished, average/best score, average attention, 10-session trend, "Focus next" (recurring reasoning gaps → weak dimensions → weak technical topics).
- **Results:** tests `test_accounts.py` 31 (6 profile-photo), `test_app_auth_guard.py` 8, `test_session_history.py` 13, `test_insights_and_settings.py` 9; all pass. **Before/after:** Review 1 had no accounts or persistence (in-memory only).

### 6.2 Full Interview flow and standalone Technical Interview
- Full Interview: rules → full screen → Round 1 (10) → summary → Round 2 (8) → combined report; one unbroken proctored session.
- Standalone Technical Interview: 10 questions, same rules and report cards.
- Combined report headline from both round scores (e.g. "Strong on your projects, but the technical round needs real work.").
- **Results (live end-to-end run against the real server and models, 2026-09-30):** 22/22 checks passed: signup with resume and photo, profile parsed, 10 Round 1 answers, "idk" scored 0.02 vs 0.87 for a real answer, feedback present, Round 2 8 distinct questions, standalone 10 distinct questions with no overlap with Round 2, history lists 3 sessions, reopen works, API locked after logout; no server errors. **Before/after:** Round 2 was 5 hardcoded fill-in-the-blank CN questions scored by token overlap.

### 6.3 Resume Intelligence Engine
- 8 local stages: extraction → layout (1/2 columns) → sections → entity parsers → cross-reference + interview seeds → normalization → validation → confidence.
- Phase 1 rewrite (teammate) integrated with fixes (dates, sentence-like bullets, page footers, certifications, names, phones).
- **Results (41 resumes; `integration_checks/`):** golden-corpus jobs found 21 → 33; real-resume education entries 5 → 8; no sentence junk in skills; Round 1 plans 91 → 110 questions over 38 resumes. Tests: 511 pass (31 golden-corpus fixtures).

### 6.4 Round 1 questioning and evaluation
- **Questioning:** deterministic planner + 21 phrasing families; project seeds asked verbatim with the project named; family and item rotation.
  - Over 38 resumes: repeated questions 2 → 0; same family within 3 turns 26 → 6; back-to-back same resume item 33 → 20; resume-specific questions 0 → 9.
- **Evaluation:** `AveragedEvaluator` = 0.8 × DeBERTa-v3 `overall_single_v5_1088` + 0.2 × heuristic; non-answer gate; data-driven feedback.

| Test set | Blended evaluator | Heuristic alone |
|---|---|---|
| Teammate's 151-answer held-out test set (QWK) | **0.86** (98% within one grade) | 0.10 |
| 58-answer stress set (QWK) | **0.70**; pairs ordered right 57/61; strong answers crushed 0/31; weak inflated 0/8 | 0.23 |

- **Non-answer gate:** 0/628 genuine answers wrongly flagged (teammate's original: 42/628); junk replies caught 16/16 (his: 14/16).
- **Before/after:** Review 1 evaluator: old multi-task DeBERTa QWK 0.40 vs heuristic 0.13 on a synthetic 362-example test set (different test set; not directly comparable).
- **Known biases:** score tracks answer length (r = 0.70); short but relevant one-liners can score high (e.g. "we built and tested it locally" got 87%); factual correctness is not verified (the report says so).

### 6.5 Slide RAG pipeline
| Subject | Slides | Content slides | Sections |
|---|---|---|---|
| CN | 774 | 625 | 477 |
| DBMS | 1,462 | 1,213 | ~690 |
| DSA | 1,607 | 1,258 | ~557 |
| OOAD | 1,038 | 780 | ~507 |
| OS | 943 | 805 | 587 |
| **Total** | **5,824** | **4,681** | **~2,818** |

| Subject | hit@1 | hit@5 | Old index hit@1 / hit@5 |
|---|---|---|---|
| DBMS | 0.77 | **1.00** | 0.59 / 0.82 |
| DSA | 0.82 | **1.00** | 0.55 / 0.68 |
| OOAD | 0.73 | **1.00** | 0.68 / 0.82 |
| CN | 0.74 | **0.96** (1.00 with vision) | n/a |
| OS | 0.85 | **1.00** | n/a |

- 122 hand-labelled gold questions + 750 generated probes (probe hit@5 0.97–0.99).
- **Ablations:** breadcrumb headers: no measurable change; bge-small instead of MiniLM: no gain; no reranker: hit@5 drops (DBMS 1.00 → 0.95) but OOAD hit@1 rises (0.73 → 0.82). Vision stage on CN: gold hit@5 0.96 → 1.00, MRR 0.83 → 0.89, diagram set hit@1 0.45 → 0.55.

### 6.6 Question bank and NLI grader
**The 422-question bank:**

| Stage | CN | DBMS | DSA | OOAD | OS | Total | Easy / Medium / Hard |
|---|---|---|---|---|---|---|---|
| Generated from the slides | 60 | 101 | 80 | 87 | 94 | **422** | 109 / 217 / 96 |
| Passed automated ranking | 39 | 61 | 50 | 64 | 68 | 282 | 86 / 164 / 32 |
| Curated top tier (served) | 18 | 29 | 20 | 36 | 29 | **132** | 49 / 70 / 13 |

- **How questions are verified:**
  - Every key point carries a slide quote that must appear in the slide text (fuzzy match ≥ 88) and relate to the point (cosine ≥ 0.35).
  - Each question keeps at least 2 verified points, and trivia patterns are rejected.
  - Qwen3 judge pass: on topic, tests understanding, quotes support the points, reference answer correct.
  - Distinctness checks (cosine < 0.85 within a topic, < 0.90 across the bank).
  - Confidence ranking from six signals.
  - Every active question was hand-scored 1–10 with a note.
- 1,057 key points (1,055 with a prepared follow-up); the curated tier has 367 key points, all with follow-ups; curated mean quality 8.23/10; it covers 118 topics.
- **Interview priority:** topics rated by interview frequency (★★★ / ★★ / ★); 87% of questions asked come from the most-asked topics (47% without weighting); every 8-question interview gets 8 distinct topics; no repeats across 5 consecutive interviews (3,000 simulated sessions).
- **NLI grader** (`cross-encoder/nli-deberta-v3-base` + MiniLM; score = 0.85 × key points + 0.15 × reference similarity). Tuning set: key-point agreement 85% (earlier MiniLM NLI: 72%).

| Evaluation (re-run 2026-10-01) | Key-point agreement | Score correlation (r) | Same move-on decision as human | Confidently wrong answers avg score |
|---|---|---|---|---|
| 400 held-out answers, 100 questions | **81%** | **0.84** | **357/400 (89%)** | 0.21 |
| Curated questions only (180 answers, 45 questions) | **81%** | 0.82 | 159/180 (88%) | 0.25 |
| Other questions (220 answers, 55 questions) | 82% | 0.85 | 198/220 (90%) | 0.17 |

- Weak answers passed 3%; strong answers held back 9% (400-answer set).
- **Real answers** (40 typed by a team member; tuning half / held-out half): r 0.80 / 0.68; same decision 15/20 / 14/20; **follow-ups judged right 35/40** (was 15/40 before the follow-up rewrite and enrichment); the grader is stricter than the human on the held-out half (avg 0.45 vs 0.67).

### 6.7 Webcam monitoring and proctoring
- **Camera setup check** before the rules: blocks on no camera, no face, or more than one face; warns on off-centre, distance, low light (face brightness < 65), blur (sharpness < 15).
- **Attention:**
  - Head pose: yaw/pitch beyond 26°, smoothed (EMA 0.30).
  - Iris gaze: thresholds |x| 0.44, |y| 0.60, with a calibrated baseline and 5 confirming frames.
  - Fusion: 0.35 × head + 0.55 × gaze (+0.10 when they agree); a deviation starts at ≥ 0.50 and ends < 0.34.
  - States: CAUTION at 3.5 s, WARNING at 8.5 s, FACE_ABSENT at 7.5 s, 45 s cooldown per warning type.
- **Liveness:** random head-turn challenge (13° yaw, 12 s timeout); re-check after 35 s with no natural facial activity.
- **Alerts:** red banner for a second person (shown after 0.6 s, cleared 1.2 s after); amber "please sit in a well-lit environment" for dark/blurry video (2.5 s hysteresis). Spoken warnings are muted while either microphone is on.
- **Session rules:** full screen, no tab/window switch (1.5 s blur grace), no copy/cut/paste; the first violation terminates the interview.
- **Saved per session:** attention metrics (warnings, face-absent warnings, time looking away, liveness re-checks and failures, attention score 0–100: FOCUSED ≥ 85, MOSTLY FOCUSED ≥ 65, DISTRACTED) and the integrity record (type, label, round, question number, time). Frames never leave the browser.
- **Results:** `test_session_integrity.js` passes. The detection-rate numbers have not been measured on a labelled video set ([TEAM INPUT NEEDED] if the panel expects them).

### 6.8 Performance and testing
| Metric | Before | Now | Source |
|---|---|---|---|
| Server start | 6.8 s | **2.1 s** | `model_warmup.py` (§5.1) |
| First technical answer | 16.2 s | **0.2 s** | §5.1 |
| Round 1 answer (end to end) | — | **~0.3 s** | live run 2026-09-30 (RTX 5050 laptop) |
| Round 2 turn incl. follow-ups | — | **~0.3 s** | live run 2026-09-30 |
| Round 1 trained model per answer | — | ~0.1 s GPU / ~1 s CPU | §4.6 |
| Server memory after loading models | — | 2.8 GB | measured 2026-09-30 |

| Test suite (re-run 2026-10-01) | Result |
|---|---|
| App (`main_cap/cap`, excluding resume engine) | **1,241 passed, 17 skipped, 0 failed** |
| Resume engine | **511 passed** |
| Frontend (Node) | **9/9 test files pass** |
| Slide pipeline | **19 passed** |
| End-to-end live journey | **22/22 checks** |

---

## 7. SCREENSHOTS TO CAPTURE

Run `python app.py` in `main_cap/cap` and open http://localhost:5000 in Chrome. Use an account with at least one finished Full Interview for the history shots.

1. **Login screen**: open the URL while logged out.
2. **Signup step 1 with profile photo**: "Create account" → step 1 (photo picker filled).
3. **Signup step 3, resume drop zone**: Continue to step 3.
4. **Home**: log in; the greeting, two start cards, 4 stats, trend sparkline, "Focus next", recent sessions.
5. **Resume screen (saved resume)**: Home → "Full Interview" card.
6. **Candidate briefing**: "Continue with this resume" → wait for the build animation → briefing grid.
7. **Camera setup check (all green)**: briefing CTA → the camera check overlay with the checklist.
8. **Camera setup check: second person blocked**: same overlay with a second person in frame (Continue disabled).
9. **Rules screen**: Continue on the camera check → the "full" rules overlay.
10. **Round 1 question**: accept the rules → first Round 1 question with the webcam panel visible.
11. **Live alert banners**: during Round 1, a second person in frame (red banner); dim the light (amber banner).
12. **Liveness challenge**: wait for the "turn your head slightly to your left/right" prompt.
13. **Round 1 summary**: finish 10 answers → "Round 1 complete" screen (score, grade, verdict, Begin Round 2).
14. **Round 2 question**: Begin Round 2 → first technical question.
15. **Round 2 follow-up**: give a partial answer → the follow-up chat turn.
16. **Combined report (top)**: finish Round 2 → headline + score line.
17. **Combined report: Round 1 section**: performance snapshot, "Before Your Next Interview", topics, discussion record.
18. **Combined report: Round 2 section**: per-subject bars, per-question cards with ✓/~/✗ key points and model answer.
19. **Combined report: attention section**: "Attention · Whole interview".
20. **Termination**: start a Technical Interview → press Alt+Tab → the red "Session terminated" overlay; then the terminated banner on the results page.
21. **Standalone Technical Interview results**: Home → "Technical Interview" → finish 10 → results page.
22. **Sessions page**: top nav → Sessions (filter chips, rows).
23. **Reopened past report**: click a Resume Discussion row.
24. **Technical session detail**: click a technical row.
25. **Profile page**: top nav → Profile (personal details, resumes, account settings, photo).
26. **Voice answer**: click the mic in Round 1 and dictate (transcribed text in the box).

---

## 8. PENDING WORK

Final review / submission date: [TEAM INPUT NEEDED]

| Task | Why it matters | Effort | Depends on |
|---|---|---|---|
| Generate questions for the 41 most-asked topics with no curated question (29 have no question at all, e.g. OSI/TCP-IP models, DNS, paging, round robin, SJF, quick sort, hashing, SQL views, BCNF) | These are the topics interviewers ask most; grows the served bank | Large (GPU, ~hours) | Ollama + slides; vision text as evidence for diagram-only topics; OOAD rebuild |
| Fix or replace the 35 active questions scored ≤ 4/10 (false key points, references to unseen text, vague) | Wrong key points mis-grade correct answers | Medium | Review list in `quality_review.md` |
| Add curated hard DSA questions (currently 0) | DSA's hard slot falls back to easy/medium | Small–medium | Generation run |
| Rebuild the OOAD index (extractor v3 → current) and re-map its topics | Stale answer-key slides may have fed some questions | Small | Slides |
| Run the vision stage on the other subjects (~550 picture/table slides, ~1,100 diagram slides) | Diagram-only topics can't get questions or good retrieval | Large (GPU ~4–5 h) | GPU |
| Link the two rounds of a Full Interview in the database | History shows two entries; the combined report isn't reopenable | Medium (migration + UI) | — |
| 30-question MCQ test (30 min, +1 / −0.25) | Planned third session type | Large | Question bank; blind-solve filter |
| Voice interview: speak the questions (text-to-speech) and/or merge the `Audio` branch (Whisper) | Promised Review 1 item, currently partial | Medium | Team decision on browser vs Whisper |
| Pseudocode evaluator | Promised Review 1 item, not started | Large, or drop with justification | Team decision |
| Cap scores of very short Round 1 answers (e.g. under ~12 words) | One-liners currently score high | Small | Team agreement on the policy |
| Make the technical grader less strict on short informal correct answers | Real-answer held-out avg 0.45 vs human 0.67 | Medium | More real labelled answers |
| Calibrate webcam thresholds (blur 15, lighting 65, gaze) on several webcams | Avoid false alerts on other hardware | Small | Teammates' laptops |
| Remove dead legacy code (old quiz routes, v1 discussion engine, broken legacy RAG files, archived references) | Smaller, clearer codebase | Medium | Tests updated |
| Production hardening: WSGI server, persistent live state, login rate limiting, email verification | Multi-user deployment | Medium–large | — |
| Re-upload resumes parsed by the old engine (pre-2026-09-30) | Old profiles show stack text in project titles | Small | Users |
| Fix documentation drift listed in section 12 | Docs must match code for the final review | Small | — |
| Decide how `ninad_latest` relates to `main` (it has no shared history) | A PR into main will show "unrelated histories" | Small–medium | Team decision |

---

## 9. KNOWN LIMITATIONS

| # | Limitation | Mitigation / plan |
|---|---|---|
| 1 | The technical grader checks that key points are *stated*, not that facts are right: confidently wrong answers average ~0.21 (0.25 on curated questions). | Slide-backed key points plus a follow-up second chance; plan: a contradiction check against the reference answer. |
| 2 | The Round 1 evaluator rewards length (r = 0.70) and can over-score short relevant answers; it does not verify factual claims. | Non-answer gate, 20% heuristic blend, scope note on the report; plan: short-answer cap. |
| 3 | Proctoring is client-side and can be bypassed with browser DevTools. | Zero tolerance plus a saved integrity record; plan: server-side heartbeat checks. |
| 4 | Webcam thresholds (gaze, lighting, blur) were tuned on one laptop; detection rates aren't measured on labelled video. | Debounced, visual-only alerts that never terminate on their own; plan: calibrate on more webcams. |
| 5 | Bank coverage: 41 most-asked topics lack a curated question, DSA has no curated hard question, and the served tier is 132 of 422. | Interview-priority weighting; ranked + curated tiers; plan: targeted generation (section 8). |
| 6 | Questions were generated by an 8B model; its judge is lenient on reasoning. | Quote verification in code, confidence ranking, human scoring of all 282 active questions. |
| 7 | The trained Round 1 model was validated on a held-out split of its own 1,088-example dataset; performance on unseen real candidates is unmeasured. | Heuristic blend + gate; plan: collect consented real sessions (training consent exists in signup). |
| 8 | Live interview state is in memory in one process; Flask development server. | Every answered turn is persisted immediately; abandoned sessions handled; plan: WSGI + shared state. |
| 9 | The two rounds of a Full Interview are stored as two sessions. | Combined report shown live at the end; plan: link rounds in the DB. |
| 10 | Needs internet for MediaPipe (CDN), first-run model downloads and voice input (Chromium only). | Documented in `SETUP_PREREQUISITES.md`; plan: serve MediaPipe locally. |

---

## 10. CONTRIBUTIONS

**How counted (recomputed from git, 2026-10-01):** non-blank lines of `.py`, `.js` and `.html` files tracked on `ninad_latest` (`git ls-files`). Test files (`test_*`, `*/tests/*`) are counted separately. Each file is attributed to the module owner. `templates/index.html` is split: its webcam, camera-check and session-integrity styles, markup and script go to Surya; the rest of the UI goes to Nandagopal. Markdown, JSON data (including the question bank), weights and anything not in git are excluded. The recount matches your figures exactly.

| Member | Areas owned | LOC | Test LOC |
|---|---|---|---|
| **Mayuran** | Resume Intelligence Engine (8-stage parser, Phase 1 rewrite), Candidate Profile, resume text extraction, Round 1 question planning and phrasing (planner, topic pool, realizer, families, discussion policy, conversation engine) | 13,618 | 8,796 |
| **Ninad** | Slide RAG pipeline, 422-question bank (generation, verification, ranking, enrichment, curation, interview priority), technical interview (NLI grader, follow-ups, selector), Round 1 answer evaluation (DeBERTa-v3 evaluator integration, heuristic evaluator, non-answer gate), ML research track, grader evaluation | 23,498 | 9,078 |
| **Nandagopal** | Accounts and login, profile photos, SQLite database and migrations, session history, Home insights, Sessions/Profile screens, report pages and the rest of the UI | 9,179 | 2,321 |
| **Surya** | Webcam monitoring (MediaPipe face tracking, gaze/head pose, attention score), liveness checks, camera setup check, second-person and lighting alerts, session-integrity rules | 2,162 | 235 |
| **Total** | | **48,457** | **20,430** |

---

## 11. REFERENCES

[1] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in *Proc. EMNLP-IJCNLP*, 2019, pp. 3982–3992.
[2] J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, "BERT: Pre-training of deep bidirectional transformers for language understanding," in *Proc. NAACL-HLT*, 2019, pp. 4171–4186.
[3] P. He, X. Liu, J. Gao, and W. Chen, "DeBERTa: Decoding-enhanced BERT with disentangled attention," in *Proc. ICLR*, 2021.
[4] P. He, J. Gao, and W. Chen, "DeBERTaV3: Improving DeBERTa using ELECTRA-style pre-training with gradient-disentangled embedding sharing," in *Proc. ICLR*, 2023.
[5] W. Cao, V. Mirjalili, and S. Raschka, "Rank consistent ordinal regression for neural networks with application to age estimation," *Pattern Recognit. Lett.*, vol. 140, pp. 325–331, 2020. (CORAL)
[6] J. Cohen, "Weighted kappa: Nominal scale agreement provision for scaled disagreement or partial credit," *Psychol. Bull.*, vol. 70, no. 4, pp. 213–220, 1968. (QWK)
[7] S. R. Bowman, G. Angeli, C. Potts, and C. D. Manning, "A large annotated corpus for learning natural language inference," in *Proc. EMNLP*, 2015, pp. 632–642. (SNLI; NLI cross-encoders)
[8] A. Williams, N. Nangia, and S. Bowman, "A broad-coverage challenge corpus for sentence understanding through inference," in *Proc. NAACL-HLT*, 2018, pp. 1112–1122. (MultiNLI; NLI cross-encoders)
[9] W. Wang, F. Wei, L. Dong, H. Bao, N. Yang, and M. Zhou, "MiniLM: Deep self-attention distillation for task-agnostic compression of pre-trained transformers," in *Proc. NeurIPS*, 2020. (all-MiniLM-L6-v2, nli-MiniLM2, ms-marco-MiniLM)
[10] P. Bajaj *et al.*, "MS MARCO: A human generated MAchine Reading COmprehension dataset," arXiv:1611.09268, 2016. (reranker training data)
[11] R. Nogueira and K. Cho, "Passage re-ranking with BERT," arXiv:1901.04085, 2019. (cross-encoder reranking)
[12] P. Lewis *et al.*, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Proc. NeurIPS*, 2020, pp. 9459–9474.
[13] Qwen Team, "Qwen2.5 technical report," arXiv:2412.15115, 2024. (legacy RAG only; see flags)
[14] A. Yang *et al.*, "Qwen3 technical report," arXiv:2505.09388, 2025.
[15] Qwen Team, "Qwen3-VL-2B-Instruct," model card, Hugging Face, 2025. [Online]. Available: https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct
[16] J. Johnson, M. Douze, and H. Jégou, "Billion-scale similarity search with GPUs," *IEEE Trans. Big Data*, vol. 7, no. 3, pp. 535–547, 2021. (FAISS)
[17] S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Found. Trends Inf. Retr.*, vol. 3, no. 4, pp. 333–389, 2009.
[18] C. Lugaresi *et al.*, "MediaPipe: A framework for building perception pipelines," arXiv:1906.08172, 2019.
[19] Y. Kartynnik, A. Ablavatski, I. Grishchenko, and M. Grundmann, "Real-time facial surface geometry from monocular video on mobile GPUs," arXiv:1907.06724, 2019. (Face Landmarker mesh)
[20] A. Ablavatski *et al.*, "Real-time pupil tracking from monocular video for digital puppetry," arXiv:2006.11341, 2020. (iris landmarks)
[21] T. Wolf *et al.*, "Transformers: State-of-the-art natural language processing," in *Proc. EMNLP: System Demonstrations*, 2020, pp. 38–45.
[22] A. Paszke *et al.*, "PyTorch: An imperative style, high-performance deep learning library," in *Proc. NeurIPS*, 2019, pp. 8024–8035.
[23] M. Grootendorst, "KeyBERT: Minimal keyword extraction with BERT," Zenodo, 2020, doi: 10.5281/zenodo.4461265.
[24] W3C Web Platform Incubator Community Group, "Web Speech API," draft community group report. [Online]. Available: https://webaudio.github.io/web-speech-api/
[25] Ollama, "Ollama," software, 2025. [Online]. Available: https://ollama.com (local LLM runtime, llama.cpp engine)
[26] RapidAI, "RapidOCR," software. [Online]. Available: https://github.com/RapidAI/RapidOCR
[27] Gemini Team, Google, "Gemini 2.5: Pushing the frontier with advanced reasoning, multimodality, long context, and next generation agentic capabilities," arXiv:2507.06261, 2025. **Cite only if Gemini is mentioned:** it is now developer tooling only, not part of the system.

**Flags for the Review 1 deck:**
- **RoBERTa** (Liu *et al.*, 2019) and **DistilRoBERTa**: no longer apply. The question classifier was archived and never ran in the app.
- **CodeBERT** (Feng *et al.*, 2020): no longer applies. It exists only in a broken legacy file, and code evaluation is not part of the system.
- **Qwen2.5-1.5B** [13]: legacy. It was replaced by offline Qwen3-8B generation [14]; keep it only as "Review 1 baseline".
- **FLAN-T5**, if cited: no longer applies (phrasing uses templates).
- **BLIP**, if cited: no longer applies (diagram understanding uses Qwen3-VL [15]).
- **Whisper** (Radford *et al.*, "Robust speech recognition via large-scale weak supervision," *Proc. ICML*, 2023): applies only if the `Audio` branch is merged.

---

## 12. INCONSISTENCIES FOUND

In `PROJECT_DOCUMENTATION.md` unless stated otherwise:

| # | Where | Says | Correct version |
|---|---|---|---|
| 1 | §3.3 sequence diagram | Round 2 = `POST /api/technical-sessions` → 5 × (`/api/next_question` + `/api/evaluate`) | `POST /api/tech-interview/start {mode:"round2"}` → 8 × `/api/tech-interview/<id>/answer` (follow-ups possible) → `/api/tech-interview/<id>/end` (as §5.2 step 6 already says) |
| 2 | §4.23 full-interview flow block | Same old Round 2 flow ("5 × next_question, evaluate") | Same correction as #1; 8 questions |
| 3 | §4.10 routes table | `/api/next_question` and `/api/evaluate` marked "used by the UI (Technical)" | Not called by the UI; legacy routes (as §7 #36 says) |
| 4 | §4.13 "Backend" row | Technical sessions end via `/api/technical-sessions/<id>/end` | `/api/tech-interview/<id>/end` |
| 5 | §4.21 History API table | Lists `/api/technical-sessions` start/end as the technical endpoints | Those are legacy; the live endpoints are `/api/tech-interview/{start, <id>/answer, <id>/end}` |
| 6 | §7 #26 vs §4.12 | #26: spoken warnings check only the technical mic (`isRecording`) | Fixed: `speakAttentionWarning` mutes when either mic is on (`isRecording` or `rdIsRecording`), as §4.12 says |
| 7 | §4.12 "Loading" | Face Landmarker configured for "one face" | `numFaces: 2` (the second face triggers the second-person alert) |
| 8 | §1, §3.4, §4.6 fallback table, §5.1, §5.2 step 4, glossary | Production Round 1 evaluator is `HybridEvaluator` ("hybrid-v1", DeBERTa multi-task authoritative) | Production is `AveragedEvaluator` = 0.8 × `OverallSingleEvaluator` (v5_1088) + 0.2 × heuristic when its weights are present; otherwise the old hybrid tier (weights absent) → heuristic. §4.6 "Round 1 scoring with a trained model" is the correct description |
| 9 | §4.7, §7 #4, §3.6 | Weights file not in the repository; a clone runs on the heuristic; deployment = `deployed_model/` | The v5_1088 weights are in `ninad_latest` via Git LFS under `deployed_model_overall_single_v5_1088/`; only the old Experiment 4 weights are absent |
| 10 | §2, §7 #35 | `Requirements_Global.txt` is missing Pillow and rapidocr-onnxruntime | Both are now listed; legacy-RAG packages (graphviz, matplotlib, pytesseract) are intentionally excluded; torchvision (vision stage only) is still not listed |
| 11 | §2, §7 #30 | `index.html` is ~8,600 lines | 9,308 lines |
| 12 | §3.2 table, §4.24 "Status" | Slide RAG "not yet called by the app", "basis of the planned question bank" | Offline by design; its 422-question bank powers Round 2 and the Technical Interview |
| 13 | §7 #42 | "No human review of the bank has been done yet" | All 282 active questions were hand-scored on 2026-09-30 (`quality_review.md`) |
| 14 | §7 numbering | Items 41 and 42 appear twice (Slide RAG and Documentation drift) | Renumber 41–46 |
| 15 | §7 #41 (Documentation drift: README) | README says Gemini is needed, `main_cap/cap/requirements.txt`, heuristic authoritative | README was rewritten 2026-09-30; these items are resolved |
| 16 | §8 Testing table | `test_tech_interview.py` (19); resume engine 510 tests | 24 tests (§4.25 says 24); resume engine 511 (the same section's summary says 511); `test_model_warmup.py` (5 tests) is not listed |
| 17 | §4.21 "Migrations" | Lists 2 migrations | 3: `ee1633ec7576`, `eeeb3959ae84`, `a7c3e91f2b40` (profile photo), as §4.1 says |
| 18 | §4.1 directory tree | Lists `archive/superseded_caches`, `archive/Roberta`, `parser_tests` "10 PDFs" | `archive/` and the parser-test resumes are local only (gitignored); not in the repository |
| 19 | §1 overview | Repository includes "a RoBERTa question classifier" | Archived locally, not in the repository |
| 20 | §4.10 startup step 6 | `rag_integration` imported at startup | Imported lazily only if the legacy `/api/next_question` route is used (§5.1) |
| 21 | §2 "Pretrained models" table | No entry for the deployed `overall_single_v5_1088` model | Add it: DeBERTa-v3-base fine-tuned overall scorer, 735 MB, Round 1 (80% of the blend) |
| 22 | §4.12 "Attention state machine" | "Warnings are both visual and spoken" | Spoken only while no microphone is on; second-person and lighting alerts are visual only |
| 23 | §4.1 / `CONTRIBUTING.md` | Branch workflow main / adaptive-engine / resume_classifier | Remote branches are main, Audio, feature/webcam-integration, maburan, maburan-new, ninad_latest |
| 24 | `docs/architecture/ResumeDiscussion_v2.md` | v1 behaviour (random jitter, 12/20 target, adaptive follow-ups) | v2: deterministic planner, 10-question budget (already noted in §7) |

---

## 13. TEAM INPUT NEEDED

1. Suggestions and remarks from the Review 1 panel.
2. Guide approval mail for this deck.
3. Final review / submission date.
4. Decision on promised item (3), the pseudocode evaluator: build it or drop it with a justification.
5. Decision on promised item (2), voice: merge the `Audio` branch (Whisper + TTS), add browser text-to-speech for questions, or present it as partial.
6. Confirmation that the module ownership in section 10 matches what each member will present (Nandagopal: accounts, data and UI).
7. The Review 1 deck's reference list, to confirm which flagged references (RoBERTa, CodeBERT, Qwen2.5, FLAN-T5, BLIP) appeared there.
8. Whether the panel expects measured webcam detection rates (would need a small labelled video test).
9. Where and how the teammate's `overall_single_v5_1088` model was trained (hardware, epochs), for the methodology slide.
10. Whether `ninad_latest` should be merged into `main` before the final review (it currently shares no history with `main`).
