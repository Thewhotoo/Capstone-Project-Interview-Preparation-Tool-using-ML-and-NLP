# Project Documentation — AI Resume-Grounded Interview Preparation Platform

> Scope: this document describes the whole repository end to end, as the code actually behaves today, including where older documents (`README.md`, `docs/architecture/*`) have drifted from it. Superseded documents (the old version of this file, `WORKFLOW_INTEGRATION_GUIDE.md`, `WEBCAM_AND_GAZE_MONITORING.md`) were moved to `archive/` (not in the repository).
> Convention: paths are relative to the repository root. Unless noted otherwise, Python module names refer to files in `main_cap/cap/`.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
   - 1.1 [The four main modules](#11-the-four-main-modules)
2. [Tech Stack & Dependencies](#2-tech-stack--dependencies)
3. [High-Level Design (HLD)](#3-high-level-design-hld)
4. [Low-Level Design (LLD)](#4-low-level-design-lld)
   - 4.1 [Directory structure](#41-directory--file-structure)
   - 4.2 [Resume Intelligence Engine (`resume_engine/`)](#42-resume-intelligence-engine-resume_engine)
   - 4.3 [Candidate Profile (`candidate_profile_generator.py`)](#43-candidate-profile-candidate_profile_generatorpy)
   - 4.4 [Resume Discussion: planning & phrasing](#44-resume-discussion--planning--phrasing)
   - 4.5 [Resume Discussion: session orchestration (`conversation_engine.py`)](#45-resume-discussion--session-orchestration-conversation_enginepy)
   - 4.6 [Answer evaluation subsystem](#46-answer-evaluation-subsystem)
   - 4.7 [Trained model layer (DeBERTa)](#47-trained-model-layer-deberta)
   - 4.8 [Improved Answer / coaching & concept analysis](#48-improved-answer--coaching--concept-analysis)
   - 4.9 [ML research track: synthetic data, labeling, training, experiments](#49-ml-research-track)
   - 4.10 [Flask application (`app.py`)](#410-flask-application-apppy)
   - 4.11 [Frontend (`templates/index.html`)](#411-frontend-templatesindexhtml)
   - 4.12 [Webcam, gaze & liveness monitoring](#412-webcam-gaze--liveness-monitoring)
   - 4.13 [Session integrity (full-screen / tab-switch / copy-paste rules)](#413-session-integrity)
   - 4.14 [Legacy v1 discussion engine (`discussion_engine.py`)](#414-legacy-v1-discussion-engine)
   - 4.15 [Supporting subsystems: RAG, RoBERTa, resume classifier, parser benchmark](#415-supporting-subsystems)
   - 4.16 [Data models / schemas (consolidated)](#416-data-models--schemas-consolidated)
   - 4.17 [Design patterns used](#417-design-patterns-used)
   - 4.18 [Internal interfaces between modules](#418-internal-interfaces-between-modules)
   - 4.19 [Configuration & environment variables](#419-configuration--environment-variables)
   - 4.20 [Accounts, login & profiles (`account_routes.py`)](#420-accounts-login--profiles)
   - 4.21 [Database & session history (`database.py`, `models.py`, `session_history.py`)](#421-database--session-history)
   - 4.22 [Home insights & "Focus next" (`insights.py`)](#422-home-insights--focus-next)
   - 4.23 [App shell & the full interview flow (frontend)](#423-app-shell--the-full-interview-flow)
   - 4.24 [Slide RAG pipeline (`rag_system/rag_tester/slide_rag/`)](#424-slide-rag-pipeline)
   - 4.25 [Question bank and session types](#425-question-bank-and-session-types)
5. [Entry Points & Execution Flow](#5-entry-points--execution-flow)
6. [Error Handling & Edge Cases](#6-error-handling--edge-cases)
7. [Known Limitations / Tech Debt / TODOs](#7-known-limitations--tech-debt--todos)
8. [Testing](#8-testing)
9. [Glossary](#9-glossary)

---

## 1. Project Overview

This project is an **AI-powered interview preparation platform built around the candidate's own resume**.

**Accounts and history.** Candidates sign up with their personal and academic details and a resume, which is parsed into a structured **Candidate Profile** and stored with the account. After logging in they land on a **Home** page with:
- their stats and a score trend;
- a **"Focus next"** list of the weaknesses that keep recurring;
- their recent sessions.

A top navigation bar leads to **Sessions** (every past interview, reopenable with its full report) and **Profile** (personal details, resumes, and account settings).

**The Full Interview** is one continuous, proctored session in two rounds:
1. **Round 1 · Resume Discussion:** a 10-question conversation. Every question is traceable to a specific project, job, certification or in-context skill on the resume.
2. A short Round 1 summary.
3. **Round 2 · Technical:** 8 concept questions from the slide-grounded question bank, across CN, DBMS, DSA, OOAD and OS, with a follow-up or clarification request when an answer is unclear or misses a key point (at most 2 per question).
4. A combined final report.

Each Resume Discussion answer is scored across named dimensions (technical accuracy, depth, completeness, communication, architecture, trade-offs, ownership and others). Each score comes with strengths, weaknesses, missing-reasoning gaps and a coaching note. A standalone **Technical Interview** (10 questions) runs only the technical round.

**Proctoring.** Throughout an interview the browser runs webcam attention and liveness monitoring (MediaPipe Face Landmarker). It also enforces zero-tolerance full-screen, no-tab-switch and no-copy-paste rules: the first violation ends the interview. Every session is saved to a SQLite database turn by turn.

The **target users** are students and early-career engineers preparing for placement or technical interviews, who want practice that feels like a senior engineer asking "tell me about *this* project you built", rather than a generic question bank. The design documents frame the Resume Discussion's purpose narrowly: *verify authenticity, depth of contribution, engineering judgement and communication, grounded strictly in what this resume claims.* General CS knowledge is deliberately left to the separate Technical Interview flow.

The **core value proposition** has three parts:
1. **Resume-specific questioning**: a deterministic planner guarantees that every question comes from the resume and can be explained after the fact.
2. **Explainable scoring**: every score carries a reasoning trail, evidence-linked claims and version metadata. It is produced by a hybrid of a fine-tuned **DeBERTa-v3** multi-task evaluator and a deterministic heuristic evaluator, with automatic fallback.
3. **No paid API on the runtime path**: resume parsing moved from a single Gemini call to a fully deterministic, local 8-stage **Resume Intelligence Engine**, and the entire discussion runs locally.

The repository also contains a substantial **ML research track**: synthetic dataset generation, labeling, training infrastructure and five experiment rounds. This track produced the deployed DeBERTa checkpoint. The repository also includes supporting and exploratory subsystems (a RAG question generator, a RoBERTa question classifier, a legacy resume domain classifier, and a parser benchmark harness), most of which are not wired into the shipped UI flow.

**Teammate's branch integrated (2026-09-30, `resumeParser_integration.md`).** A teammate's improved resume engine, Round 1 question-variety changes, a trained Round 1 answer evaluator (blended 80/20 with the heuristic) and data-driven report feedback were merged in, each measured before/after and with a rollback in `archive/` (`resume_engine_backup_2026-09-30/`, `round1_planner_backup_2026-09-30/`, `evaluator_backup_2026-09-30/`). Comparison scripts: `integration_checks/`.

**Slide RAG pipeline and question bank.** `rag_system/rag_tester/slide_rag/` rebuilds the technical knowledge base from the faculty lecture slides of five subjects (CN, DBMS, DSA, OOAD, OS; ~5,800 slides). It reads slides by layout, cleans and classifies them, regroups them into sections, and indexes them for hybrid retrieval with exact slide-page citations. On hand-labelled interview questions it finds the right slides in its top 5 for 96–100% of questions, against 68–82% for the old page-per-chunk index (§4.24). From it and 279 curated topics, a local LLM (Qwen3-8B via Ollama) generated a **422-question technical-interview bank** offline, spanning all five subjects and three difficulty levels. Every key point is backed by a verified slide quote and every question passed an LLM judge; each question then carries a confidence rank, a hand-assigned quality score and an interview-frequency tier, so interviews draw the strongest questions on the most-asked topics first (§4.25). It feeds the standalone Technical Interview (10 questions) and the full interview's Round 2 (8), graded by an NLI grader that needs no LLM or GPU at interview time (`tech_interview/`, §4.25); a 30-question MCQ test is planned for later (`mcq_tobedone.md`).

### 1.1 The four main modules

The project is organised into four modules, each owned by one team member. LOC is non-blank source lines in the repository, excluding tests (2026-09-30).

| # | Module | Owner | What it does | Main code | LOC | Test LOC |
|---|---|---|---|---|---|---|
| 1 | **Resume Intelligence & Resume Discussion** | Mayuran | Parses the uploaded resume into a structured Candidate Profile, then plans and phrases the 10 Round 1 questions, each traceable to a specific project, job, certification or skill | `resume_engine/`, `candidate_profile_generator.py`, `resume_classifier/`, `planner.py`, `topic_pool.py`, `question_realizer.py`, `question_families.py`, `discussion_policy.py`, `conversation_engine.py` | 13,618 | 8,796 |
| 2 | **RAG, Technical Interview & Answer Evaluation** | Ninad | Builds the knowledge base from the lecture slides and the 422-question bank; runs the technical interview with its NLI grader and follow-ups; scores Round 1 answers with the fine-tuned DeBERTa-v3 evaluator blended with the heuristic evaluator | `rag_system/rag_tester/slide_rag/`, `question_bank/`, `tech_interview/`, `evaluation_engine.py`, `averaged_evaluator.py`, `overall_single_evaluator.py`, `heuristic_evaluator.py`, `answer_gate.py`, `deployment_evaluator.py`, ML research track | 23,498 | 9,078 |
| 3 | **Webcam Monitoring & Proctoring** | Surya | In the browser: camera setup check, face tracking (MediaPipe Face Landmarker), gaze and head-pose attention score, head-turn liveness checks, second-person and lighting/blur alerts, and the full-screen / tab-switch / copy-paste rules | Monitoring, camera-check and session-integrity code in `templates/index.html`, `static/models/face_landmarker.task` | 2,162 | 235 |
| 4 | **Accounts, Data & User Interface** | Nandu | Sign up and login, profile photos, the SQLite database and its migrations, saving every session turn by turn, Home stats and "Focus next", the Sessions and Profile screens and the interview report pages | `app.py`, `account_routes.py`, `avatar_store.py`, `database.py`, `models.py`, `migrations/`, `session_history.py`, `session_routes.py`, `insights.py`, `interview_feedback.py`, the rest of `templates/index.html` | 9,179 | 2,321 |
| | **Total** | | | | **48,457** | **20,430** |

**How the modules connect in one Full Interview:**

1. **Module 4** signs the candidate in and stores the resume.
2. **Module 1** turns it into a Candidate Profile and asks the Round 1 questions.
3. **Module 2** scores each Round 1 answer, then runs Round 2 from the question bank and grades it.
4. **Module 3** watches the camera and enforces the session rules throughout; a violation ends the interview.
5. **Module 4** saves every turn and shows the final report, the history and the Home stats.

---

## 2. Tech Stack & Dependencies

### Languages & runtime
| Item | Detail |
|---|---|
| Python | 3.12 (development machine); the whole backend and ML stack |
| JavaScript | Vanilla ES2020+ inline in one HTML page; no framework and no build step |
| HTML/CSS | A single `templates/index.html` (~8,600 lines: inline CSS, then markup, then one inline script) |
| Node.js | Used only to run the frontend unit tests (`node test_*.js`) |

### Backend & ML libraries
Source: `Requirements_Global.txt` is the only requirements file that exists. The per-subsystem `requirements.txt` files referenced in the READMEs are **missing**.

| Library | Used for | Where |
|---|---|---|
| `flask>=3.0` | HTTP server and routing | `app.py` |
| `flask-sqlalchemy>=3.1` | ORM over SQLite (accounts, resumes, sessions) | `database.py`, `models.py` |
| `flask-migrate>=4.0` (Alembic) | Versioned schema migrations, applied automatically at startup | `database.py`, `migrations/` |
| `flask-login>=0.6` | Session-cookie login, `login_required`, `current_user` | `account_routes.py`, `app.py` |
| `python-dotenv` | Loads `main_cap/cap/.env` | `app.py`, `generation_client.py`, `candidate_profile_generator.py` |
| `pydantic>=2` | Frozen, validated contracts (profile, spec, request/result, training records) | Everywhere |
| `PyMuPDF` (`pymupdf`/`fitz`) | PDF span / font / bbox / hyperlink extraction | `resume_engine/extractor.py`, RAG ingestion |
| `python-docx>=1.1` | DOCX extraction (runs, styles, tables, hyperlinks) | `resume_engine/extractor.py`, `resume_classifier` |
| `rapidfuzz` | Fuzzy gazetteer matching (`token_sort_ratio` / `token_set_ratio`) | `resume_engine/sections.py`, parsers |
| `python-dateutil` | Date-range parsing | `resume_engine/dates.py` |
| `sentence-transformers` | SBERT `all-MiniLM-L6-v2` (similarity, section fallback, KeyBERT backbone), NLI cross-encoder | `resume_engine`, `heuristic_evaluator.py`, RAG |
| `keybert` | Keyphrase extraction for project concepts | `resume_engine/parsers/project_parser.py`, legacy v1 |
| `torch>=2.2`, `transformers>=4.49` | DeBERTa-v3 cross-encoder + CORAL heads; Qwen2.5 (legacy RAG) | `model_*.py`, RAG |
| `google-genai>=2` | Gemini 2.5 Flash, now used **only** by dev tooling (Shadow Mode, synthetic generation, rewrite pilot) | `candidate_profile_generator.py`, `generation_client.py`, `rewrite_verifier_client.py` |
| `faiss-cpu`, `rank-bm25` | Vector + BM25 hybrid retrieval | `rag_system/rag_tester`, `slide_rag` |
| `rapidocr-onnxruntime` | OCR of picture-only slides (optional; skipped if not installed) | `slide_rag/extract.py` |
| `torchvision` (must match the installed torch build, e.g. `0.28.0+cu130` for torch 2.13 cu130) | Required by the Qwen3-VL processor | `slide_rag/vision.py` |
| `pdfplumber` | Legacy resume text extraction | `resume_classifier`, `parser_tests` |
| `datasets`, `scikit-learn`, `accelerate` | RoBERTa training (archived) | `archive/Roberta/` |
| `sentencepiece`, `protobuf`, `tiktoken` | DeBERTa-v3 tokenizer requirements | model layer |
| `pytest` | Python tests (many files are `unittest`-style and pytest-collectable) | tests |

Packages the code imports that are **missing from `Requirements_Global.txt`**: `graphviz`, `matplotlib`, `pytesseract`, `Pillow` (all legacy RAG diagram/OCR code), and `rapidocr-onnxruntime` and `torchvision` (slide pipeline). The Tesseract and Graphviz system binaries are needed only by the legacy RAG code.

**Hardware used for the slide pipeline:** an NVIDIA RTX 5050 laptop GPU (8 GB VRAM) with CUDA 13.0. Embeddings and the reranker use CUDA automatically when it is available; the vision model (Stage 3) needs the GPU.

### Pretrained models
| Model | Purpose |
|---|---|
| `microsoft/deberta-v3-base` | Backbone of the trained answer evaluator (cross-encoder, `max_length=128` as deployed) |
| `all-MiniLM-L6-v2` (SBERT) | Semantic similarity, section-header embedding fallback, KeyBERT backbone, RAG embeddings, rewrite drift check |
| `cross-encoder/nli-MiniLM2-L6-H768` | Contradiction flag (never blended into a score) |
| `cross-encoder/nli-deberta-v3-base` | Technical-interview grader: key-point entailment (`tech_interview/grader.py`) |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | RAG reranker |
| `Qwen/Qwen2.5-1.5B-Instruct` | Legacy RAG question/answer generation (not viable for the planned question bank; see `mcq_tobedone.md`) |
| `Qwen/Qwen3-VL-2B-Instruct` | Slide pipeline Stage 3: reads diagrams, tables, formulas and picture-only slides (local, bf16, ~4.3 GB, fits 8 GB VRAM, ~10 s per slide). Run on CN's picture/table slides so far |
| `qwen3:8b` via **Ollama** (GGUF Q4_K_M, llama.cpp engine) | Question-bank generator and judge (`slide_rag/qbank.py`, `llm_client.py`). Runs 100% on the RTX 5050 (~6.2 GB VRAM, 8,192-token context), ~45 tokens/s. Offline only — the app never calls it |
| `Qwen/Qwen3-8B` (4-bit NF4, bitsandbytes) | Earlier feasibility test only (`slide_rag/llm_smoke_test.py`: ~16 tokens/s); replaced by Ollama, which is ~2.7× faster |
| RapidOCR (ONNX) models | Slide pipeline: OCR of picture-only slides |
| `distilroberta-base` | RoBERTa intent/difficulty/topic classifiers (weights not in repo) |
| `bert-base-uncased` | Legacy resume domain classifier (never trained; untrained head) |
| MediaPipe `face_landmarker.task` | Browser-side face mesh (478 landmarks), at `main_cap/cap/static/models/` |

### External services
| Service | Status |
|---|---|
| **Google Gemini 2.5 Flash** (`GEMINI_API_KEY`) | Not on the production request path since the Milestone 7 cutover. Used by Shadow Mode dev tooling, `GeminiGenerationClient`, the Experiment 4 Gemini rewrite pilot, and `_verify_traceability.py`. |
| **Hugging Face Hub** | Model and tokenizer downloads on first run (DeBERTa ≈700 MB, SBERT, NLI, Qwen). |
| **Ollama** (local, `http://localhost:11434`) | Local LLM server used only to generate the question bank offline (`qwen3:8b`). Installed with `winget install Ollama.Ollama`; model via `ollama pull qwen3:8b`. Not needed to run the app. |
| **jsDelivr CDN** | `@mediapipe/tasks-vision@0.10.14` ESM bundle + WASM, loaded by the browser. |
| **Google Colab (T4 GPU)** | Where the DeBERTa training phases were run; artifacts moved as JSON/JSONL. |
| **Google Fonts** | Inter, Roboto Mono. |

### Databases
**SQLite**, one file at `main_cap/cap/instance/app.db`, accessed through Flask-SQLAlchemy. Its schema is versioned with Alembic migrations in `main_cap/cap/migrations/`, which are applied automatically when the app starts.
- **Tables:** `users`, `student_profiles`, `resumes`, `interview_sessions`, `session_turns` (see §4.21).
- **Resume files:** stored on the server's disk under `instance/uploads/resumes/<user_id>/`; the database keeps their paths.
- **Moving to PostgreSQL:** set `CAP_DATABASE_URL`. No code changes are needed.

**Still in memory:** the live state of an interview in progress:
- `conversation_engine._conversations` (planner, evaluator, memory);
- `session_history._live`;
- `app._candidate_profiles` / `_profile_owners`.

Every answered turn is written to the database immediately, so a restart loses nothing already answered. Unfinished sessions are marked `abandoned`.

**Other files written to disk:** `user_profiles/*.json` (the legacy adaptive quiz), `hybrid_diagnostics.jsonl` (evaluator diagnostics), and `user_progress/*.json` (the RAG CLI).

---

## 3. High-Level Design (HLD)

### 3.1 System architecture overview

```
┌──────────────────────────────── Browser (templates/index.html) ─────────────────────────────────┐
│ Login/Signup → [Top nav: Home · Sessions · Profile]                                              │
│ Full Interview: resume screen → briefing → rules → Round 1 Resume Discussion → summary →         │
│                 Round 2 Technical → combined results    (Technical Interview: rules → round 2)   │
│ + Webcam/gaze/liveness monitor (MediaPipe, client-only)   + Session-integrity rules (proctor*)   │
└──────┬──────────────────┬───────────────────────────────┬────────────────────────┬──────────────┘
       │ /api/auth/*       │ /api/resumes/<id>/use          │ /api/resume-discussion- │ /api/tech-
       │ /api/profile      │ /api/classify-resume           │   v2/{start,reply,end}  │  interview/{start,
       │ /api/resumes      │                                │                         │  <id>/answer,
       │ /api/sessions, /api/insights                       │                         │  <id>/end}
┌──────▼──────────────────▼───────────────────────────────▼────────────────────────▼──────────────┐
│  Flask app (app.py)  ·  before_request login guard  ·  account_routes / session_routes blueprints │
│  in-memory live state: _candidate_profiles(+owners) · conversation_engine._conversations ·       │
│                        session_history._live                                                      │
└──────┬──────────────────┬───────────────────────────────┬────────────────────────┬──────────────┘
       │                  │                               │                        │
┌──────▼───────────┐ ┌────▼─────────────────────┐ ┌───────▼───────────────────┐ ┌──▼──────────────┐
│ SQLite (instance/│ │ Resume Intelligence      │ │ Conversation Engine (v2)  │ │ Quiz helpers    │
│ app.db) via      │ │ Engine: 8 deterministic  │ │ Planner → Realizer →      │ │ tech_interview/ │
│ SQLAlchemy:      │ │ stages → CandidateProfile│ │ Evaluator (Hybrid /       │ │ bank · selector │
│ users, profiles, │ │ (parsed once at upload,  │ │ Heuristic) → Ledger       │ │ NLI grader      │
│ resumes, sessions│ │ stored on the Resume row)│ └──────────┬────────────────┘ └──┬──────────────┘
│ turns            │◄┴──────────────────────────┘            │ each turn           │ each turn
│                  │◄────────── session_history.py ◄────────┴─────────────────────┘
└──────────────────┘   (records turns as they happen; insights.py reads them for Home)
      Offline / research (not on request path):
      synthetic data gen → DatasetManifest → relabel → split → train (Colab) → benchmark → promote
      → deployed_model/{best_checkpoint.json, final_promotion_decision.json, best_checkpoint_weights.pt*}
      (* weights file is gitignored and absent from the repo)
      Slide RAG (offline, rag_system/rag_tester/slide_rag; its question bank is read by tech_interview/):
      sources/<subject>/*.pdf → extract → classify/clean → [vision: Qwen3-VL on GPU] → sections
      → knowledge_base_v2/<subject>/ (hybrid index)  ·  topics/<subject>.txt  → qbank (Qwen3-8B) → rank_bank
      → question_bank/<subject>.json → enrich_bank (Qwen3-8B, follow-up replies)
```

### 3.2 Major components and how they interact

| Component | Main files | Responsibility | Talks to |
|---|---|---|---|
| **Web UI** | `templates/index.html` | Auth screen, app shell (nav, Home, Sessions, Profile), full-interview flow, client-side report building, voice input, webcam monitoring, session-integrity rules | Flask routes |
| **Flask API** | `app.py` | Routing, login guard (`before_request`), in-memory live state, startup wiring, per-turn session recording hooks | Every backend module |
| **Accounts** | `account_routes.py`, `account_schemas.py`, `resume_store.py` | Signup/login/logout, profile edit, password & consent, resume storage + parsing, account deletion | Database, resume engine |
| **Persistence** | `database.py`, `models.py`, `migrations/` | SQLite + SQLAlchemy models, Alembic migrations, secret key | Everything that stores data |
| **Session history** | `session_history.py`, `session_routes.py`, `insights.py` | Record interviews turn by turn, statuses (completed/terminated/abandoned), history API, Home stats and "Focus next" | Database, conversation engine |
| **Resume Intelligence Engine** | `resume_engine/*` | File → `AnnotatedCandidateProfile` in 8 local stages | `candidate_profile_mapper` → `CandidateProfile` |
| **Candidate Profile contract** | `candidate_profile_generator.py` | Pydantic schema, engine wrapper, frontend formatter, legacy Gemini path | App, planner, dashboard |
| **Planner** | `planner.py`, `topic_pool.py`, `question_specification.py`, `traceability.py`, `coverage_tracker.py` | Deterministic *what to ask* | Conversation engine |
| **Realizer** | `question_realizer.py`, `question_families.py`, `discussion_policy.py`, `interview_question.py`, `conversation_memory.py` | *How to phrase it* (families, transitions, anti-repetition) | Conversation engine |
| **Conversation Engine** | `conversation_engine.py` | Session lifecycle; the only module importing both planning and evaluation types | Planner, realizer, evaluation engine |
| **Evaluation** | `evaluator.py`, `evaluator_registry.py`, `evaluation_request.py`, `evaluation_result.py`, `evaluation_engine.py`, `heuristic_evaluator.py`, `hybrid_evaluator.py`, `reasoning_dimension_relevance.py`, `expected_concepts_registry.py` | Stable evaluator interface and implementations | Conversation engine |
| **Trained model layer** | `model_backbone.py`, `model_heads.py`, `model_dataset.py`, `model_checkpoint_io.py`, `model_evaluator.py`, `deployment_evaluator.py` | DeBERTa-v3 multi-task evaluator: training, inference, startup wiring | Evaluator registry |
| **Coaching** | `strong_answer.py`, `concept_analysis.py` | Deterministic coaching note and concept-coverage % | Conversation engine |
| **ML research track** | `training_example*.py`, `generation_*.py`, `prompt_*.py`, `coverage_strategy.py`, `dataset_*.py`, `labeling_operations.py`, `training_experimentation.py`, `rewrite_*.py`, `deterministic_rewrite*.py`, `run_*.py` | Produce and benchmark training data and checkpoints | Model layer (offline) |
| **Legacy v1 discussion** | `discussion_engine.py`, `legacy_topic_pool_adapter.py` | Older adaptive engine (still routed at `/api/resume-discussion/*`, unused by the UI) | Planner via adapter |
| **Slide RAG pipeline** | `rag_system/rag_tester/slide_rag/*`, `topics/`, `knowledge_base_v2/` | Offline: lecture slides → cleaned sections → hybrid index; topic lists; retrieval evaluation. Basis of the planned question bank | Not yet called by the app |
| **Supporting subsystems** | `rag_system/` (legacy RAG), `resume_classifier/`, `parser_tests/` (RoBERTa archived) | Old RAG question generation, legacy resume classifier, parser benchmark | Loosely via `sys.path` in `app.py` |

### 3.3 Data flow through the system

```mermaid
sequenceDiagram
    participant U as Browser
    participant A as Flask app.py
    participant RE as resume_engine (8 stages)
    participant M as candidate_profile_mapper
    participant CE as conversation_engine
    participant P as Planner/TopicPool
    participant QR as question_realizer
    participant EV as Evaluator (Hybrid/Heuristic)

    participant DB as SQLite (session_history)

    Note over U,A: Signup (multipart, with resume): the resume is parsed ONCE<br/>(resume_engine → mapper) and the CandidateProfile is stored on its Resume row
    U->>A: POST /api/resumes/<id>/use (saved resume) or /api/classify-resume (new upload, saved as current)
    A-->>U: profile_to_frontend_format(parsed_profile) + profile session_id
    U->>A: POST /api/resume-discussion-v2/start {session_id}
    A->>CE: start_conversation(profile)
    CE->>P: plan_next()
    P-->>QR: QuestionSpecification
    QR-->>U: InterviewQuestion payload
    A->>DB: begin_resume_discussion (status in_progress)
    loop up to 10 turns (Round 1)
        U->>A: POST .../reply {conversation_id, answer}
        CE->>EV: evaluate(build_request(...))
        EV-->>CE: EvaluationResult → EvaluationLedger
        CE->>P: advance(spec, COVERED); plan_next()
        A->>DB: record_resume_discussion_turn (question, answer, evaluation)
        CE-->>U: evaluation payload + next question (or is_completed)
    end
    U->>A: POST .../end {session_id, integrity, attention_metrics}
    A->>DB: finish_resume_discussion (completed | terminated)
    Note over U: Round 1 summary (still full screen)
    U->>A: POST /api/technical-sessions → 5 × (/api/next_question + /api/evaluate {session_id}) → .../end
    A->>DB: technical session + one turn per question
    Note over U: combined final results built client-side (rdRenderReport combined mode)
```

Flow invariants:
1. The **raw resume is read exactly once per upload**, by the engine. The parsed `CandidateProfile` is stored on the `Resume` row and reused for every later interview; nothing downstream re-reads the file (architecture principle NFR6).
2. **No network call after upload.** The discussion, evaluation and coaching all run locally (the first run downloads the SBERT/NLI models from Hugging Face).
3. **Evaluation never changes what is asked next** in v2. Results are appended to the ledger and returned, and the planner order is unconditional.
4. **Every answered turn is persisted before the response returns.** Interrupted sessions keep their answers and are marked `abandoned`.
5. **Users only ever see their own data.** Every query filters by `current_user`; other users' ids answer 404.

### 3.4 Key design decisions and the reasoning behind them

| Decision | Reasoning (from code docstrings and `docs/architecture/*`) |
|---|---|
| **Replace Gemini parsing with a deterministic engine** (Milestones 0–7) | Removes per-candidate API cost, quota failures, truncated JSON and hallucinated or non-XOR fields "by construction". Confidence becomes explainable (`Confidence.reasons`). Shadow Mode compared both sides before cutover (18/30 corpus comparisons were completed before quota ran out). |
| **Planning is deterministic, never an LLM** | Traceability (every question maps to one profile entry) cannot be guaranteed by an LLM planner; per-turn network calls would violate the latency and cost principles; determinism makes it testable. v2 uses no `random` at all (crc32 for variant choice). |
| **Planning is separate from phrasing** | The Planner decides *what* (category, seed, grounding) and the Realizer decides *how*. The realizer can never change the subject. The `QuestionSpecification` provenance core is immutable (frozen Pydantic). |
| **Templates, not generative phrasing** | FLAN-T5-small produced definitional drift ("What is X?"); hand-written families hit the "senior engineer" tone every time. |
| **Two traceability gates** | The *shape* gate (exactly one origin) runs at profile generation; the *substance* gate (the origin actually exists on this profile) runs in `TopicPool._build`, where the full profile is available. Rejected topics go to `TopicPool.rejected`. |
| **The evaluator interface is the architecture** | `Evaluator` Protocol + registry + frozen `EvaluationResult`, so heuristic → pretrained → fine-tuned models can be swapped without touching routes, session code or the UI. The evaluator is pinned per session so a session is never scored by two model versions. |
| **Hybrid Round 3: DeBERTa authoritative** | On the 362-example held-out test set, raw DeBERTa scored QWK 0.3976, the heuristic 0.1341, and the Round 2 blended hybrid 0.1814. Blending let the weaker model override the stronger one, so DeBERTa now scores and the heuristic supplies feedback text, confidence, a downgrade-only guardrail, and fallback. |
| **NLI used only as a contradiction flag** | Entailment rewarded lexical echoing, so NLI never contributes to a score. |
| **Reject, never repair (data pipeline)** | Any failed validation discards the whole generation attempt, so no partially-fixed example enters the dataset. |
| **Specification-level (group) splits** | Examples from the same `QuestionSpecification` at different quality tiers had leaked across train and test in the first experiment. |
| **API-free Track B augmentation** | Gemini's free tier (20 requests/model/day) blocked data collection, so deterministic rewrites plus an SBERT drift check replaced it. |
| **Client-side proctoring and attention** | A browser can only detect, not prevent, leaving full screen or switching apps; webcam frames never leave the browser (privacy). |
| **One unbroken proctored session for the full interview** | Round 1 → summary → Round 2 never leaves full screen or disarms the rules; only the final results release it. A violation anywhere ends the whole interview (zero tolerance). |
| **SQLite + SQLAlchemy + Alembic** | Nothing to install, one-file backups, enough for this write pattern; Postgres is a config change. Migrations apply automatically at startup so teammates never run manual schema commands. |
| **Resume files on disk, metadata + parsed profile in the DB** | Keeps the DB small; files are server-side, so a user sees the same resume from any device. Parsing once at upload means interviews start without re-parsing. |
| **Route layer records sessions; the engine stays DB-free** | `conversation_engine` keeps its in-memory, evaluation-pure design; `app.py` routes call `session_history` around it. |
| **One interview at a time per user** | Starting a new interview abandons any unfinished one (e.g. after a page reload mid-interview), which keeps history consistent. |
| **Signup data kept to what placements need** | Name, DOB, phone, 10th and 12th/Diploma scores, college, degree, branch, CGPA, resume; explicit data-storage consent (required) and model-training consent (optional, revocable). |

### 3.5 External integrations
- **Gemini** (`google-genai` client, lazy singleton, `gemini-2.5-flash`): dev tooling only (see §2).
- **Hugging Face Hub**: model downloads at first use.
- **MediaPipe via jsDelivr**: browser-side face landmarking.
- **SQLite** (local file). There is no external DB, queue or cache service.

### 3.6 Deployment / runtime architecture
- There are **no Dockerfile, CI, WSGI or cloud config files**. The app runs with `python app.py` from `main_cap/cap/`, which uses Flask's development server: `app.run(debug=False, port=5000, threaded=True, use_reloader=False)`.
- **Startup sequence:**
  1. load `.env`;
  2. `bootstrap_production_evaluator()`;
  3. `init_accounts(app)`, which configures SQLite, applies pending migrations, loads or creates the secret key, and sets up Flask-Login and the 10 MB upload limit;
  4. register `sessions_bp`;
  5. mark every still-`in_progress` session `abandoned`.
- **Runtime data** lives in `main_cap/cap/instance/` (git-ignored):
  - `app.db`: the database;
  - `uploads/`: resume files;
  - `secret_key`: the Flask secret, generated once so logins survive restarts.
- It is a **single process**. Account and history data are durable (SQLite), but *live* interview state is in memory, so the app can't be scaled across workers as-is.
- **Model deployment** is file-based: copy `best_checkpoint_weights.pt`, `best_checkpoint.json` and `final_promotion_decision.json` into `main_cap/cap/deployed_model/`. `deployment_evaluator.bootstrap_production_evaluator()` checks that all three exist and that the promotion is approved *before* loading anything. Otherwise it skips the ~700 MB backbone download entirely and activates the heuristic evaluator.
- **Training** ran on Google Colab (the `artifact_uri` in `best_checkpoint.json` is `/content/e4/artifacts/experiment_4_train/best_checkpoint_weights.pt`).

---

## 4. Low-Level Design (LLD)

### 4.1 Directory / file structure

```
capstone_latest/
├── README.md                         Project readme (partly outdated — see §7)
├── PROJECT_DOCUMENTATION.md          This document
├── mcq_tobedone.md                   Plan for the MCQ / question-bank generation (not built yet)
├── grader_eval/                      Grader test sets: questions.json, output_questions.json (400 LLM-written
│                                     answers), my_answers.json (40 real answers), tuning_set/, run_*.py
├── CONTRIBUTING.md                   Branch workflow (main / adaptive-engine / resume_classifier)
├── Requirements_Global.txt           The only requirements file (sectioned per subsystem)
├── .gitignore                        Ignores venvs, caches, *.pt/*.safetensors, artifacts/, .env, diagnostics
├── docs/architecture/                Design specs + milestone reports (see below)
├── main_cap/cap/                     ★ The application (Flask + all core modules)
├── rag_system/rag_tester/            Legacy RAG CLI (app integration dead) + the new slide pipeline:
│   ├── slide_rag/                    ★ Slide RAG pipeline package (§4.24)
│   ├── sources/<subject>/*.pdf       Faculty lecture slides, one slide per page (git-ignored)
│   ├── topics/<subject>.txt          Curated topic lists (279 topics) checked against the slides
│   ├── question_bank/<subject>.json  Generated technical-interview questions (+ <subject>_report.md for review;
│   │                                 enrichment fields and enrich_report.md from slide_rag/enrich_bank.py)
│   ├── knowledge_base_v2/<subject>/  Pipeline output: slides, sections, index, reports, quiz.json
│   ├── knowledge_base/, samples/     Old page-per-chunk index and its PDFs (kept as the baseline)
│   └── .slide_cache/, .vision_cache/, .qbank_cache/, .enrich_cache/   Stage 1 / vision / question-generation / enrichment caches (git-ignored)
├── archive/superseded_caches/        Archived old-version caches (safe to delete; see its README)
├── archive/Roberta/                  Archived: question intent/difficulty/topic classifiers + adaptive quiz (never used by the app; see §4.15)
├── resume_classifier/                Legacy resume parser + SBERT/BERT domain classifier
└── parser_tests/                     Benchmark harness for the legacy resume parser (10 PDFs)
```

**`docs/architecture/`**
| File | Purpose |
|---|---|
| `ResumeDiscussion_v2.md` | Engineering spec for the discussion, evaluation, explainability and dashboard (describes several v1 behaviours; see §7) |
| `ResumeIntelligenceEngine.md` | Architecture of the deterministic parser: stages, plugin registry, PipelineTrace, confidence, validation, milestones, decision log |
| `Milestone{1,2,3,4,6,7}_ValidationReport.md`, `Milestone4_Design.md` | Per-milestone build and validation reports; Milestone 4 designs interview-seed synthesis |
| `Milestone7_CutoverChecklist.md`, `Milestone7_EvaluationGuide.md` | The Gemini → engine cutover record and evaluation procedure |
| `Experiment4_TrackB_APIFree.md` | API-free rewrite augmentation (states "pilot only"; the code shows full scale was run) |

**`main_cap/cap/`: core application modules**
| File | One-line purpose |
|---|---|
| `app.py` | Flask entrypoint: startup wiring, login guard, interview routes (with session-recording hooks), in-memory live state, quiz helpers |
| `database.py` | SQLite/SQLAlchemy setup, `configure_database` (auto-migrate, secret key, upload dir), foreign-key + WAL pragmas |
| `models.py` | `User`, `StudentProfile`, `Resume`, `InterviewSession`, `SessionTurn` + `to_dict()`; `iso_utc` date helper |
| `account_schemas.py` | Pydantic signup/profile validation (`ProfileFields`, `SignupRequest`, `password_problem`) |
| `account_routes.py` | Accounts API blueprint + `init_accounts(app)`: signup, login/logout, me, profile, password, consent, resumes, account deletion |
| `resume_store.py` | Resume files on disk (random names, SHA-256), staging for signup, parsing via the resume engine |
| `avatar_store.py` | Profile photos: validate and re-encode uploads to a 256×256 JPEG (§4.20) |
| `model_warmup.py` | Local-only model loading when all models are cached, and background model warm-up at startup (§5.1) |
| `tech_interview/` | Question-bank technical interview: `bank.py`, `selector.py`, `grader.py`, `followup.py`, `session.py` (§4.25) |
| `session_history.py` | Records both interview types turn by turn; completed/terminated/abandoned; deletion |
| `session_routes.py` | History API blueprint: `/api/sessions`, `/api/insights`, `/api/technical-sessions`, and the technical interview `/api/tech-interview/*` |
| `insights.py` | Home stats, score trend, "Focus next" |
| `db_manage.py` | Minimal Flask app for `flask --app db_manage db migrate/upgrade` (skips loading ML models) |
| `migrations/` | Alembic migrations (initial schema; `last_activity_at`; profile photo `a7c3e91f2b40`) |
| `instance/` | Runtime data, git-ignored: `app.db`, `uploads/`, `secret_key` |
| `candidate_profile_generator.py` | `CandidateProfile` Pydantic schema; engine wrapper; `profile_to_frontend_format`; legacy Gemini parser |
| `conversation_engine.py` | v2 Resume Discussion session facade (start/advance/end), 10-question budget, integrity sanitizer |
| `planner.py` | Deterministic facade over `TopicPool` (`plan_next`, `advance`) |
| `topic_pool.py` | Builds one immutable `QuestionSpecification` per discussable fact; selection scoring; lifecycle and coverage |
| `question_specification.py` | Frozen spec and grounding models, enums, `CATEGORY_PRIORITY`, lifecycle state machine |
| `traceability.py` | Substance gate: does a cited project/experience/certification exist on this profile? |
| `coverage_tracker.py` | Categories present vs covered |
| `question_families.py` | Registry of 21 phrasing families (2 variants each) and the `ReasoningType` enum |
| `discussion_policy.py` | Chooses family (per-category narrative arc) and transition phrase |
| `question_realizer.py` | Spec → `InterviewQuestion` (crc32-deterministic variants); dormant follow-up machinery |
| `interview_question.py` | Frozen record of a question actually shown |
| `conversation_memory.py` | Evaluation-free session memory (topics, families, transitions, timeline, answer lengths) |
| `evaluation_request.py` / `evaluation_result.py` | Frozen evaluator input/output contracts (schema v2) |
| `evaluator.py` / `evaluator_registry.py` | `Evaluator` Protocol + conformance check; name → evaluator registry with active pointer |
| `evaluation_engine.py` | `build_request`, `evaluate`, `EvaluationLedger`, expected-concepts lookup policy |
| `heuristic_evaluator.py` | `HeuristicEvaluator` ("heuristic-v1"): SBERT + lexical markers + NLI flag |
| `hybrid_evaluator.py` | `HybridEvaluator` ("hybrid-v1"), Round 3 policy (DeBERTa primary) + JSONL diagnostics |
| `model_backbone.py` / `model_heads.py` / `model_dataset.py` / `model_checkpoint_io.py` | DeBERTa cross-encoder, CORAL heads, data loaders, checkpoint IO |
| `model_evaluator.py` | `TrainedEvaluator` adapter + `promote_trained_model` |
| `deployment_evaluator.py` | `bootstrap_production_evaluator()`: startup wiring with fallback chain (skips model loading when the weights are missing or not approved) |
| `reasoning_dimension_relevance.py` | 12 dimension names; ReasoningType → relevant dimensions table |
| `expected_concepts_registry.py` | Hand-curated technology → expected concepts table (4 entries) |
| `concept_analysis.py` / `strong_answer.py` | Concept-coverage % and deterministic coaching note / "improved answer" |
| `discussion_engine.py` / `legacy_topic_pool_adapter.py` | Legacy v1 engine and its dict-shaped adapter onto the v2 `TopicPool` |
| `rag_integration.py` | Wrapper around `rag_system` (non-functional at present; see §4.15) |
| `regenerate_promotion_decision.py` | CLI: re-benchmark a checkpoint and rewrite `final_promotion_decision.json` |
| `training_example.py` … `run_experiment_4_*.py` | ML research track (see §4.9) |
| `_planning_test_fixtures.py` / `_verify_traceability.py` | Shared test fixtures; manual Gemini-backed traceability check script |
| `deployed_model/` | `best_checkpoint.json`, `final_promotion_decision.json` (weights `.pt` absent) |
| `experiment_3_reproducibility/` | Provenance package for the Experiment 3 dataset (README, COMPARISON, REPRODUCE, manifests, SHA-256 hashes) |
| `static/models/face_landmarker.task` | MediaPipe model served to the browser |
| `templates/index.html` | The entire frontend (auth, app shell, interview flow, reports) |
| `test_*.py`, `test_*.js`, `_app_test_setup.py` | Python and Node tests (see §8); `_app_test_setup.py` imports the real `app.py` with an in-memory DB for integration tests |

**`main_cap/cap/resume_engine/`**
| File | One-line purpose |
|---|---|
| `__init__.py` | Package docstring, `__version__ = "0.1.0"` |
| `interfaces.py` | Stage Protocols, `ParserResult`, `check_parser_conformance` |
| `factory.py` | Composition root: `default_parser_registry()`, `default_pipeline()` |
| `pipeline.py` | `ResumePipeline` orchestration, `_timed`, unknown-section absorption, label grouping |
| `pipeline_trace.py` | `StageTrace` / `PipelineTrace` with JSON and console renderers |
| `document_model.py` | `TextSpan`, `ExtractionQuality`, `DocumentModel` |
| `extractor.py` | Stage 1: PDF/DOCX/TXT extraction, `ExtractionFailure` |
| `layout.py` | Stage 2: one- vs two-column detection and reading order |
| `sections.py` | Stage 3: 4-tier header cascade, contact safety net, `Section` |
| `registry.py` | Stage 4: `ParserRegistry` (plugin runner) |
| `parsers/*.py` | Contact, Experience, Project, Education, Skills, Certification parsers + `_entry_clustering.py` |
| `dates.py` | Date-range regex + dateutil parsing |
| `cross_reference.py` / `seed_synthesis.py` | Stage 5: demonstrated-skill tagging and deterministic interview seeds |
| `normalization.py` | Stage 6: Unicode, whitespace, glyph cleanup; technology de-aliasing and dedup |
| `validation.py` | Stage 7: `Observation` + validation rules (observes, never gates) |
| `confidence.py` | Stage 8: `Confidence`, `AnnotatedCandidateProfile`, `DefaultConfidenceEngine` |
| `candidate_profile_mapper.py` | Engine output → public `CandidateProfile` (domain, level, blueprint, summary) |
| `*_gazetteer.py` (9 files) | Curated vocabularies: sections, technologies, concepts, job titles, locations, degrees, institutions, certifications, domains |
| `devtools/shadow_mode.py`, `shadow_mode_batch.py`, `golden_corpus_report.py` | Dev-only comparison and report CLIs |
| `tests/` | ~356 tests + `golden_corpus/` (31 resume fixtures + seed-synthesis fixtures) |

---

### 4.2 Resume Intelligence Engine (`resume_engine/`)

**Responsibility:** turn a resume file into an `AnnotatedCandidateProfile` using only local, deterministic logic, with SBERT/KeyBERT used surgically for fuzzy matching.
**Entry:** `candidate_profile_generator.generate_candidate_profile_via_engine(file_path)` calls `factory.default_pipeline().run(file_path, source_format)` and then `candidate_profile_mapper.map_to_candidate_profile(...)`. A new pipeline and registry are built on every request.

**Phase 1 engine (integrated 2026-09-30, `resumeParser_integration.md`).** The engine is a teammate's "Phase 1" rewrite (11 files + `text_normalization.py`): entry boundaries use a two-tier line role (strong header vs title-like) plus blank-line gaps and body context instead of font alone, a per-section body font, majority-bold headers, glyph-split heading repair ("T ECHNICAL S KILLS"), stricter skills/certification/contact parsing. On 41 resumes it finds far more of the resume than the previous engine (golden-corpus jobs 21 → 33, real-resume education 5 → 8, no sentence junk in skills); Round 1 plans went from 91 to 110 questions across 38 resumes. Integration fixes on top (`resume_engine/tests/test_integration_fixes.py`): date-range dashes are not title separators, sentence-like bullet lines and wrapped continuations are not titles (`reads_as_sentence`), page footers are not entries, glyph-only lines are not body, certification lines must look like names, "- Resume" suffixes don't hide the name, phones don't swallow the next field's number, "March, 2022"-style dates are recognised. **Rollback:** the previous engine is in `archive/resume_engine_backup_2026-09-30/` (`python archive/resume_engine_backup_2026-09-30/restore_old_parser.py`).

#### Pipeline orchestration (`pipeline.py`)
`ResumePipeline` is a dataclass with eight injected Protocol collaborators. `run(file_path, source_format, trace=None)` calls each stage through `_timed(stage_name, trace, fn, ..., enrich=None)`. When `trace` is `None` it is a plain call; otherwise it records a `StageTrace` with timing and optional enrichment.

```
[1] document_extraction   PdfDocxExtractor           → DocumentModel
[2] layout_reconstruction ColumnAwareLayoutReconstructor → DocumentModel (reordered, column_index set)
[3] section_detection     HeuristicSectionDetector   → list[Section]
      _absorb_repeated_unknown_entries → _group_sections_by_label → dict[str, Section]
[4] entity_parsing        ParserRegistry.run_all      → dict[str, ParserResult]
[5] cross_reference       DefaultCrossReferenceEngine (demonstrated skills + interview seeds)
[6] normalization         DefaultNormalizer
[7] validation            DefaultValidationEngine     → list[Observation]
[8] confidence_scoring    DefaultConfidenceEngine     → AnnotatedCandidateProfile
```

#### Stage 1: Document extraction (`extractor.py`, `PdfDocxExtractor`)
- **Validation:** a missing file, unsupported format, or `chars_extracted < MIN_EXTRACTED_CHARS = 50` (a scanned or unreadable file) raises `ExtractionFailure`.
- **PDF:** PyMuPDF `page.get_text("dict")` gives one `TextSpan` per span. `is_bold` comes from `flags & 16` or "bold" in the font name. Hyperlinks come from `page.get_links()` (so an icon-only LinkedIn link is still recovered). `body_font_size` is the modal rounded span size. Password-protected files raise `ExtractionFailure`.
- **DOCX:** python-docx with **synthetic geometry** (`DOCX_PAGE_WIDTH=612`, margins 72, `DOCX_LINE_HEIGHT=14`, default font 11). Runs and hyperlink runs become spans, and paragraph `style_name` is preserved. Tables are treated as layout: each cell becomes a synthetic column (the note `docx_table_layout_detected:N_columns` is recorded).
- **TXT:** one span per non-blank line, single column.

#### Stage 2: Layout reconstruction (`layout.py`)
Pages are processed independently, and the algorithm decides between one and two columns by gap analysis:
1. Fewer than 6 spans, or only one distinct left edge: `single_column` (0.95).
2. Find the largest gap between distinct left edges. If it is below `COLUMN_GAP_RATIO = 0.12` × page width: `single_column`.
3. Otherwise split at the gap and check **all** of the `CORROBORATION_SIGNALS` (strict AND):

| Signal | Rule | Constant |
|---|---|---|
| `_line_count_signal` | each band has ≥ 3 lines | `MIN_CORROBORATING_LINES=3` |
| `_balance_signal` | min/max line count ≥ 0.1 | `MIN_BAND_BALANCE_RATIO=0.1` (recalibrated from 0.25) |
| `_pitch_continuity_signal` | ratio of the two bands' median row pitch ≤ 1.5 (catches inline right-aligned dates, which measure ≈2.0) | `MAX_PITCH_RATIO=1.5` |
| `_y_overlap_signal` | bands overlap vertically ≥ 50% of the shorter band | `MIN_BAND_Y_OVERLAP_RATIO=0.5` |

If all pass, the page is `two_column` with confidence `min(0.9, 0.6 + 0.05·(min_lines−3))`, and spans are emitted left column first, then right. If any fails, it is `ambiguous` (0.35) and read top to bottom. The document mode is `two_column` if any page is two-column.

#### Stage 3: Section detection (`sections.py`, `HeuristicSectionDetector`)
- Spans are grouped into lines by y within 3pt, never crossing a page or column change.
- **Candidate header line:** ≤ 6 words and (font ≥ body × 1.05, or bold, or ALL CAPS), or a DOCX `Heading*` style.
- **Classification cascade:**
  1. `rapidfuzz.process.extractOne` against `SECTION_ALIASES` (41 aliases, 7 labels) using `token_sort_ratio` and `processor=str.lower`. A score ≥ 85 gives confidence 0.9 (0.98 with a DOCX heading style). A score ≥ 55 gives confidence 0.4.
  2. Otherwise, an SBERT embedding fallback: cosine similarity ≥ `EMBEDDING_SIMILARITY_FLOOR=0.55` gives confidence 0.4.
  3. Otherwise, `("unknown", 0.2)`.
- **Special cases:**
  - The leading block becomes `contact` ("pre_first_header_block").
  - A **contact safety net** sweeps every email, phone or URL anywhere into `contact`.
- **Canonical labels:** contact, summary, experience, projects, education, skills, certifications, unknown.
- **Post-processing (`pipeline.py`):** `_absorb_repeated_unknown_entries` merges runs of 2+ non-font-elevated `unknown` sections into the preceding real section. It merges a single unknown section only when the previous section is projects or experience and has bold entry lines. This fixes job and project title lines being mistaken for new sections.

#### Stage 4: Entity parsers (`registry.py`, `parsers/`)
Every parser implements the `EntityParser` Protocol (`entity_name`, `required_sections`, `version="0.1.0"`, `parse(sections, doc, trace) -> ParserResult`) and is conformance-checked at registration. Shared helpers:
- **`_entry_clustering.cluster_entries`:** a header line is bold (≥ 30% of its characters bold) or has font ≥ the section's local median × 1.05, and it starts a new entry.
- **`dates.parse_date_range`:** explicit month-name alternation (a generic word class had matched "Engineer 2021" as a date); never raises.

| Parser | Output fields | Key logic | Confidence |
|---|---|---|---|
| `ContactParser` | name, email, phone, linkedin, location | Regexes; LinkedIn falls back to the hyperlink list. Location: segments scored against `LOCATIONS` with `token_set_ratio` ≥ 80. Name: the lines with the largest font, joined. | hits / 5 |
| `ExperienceParser` | role, company, duration, summary | Splits the header on " at ", dash, "-" or ",". The half matching `JOB_TITLES` (≥ 75) is the role. An institution marker gives `role=""`. Dates come from the header or body. | role +0.4, date +0.3, summary +0.2, header 0.1 |
| `ProjectParser` | title, summary, technologies, concepts | Tech: labelled line (`Tech:`, `Stack:`, `Built with:`) + word-boundary `TECHNOLOGIES` matches. Concepts: KeyBERT (1–3-grams, top 10) filtered through the `CONCEPTS` gazetteer. | ≈ 0.8 maximum |
| `EducationParser` | degree, major, institution, graduation_year | Degree gazetteer, "of/in" major regex, institution keyword regex, first 4-digit year | degree 0.5, year 0.25, institution 0.25 or 0.125 |
| `SkillsParser` | list of strings | Split on delimiters, drop "Category:" prefixes, canonicalise via `TECHNOLOGIES` | 0.7 + 0.2 × header + 0.2 on gazetteer hit |
| `CertificationParser` | list of strings | One per line, canonicalised against `CERTIFICATIONS` (≥ 85); stray-mention sweep of skills and summary | 0.6 + 0.15 × header + 0.25 on match |

#### Stage 5: Cross-reference (`cross_reference.py`, `seed_synthesis.py`)
1. **`_tag_demonstrated_skills`:** each skill is searched (word boundary) in project and experience text. A hit adds the reason `+demonstrated_in_project:X` and +0.1 confidence; a miss adds the observation `skill_not_demonstrated`.
2. **`synthesize_seeds(project)`:** deterministic interview seeds with **no LLM and no generic fallback**. Zero evidence means zero seeds (a permanent rule).

| Family (priority) | Template | Confidence | Cap |
|---|---|---|---|
| metric_probe (0) | `You mentioned "{metric}" — how was that measured or achieved?` | 0.85 | — |
| tradeoff_probe (1) | `Why {tech_a} over the alternative, given you mentioned "{comparison}"?` (two technologies within 100 characters of a comparison phrase) | 0.8 | — |
| tech_probe (2) | `Why did you use {tech} in this project?` | 0.75 with a labelled tech line, else 0.6 | 2 |
| integration_probe (3) | `How did {tech_a} and {tech_b} work together in this project?` | 0.55 | 1 |
| concept_probe (4) | `How did you approach {concept} in this project?` | 0.5 | 1 |

`MAX_SEEDS_PER_PROJECT = 4`. Selection is greedy by (priority, −score) with evidence-overlap dedup. `EvidenceAccounting` records why each unused piece of evidence was dropped.

#### Stage 6: Normalization (`normalization.py`)
`clean_text` removes control characters and U+FFFD, applies NFKC, collapses whitespace and strips bullet glyphs. Technologies are de-aliased (14 aliases: js, ts, py, postgres, k8s, golang, and others) and deduplicated, with an info observation `duplicate_technologies_merged`. It never introduces `None` and never changes a field's type.

#### Stage 7: Validation (`validation.py`)
Collects parser observations and runs `_NEW_RULES`: `missing_linkedin`, `no_measurable_outcome` (no `%` or `Nx` in a project), `empty_experience_summary`, and `inconsistent_dates` (end before start). Severities are `info`, `notice` and `warning`. **Validation never blocks profile generation.**

#### Stage 8: Confidence (`confidence.py`)
`overall_confidence.score` is the unweighted mean of every entity confidence across all parsers. Reasons use the `+`/`-` sign convention. Returns `AnnotatedCandidateProfile(parser_results, observations, overall_confidence)`.

#### Mapper (`candidate_profile_mapper.py`)
| Public field | Derivation |
|---|---|
| contact fields, skills, certifications, education, experience, projects | Copied from parser entities (projects include the synthesized `interview_seeds`) |
| `predicted_domain` | `classify_domain`: keyword-hit count per domain from `DOMAIN_KEYWORDS`; default "Software Engineering" |
| `experience_level` | `infer_experience_level`: year span from durations plus a seniority keyword bump → Beginner / Intermediate / Advanced |
| `confidence` | Engine mean entity confidence (not a domain confidence, unlike the Gemini path) |
| `interview_blueprint.technical_topics` | Up to 8: project technologies and concepts first (origin = project), then gazetteer hits in experience summaries (origin = "role at company"); `evidence` is a literal substring |
| `estimated_strengths` / `estimated_weaknesses` | Technology frequency (top 5) / validation observation categories mapped to weaknesses (top 5) |
| `resume_summary` | Grounded template, e.g. "{name} is a mid-level software engineering professional with N years of experience, skilled in …"; empty when there is no evidence |

The mapper builds a real `candidate_profile_generator.CandidateProfile`, which validates the shape, and returns `.model_dump()`.

#### Gazetteers
| File | Size | Used by |
|---|---|---|
| `section_gazetteer.py` | 41 aliases / 7 labels | Section detection |
| `technology_gazetteer.py` | 76 technologies | Project, skills, normalization, mapper |
| `concept_gazetteer.py` | 64 concepts | Project (KeyBERT filter), mapper |
| `job_title_gazetteer.py` | 58 titles | Experience |
| `location_gazetteer.py` | 47 locations | Contact |
| `degree_gazetteer.py` | 40 degrees | Education |
| `institution_gazetteer.py` | 30 institutions | Education (confidence tier only) |
| `certification_gazetteer.py` | 47 certifications | Certification |
| `domain_gazetteer.py` | 10 domains, 9–22 keywords each | Mapper `classify_domain` |

#### Observability (`pipeline_trace.py`)
`PipelineTrace(document_id, engine_version, parser_versions, stages)` exposes `to_json()` and `to_console()`, which renders ✓ for `+` reasons and ⚠ for `-` reasons. `to_html()` raises `NotImplementedError`. Tracing has zero cost when `trace=None` (production).

#### Devtools (dev-only; never imported by `app.py`)
- `shadow_mode.py`: `compare_profiles(gemini, engine)` produces neutral discrepancy categories (`missing_in_engine`, `missing_in_gemini`, `different_value`, `count_mismatch`) and never decides which side is ground truth. `check_engine_topic_pool_health` runs the real `TopicPool`.
- `shadow_mode_batch.py`: `python -m resume_engine.devtools.shadow_mode_batch --dir <resumes> --report out.json` (needs `GEMINI_API_KEY`). Errors are grouped by stage.
- `golden_corpus_report.py`: `python -m resume_engine.devtools.golden_corpus_report`, a Milestone 1–3 fixture health report.

---

### 4.3 Candidate Profile (`candidate_profile_generator.py`)

The **public contract** consumed by every downstream module:

```python
class CandidateProfile(BaseModel):
    candidate_name: str = ""
    contact_details: ContactDetails            # email, phone, linkedin, location
    skills: list[str]
    education: list[EducationEntry]             # degree, major, institution, graduation_year
    experience: list[ExperienceEntry]           # company, role, duration, summary
    projects: list[ProjectEntry]                # title, summary, technologies, concepts, interview_seeds
    certifications: list[str]
    predicted_domain: str = "Software Engineering"   # one of DOMAIN_LABELS (10)
    experience_level: str = "Intermediate"           # Beginner | Intermediate | Advanced
    confidence: float = 0.5
    interview_blueprint: InterviewBlueprint     # resume_verification_topics, technical_topics[TechnicalTopic],
                                                #   starting_difficulty, estimated_strengths, estimated_weaknesses
    resume_summary: str = ""
```
`TechnicalTopic(topic, originating_project, originating_experience, evidence)`: exactly one origin must be set (XOR). Empty string or empty list is the "missing" sentinel; fields are **never `None`**.

**Functions:**
- `generate_candidate_profile_via_engine(file_path)`: the production path.
- `engine_supports_format(ext)`: `.pdf`, `.docx`, `.txt`.
- `get_active_parser_backend()`: reads `CAP_RESUME_PARSER`. Note that `app.py` does not call it, so the engine is always used.
- `profile_to_frontend_format(profile)`: produces the flat dict the UI uses (`name`, `email`, `phone`, `predicted_domain`, `discussion_domain`, `confidence`, `skills`, `experience{years, level}`, `education`, `projects`, `certifications`, `focus_topics`, `resume_summary`, `experience_detail`).
- **Legacy Gemini path** `generate_candidate_profile(resume_text)`, kept for Shadow Mode:
  - `gemini-2.5-flash` with `response_schema=CandidateProfile`, temperature 0.1, 3 retries with exponential backoff on rate-limit, timeout or 5xx errors.
  - A 3-stage JSON parse fallback, `_post_process` (fuzzy domain match, confidence clamp, XOR shape gate), and a one-time retry when zero skills come back.

---

### 4.4 Resume Discussion: planning & phrasing

#### Data model (`question_specification.py`)
- `QuestionCategory`: `project_deep_dive`, `project_overview`, `experience`, `certification`, `skill_in_context`.
- `CATEGORY_PRIORITY`: deep_dive **5**, overview **4**, experience **3**, certification **2**, skill_in_context **1**.
- `QuestionSpecification` (frozen): `id` ("topic_N"), `category`, `text_seed`, `text_seed_is_sentence`, `grounding` (exactly one of `ProjectGrounding`, `ExperienceGrounding`, `CertificationGrounding`), `priority_boost`, `source_type`, `source_id`, `source_field`, `reason`, `schema_version="v1"`.
- `UnitLifecycleState` is separate and mutable only through `TopicPool.mark_*`. It uses `_ALLOWED_TRANSITIONS` (UNASKED → ACTIVE, COVERED or SKIPPED; ACTIVE → COVERED or SKIPPED; terminal states stay terminal). Any other transition raises `InvalidLifecycleTransitionError`.

#### Building units (`topic_pool.TopicPool._build`)
1. **Deep dive:** one unit per `interview_seeds` entry per titled project, deduplicated by (title, seed). `text_seed_is_sentence=True`.
2. **Overview:** one unit per titled project.
3. **Experience:** one unit per entry with a role or company. `source_id` is "role at company".
4. **Certification:** one unit per certification.
5. **Skill in context:** each `technical_topics` entry passes through `traceability.validate_technical_topic_origin`. If it fails, it goes to `rejected` and is logged, and is never asked.

`priority_boost` is set when the unit touches `interview_blueprint.estimated_weaknesses` (bidirectional substring match).

#### Selection (`TopicPool.select_next`)
```
score = CATEGORY_PRIORITY*10 + (100 if category not yet covered) + (2 if priority_boost) + (1 if category != last_category)
tie-break: earlier build order.   No randomness.
```
The effect is one unit per present category in tier order (a coverage sweep), then strict tier order. (The diversity bonus can never change the outcome; see §7.)

#### Phrasing
- **`question_families.py`:** 21 registered families, each with a `ReasoningType` and 2 lambda variants. The `ReasoningType` values are `RECALL`, `EXPLANATION`, `APPLICATION`, `TRADE_OFF_ANALYSIS`, `DEBUGGING`, `DESIGN` (unused), `OPTIMIZATION`, `REFLECTION`, `OWNERSHIP`, `DECISION_MAKING`.

  | Category | Families available |
  |---|---|
  | Overview | overview, architecture, decision_making, lessons_learned, future_improvements, ownership |
  | Deep dive | implementation, architecture, tradeoffs, decision_making, debugging, optimization, scaling, testing, deployment, failures, reflection |
  | Experience | responsibilities, team_collaboration, ownership, lessons_learned, reflection, failures |
  | Certification | motivation, application |
  | Skill in context | decision_making, skill_application, skill_context |

- **`discussion_policy.select_family(spec, memory)`:**
  - The first touch of a project's deep-dive is forced to "overview", so a project never opens with a deep question.
  - Otherwise it cycles through the per-category `_ARC`, skipping the immediately previous family and families unsafe for sentence-shaped seeds.
- **`discussion_policy.select_transition`:** chooses between `same_topic`, `new_project`, `returning_project`, `new_experience` and `new_certification` (2 variants each), avoiding the last 3 transitions used.
- **`question_realizer.realize(spec, memory, turn_number)`:** returns `(InterviewQuestion, variant_idx)`. The variant is `crc32(spec.id::family) % n`, flipped if it would repeat the last one. `realize_followup` / `select_followup_angle` exist but are **never called** in v2.
- **`conversation_memory.ConversationMemory`:** records the projects, technologies, reasoning types, recent families, styles and transitions, timeline, and `AnswerMetadata(word_count, sentence_count)`. **No evaluation data is ever stored here** (an enforced boundary).

---

**Question variety (integrated 2026-09-30, `resumeParser_integration.md` step 4).** A project's own
`interview_seeds` (from `seed_synthesis.py`) are asked verbatim after its first mention, naming the project
("Why did you use Redis in AI SOC Analyst?"), never two seed questions back to back
(`question_realizer.realize`); a question family used in the last 3 turns is avoided when the arc has an
alternative (`discussion_policy.select_family`); and a project/job touched in the last few turns gets a
small score penalty (`topic_pool._RECENT_SOURCE_PENALTY`, fed by `conversation_memory.recent_source_ids`) so
interviews move between resume items. Over 38 resumes: repeated questions 2 → 0, same family within 3
turns 26 → 6, back-to-back same item 33 → 20, resume-specific questions 0 → 9.

### 4.5 Resume Discussion: session orchestration (`conversation_engine.py`)

The **only** module allowed to import both planning types and evaluation types (enforced by AST tests in `test_evaluation_engine.py`).

| Function | Behaviour |
|---|---|
| `start_conversation(profile)` | Builds `Planner`, `ConversationMemory`, and the **pinned** evaluator (`_resolve_session_evaluator`, which registers a `HeuristicEvaluator` if none is active). No spec gives 400 "No discussion questions could be generated from this profile." Otherwise stores the session under `conv_<hex12>` and returns `{status, conversation_id, question, total_questions=min(planner.total(), 10)}`. |
| `advance_conversation(id, answer)` | 404 if the id is unknown; `{"status":"completed"}` if the session has ended. Then: `build_request` → `evaluate` → `ledger.append` → `memory.record_turn` → `planner.advance(spec, COVERED)` (unconditional). Stops once `turn_count ≥ RESUME_DISCUSSION_QUESTION_BUDGET = 10`. Returns `{status, next_question \| null, is_completed, turn_number, evaluation}`. |
| `end_conversation(id, integrity=None)` | Returns `{status, total_questions, projects_discussed, skills_discussed, technologies_mentioned, reasoning_types_covered, timeline[], evaluations[], integrity}`, then **pops the session** (later replies get 404). |
| `evaluator_info(id)` | `(name, version)` of the evaluator pinned to a conversation, for session history |
| `sanitize_integrity(raw)` | Public; also used for Technical sessions. Whitelists the client integrity record: `terminated` must be literally `True`; `type` must be in `INTEGRITY_VIOLATION_TYPES` (otherwise "unknown"); `label[:120]`; `at_turn` must be a non-bool int ≥ 0; `occurred_at[:40]`. Terminations are logged as a warning. |
| `_result_payload(result)` | Pure field selection from `EvaluationResult`. The reply adds `improved_answer`, `coaching_note` and `concept_coverage_pct`. |

---

### 4.6 Answer evaluation subsystem

#### Contracts
- **`Evaluator` Protocol** (`evaluator.py`, structural and `@runtime_checkable`): attributes `name`, `version`, `declared_dimensions`, `declared_reasoning_types`, `requires_network`; method `evaluate(request) -> EvaluationResult`. `check_conformance()` verifies the request_id echo, the declared dimensions and reasoning types, non-blank reasoning and rationale, and the evaluator name.
- **Registry** (`evaluator_registry.py`): `register_evaluator(e, sample_request=None, make_active=False)`, `set_active_evaluator`, `get_active_evaluator`, `get_evaluator`, `registered_evaluator_names`. It is module-global and not thread-safe.
- **`EvaluationRequest`** (schema "v2", frozen): `request_id`, `requested_at`, `specification`, `question_text`, `reasoning_type`, `answer_text`, `conversation_context` (`ConversationContextSnapshot`: turn, follow-up flag, prior answers for this spec, projects and technologies so far, …), `evaluation_focus`, `expected_concepts`.
- **`EvaluationResult`** (schema "v2", `evaluation_strategy_version="v1"`, frozen):

| Group | Fields |
|---|---|
| Identity & provenance | `result_id`, `request_id`, `specification_id`, `source_id`, `category`, `project_reference`, `reasoning_type`, `evaluator_name`, `evaluator_version`, `model_version` ((role, model id) pairs), `dataset_version`, `training_date` |
| Scores | `dimensions: tuple[DimensionScore(name, raw_score, weight_used, confidence, confidence_source, contributes_to_overall, evidence_refs)]`, `overall_score`, `grade`, `confidence`, `confidence_source`, `confidence_rationale` |
| Explanation | `reasoning`, `strengths` / `weaknesses` (`EvidenceLinkedClaim(claim, dimension, evidence)`), `missing_reasoning` (`MissingReasoningItem(category, explanation, expected_because, evidence, severity)`), `concept_coverage` (`ConceptObservation(concept, status ∈ {DEMONSTRATED, SUPERFICIAL, OMITTED}, evidence, …)`), `suggested_improvements`, `recommended_topics` |
| Flags & raw data | `contradiction_detected`, `contradiction_explanation`, `resume_grounding_score`, `raw_model_output`, `calibration_version`, `recommended_action ∈ {probe_deeper, clarify, move_on, skip}` |

Validators enforce "no opaque scores" (non-blank reasoning) and "no invented evidence" (OMITTED concepts must have no evidence; the others require it).

#### Orchestration (`evaluation_engine.py`)
- `build_request(...)` snapshots the context (prior answers for this spec only) and chooses the expected concepts via `_lookup_expected_concepts(spec)`:
  - skill_in_context → the single skill;
  - project deep-dive and overview → `()` (a fix for a leaked tech list);
  - certification → the certification name.
- `EvaluationLedger`: session-scoped and append-only (`append`, `all`, `for_specification`).

#### Dimensions (`reasoning_dimension_relevance.py`)
The 12 dimensions are: technical_accuracy, technical_depth, communication, completeness, architecture, tradeoffs, ownership, debugging, testing, scalability, resume_grounding, authenticity.
- **Always relevant:** accuracy, communication, completeness, resume_grounding.
- **`authenticity`** never contributes to the overall score.
- **Per `ReasoningType` extras**, e.g. TRADE_OFF_ANALYSIS → tradeoffs + architecture. The one category exclusion is (DECISION_MAKING, SKILL_IN_CONTEXT), which removes architecture and tradeoffs.

#### `HeuristicEvaluator` ("heuristic-v1")
- **Similarity:**
  - SBERT `all-MiniLM-L6-v2` cosine against the *grounding* text; Jaccard similarity if SBERT is unavailable.
  - Rescaled linearly (grounding 0.08–0.33, accuracy 0.10–0.32).
  - accuracy = 0.85 × grounding-sim + 0.15 × question-sim. Question similarity alone was found to be *inversely* correlated with answer quality.
- **Dimension scores:**
  - depth: 0.95 × accuracy + 0.05 × term coverage.
  - communication: 0.5 + sentence/connective/length bonuses.
  - completeness: word-count buckets.
  - marker dimensions (architecture, tradeoffs, debugging, testing, scalability): max(0.9 × similarity, lexical marker score).
  - ownership and authenticity: first-person ownership phrases.
- **Weights and grade:**
  - weights: 1.5 for always-relevant dimensions, 1.0 for the others, normalised.
  - **Grade:** ≥ 0.90 excellent, ≥ 0.75 good, ≥ 0.55 adequate, ≥ 0.30 weak, otherwise poor.
- **Claims and extras:**
  - `STRENGTH_THRESHOLD = 0.65` and `WEAKNESS_THRESHOLD = 0.35` bucket evidence-quoting claims.
  - `missing_reasoning` is produced for dimensions scoring < 0.4.
  - NLI `cross-encoder/nli-MiniLM2-L6-H768`: contradiction probability ≥ 0.5 sets the flag.
  - Concept coverage by lexical phrase matching (called a "temporary reference implementation" in the code).

#### `HybridEvaluator` ("hybrid-v1", Round 3)
1. The heuristic always runs. The trained model runs inside `try/except`; on failure the turn falls back to the heuristic (`score_source="heuristic_fallback"`).
2. When DeBERTa succeeds, its `dimensions`, `overall_score`, `grade` and `reasoning` are used **as produced**.
3. **Plausibility guardrail (downgrade only):** a dimension becomes `min(trained, heuristic)` only if its own agreement band is "low" (agreement = 1 − |Δ| < 0.60) **and** the heuristic scored it < 0.35. The overall score and grade are then recomputed.
4. **Confidence** = heuristic confidence × clamp(band multiplier {high 1.0, medium 0.8, low 0.55} × (0.70 + 0.30 × trained confidence)). It can never exceed the heuristic's confidence.
5. **Concept coverage** is reconciled downgrade-only against DeBERTa's per-concept head. **Strengths and weaknesses are re-bucketed** against the final scores (fixing "25% labelled Strong").
6. `missing_reasoning`, `suggested_improvements`, `recommended_topics` and `recommended_action` come from the heuristic.
7. One JSON line per turn is written to `hybrid_diagnostics.jsonl` (per-dimension heuristic, trained, final and agreement values). Write errors are swallowed.

#### Fallback chain
| Situation | What handles scoring |
|---|---|
| Normal operation | `HybridEvaluator` (DeBERTa authoritative) |
| DeBERTa fails on one turn | Hybrid falls back to heuristic-only scoring for that turn |
| Trained model can't load at startup | Bare `HeuristicEvaluator` |
| Nothing registered (tests) | `conversation_engine` auto-registers `HeuristicEvaluator` |

---

**Round 1 scoring with a trained model (`averaged_evaluator.py`, 2026-09-30, `resumeParser_integration.md` step 5).** When `main_cap/cap/deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt` (735 MB, git-ignored, a teammate's DeBERTa-v3 `overall_single_v5_1088` model) is present, `deployment_evaluator.bootstrap_production_evaluator` activates `AveragedEvaluator`: score = 0.8 × the model (`OverallSingleEvaluator`) + 0.2 × `HeuristicEvaluator`, with the heuristic's dimensions and feedback kept for the report. QWK vs gold: 0.86 on the model's 151-answer held-out test set (heuristic alone 0.10) and 0.70 on a 58-answer stress set (heuristic 0.23); no strong answer crushed, no weak one inflated. Without the file (or with `CAP_TRAINED_EVALUATOR=0`) the previous tiers apply unchanged. Adds ~4 s to server start and ~0.1 s per answer on a GPU (~1 s on CPU). Known bias: the model's score tracks answer length (r = 0.70).

**End-of-session feedback (`interview_feedback.py`, 2026-09-30).** `conversation_engine.end_conversation` adds `summary["feedback"]` (headline, summary, strengths, focus areas, a scope note that factual correctness isn't verified, stats), built from the per-turn results: depth (`technical_depth`), relevance (`completeness`) and grounding (`ownership`, `resume_grounding`), averaged over answered questions only (non-answers are ignored). The Round 1 report uses its headline/summary instead of the fixed per-grade text, lists its focus tips first under "Before Your Next Interview" and shows the scope note; it is saved with the session, so History shows the same text. In the Full Interview report the top headline comes from both round scores instead (`rdCombinedVerdict`: ≥60% good, <40% weak, e.g. "Strong on your projects, but the technical round needs real work."), and the Round 1 headline moves to the top of the Round 1 section.

**Non-answer gate (`answer_gate.py`, 2026-09-30).** `evaluation_engine.evaluate` passes every Round 1
result through `answer_gate.gate`: "idk"-style replies, replies under 3 words, keyword dumps, comma lists of
terms, gibberish, repetition and pasted code/markup are capped at 0.1 / "poor" (strengths cleared, one
weakness explaining why), whichever evaluator is active. A keyword dump previously scored 0.79 "good". It
flags 0 of 628 genuine answers tested (`integration_checks/gate_check.py`).

### 4.7 Trained model layer (DeBERTa)

| File | Key elements |
|---|---|
| `model_backbone.py` | `BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256 default / 128 deployed, pooling="cls"\|"mean")`; `build_tokenizer`; `tokenize_pair` (`[CLS] q [SEP] a [SEP]`); `CrossEncoderBackbone` (forced fp32) |
| `model_heads.py` | **CORAL ordinal heads** (`CoralOrdinalHead`: shared linear layer, monotonic biases `base − cumsum(softplus(deltas))`, K=5 tiers) per dimension (`DimensionOrdinalHeads`); `ConceptObservationHead` (3-class, one pass per (answer, concept) pair); `MissingReasoningHead` (11-category presence + severity); `MultiTaskModel`; `compute_batch_loss`; `train_model` (AdamW lr 2e-5, weight decay 0.01, optional linear warmup and decay, seeded, `on_epoch_end` callback) |
| `model_dataset.py` | `score_to_tier` (0.80/0.60/0.40/0.25 → tiers 4..0), `TrainingExampleDataset`, `collate_fn` (dimension masks by relevance), `build_dataloaders(batch_size=8, seed)` |
| `model_checkpoint_io.py` | `save_checkpoint_artifact` / `load_checkpoint_artifact` (rebuilds the architecture, strict `load_state_dict`, `eval()`) |
| `model_evaluator.py` | `TrainedEvaluator` (`name=f"trained-{model_version}"`): ordinal → raw score {0, .25, .5, .75, 1}; confidence = 1 − mean binary entropy; concept argmax; missing-reasoning sigmoid > 0.5; its own NLI contradiction flag. `promote_trained_model(checkpoint, decision, evaluator, make_active)` raises if the decision is not approved. |
| `deployment_evaluator.py` | `bootstrap_production_evaluator()` (never raises): check all three files exist and the `PromotionDecision` is approved *first* (otherwise fall back without loading anything) → tokenizer → `load_checkpoint_artifact(weights)` → `TrainedEvaluator` → register it (not active) → activate `HybridEvaluator(HeuristicEvaluator(), trained)`. Any failure activates a bare heuristic (`_activate_heuristic_fallback`). |

**Deployed checkpoint metadata** (`deployed_model/best_checkpoint.json`):

| Field | Value |
|---|---|
| model version | `deberta_v3_base_experiment_4_epoch4` |
| dataset | `v_experiment_4_combined` |
| formulation | `ordinal_regression` |
| hyperparameters | epoch 4, lr 2e-5, batch 4, weight decay 0.01, 615 warmup steps, linear decay, seed 42, split 0.7/0.15/0.15 |
| promotion (`final_promotion_decision.json`) | **approved**, candidate QWK 0.3976 vs heuristic baseline 0.1341 |

**The weights file is not in the repository** (`*.pt` is gitignored), so a fresh clone runs on the bare `HeuristicEvaluator`. Startup detects the missing file up front and never downloads or loads the DeBERTa tokenizer or backbone in that case.

---

### 4.8 Improved Answer / coaching & concept analysis

- **`strong_answer.py`** (deterministic, no LLM):
  - `build_improved_answer(q, result, answer)` returns the candidate's own answer, deduplicated, plus a first-person addition naming up to 3 missing concepts and 2 weak areas (from `_WEAK_AREA_CLAUSES`), plus an optional grounded example sentence.
  - `coaching_note(...)` returns only that addition. It is hidden when the grade is good or excellent, the answer is under 12 words, or there is nothing concrete to add.
  - The UI shows "Your Answer" and "Coaching Note" separately. This UI-honesty fix came after the old "Improved Answer" label was found to present an unchanged answer.
- **`concept_analysis.py`:**
  - `concept_pool` uses only `grounding.project.concepts` (the Phase 8 fix: no registry concepts).
  - `concept_coverage_percent(result)` = 100 × mean status credit (DEMONSTRATED 1.0, SUPERFICIAL 0.5, OMITTED 0) over `result.concept_coverage`, or `None` if that list is empty.

---

### 4.9 ML research track

**End-to-end pipeline, with the function at each step:**
```
Planner over 36 profiles → CoverageUnit pool
 → coverage_strategy.plan_batch  (5% off-topic, 5% contradictory, 20% per core tier, 17.5% follow-up)
 → generation_recipe.sample_recipe  (crc32-deterministic concept/reasoning targets per tier)
 → prompt_assembler.assemble_prompt("promptbook","1.0.0")  (9 pure prompt_controllers)
 → GenerationClient.generate  (GeminiGenerationClient | FakeGenerationClient — all real datasets used Fake)
 → generation_validation.validate_generation  (reject, never repair; max 3 attempts)
 → training_example_assembler.assemble_training_example  → TrainingExample
 → dataset_manifest.assemble_manifest  (version stamp, provenance, tier distribution)
 → dataset_relabeling.relabel_example  (per-dimension scores from recipe data)
 → training_experimentation.split_dataset_by_group  (specification-level; no leakage)
 → [Exp 4] deterministic_rewrite (concise/conversational/reflective) + SBERTDriftVerifierClient + rewrite_validation
 → model_dataset.build_dataloaders → model_heads.train_model (Colab T4)
 → run_benchmark (QWK vs HeuristicEvaluator, core grades only) → decide_promotion → deployed_model/
```

**Key data models:**
- **`TrainingExample`** (frozen, v1): `metadata`, `provenance` (SYNTHETIC or REAL_SESSION), `inputs` (spec, question, reasoning type, answer, expected concepts), `privacy`, `synthetic` meta (prompt id and version, generator model, intended tier and targets, rewrite lineage), and `labels`:
  - `label_source`
  - `dimension_labels`, `missing_reasoning_labels`, `concept_labels`
  - `contradiction_label`
  - `overall_label(score, grade, rationale)`
- **`QualityTier`:** excellent, good, adequate, weak, poor, off_topic, contradictory. The synthetic tier score is 0.90 / 0.70 / 0.50 / 0.30 / 0.12 / 0.05 / 0.70.
- **`DatasetManifest`:** version, parent, superseded_by, example_ids, generator_provenance, distributions, review_summary. Related: `ReviewEvent` and the append-only `ReviewEventLog`.
- **`labeling_operations`:** `ReviewerRegistry` (ANNOTATOR / ADJUDICATOR), a derived `ReviewState`, `record_review` (role-gated), and `apply_relabel` (REAL_SESSION only).
- **`training_experimentation`:** `ExperimentConfig`, `DatasetSplit`, `Checkpoint` (lineage), `BenchmarkResult`, `PromotionPolicy(minimum_qwk_improvement=0.0)`, `PromotionDecision`, and `compute_qwk` (a dependency-free quadratic weighted kappa).

**Experiment scripts:**
| Script | Dataset / output | Notes |
|---|---|---|
| `run_first_experiment.py` | 50 recipes, 1 profile | Real Gemini hit quota after 4/50 examples |
| `run_second_experiment.py` | 120 recipes, 5 profiles | First specification-level split |
| `run_third_experiment.py` | 2,500 recipes, 36 profiles | Scaling check, no training |
| `run_experiment_1.py generate\|train` | 500-recipe anchor, 5-epoch curve | `artifacts/experiment_1/` |
| `run_experiment_2.py`, `_train.py`, `_train_tuned.py` | `v_experiment_2_scaled_library` (2,480 accepted) | Tuned: val QWK 0.49→0.54, test peaks 0.445 at epoch 3 |
| `run_dataset_relabel.py relabel` | `v_experiment_3_relabeled_dimensions` (2,479) | Broke the flat per-tier dimension labels (exact-tie rate 100% → 16.6%) |
| `run_experiment_4_pilot.py` | Gemini rewrite pilot, 40×3 | Quota-limited |
| `run_experiment_4_deterministic.py select\|generate\|select_full\|generate_full` | API-free rewrites | Pilot acceptance 45.8% → 61.7% |
| `validate_experiment_4_deterministic_full.py` | `v_experiment_4_deterministic_full` | Leakage, schema and provenance report |
| `run_experiment_4_prepare_training_data.py` | `v_experiment_4_combined` = 2,479 + 3,185 = **5,664** (4,923 / 379 / 362) | Plus `label_mappings.json` |
| `run_experiment_4_train.py train` | Deployed checkpoint | Colab |
| `run_experiment_4_evaluate.py <old_ckpt>` | Head-to-head on 362 test examples | Old vs new DeBERTa vs heuristic vs hybrid |
| `regenerate_promotion_decision.py` | Rewrites `final_promotion_decision.json` | Hard-wired to `artifacts/experiment_2` |

**Reproducibility:**
- crc32 everywhere (never `random` or salted `hash()`), seed 42.
- Append-only prompt registries (`promptbook/1.0.0`, `rewrite_promptbook/1.0.0`, `deterministic_rewrite/1.0.0`).
- The Experiment 3 provenance package pins SHA-256 hashes.
- `artifacts/` is gitignored and not present locally.

---

### 4.10 Flask application (`app.py`)

**Startup (in import order):**
1. `load_dotenv(main_cap/cap/.env)`; an INFO log if `GEMINI_API_KEY` is unset (expected).
2. `deployment_evaluator.bootstrap_production_evaluator()`.
3. `Flask(__name__, template_folder="templates", static_folder="static")`.
4. `init_accounts(app)` (database, migrations, secret key, Flask-Login, accounts routes, 413 handler), `register_blueprint(sessions_bp)`, `abandon_all_open_sessions()`.
5. `_require_login_for_api` (`before_request`): every `/api/*` path answers **401** without a session, except `/api/auth/login` and `/api/auth/signup`. `/` and `/health` stay public.
6. `sys.path` gets `resume_classifier/`, then `from rag_integration import rag_generator` is attempted (`_rag_available` evaluates to False; see §4.15), then `resume_classifier` is re-prioritised.
7. Module-level stores: `_candidate_profiles`, `_profile_owners` (profile session id → `(user_id, resume_id)`), the RAG question pool, and `SAMPLE_QUESTIONS` (5 computer-networks questions with fill-mask).

**Routes** (the accounts and history routes are in §4.20–4.21):
| Route | Method | Used by the UI | Summary |
|---|---|---|---|
| `/` | GET | ✅ | Serves `index.html` |
| `/health` | GET | — | `{"status":"ok"}` |
| `/api/resumes/<id>/use` | POST | ✅ | Loads a **saved** resume's parsed profile into `_candidate_profiles` (no upload, no re-parse) and returns `profile_to_frontend_format` + `session_id` + `resume`. Other users' ids → 404 |
| `/api/classify-resume` | POST (multipart `file`) | ✅ | Main-page upload: `account_routes.add_resume_for_user` stores, parses and saves it as the **current** resume, then the same response as `/use`. Unreadable/unsupported → 400 (the saved resume is kept) |
| `/api/resume-discussion-v2/start` | POST `{session_id}` | ✅ | Checks the profile session belongs to `current_user`; `conversation_engine.start_conversation`; then `session_history.begin_resume_discussion` |
| `/api/resume-discussion-v2/reply` | POST `{session_id, answer}` | ✅ | Ownership check (`owns_conversation`), `advance_conversation`, then `record_resume_discussion_turn` |
| `/api/resume-discussion-v2/end` | POST `{session_id, integrity, attention_metrics}` | ✅ | Ownership check, `end_conversation(id, integrity=...)`, then `finish_resume_discussion` |
| `/api/next_question` | POST `{asked_ids, difficulty, topic}` | ✅ (Technical) | Takes from the RAG pool if available (it never is), else `SAMPLE_QUESTIONS`; relaxes filters; `completed` when exhausted |
| `/api/evaluate` | POST | ✅ (Technical) | Inline heuristic: gibberish filter, token overlap with the reference, fill-mask flexible match; `combined = 0.7·main + 0.3·fill` → marks /10. With a `session_id` of the user's in-progress technical session, the question is also recorded (`record_technical_turn`) |
| `/api/candidate-profile/<id>` | GET | — | Raw stored profile |
| `/api/get-resume-discussion` | POST | — | Legacy MCQ-style discussion generator + `_hardcoded_fallback` |
| `/api/resume-discussion/{start,reply,end}` | POST | — | Legacy v1 `discussion_engine` |

**Dead helpers:** `_build_local_candidate_profile` and `_map_local_level_to_profile_level` (no callers).

---

### 4.11 Frontend (`templates/index.html`)

A single page with inline CSS and JS, and no framework. Screens are top-level containers toggled with `style.display`.

| Screen | Container | Key functions |
|---|---|---|
| Login / Signup | `#auth-container` | See §4.20 / §4.23 (`authBootstrap`, `showAuthScreen`, `enterApp`, 3-step signup) |
| Top nav, Home, Sessions, Profile | `#app-nav`, `#home-page`, `#sessions-page`, `#profile-page`, `#profile-menu` | See §4.23 (`showAppScreen`, `loadHome`, `loadSessions`, `openSession`, `loadProfile`) |
| Resume screen (Full Interview setup) | `#landing-container`, `#vessel` | `showResumeStart` (saved-resume state: filename + "Upload different"), `handleResumeFileChosen`, `onStartClicked` → `useSavedResume` (`/api/resumes/<id>/use`) or `uploadResume` (`/api/classify-resume`), both through `buildCandidateProfile` (typed build animation); `setVesselStage(idle / saved / recognized / building / ready)` |
| Candidate Briefing | `#candidate-dashboard` | `showCandidateDashboard` (stores `parsedResumeData`), `renderBriefingGrid` (profile, AI summary, strategy + focus chips, projects, technical stack), `runBriefingSequence` → CTA `rdShowIntegrityRules()` |
| Round 1 · Resume Discussion | `#rd-container` | `showInterviewRules("full")` → `acceptInterviewRules` → `startInterviewMode("full")` → `startDomainDiscussionFromDashboard` (guarded by `rdSessionStarting`, starts the webcam) → `rdStartSession` → `rdRenderStage` → `rdHandleSubmission` / `rdHandleReply` → `rdTriggerReport` |
| Between rounds | `#round-transition` | `showRoundTransition` (score, grade, verdict, Round 2 card), `beginRound2` |
| Round 2 · Technical / Technical Interview | `#chat-container` | `startTechnicalRound` → `beginTechInterview` (`/api/tech-interview/start`), `handleSubmission` (`/<id>/answer`), `showTechPrompt` (question / follow-up / clarification), `finishTechnicalRound` → `endTechInterview` (`/<id>/end`, returns the report) |
| Results | `#rd-report-container` (full interview, history) / `#dashboard-container` (standalone Technical Interview) | `rdBuildReportFromV2`, `rdRenderReport(data, {historical} or {combined})`, `rdRound2Html`, `rdAttentionHtml`; `triggerDashboard(round2)` for practice |
| Overlays | `#proctor-overlay` (rules, termination, confirm dialogs), `#toast-container` | `proctorShowOverlay`, `confirmDialog`, `showToast` |

**Other mechanisms:**
- **Answer boxes:** both (`#user-input`, `#rd-user-input`) are multi-line `<textarea class="answer-box">`: Enter sends, Shift+Enter adds a line.
- **Profile photo:** `fillAvatar(el, url, fallback)` puts the photo (or initials) in the top-right circle, on the Profile page and next to the candidate's technical-chat messages; picker on signup step 1 (`setSignupPhoto`) and on the Profile page (`renderProfilePhoto`, `removeProfilePhoto`).
- **Voice input:** two Web Speech API recognizers, `rdRecognition` (Round 1) and `recognition` (technical). Both suspend the blur check while a mic permission prompt may be open (`proctorSuspendBlur` / `rdMicSettled`).
- **Typewriter:** `typeLine(el, text)` uses a per-element cancellation token, so a superseded call stops and its promise never resolves (the fix for a race condition).
- **System log:** `setSystemLog` plus an idle cycle.
- **Escaping:** `esc()` HTML-escapes user and server text everywhere, including the technical chat (`addMessage` escapes plain-text messages; questions, topics and feedback are escaped).
- **Session expiry:** a wrapper around `window.fetch` sends the user back to the login screen on any 401 while logged in.

---

### 4.12 Webcam, gaze & liveness monitoring

All processing is **client-side**; frames never reach Flask.
- **Loading:**
  - `ensureGazeLandmarkerReady()` dynamically imports `@mediapipe/tasks-vision@0.10.14` from jsDelivr.
  - `FaceLandmarker.createFromOptions` uses `modelAssetPath="/static/models/face_landmarker.task"`, the GPU delegate with a CPU retry, `runningMode:"VIDEO"`, one face, and transformation matrixes.
- **Lifecycle:** `initializeGazeMonitoring()` is idempotent and calls `getUserMedia({video:true})`. It shows a "Camera blocked" panel on denial. `startGazeDetectionLoop()` runs `detectForVideo` in a rAF loop. `stopGazeMonitoring()` releases everything.
- **Head pose:** yaw and pitch come from the facial transformation matrix, smoothed with EMA 0.30. Beyond 26° the head counts as left, right, up or down.
- **Iris gaze:**
  - Eye landmarks: left 33/133/159/145 with iris 468; right 263/362/386/374 with iris 473.
  - The iris offset is normalised by the eye's own width and height, and the two eyes are combined weighted by confidence.
  - Calibration: a baseline is taken over 15 samples and 2 s (5 s maximum), then frozen.
  - Classification uses thresholds |x| 0.44 and |y| 0.60 with hysteresis, and requires 5 confirming frames.
- **Fusion:** raw = 0.35 × head + 0.55 × gaze + 0.10 when head and gaze agree, then EMA. A deviation starts at ≥ 0.50 and ends below 0.34. Looking down within 5 s of typing is tolerated.
- **Attention state machine:**
  - NORMAL → CAUTION (3.5 s) → WARNING (8.5 s).
  - FACE_ABSENT after 7.5 s without a face.
  - A 45 s cooldown per warning type.
  - Warnings are both visual (`showGazeWarning`) and spoken (`speechSynthesis`).
- **Liveness:**
  - States: NO_FACE → FACE_DETECTED → LIVENESS_CHECKING → LIVE_PERSON_CONFIRMED.
  - One random challenge: turn the head left or right, with a 12 s timeout. (The blink challenge is disabled since 2026-09-30 as unreliable on webcams; its checker code is kept.)
  - A passive watchdog forces a head-turn re-check after 35 s with no natural activity (natural blinks still count as activity).
- **Metrics:** `attentionMetrics` = `{sessionStartedAt, totalWarnings, faceAbsentWarnings, totalDeviationMs, livenessRechecks, livenessFailures}`.
- **Attention Score:** `computeAttentionScore` = `100 − 4·warnings − 6·faceAbsent − 5·livenessFailures − min(20, 0.25·deviationSec)`, shown as FOCUSED (≥ 85), MOSTLY FOCUSED (≥ 65) or DISTRACTED.
  - `attentionSnapshot()` packages the metrics plus `sessionMs` and the score. It is **saved with every session** when a round ends.
  - In the full interview each round keeps its own figures (reset at `beginRound2`), and `combineAttention` totals them for the final results.
  - When the camera panel is showing, the profile menu and nav hide (`setProfileMenuSuppressed`).
- **Teammate's webcam updates (ported 2026-09-30 from a teammate's copy of the project (`projectwithnewwebcam/`, since deleted)):**
  - **Camera setup check** (`showCameraSetup`, `_cs*` helpers, `#camera-setup-overlay`): before the rules screen of both the Full Interview (`rdShowIntegrityRules`) and the Technical Interview (`openTechnicalSetup`, `proceedToAdaptiveInterview`). A live preview with a checklist: camera available, face detected, **one face only** (these three block Continue, with a Retry button), face centred, distance, lighting (mean face brightness < 65 = low light; these warn but never block). It uses its own short-lived camera stream and closes it on Continue, so monitoring still starts in `startDomainDiscussionFromDashboard` / `startTechnicalRound` exactly as before and still runs through the break into Round 2; the camera permission prompt now happens during the check, before full screen and proctoring.
  - **Second-person warning:** the Face Landmarker tracks up to 2 faces (`numFaces: 2`); `faces[0]` stays the candidate; when a second face is present `#second-face-warning` ("Another person detected on camera") is shown, visual only, attention metrics unchanged; cleared by `stopGazeMonitoring`.
  - **Spoken warnings muted while any mic is on** (`speakAttentionWarning`): the technical mic (`isRecording`) and now also the Round 1 mic (`rdIsRecording`), so warning audio can't be transcribed into the answer. The visual banner still shows.
  - **Prominent camera alerts** (`#cam-alerts`, `camAlertUpdate`): large banners at the top of the screen while monitoring runs (they don't block typing and are visual only). Red: another person is visible (shown after 0.6 s, cleared 1.2 s after they leave). Amber: "too dark or blurry — please sit in a well-lit environment" (face brightness < `CS_DARK_LUMA` 65, whole-frame brightness < 40 when no face is found, or face sharpness (Laplacian variance on a 64×64 crop, `camFaceSharpness`) < `CAM_BLUR_VAR` 15; sampled every 500 ms, smoothed, shown/cleared after 2.5 s). The small orange line under the preview is kept. The camera setup check shows the same amber notice (`#cs-light-notice`) and a "blurry" state on the Lighting row; like low light it warns but doesn't block Continue. `console.debug` logs `[CameraQuality]` values every ~5 s for tuning the thresholds.
  - Rollback: `archive/webcam_backup_2026-09-30/`. `index_before_camera_alerts.html` is the copy from just before the prominent alerts.

---

### 4.13 Session integrity

Zero-tolerance rules for **the whole interview**: the full interview (Round 1, the break, Round 2) and the standalone Technical Interview. They are implemented in the round-agnostic `SESSION INTEGRITY` block of `index.html`, which calls `interview*` hooks from the INTERVIEW FLOW section (§4.23), and recorded by the backend.

| Piece | Behaviour |
|---|---|
| `showInterviewRules(mode)` | Rules overlay (`mode` = `full`: explains both rounds; `technical`: practice). Browsers without full-screen support are blocked with a message |
| `acceptInterviewRules(mode)` | Inside the click gesture: `proctorEnterFullscreen()` (`requestFullscreen` + Chromium `navigator.keyboard.lock(["Escape"])`), then `startInterviewMode(mode)` |
| `proctorArm()` | As soon as the session exists (Round 1: when `rdStartSession` gets the conversation, before the first question types out; Technical: `beginTechInterview` when the first question arrives) and the camera prompt has settled (it waits for it). If `interviewSessionActive()` and not in full screen, shows the "Return to full screen" overlay; otherwise adds the listeners. **Stays armed from Round 1 through the break and Round 2** |
| Violations | `visibilitychange` hidden → `tab_switch`; window `blur` not regained within `PROCTOR_BLUR_GRACE_MS=1500` → `window_switch`; `fullscreenchange` exit → `fullscreen_exit`; `copy`/`cut`/`paste`/`drop` and Ctrl/Cmd+C/X/V and Shift/Ctrl+Insert → blocked + violation; right-click is blocked only |
| Permission prompts | Both mic buttons suspend blur tracking (`proctorSuspendBlur` / `rdMicSettled`). Losing full screen while suspended asks the candidate to re-enter instead of terminating |
| `proctorViolation(type)` | Terminates exactly once. It records `{type, label, at_turn, round, occurred_at}`, then disarms, exits full screen, stops mics, disables input, shows the red overlay, and calls `interviewTerminate()`. That ends whatever phase is running: Round 1 (`rdTriggerReport`), the break (`terminateBetweenRounds`) or technical (`finishTechnicalRound`) |
| Backend | Both `/api/resume-discussion-v2/end` and `/api/technical-sessions/<id>/end` receive `proctorIntegrityPayload()`. `conversation_engine.sanitize_integrity` whitelists it, and the session is saved as `terminated` |
| Results | Red "Session terminated" banner naming the round and question. Unanswered turns are dropped, and "Round 2 not taken" is shown if it ended before Round 2 |

Limitation: enforcement is client-side and can be bypassed with DevTools.

---

### 4.14 Legacy v1 discussion engine

`discussion_engine.py` (routed at `/api/resume-discussion/*`, **not used by the UI**):
- `DiscussionMemory` does SBERT semantic dedup (≥ 0.82), tracks concept mastery, and sets difficulty from the last 3 scores.
- Phrasing uses `random.choice` over styles and variants.
- The local evaluator uses SBERT correctness, KeyBERT coverage, and an NLI flag. `EvaluationWeights` are correctness 0.30, depth 0.25, completeness 0.20, communication 0.15, coverage 0.10, and can be overridden via the `CAP_EVAL_W_*` env vars.
- `_decide_action` thresholds, checked in order: skip < 0.15; move_on if 2 follow-ups have been used; probe_deeper ≥ 0.55 with missing concepts; clarify 0.25–0.55; otherwise move_on.
- Session limits: a soft target of 12 and a hard cap of 20 questions.
- It runs on the v2 `TopicPool` through `legacy_topic_pool_adapter._UnitView`, a live `MutableMapping` whose writes are routed through the pool's hardened lifecycle APIs.

---

### 4.15 Supporting subsystems

#### `rag_system/rag_tester/`: legacy RAG question generation and grading (standalone CLI)
> Superseded for retrieval by the slide pipeline (§4.24). The old `knowledge_base/` is kept only as the evaluation baseline. `evaluate.py`'s rubric grader (below) is the planned grader for open technical answers once it is adapted (key points passed in, short reference answer, concept matching by meaning, no Qwen call per answer).

- **Knowledge base:** `knowledge_base/{cn,dbms,dsa,ooad,os}/` each hold `index.faiss` (`IndexFlatIP`, MiniLM, normalised), `chunks.json`, `bm25.pkl`, `bm25_tokens.json`, `diagram_chunks.json` (empty) and `metadata.json`.

  | Subject | Chunks |
  |---|---|
  | cn | 99 |
  | dbms | 839 |
  | dsa | 727 |
  | ooad | 569 |
  | os | 232 |

  The source PDFs (≈189 MB) are in `samples/`.
- **Ingestion (`dynamic_ingestor.py`):**
  - One chunk per slide or page, using OCR fallback (`pytesseract`) for near-empty pages.
  - Large pages go through semantic chunking (500 words, 100 overlap), and chunks under 100 words are merged.
  - `embedding_text` = headings + concepts + text.
- **Retrieval (`retrieval.py`):**
  - Hybrid score = 0.6 × FAISS cosine + 0.4 × normalised BM25, with a threshold of 0.25.
  - Optional rerank with `cross-encoder/ms-marco-MiniLM-L-6-v2`.
  - `get_context_with_pages` returns `(context, pages, headings, concepts)`.
- **Generation (`generate.py`):** `Qwen/Qwen2.5-1.5B-Instruct` with a grounding system prompt. It generates interview questions, reference answers, MCQs, pseudocode and coding questions, and test cases.
- **Grading (`evaluate.py`):** overall = 0.45 × semantic + 0.35 × weighted concept + 0.20 × clarity, graded A to F.
- **Extras:** `counterfactual_feedback.py` (minimal-edit analysis) and the diagram pipeline (`diagram_*.py`), where `call_vlm()` raises `NotImplementedError` by design.
- **Tracking:** `tracking.py` stores per-user progress JSON.
- **CLI:** `python main.py` (interactive menu).
- **Integration with the app is broken:** `rag_integration.py` imports `ingestor.ingest_subject`, which doesn't exist, and expects a flat `*.index` layout and a `cn_unit1` subject. As a result, `/api/next_question` always serves the hardcoded `SAMPLE_QUESTIONS`.

#### `archive/Roberta/roberta-multitask-model/`: question classification and adaptive quiz (archived)
> **Archived.** It was part of the original plan (label questions with intent/difficulty/topic, drive an adaptive quiz) but never ran in the app: the trained weights were never committed (inference was always rule-based) and the UI never called its routes. Its job is now covered by the question bank (topic and difficulty by construction) and the planned Phase 2 selector. The folder moved to `archive/` and its `/roberta/classify` and `/adaptive/*` routes were removed from `app.py`.

- **Data:** `data/dataset.json` has 172 questions `{text, intent, difficulty, topics[]}`.
  - Intents: definition, explanation, comparison, procedure, reasoning.
  - Difficulty: easy, medium, hard.
  - Topics: OS, DBMS, CN, OOP, DSA.
- **Training:** three separate `distilroberta-base` models (`python -m model.train_{difficulty,intent,topic}`). Hyperparameters: max length 64, lr 2e-5, batch 8, early stopping, class-weighted loss. Multi-label topics use BCE with `pos_weight`.
- **Inference:** `inference/predict_*.py` apply an input-validation gate (the text must start with a question word), then the model if its weights exist, otherwise `rule_based.py`. **No weights are in the repo, so inference is always rule-based.**
- **Adaptive engine:**
  - `adaptive/user_profile.py`: per-topic and per-intent accuracy, level, and target difficulty.
  - `adaptive_selector.py`: strategy weighted 60% weak topic, 30% weak intent, 10% random.
  - `session_manager.py`: CLI grader.
- **App integration (before archiving):** `/roberta/classify` and `/adaptive/*`, which the UI never used.

#### `resume_classifier/`: legacy parser and domain classifier
- **`src/parser.py`:** `extract_text` (pdfplumber / python-docx / txt) and `parse_resume`.
- **`src/features.py`:** experience, skills, education and project count.
- **`src/models.py`:** `EnsembleClassifier` = 0.4 × SBERT similarity to `data/domains.json` + 0.6 × BERT. **The BERT model was never trained** (its head is random).
- **`src/train.py`:** needs `data/labeled/labeled_resumes.json`, which is missing.
- **Uses today:** only `shadow_mode_batch._extract_text` uses its parser. The main app does not use the classifier.

#### `parser_tests/`: benchmark for the legacy parser
- `generate_metadata.py`: pdfplumber layout heuristics → `metadata/*.json`.
- `evaluate_parser.py [--resume 001] [--verbose]` runs `parse_resume` + features + `SBERTMatcher` → `baseline/*.json`, and scores against `ground_truth/`, which doesn't exist, so only baseline mode works.
- There are 10 PDFs, and the baselines contain real PII.

---

### 4.16 Data models / schemas (consolidated)

The **database tables** (SQLAlchemy, `models.py`) are described in §4.21. Everything else is frozen Pydantic models and dataclasses passed between modules:

```
CandidateProfile ──(TopicPool._build)──► QuestionSpecification* ──(realize)──► InterviewQuestion
      │                                         │                                     │
      │ projects/experience/certs/topics        │ grounding (1 entity)                 │ + answer
      ▼                                         ▼                                     ▼
 (dashboard, briefing)                  UnitLifecycleState               EvaluationRequest ──► EvaluationResult
                                                                           (ConversationContextSnapshot)   │
                                                                                                           ▼
                                                                                              EvaluationLedger (per session)
TrainingExample ◄── GenerationRecipe + GenerationOutput      DatasetManifest ─► DatasetSplit ─► Checkpoint ─► BenchmarkResult ─► PromotionDecision
Resume engine internals: TextSpan → DocumentModel → Section → ParserResult → AnnotatedCandidateProfile (+ Confidence, Observation, PipelineTrace)
```

| Model | File | Key fields | Relationships |
|---|---|---|---|
| `CandidateProfile` | `candidate_profile_generator.py` | see §4.3 | The source for all `QuestionSpecification`s |
| `QuestionSpecification` | `question_specification.py` | id, category, text_seed, grounding, source_* | 1 per profile fact; embedded in `InterviewQuestion` and `EvaluationRequest` |
| `InterviewQuestion` | `interview_question.py` | question_text, transition_text, family, reasoning_type, turn_number, specification | Recorded in `ConversationMemory.timeline` |
| `EvaluationRequest` / `EvaluationResult` | `evaluation_request.py` / `evaluation_result.py` | see §4.6 | 1:1 via `request_id` |
| `TrainingExample` | `training_example.py` | metadata, provenance, inputs, privacy, synthetic, labels | Referenced by id from `DatasetManifest` and `DatasetSplit` |
| `Checkpoint` / `PromotionDecision` | `training_experimentation.py` | model_version, dataset_version, experiment_config, artifact_uri / approved, rationale | Persisted in `deployed_model/` |
| `DocumentModel`, `Section`, `ParserResult`, `AnnotatedCandidateProfile` | `resume_engine/*` | see §4.2 | Engine-internal only |
| `User`, `StudentProfile`, `Resume`, `InterviewSession`, `SessionTurn` | `models.py` | see §4.21 | SQLite tables; `Resume.parsed_profile` holds a `CandidateProfile`; `SessionTurn.evaluation` holds the `_result_payload` of an `EvaluationResult` |
| `SignupRequest` / `ProfileFields` | `account_schemas.py` | see §4.20 | Validate signup and profile edits |

---

### 4.17 Design patterns used

| Pattern | Where |
|---|---|
| **Strategy via structural Protocol** | `evaluator.Evaluator` (Heuristic/Hybrid/Trained); `resume_engine.interfaces` stage Protocols; `GenerationClient`, `RewriteVerifierClient` |
| **Registry** | `evaluator_registry` (active pointer + conformance gate), `resume_engine/registry.ParserRegistry` (plugins), `question_families._FAMILY_REGISTRY`, `expected_concepts_registry`, prompt registries |
| **Dependency injection + composition root** | `resume_engine/factory.py` is the only module importing concrete stage classes; `ResumePipeline` depends only on Protocols |
| **Pipeline / chain of stages** | `ResumePipeline.run`, the synthetic generation pipeline |
| **Facade** | `Planner` (over TopicPool/Coverage/Traceability), `conversation_engine` (whole session) |
| **Adapter** | `TrainedEvaluator` (PyTorch → Evaluator), `legacy_topic_pool_adapter._UnitView`, `candidate_profile_mapper`, `evaluation_engine.build_request` |
| **Decorator / composite** | `HybridEvaluator` wraps two evaluators behind the same Protocol |
| **Lazy singleton with graceful fallback** | `_LazySemanticModel`, `_LazyKeyBERT`, `_get_sem_model`/`_get_nli_model`, `_get_genai_client` (they cache `False` on failure) |
| **Immutable value objects** | Frozen Pydantic: `QuestionSpecification`, `InterviewQuestion`, `EvaluationRequest/Result`, `TrainingExample`, … |
| **State machine** | `UnitLifecycleState._ALLOWED_TRANSITIONS`; the attention and liveness state machines in JS |
| **Observer-like tracing** | Optional `PipelineTrace` threaded through stages (zero cost when `None`) |
| **Append-only log / event sourcing** | `EvaluationLedger`, `ReviewEventLog` (review state derived, never stored), `hybrid_diagnostics.jsonl` |
| **Command/query separation** | `plan_next` / `select_next` (read-only) vs `advance` / `mark_*` (mutating); `realize` is pure, `memory.record_turn` is the only mutator |
| **Blueprints + app factory-style init** | `account_routes.accounts_bp` + `init_accounts(app)`, `session_routes.sessions_bp`; `db_manage.py` builds a minimal app for migrations |
| **Hooks / strategy (frontend)** | The `SESSION INTEGRITY` block is round-agnostic and delegates to `interview*` hooks (`interviewSessionActive`, `interviewTerminate`, …) implemented by the INTERVIEW FLOW section |
| **Write-through recording** | Interview routes keep live state in memory and write each turn to SQLite immediately (`session_history`) |

---

### 4.18 Internal interfaces between modules

| Interface | Producer → Consumer | Contract |
|---|---|---|
| `CandidateProfile` dict | engine mapper → `Resume.parsed_profile` (DB) → `app._candidate_profiles` → `Planner`, `profile_to_frontend_format` | Pydantic schema §4.3; no `None`s |
| `session_history.*` | `app.py` interview routes, `session_routes` → SQLite | `begin_resume_discussion` / `record_resume_discussion_turn` / `finish_resume_discussion`; `begin_technical_session` / `record_technical_turn` / `finish_technical_session`; abandonment helpers |
| `interview*` hooks | INTERVIEW FLOW → SESSION INTEGRITY (JS) | `interviewSessionActive`, `interviewCurrentTurn`, `interviewRoundLabel`, `interviewDisableInput`, `interviewResumeInput`, `interviewStopMic`, `interviewTerminate`, `startInterviewMode` |
| `Planner.plan_next(ConversationState)` / `advance(spec_id, UnitStatus)` | planner → conversation engine | Returns a `QuestionSpecification` or `None` |
| `question_realizer.realize(spec, memory, turn)` | realizer → conversation engine | Returns `(InterviewQuestion, variant_idx)` |
| `Evaluator.evaluate(EvaluationRequest) -> EvaluationResult` | any evaluator → `evaluation_engine.evaluate` | Protocol + `check_conformance` |
| `EntityParser.parse(sections, doc, trace) -> ParserResult` | parsers → `ParserRegistry` | `check_parser_conformance` (entity/confidence counts match, reasons non-empty) |
| `GenerationClient.generate(AssembledPrompt) -> GenerationOutput` | Gemini/Fake → generation pipeline | Protocol |
| HTTP JSON contracts | Flask ↔ `index.html` | See §4.10 and `_question_payload` / `_result_payload` |
| Import boundary | `conversation_memory`, `question_realizer`, `discussion_policy`, `planner`, `topic_pool` must **not** import evaluation modules | AST-tested |

---

### 4.19 Configuration & environment variables

| Variable / constant | Default | Effect |
|---|---|---|
| `GEMINI_API_KEY` (`main_cap/cap/.env`) | unset | Needed only for Shadow Mode, Gemini generation, the rewrite pilot and `_verify_traceability.py` |
| `CAP_RESUME_PARSER` | `engine` | Read by `get_active_parser_backend()` (tested), but **ignored by `app.py`** |
| `CAP_DEBUG_SAVE_GEMINI_RESPONSES` | off | Legacy Gemini path writes `debug_candidate_profile*.json` (contains PII) |
| `CAP_EVAL_W_{CORRECTNESS,TECH_DEPTH,COMPLETENESS,COMMUNICATION,COVERAGE}` | 0.30/0.25/0.20/0.15/0.10 | Legacy v1 evaluator weights only |
| `EXPERIMENT_GENERATION_CLIENT` | `fake` | First and second experiment scripts only (`fake` or `gemini`) |
| `HF_DEACTIVATE_ASYNC_LOAD` | set to `1` by experiment scripts | Works around a transformers crash on Windows |
| `RESUME_DISCUSSION_QUESTION_BUDGET` | 10 | `conversation_engine.py` |
| `DEPLOYED_MODEL_DIR`, `_DEPLOYED_MAX_LENGTH` | `deployed_model/`, 128 | `deployment_evaluator.py` |
| `PROCTOR_BLUR_GRACE_MS` | 1500 | Session-integrity blur grace (JS) |
| `CAP_DATABASE_URL` | `sqlite:///main_cap/cap/instance/app.db` | Database URL (any SQLAlchemy URL, e.g. PostgreSQL) |
| `CAP_UPLOAD_DIR` | `main_cap/cap/instance/uploads` | Where resume files are stored |
| `CAP_SECRET_KEY` | generated once into `instance/secret_key` | Flask session secret; set explicitly in production |
| `MAX_UPLOAD_BYTES` / `MAX_CONTENT_LENGTH` | 10 MB | Upload limit; larger requests get a JSON 413 |
| `REMEMBER_COOKIE_DURATION` | 30 days | "Keep me signed in" |
| `session_history.STALE_AFTER` | 2 hours | Idle in-progress sessions become `abandoned` |
| `insights` constants | `TREND_LENGTH=10`, `FOCUS_WINDOW_SESSIONS=5`, `FOCUS_LIMIT=3`, `WEAK_SCORE=0.55`, `MIN_RECURRENCE=2` | Home stats and "Focus next" |
| Port | 5000 | Hard-coded in `app.run` |
| `slide_rag.build` constants | `DEFAULT_MODEL=all-MiniLM-L6-v2`, `VISION_MODEL=Qwen/Qwen3-VL-2B-Instruct`, `EXTRACTOR_VERSION=4` | Embedding model; whose cached vision output to merge; bump the version to invalidate the Stage 1 cache |
| `slide_rag.extract` constants | `HEADER_BAND=0.14`, `FOOTER_BAND=0.86`, `TITLE_BAND=0.32`, `REPEAT_MIN_FRACTION=0.03`, `REPEAT_MIN_SPAN=0.25`, `DIAGRAM_MIN_PATHS=3`, `LABEL_MAX_WORDS=4` | Position/repetition rules (fractions of the page) |
| `slide_rag.sections` constants | `SECTION_MAX_WORDS=450`, `UNTITLED_SIM=0.35`, `STEM_SIM=0.6` | Section grouping |
| `slide_rag.vision` constants | `MAX_SIDE=1280`, `MAX_NEW_TOKENS=450`, `PROMPT_VERSION=1` | Stage 3 rendering, output length, cache key |
| `slide_rag.qbank` constants | `PROMPT_VERSION=6`, `QUOTE_MATCH=88`, `QUOTE_MIN_WORDS=4`, `POINT_QUOTE_SIM=0.35`, `MIN_KEY_POINTS=2`, `DISTINCT_SIM=0.85`, `DUPLICATE_SIM=0.90`, `MAX_CONTEXT_CHARS=9000` | Question generation and its checks (bump `PROMPT_VERSION` to regenerate) |
| `slide_rag.llm_client` constants | `DEFAULT_MODEL=qwen3:8b`, `NUM_CTX=8192`, `THINK_BUDGET=3000`, `KEEP_ALIVE=30m` | Ollama client |
| `slide_rag.rank_bank` | `DEFAULT_THRESHOLD=0.80` (bank currently ranked with 0.75), signal weights | Which questions are active |
| `CAP_CURATED_ONLY` | `1` | New technical interviews draw only from the 132 hand-reviewed best questions (`"curated": true`). `0` serves all 282 active. See §4.25 |
| `CAP_GRADER_ENRICHMENT` | `replies` | Technical grader's use of the offline enrichment: `off`, `replies` (short correct follow-up replies), `all` (also key-point variants + main idea; measured to pass wrong answers). See §4.25 |
| `CAP_QUESTION_BANK_DIR` | `rag_system/rag_tester/question_bank` | Where the app reads the question bank |
| `CAP_TRAINED_EVALUATOR` | on | Round 1 uses the averaged evaluator when the v5_1088 model file is installed; `0` forces the heuristic evaluator |
| `CAP_MODEL_WARMUP` | on | `python app.py` loads every model in a background thread at startup; `0` disables |
| `HF_HUB_OFFLINE` | set to `1` automatically when all models are cached | Loads models without checking huggingface.co (`model_warmup.use_local_models_only`); an explicit value is respected |
| `tech_interview.grader` constants | `NLI_MODEL=cross-encoder/nli-deberta-v3-base`, covered entail ≥ 0.60 (or ≥ 0.20 with sim ≥ 0.80), `KEYPOINT_WEIGHT=0.85`, follow-ups: `FU_COVERED_ENTAIL=0.50`, `FU_PARTIAL_SIM=0.60`, `FU_REPLY_MATCH_SIM=0.85` | Grading thresholds (calibration in §4.25 and `grader_eval/`) |
| `slide_rag.enrich_bank` constants | `PROMPT_VERSION=4`, `CORE_VERSION=5`, `VARIANT_MIN_SIM=0.35`, `VARIANT_MAX_CONTRADICTION=0.5`, `VARIANT_MAX_IMPLIED_BY_QUESTION=0.5` | Offline enrichment and its paraphrase filters |
| `HF_HUB_DISABLE_XET=1` | unset | Use when a Hugging Face model download hangs at 0 MB (happened for Qwen3-VL on this machine) |

Session cookies are HttpOnly with `SameSite=Lax`.

---

### 4.20 Accounts, login & profiles

**Files:** `account_routes.py` (blueprint `accounts_bp`, `init_accounts`), `account_schemas.py`, `resume_store.py`.

**Signup** (`POST /api/auth/signup`, multipart):
- **Fields:**
  - account: `email`, `password`;
  - profile: `full_name`, `date_of_birth`, `phone`;
  - Class 10: `class10_board`, `class10_score`, `class10_score_type` (`percentage` | `cgpa`), `class10_year`;
  - `higher_secondary_type` (`class12` | `diploma`) with `higher_secondary_board` (board, or institute for a diploma), `_score`, `_score_type`, `_year`;
  - current education: `college`, `degree`, `branch`, `cgpa`, `cgpa_scale` (4 | 10), `graduation_year`;
  - consents: `consent_data` (required), `consent_training` (optional);
  - the `resume` file.
- **Validation** (`SignupRequest` / `ProfileFields`, pydantic, `extra="forbid"`):
  - Email format is checked and the email is lowercased.
  - Password: 8–128 characters, with a letter and a digit (`password_problem`, shared with change-password).
  - Phone is normalised and must have 10–15 digits.
  - Age must be 13–100.
  - Scores must be within their scale (100 for a percentage, 10 for a CGPA), and the CGPA can't exceed its scale.
  - Years must be in order: DOB < 10th ≤ 12th/diploma ≤ graduation ≤ now + 8.
  - Errors come back as `[{field, message}]`, with `field: null` for cross-field errors.
- **Order of operations:**
  1. Validate the form.
  2. Reject a duplicate email (409).
  3. Save the resume to `resumes/_pending/` and **parse it with the resume engine** (an unreadable file gives 400 and nothing is kept).
  4. Create the `User` + `StudentProfile` and flush to get the id.
  5. Move the file into `resumes/<user_id>/` and create the `Resume` row (current).
  6. Commit and log the user in.

  Any failure rolls back and removes the file.

**Login:**
- `POST /api/auth/login {email, password, remember}`. A wrong password and an unknown email return the same 401 (an unknown email still runs a dummy hash check, so timing doesn't reveal it). A disabled account gives 403.
- Updates `last_login_at`.
- `remember` sets a 30-day cookie.

**Other endpoints:**

| Endpoint | Behaviour |
|---|---|
| `POST /api/auth/logout`, `GET /api/auth/me` | `me` returns `{user, profile, current_resume}` |
| `PATCH /api/profile` | Merges the changes into the stored profile and re-validates the whole thing with `ProfileFields` |
| `POST /api/auth/change-password` | `{current_password, new_password}` |
| `PATCH /api/auth/consent` | `{consent_training: bool}`; stamps `consented_at` / `consent_version` |
| `DELETE /api/auth/account` | `{password}`; deletes every row (cascade) and the user's resume folder |
| `GET / POST / DELETE /api/auth/avatar` | Profile photo: get (JPEG, 404 if none), set (multipart `avatar`), remove. Also optional at signup (`avatar` field). `avatar_store.py` decodes and re-encodes every upload to a 256×256 JPEG (rejects non-images, strips EXIF/GPS, applies phone rotation, flattens transparency); stored on `users.avatar` (migration `a7c3e91f2b40`). `user.avatar_url` is versioned (`?v=<time>`) so browsers cache it safely. The UI shows it in the top-right circle, on the Profile page and next to the candidate's chat messages; initials when there is none. |
| `GET /api/resumes`, `POST /api/resumes` | List; upload a new resume (parsed, becomes current) via `add_resume_for_user` |
| `GET /api/resumes/<id>`, `/file` | Details + parsed profile; the file itself (`?download=1` to download) |
| `POST /api/resumes/<id>/make-current`, `DELETE /api/resumes/<id>` | The only resume can't be deleted (409). Deleting the current one promotes the newest remaining |

**Email verification** is not implemented: `users.email_verified` exists and defaults to false, and nothing checks it yet.

**Resume storage** (`resume_store.py`):
- Files are saved under random names (`<uuid>.<ext>`), never the user's filename, and SHA-256 hashes are recorded.
- Only `.pdf`, `.docx` and `.txt` are accepted.
- `parse_resume` wraps `generate_candidate_profile_via_engine` and turns `ExtractionFailure` into a user-safe `ResumeUploadError`.

---

### 4.21 Database & session history

**Setup** (`database.py`): `configure_database(app)`
- sets `SQLALCHEMY_DATABASE_URI` and `UPLOAD_DIR`;
- loads or creates the secret key;
- turns on `PRAGMA foreign_keys=ON` (without it SQLite ignores `ON DELETE CASCADE`) and WAL mode;
- binds Flask-SQLAlchemy and Flask-Migrate (`render_as_batch=True` for SQLite ALTERs);
- runs `flask_migrate.upgrade()` at startup.

**Tables** (`models.py`, all datetimes stored in UTC and serialised with `iso_utc`):

| Table | Key fields | Relations |
|---|---|---|
| `users` | email (unique), password_hash (werkzeug scrypt), email_verified, role (`candidate`/`annotator`/`admin`), is_active, consent_data, consent_training, consent_version, consented_at, created_at, last_login_at | 1:1 profile, 1:N resumes, 1:N sessions (cascade delete) |
| `student_profiles` | full_name, date_of_birth, phone, class10_*, higher_secondary_*, college, degree, branch, cgpa, cgpa_scale, graduation_year, updated_at | `user_id` unique FK, ON DELETE CASCADE |
| `resumes` | file_path (relative to `UPLOAD_DIR`), original_filename, content_type, size_bytes, sha256, **parsed_profile (JSON)**, is_current, uploaded_at | FK user, CASCADE |
| `interview_sessions` | session_type (`resume_discussion` \| `technical`), status (`in_progress` \| `completed` \| `terminated` \| `abandoned`), started_at, ended_at, last_activity_at, overall_score, overall_grade, questions_answered, evaluator_name/version, integrity (JSON), attention_metrics (JSON), summary (JSON) | FK user CASCADE; FK resume **SET NULL** (deleting a resume keeps its sessions) |
| `session_turns` | turn_number (unique per session), question_text, category, family, reasoning_type, project_reference, source_id, is_followup, answer_text, answered_at, overall_score, grade, evaluation (JSON) | FK session CASCADE |

**Migrations:**
1. `ee1633ec7576`: the initial schema.
2. `eeeb3959ae84`: adds `interview_sessions.last_activity_at`.

To create a new one: `flask --app db_manage db migrate -m "..."`.

**Recording** (`session_history.py`). `conversation_engine` stays unaware of the database; the app's routes call these around it:
- **Resume Discussion:**
  - `begin_resume_discussion(conversation_id, user_id, resume_id, first_question)` creates the row and a live link (`_LiveConversation`: db id, owner, question on screen).
  - `record_resume_discussion_turn` saves the question just answered, the answer and the full evaluation payload.
  - `finish_resume_discussion` stores the integrity, the sanitised attention metrics and the end summary (minus `evaluations`, which live in the turns), and sets `completed` or `terminated`.
- **Technical:** `begin_technical_session`, `record_technical_turn` (question, main answer, fill-in answer, marks, feedback, difficulty, topic), and `finish_technical_session(session, attention, integrity)`.
- **Finishing a session:**
  - `overall_score` = mean of the turn scores;
  - `overall_grade` uses the report's bands (0.80 / 0.60 / 0.40 / 0.25);
  - attention metrics are whitelisted to their numeric fields.
- **Abandonment:**
  - `abandon_in_progress_sessions(user_id)`: one interview at a time; runs whenever a new one starts.
  - `abandon_stale_sessions` (idle > 2 h): runs on the list and insights calls.
  - `abandon_all_open_sessions`: runs at startup.

  Abandoned sessions keep their answered turns, and their live engine state is freed.
- **Ownership:** `owns_conversation` guards reply/end; `_profile_owners` guards `/start`. Another user's ids answer 404.

**History API** (`session_routes.py`):

| Endpoint | Behaviour |
|---|---|
| `GET /api/sessions[?type=]` | Newest first; `to_dict()` includes the resume filename, integrity and attention |
| `GET /api/sessions/<id>` | Everything plus `summary` and every turn |
| `DELETE /api/sessions/<id>` | Also closes the session if it's live |
| `POST /api/technical-sessions`, `POST /api/technical-sessions/<id>/end` | Start / finish a technical session (`{attention_metrics, integrity}`) |
| `GET /api/insights` | §4.22 |

**Current limitation:** the two rounds of a full interview are stored as **two separate sessions**. They aren't linked yet, so Sessions lists them separately.

---

### 4.22 Home insights & "Focus next"

`insights.build_insights(user_id)` works from **finished** sessions only (completed or terminated):
- `stats`: sessions finished, average score, best score, average attention;
- `last_session`;
- `trend`: the last 10 scored sessions, oldest first;
- `focus`: at most 3 items, each `{key, label, reason}`, chosen in this order:
  1. **Recurring reasoning gaps** from the last 5 Resume Discussions' `missing_reasoning`. A gap must appear in at least 2 answers. They're ranked by frequency, then total severity, e.g. "Trade-off reasoning — Missing in 4 of your last 9 answers".
  2. **Weak scoring dimensions** (average < 0.55), e.g. "Complete answers — Averaging 35%…".
  3. **Weak Technical topics** (average < 0.55 over the last 5 technical sessions), e.g. "DNS (technical)".

---

### 4.23 App shell & the full interview flow

**Auth screen** (`#auth-container`, shown first):
- `authBootstrap()` calls `/api/auth/me`, then `enterApp(account)` if logged in, otherwise `showAuthScreen()`.
- The login form and the 3-step signup (Account → Academics → Resume) reuse the landing page's layout, step indicator and input styles.
- Signup has a Class 12 / Diploma switch (`setHigherSecondaryType`, shared with Profile) and a resume drop zone.
- Server field errors are mapped onto their fields, and the form jumps back to that step.

**Shell:**
- `#app-nav` (Home · Sessions · Profile) and `#profile-menu` (initials avatar + email; dropdown with Log out) appear together when logged in and not mid-interview (`renderProfileMenu`, `body.has-app-nav`).
- `showAppScreen(name)` switches pages.

**Pages:**
- **Home:**
  - a typed greeting;
  - two start cards: **Full Interview** (`openResumeDiscussionSetup` → the resume screen, with the saved resume preselected) and **Technical Interview** (`openTechnicalSetup` → the rules dialog; no topic picker);
  - 4 stats, a progress sparkline (inline SVG), "Focus next", and the 5 most recent sessions.
- **Sessions:**
  - filter chips and deletable rows;
  - `openSession` rebuilds a Resume Discussion's **exact report** from the saved turns (`openHistoricalReport` → `rdBuildReportFromV2` → `rdRenderReport(..., {historical})`);
  - technical sessions open a per-question detail view (`showTechnicalDetail`).
- **Profile:**
  - editable personal details (`PATCH /api/profile`);
  - resumes (view, use, delete, upload);
  - account settings: change password, training-consent toggle, delete account (password confirmation in the overlay).

**Full interview flow** (the INTERVIEW FLOW section; `interviewFlow = {mode, phase, round1, …}`):

```
Rules (showInterviewRules "full") → full screen → phase "resume"
  Round 1 · Resume Discussion (proctor armed after first question)
  rdTriggerReport: /end saved, stays full screen, webcam on → phase "between"
  #round-transition: "Round 1 complete." score · grade · verdict → [Begin Round 2]
  beginRound2: attention counters reset → startTechnicalRound("All") → phase "technical"
  Round 2 · Technical: /api/technical-sessions + 5 × (next_question, evaluate{session_id})
  finishTechnicalRound: disarm + exit full screen, end session, stop webcam → phase "ended"
  showFinalResults: rdRenderReport(round1, {combined: {round2, integrity, attention}})
     = Round 1 report + "Round 2 · Technical" section + "Attention · Whole interview"
```

- **Technical Interview (standalone):** `mode "technical"`, 10 questions picked across all subjects, same rules. Results appear on `#dashboard-container` via `triggerDashboard(round2)`, with a termination banner if needed.
- **A violation in any phase** ends everything via `interviewTerminate()`. The final results name the round and question.
- The loop functions (`loadQuestion`, `handleSubmission`) check `interviewFlow.phase` after every await, so a late timer can't continue an ended round.

### 4.24 Slide RAG pipeline

**Location:** `rag_system/rag_tester/slide_rag/` (run commands from `rag_system/rag_tester`). **Status:** built and evaluated for all five subjects; **not yet called by the Flask app**.

**Why it replaced the old ingestion.** The old ingestor made one chunk per PDF page. Faculty slides break that: a running header and logo on every slide, diagram labels scattered through the text, build-up slides repeated with one more bullet, ideas spread over several "(contd.)" slides, and screenshots with no text layer. The new pipeline treats a slide as a laid-out object and a **section** (a run of related slides) as the unit of retrieval.

**Sources (`sources/<subject>/*.pdf`, one slide per page):**

| Subject | Slides | Content slides | Sections | Notes |
|---|---|---|---|---|
| CN | 774 | 625 | 477 | Kurose & Ross-style; all 4 units present but some decks carry the wrong unit label; some slides repeated across decks |
| DBMS | 1,462 | 1,213 | ~690 | Two page sizes; no B+ tree / recovery / timestamp coverage |
| DSA | 1,607 | 1,258 | ~557 | Includes a Design & Analysis of Algorithms deck; ~190 full-slide screenshots (see limitations) |
| OOAD | 1,038 | 780 | ~507 | Java + UML + GRASP + design patterns |
| OS | 943 | 805 | 587 | Cleanest subject (only 206 slides need vision); credits OSTEP |

**Stages and modules**

| Stage | Module | What it does |
|---|---|---|
| 1 Extract | `extract.py` | PyMuPDF text with font size/position per line. **Running header/footer:** text repeated in the top/bottom band across ≥3% of pages spread over ≥25% of the document, plus spelling variants (token-set Jaccard ≥ 0.75) and deck-specific headers (≥25 pages with a varying title underneath; kept as the section's *topic*). **Logos:** small images repeated at the same position (full-slide screenshots are never treated as decoration). **Title:** largest font near the top. **Diagram labels:** short text inside an image or a cluster of ≥3 vector drawings, kept aside. **Tables:** `page.find_tables()` only when grid lines exist. **Code:** monospace fonts or code-like syntax, indentation rebuilt from x positions. **Bullets:** wrapped lines rejoined, glyphs normalised, nesting kept. **URLs, dates, slide numbers** removed. **Personal notes** added on top of the slides as PDF annotations (typed note boxes and ink; DBMS 164 + 1,850, DSA 127 + 1,368) are stripped: text inside note boxes is dropped (recorded in `removed_notes`) and slide images are rendered without annotations for OCR and vision. **OCR** (RapidOCR) for picture-only slides. Image positions are read from the text layer's image blocks (`get_image_info(xrefs=True)` hashed every image and took ~95% of run time). |
| 2 Classify | `classify.py` | Types: `deck_title`, `contents` (incl. "Unit – 4 …" roadmap slides), `admin`, `quiz`, `divider`, `image_only`, `image_heavy`, `problem`, `code`, `table`, `concept_diagram`, `concept`. Drops admin/contents/title slides, collapses **incremental builds** (same title, ≥90% token containment) and exact duplicates within a deck. **In-slide quiz MCQs** (and "MCQ Solution" slides) are removed from retrieval and saved to `quiz.json` (94 in total) as style examples for question generation. Flags `needs_vision` reasons: diagram, table, formula, image_heavy, image_only, ocr_text. |
| 3 Vision | `vision.py` | **Run on CN's picture/table slides only** (see limitations). Renders flagged slides (longest side 1280 px) and asks local **Qwen3-VL-2B-Instruct** (bf16, GPU) only for what the extracted text misses: diagram description, table as Markdown, equations with `^`/`_`, transcription of picture-only slides; decorative pictures answer `NONE`. Results cached per slide in `.vision_cache/<subject>/` keyed by PDF hash, page, model and `PROMPT_VERSION` (resumable). `build.py` merges them as `vision_text` (shown as `[Figure] …`); a picture-only slide's transcription also supplies its title. |
| 4 Sections | `sections.py` | Consecutive slides join a section when titles match after removing continuation markers (`(contd.)`, `(more)`, `- 2`, `Part II`; a separator is required so `IPv4` survives), when an untitled slide is similar to the previous one (MiniLM cosine ≥ 0.35), when titles share a non-generic stem and content is related (≥ 0.6), or when a solution slide follows its worked problem. Max 450 words per section (longer runs split into parts). Dividers set the topic breadcrumb. Problems without an explicit solution marker are flagged `unsolved`. |
| 6 Index | `index.py`, `text_utils.py` | **Children** (searched): each slide, plus each section's opening 1,200 characters, embedded with a breadcrumb header (`DBMS › deck › topic › section: …`). **Parents** (returned): sections. FAISS `IndexFlatIP` (MiniLM, normalised) + BM25 with **one tokenizer for corpus and query** (the old code tokenised them differently). |
| Retrieve | `retrieve.py` | Dense and BM25 scores min-max normalised over a 50-candidate pool, mixed with α = 0.6, rolled up to sections (best child wins), top 20 re-ranked with `ms-marco-MiniLM-L-6-v2`. Each result has `pages`, `page_start/end`, `best_page`, `title`, `text`. `get_context_with_pages()` keeps the old function's shape for callers. |
| 8 Report | `report.py` | `report.md` / `report.json` per subject: slide types, dropped slides by reason, vision queue by reason, section-size stats, worked problems, removed running text, decks, random sample sections. |
| Build | `build.py` | Orchestrates everything; Stage 1 output cached in `.slide_cache/` per PDF hash + `EXTRACTOR_VERSION` (currently 5); flags `--no-headers`, `--no-section-children`, `--no-vision`, `--model`, `--out` for ablations. |
| Topics → slides | `topics.py` | Reads `topics/<subject>.txt`, searches each topic (name + hints), keeps up to 4 sections the cross-encoder scores relevant (within 2.5 logits of the best, scored against the name plus 3 hints), with a lexical fallback for topics it under-scores. Writes `topic_map.json` and `topic_coverage.md` (good / thin / missing). All 279 topics currently map to slides. |
| Question bank | `qbank.py`, `llm_client.py`, `rank_bank.py` | See §4.25. |

**Output per subject (`knowledge_base_v2/<subject>/`):** `slides.json`, `sections.json`, `children.json`, `quiz.json`, `index.faiss`, `bm25.pkl`, `manifest.json`, `report.md`, `report.json`.

**Topic lists (`topics/<subject>.txt`).** One topic per line, `Name | hints | priority` (priority optional: `low` = rarely asked in interviews → one question), `#` lines as optional unit headers. Each topic was checked against the slides (retrieval + text search); topics the slides don't teach were removed, and topics the slides teach heavily were added. Current counts: CN 56, DBMS 60, DSA 54, OOAD 53, OS 56 (279; the user also edits these files directly). Only "Generating permutations and subsets" is marked low so far.

**Evaluation (`retrieval_eval.py`, `eval/gold_<subject>.json`).**
- *Gold sets:* 22–27 interview-style questions per subject (122 in total), each labelled with the slide pages that answer it, chosen from slide titles before any retrieval was run.
- *Probe sets:* 150 per subject, generated automatically (a random slide's bullet as the query, that slide as the answer).
- *Metrics:* section hit@k (a returned section contains an expected page), slide hit@k (the best-matching slide is an expected page), MRR. The old index is credited for its chunk's page and the next page, because its merged chunks hold two pages.

| Subject | Gold hit@1 | Gold hit@5 | Old index hit@1 / hit@5 | Probe hit@5 |
|---|---|---|---|---|
| DBMS | 0.77 | **1.00** | 0.59 / 0.82 | 0.99 |
| DSA | 0.82 | **1.00** | 0.55 / 0.68 | 0.97 |
| OOAD | 0.73 | **1.00** | 0.68 / 0.82 | 0.99 |
| CN | 0.74 | **0.96** | n/a (old index built from a different PDF) | 0.99 |
| OS | 0.85 | **1.00** | n/a (old index built from the 4-per-page handout) | 0.97 |

Ablations: breadcrumb headers — no measurable change; `BAAI/bge-small-en-v1.5` instead of MiniLM — no gain; no reranker — top-5 drops (e.g. DBMS 1.00 → 0.95) but OOAD top-1 rises (0.73 → 0.82). The gain over the old index comes from extraction, cleaning and section grouping. CN's remaining miss is a diagram-only slide (TCP segment header), which Stage 3 targets.

### 4.25 Question bank and session types

**Why:** the technical interview needs 8–10 good questions per session, spread across subjects, never repeating, each with a correct answer to grade against and follow-ups ready. They are generated **once, offline, from the course slides**, checked, and saved; the interview only *selects* from the bank, so it is fast, needs no GPU or model at runtime, and stays grounded in what the course teaches.

**Generation (`slide_rag/qbank.py`, `python -m slide_rag.qbank`).** For each topic, local **Qwen3-8B** (Ollama, `llm_client.py`) reads the topic's slide sections and writes one question per difficulty slot. Each question stores:
- `reference_answer` (3–5 sentences);
- `key_points` (2–5), **each** with the slide `quote` that supports it, a `followup` question to ask if the candidate leaves the point out, and the `followup_answer` expected for it.

Misconceptions were tried and dropped: in the pilots they were often true statements or paired with unrelated quotes.

**Checks before a question enters the bank:**
- *In code:*
  - each quote must appear in the slides' **own** text (rapidfuzz `partial_ratio` ≥ 88; a quote joining several bullets must match part by part; ≥ 4 words; vision text never counts), and relate to its point (MiniLM cosine ≥ 0.35);
  - a question keeps ≥ 2 verified points;
  - trivia patterns (a specific return value, "the algorithm returns 0", named textbook rules) are rejected anywhere a candidate would be graded;
  - no mention of "the slides/lecture".
- *One judge call per question in Qwen3 thinking mode:* on topic? tests understanding rather than trivia? which quotes don't actually support their point (dropped)? is the reference answer correct (else rejected)?
- *Distinctness:* the second question of a topic is written knowing the first ("cover a different aspect") and must differ from it (cosine < 0.85); no duplicates across the bank (< 0.90).

A failed slot is retried once, then logged and skipped.

**Difficulty:** defined in the prompt (easy = explain one concept; medium = how/why, connecting 2–3 ideas; hard = why / what-if / trade-off reasoning, never trivia, never invented examples). Each topic gets one easy-or-medium and one medium-or-hard slot in a 4-topic cycle → 25% easy, 50% medium, 25% hard per subject. Hard questions are flagged `review: needs_review`.

**Robustness:**
- `num_ctx` is set to 8,192 and prompts are token-counted first, because Ollama silently truncates over-long prompts.
- Output is constrained by a JSON schema; seed and temperature are fixed.
- Every slot is cached in `.qbank_cache/` keyed by topic, context hash, slot, runtime (model + quantization) and `PROMPT_VERSION` (6), so runs resume after interruption.
- One pass took ~4 h of GPU time at ~45 tokens/s. It was run from a normal terminal, because Claude Code stops its own background jobs when free RAM runs low (the job needs ~4.5 GB).

**Result (422 questions):**

| Subject | Questions | Topics covered | Easy / medium / hard |
|---|---|---|---|
| CN | 60 | 36 / 56 | 16 / 32 / 12 |
| DBMS | 101 | 58 / 60 | 27 / 50 / 24 |
| DSA | 80 | 51 / 54 | 22 / 40 / 18 |
| OOAD | 87 | 49 / 53 | 21 / 46 / 20 |
| OS | 94 | 56 / 56 | 23 / 49 / 22 |

1,055 of 1,057 key points have a prepared follow-up.

**Ranking (`slide_rag/rank_bank.py`).** Each question gets a `confidence` (0–1): a weighted mean of six signals (key points kept vs proposed, judge-flagged points, quote match strength, number of verified points, first-try acceptance, topic coverage), multiplied by a difficulty factor (easy 1.0, medium 0.95, hard 0.85). Each file is sorted best-first. Questions below the threshold (0.75) get `"active": false`: the app will only use active ones, and the rest stay in the file for review.

| | CN | DBMS | DSA | OOAD | OS | Total |
|---|---|---|---|---|---|---|
| Active | 39 | 61 | 50 | 64 | 68 | **282** (86 easy / 164 medium / 32 hard) |

Change the cut-off with `python -m slide_rag.rank_bank --threshold 0.78` (0.70 keeps 358, 0.78 keeps 260). Review files: `question_bank/<subject>_report.md` (active first, then "Held back").

**Quality funnel.** Each stage keeps every question in the bank and only changes what interviews draw from:

| Stage | Questions | What it guarantees |
|---|---|---|
| Generated from the slides | **422** | 1,057 key points, each with a verified slide quote; 1,055 with a prepared follow-up |
| Passed automated ranking (`active`) | 282 | Confidence ≥ 0.75 across six signals |
| Hand-curated top tier (`curated`) | 132 | Scored 8+/10 (7+ on a most-asked topic) by human review; served by default |

Interviews serve the curated tier by default (`CAP_CURATED_ONLY=1`); `CAP_CURATED_ONLY=0` serves all 282 active questions.

**Session types (Technical Interview and Full Interview built; the MCQ test planned):**

| Home-page session | Content | Rules |
|---|---|---|
| **Full Interview** (resume parsing + technical interview) | Round 1 Resume Discussion (unchanged) → Round 2 **technical interview**: 8–10 concept questions (no MCQs, no fill-in-the-blank) with follow-ups | Proctored end to end; saved to history |
| **Technical Interview** (only technical) | The same technical interview on its own: **8–10 main concept questions**, all different, spread across subjects; at most 1–2 follow-ups each when needed | Proctored; saved to history |
| **Technical MCQ Test** (later) | **30 MCQs in 30 minutes**, random across subjects and topics | Scoring **+1 correct, −0.25 wrong, 0 unanswered**; plan in `mcq_tobedone.md` |

- **Follow-ups:** after each answer the system decides whether a follow-up is needed. A good answer moves on. Otherwise it asks for clarification (hesitation, fillers, broken sentences, a vague answer) or asks the prepared follow-up for a missing key point, **at most 1–2 per main question**.
- **Phase 2 (backend) — done:** `main_cap/cap/tech_interview/`:
  - `bank.py` loads the active questions and, by default, serves only the curated ones (below); the selector favours topics asked often in interviews; `selector.py` picks 10 (standalone) or 8 (Round 2) from different topics across all five subjects, easy → medium → hard, never repeating a question the user has seen, weighted toward the user's weak topics;
  - `grader.py` marks each key point covered / partial / missing with the NLI cross-encoder `cross-encoder/nli-deberta-v3-base` (entailment) plus a MiniLM-similarity rescue; score = 0.85 × key points + 0.15 × similarity to the reference answer (counted fully once half the points are met). Tuned on 100 hand-checked answers (key-point agreement 85% vs 72% for the earlier MiniLM NLI), then tested on 400 answers to 100 unseen questions (`grader_eval/`): 81% key-point agreement, score correlation 0.84, the same move-on decision as the human 89% of the time; 3% of weak answers pass, 9% of strong ones are held back; fillers stripped before grading but counted as hesitation;
  - `followup.py` decides next / clarify / prepared follow-up (≤ 2 per question, good ≥ 0.70); `session.py` runs the live interview; points recovered through a follow-up earn 0.75 credit;
  - routes `POST /api/tech-interview/start | /<id>/answer | /<id>/end` in `session_routes.py`; each main question is saved as one `SessionTurn` (topic in `category`, question id in `source_id`, follow-ups in `evaluation`). No new table or migration: "already seen" questions and per-topic averages are read from these turns;
  - `test_tech_interview.py`: 24 tests (incl. curated-only serving and interview-priority weighting).
- **Grader on real answers (2026-09-30):** the LLM-written test sets flattered the grader; on 40 answers typed by the user (`grader_eval/my_answers.json`) main answers were graded too strictly and follow-ups were judged right only 15/40 times. Follow-up judging was rewritten: "I don't know" → missing, a yes/no rule ("nope"), and the reply read with its question counting only what it *adds* beyond the question. Now 30/40, with 8% of wrong replies accepted (tested by giving each follow-up the replies to other questions).
- **Curated subset (2026-09-30):** every active question was read and scored 1–10 by hand (clear, answerable, key points correct and matching the question, sensible difficulty); the score and a one-line note are stored on each question (`quality_score`, `quality_note`). Each topic also has an **interview-frequency tier** (`interview_priority`: 3 asked very often, 2 regularly, 1 rarely; hand-assigned in `slide_rag/interview_priority.py`, re-applied with `python -m slide_rag.interview_priority`). The 132 scoring 8+, or 7+ on a tier-3 topic, are `"curated": true`, listed first in each bank file (most-asked first, then by score), and are the only ones new interviews use (`CAP_CURATED_ONLY`, default on): CN 18, DBMS 29, DSA 20, OOAD 36, OS 29. The selector multiplies each candidate's weight by x6 / x1 / x0.2 by tier, so 87% of questions asked come from tier-3 topics (47% without it) while no single topic appears in more than ~34% of sessions and a user taking 5 interviews in a row sees no repeated question; every 8-question interview still gets 8 distinct topics (checked on 3,000 simulated sessions). DSA has no curated hard question, so its hard slot falls back to a curated easy/medium one. 41 tier-3 topics still have no curated question (e.g. OSI model, DNS, paging, round robin, quick sort, hashing, SQL views) — listed in the review file for generation. Low scores flag false key points (e.g. "TCP guarantees minimum throughput", "the last level of a complete binary tree is always odd"), references to text the candidate never sees ("the code provided", "the example provided") and vague questions. Full list: `question_bank/quality_review.md`; bank backup: `archive/question_bank_backup_2026-09-30/`. Lookups by id (`question_by_id`) and the grader-eval scripts still see every active question.
- **Offline enrichment (`slide_rag/enrich_bank.py`, Qwen3-8B once, 79 min):** writes informal variants of each key point, short correct follow-up replies and each question's main idea into the bank; contradicting and generic paraphrases are filtered out. Measured by part: the follow-up replies (near-exact match only) raise follow-ups to 35/40 with wrong replies still at 9% → **on by default**; the key-point variants and main idea let fluent wrong answers through (confidently wrong 0.21 → 0.53, same move-on decision as a human 357 → 294 / 400) → **off** (`CAP_GRADER_ENRICHMENT`).
- **Phase 3 (frontend) — done:** in `templates/index.html`, both Home cards run the question-bank interview. The Technical Interview card (10 questions) goes straight to the rules, with no subject picker. The Full Interview's Round 2 asks 8. Follow-ups and clarification requests appear as their own chat turns, with no live scores. The standalone results page and Round 2 of the combined report show score, grade, per-subject bars, "worth revising" topics and per-question cards (answer, key points ✓/~/✗, follow-ups, model answer); history uses the same cards. The fill-in-the-blank quiz is gone from the UI; its routes (`/api/next_question`, `/api/evaluate`, `/api/technical-sessions`) remain in the backend, unused. Test: `node test_tech_interview_ui.js`.

---

## 5. Entry Points & Execution Flow

### 5.1 Running the application
```bash
pip install -r Requirements_Global.txt          # the project's requirements file; system needs: SETUP_PREREQUISITES.md
cd main_cap/cap
python app.py                                   # http://localhost:5000
```
Startup logs show which evaluator is active: `hybrid-v1` if the weights are present, otherwise `heuristic-v1` (a missing weights file is detected up front, and no model is downloaded). The database and its migrations are created and applied automatically; there are no manual DB steps.

**Startup speed (`model_warmup.py`).** When every model is already downloaded, the app loads them without asking huggingface.co for updates (`HF_HUB_OFFLINE=1`; on a fresh machine they download on first use as before). `python app.py` then loads all models in a background thread (~7 s), so no user action waits for one. Measured: server start ~6.8 s → 2.1 s; the first technical answer 16.2 s → 0.2 s. The legacy `rag_integration` module is imported only if the old `/api/next_question` route is used (it cost ~4.6 s of every start). `CAP_MODEL_WARMUP=0` turns the warm-up off. The frontend's typing effect and pauses are deliberate pacing and were left unchanged.

### 5.2 Main execution path (the shipped UI)
1. **Sign up or log in:** `authBootstrap` → the auth screen. Signup parses and stores the resume. Then `enterApp` → **Home**.
2. **Full Interview:**
   1. Home card → resume screen (saved resume preselected).
   2. **Continue with this resume** → `POST /api/resumes/<id>/use`, or upload a different one → `POST /api/classify-resume` (saved as current).
   3. → Briefing.
3. **Rules + start:** CTA → `showInterviewRules("full")` → full screen → `POST /api/resume-discussion-v2/start` → `start_conversation` → `begin_resume_discussion` (DB) → first question. The rules are armed.
4. **Round 1 turns (≤ 10):** `POST .../reply` → `build_request` → `HybridEvaluator` or `HeuristicEvaluator` → ledger → `planner.advance` → turn saved → next question.
5. **Round 1 end:** `POST .../end {integrity, attention_metrics}` → session saved → Round 1 summary, still in full screen.
6. **Round 2:** `POST /api/tech-interview/start {mode: "round2"}` → 8 main questions, each answered with `POST /api/tech-interview/<id>/answer` (which may return a follow-up or a clarification request, ≤ 2 per question, and saves the turn) → `POST /api/tech-interview/<id>/end` → final combined results. Full screen is released only now.
7. **Afterwards:** Home shows the updated stats and "Focus next"; Sessions lists both rounds.
8. **Technical Interview:** Home card → rules → full screen → 10 question-bank questions (with follow-ups) → results page.

### 5.3 CLI entry points
| Command (run from) | Purpose |
|---|---|
| `python app.py` (`main_cap/cap`) | Web app |
| `flask --app db_manage db migrate -m "..."` / `db upgrade` (`main_cap/cap`) | Create / apply schema migrations after editing `models.py` (the app also applies them on startup) |
| `python -m resume_engine.devtools.shadow_mode_batch --dir D --report R` (`main_cap/cap`) | Gemini vs engine comparison |
| `python -m resume_engine.devtools.golden_corpus_report` (`main_cap/cap`) | Parser health report |
| `python run_experiment_1.py generate\|train`, `run_experiment_2*.py`, `run_dataset_relabel.py relabel`, `run_experiment_4_*.py …` (`main_cap/cap`) | ML research track |
| `python regenerate_promotion_decision.py` (`main_cap/cap`) | Rebuild the promotion decision |
| `python _verify_traceability.py <resume>` (`main_cap/cap`) | Manual traceability check (needs Gemini or a cache) |
| `python main.py` (`rag_system/rag_tester`) / `python dynamic_ingestor.py` | Legacy RAG CLI / old knowledge-base ingestion |
| `python -m slide_rag.build [--subject cn]` (`rag_system/rag_tester`) | Build `knowledge_base_v2` (all subjects in `sources/`, or one) |
| `python -m slide_rag.vision --subject cn [--pages 400,463] [--limit N]` (`rag_system/rag_tester`) | Stage 3: read flagged slides with the vision model (GPU); rebuild afterwards to merge |
| `python -m slide_rag.retrieval_eval [--subject os] [--show-misses] [--no-baseline]` (`rag_system/rag_tester`) | Retrieval evaluation: gold + probe sets, vs the old index |
| `python -m pytest slide_rag/tests -q` (`rag_system/rag_tester`) | Slide pipeline unit tests |
| `python -m slide_rag.topics [--subject os]` (`rag_system/rag_tester`) | Map topic lists to slide sections (`topic_map.json`, `topic_coverage.md`) |
| `python -m slide_rag.qbank [--subject os] [--pilot] [--limit N]` (`rag_system/rag_tester`) | Generate the question bank with Ollama (resumable; needs Ollama running with `qwen3:8b`). Run from a normal terminal for long runs |
| `python -m slide_rag.rank_bank [--threshold 0.75]` (`rag_system/rag_tester`) | Score, sort and activate/hold back questions |
| `python -m slide_rag.enrich_bank [--subject cn] [--ids …] [--no-generate] [--strict-variants]` (`rag_system/rag_tester`) | Offline bank enrichment with Ollama (resumable, ~15 s/question); `--no-generate` re-applies cached results and filters |
| `python grader_eval/run_grader_eval.py [output_questions.json \| tuning_set/answers.json]` (project root) | Technical grader vs hand-checked key-point labels |
| `python grader_eval/run_my_answers.py [test]` (project root) | Technical grader vs the user's own answers and scores (tune/test halves) |
| `ollama stop qwen3:8b` (full path: `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`) | Unload the model from the GPU after a run |
| `python evaluate_parser.py`, `python generate_metadata.py` (`parser_tests`) | Legacy parser benchmark |
| `python -m pytest …`, `node test_*.js` (`main_cap/cap`) | Tests |

---

## 6. Error Handling & Edge Cases

**HTTP layer (`app.py`)**
- Every route is wrapped in try/except and returns `{"error": str(e)}` with 500.
- `ExtractionFailure` maps to 400 (bad input, not a server fault).
- Unknown or expired conversations return 404. Replying after completion returns `{"status":"completed"}` 200.
- Temp upload files are always removed in `finally`.

**Resume engine**
- **Typed failures:** `ExtractionFailure` covers missing, corrupt, password-protected and scanned files (< 50 characters extracted).
- **Parsers:**
  - A missing section yields an empty `ParserResult` plus `empty_section` observations.
  - `parse_date_range` never raises.
- **Degraded modes:**
  - ML model load failure: cached as `False`, falls back to "unknown" section labels or empty concepts.
  - Ambiguous layout: read top to bottom.
  - No header-like line in a section: the whole section becomes one entry.
- **Never fabricates:** no evidence means no seeds and an empty summary.
- **Edge cases handled:**
  - ALL-CAPS headers (the lowercase processor fix);
  - inline right-aligned dates (pitch continuity);
  - short sidebars (balance floor);
  - icon-only LinkedIn links;
  - names split across lines;
  - partially bold bullets (bold-character ratio);
  - font outliers (per-section median).

**Planning and session**
- **Profile edge cases:**
  - An empty profile builds zero specs → 400.
  - Untraceable technical topics are rejected, never asked.
- **Invalid calls:**
  - Illegal lifecycle transitions raise `InvalidLifecycleTransitionError` and leave state unchanged.
  - Unknown spec ids raise `KeyError`.
- **Evaluator pinning** prevents a mid-session model swap.
- **Failed evaluation:** if evaluation raises, nothing has been mutated yet, so the turn can be retried.

**Evaluation**
- **Hybrid:** catches all trained-model exceptions per turn and falls back to the heuristic. Heuristic exceptions propagate (treated as real bugs).
- **Startup:** `bootstrap_production_evaluator` never raises.
- **Diagnostics:** write failures are swallowed.
- **Validators:** they reject malformed results at construction (scores in [0,1], non-blank reasoning, evidence rules).

**Gemini (dev paths)**
- Up to 3 retries with exponential backoff on rate-limit, timeout or 5xx errors (auth errors are not retried).
- Empty-parse retry.
- `_check_truncation`, and a 3-stage JSON parse fallback.

**Data pipeline**
- **Reject, never repair:**
  - Generation: up to 3 attempts, each with a freshly salted recipe.
  - Deterministic rewrites: exactly 1 attempt.
- **Batch runs:** errors are recorded per unit and never abort the batch.
- **Scripts abort with a "BLOCKER" message** on:
  - split overlap;
  - empty pools or empty splits;
  - dataset-version mismatch.

**Accounts and persistence**
- **Signup:**
  - Validation errors come back per field.
  - A duplicate email gives 409.
  - An unreadable resume gives 400, and no account or file is left behind (rollback plus file cleanup).
- **Login:** the same 401 for a wrong password and an unknown email (with a dummy hash check); 403 for a disabled account.
- **Ownership:** every data route filters by `current_user`. Another user's resume, session or conversation answers 404, never 403.
- **Uploads:** over 10 MB gives a JSON 413; `.doc` and other formats are rejected.
- **Database:**
  - `PRAGMA foreign_keys=ON` makes cascade deletes real, which is tested by deleting through raw SQL.
  - Migrations run at startup.
  - Interrupted sessions are marked `abandoned` at startup, when a new interview starts, or after 2 h idle, and they keep their answered turns.
- **Integrity payload:** `sanitize_integrity` whitelists the client record. `terminated` must be literally `true`, and unknown violation types become `unknown`.

**Frontend**
- **Re-entrancy guards:**
  - `rdSessionStarting`: no double session;
  - `rdEnding`: no double `/end`;
  - `beginRound2`: the button disables itself;
  - `typeLine` cancellation tokens.
- **Stale timers:** `interviewFlow.phase` is checked after every await in the technical loop.
- **Camera:** a "Camera blocked" panel when permission is denied.
- **Proctoring:**
  - A permission-prompt grace period (camera and both mics), so prompts don't count as violations.
  - A violation *while Round 1 is being saved* is handled through a promise (`round1Ready`), so the final results still include Round 1.
  - `rdShowStageError` disarms proctoring and exits full screen (a broken session is not a violation).
- **Session expiry:** any 401 while logged in returns to the login screen.
- **Report:** null (never 0) for unscored dimensions, and `nonEmptyStrings` filtering.

---

## 7. Known Limitations / Tech Debt / TODOs

The code has no literal `TODO` markers. The items below come from docstrings, comments, and inspection.

**Architecture and runtime**
1. **Live interview state is still in memory:**
   - `_candidate_profiles` / `_profile_owners`, `conversation_engine._conversations` and `session_history._live`;
   - the RAG pool.

   Answered turns are safe in SQLite, but live state is per-process, and `_candidate_profiles` entries are never evicted. The app can't run with multiple workers as-is.
2. **Flask development server only.** There is no production WSGI server, container or CI.
3. **No login rate limiting, and no email verification yet.** `email_verified` exists but nothing checks it.
4. **Model weights are absent:** `deployed_model/best_checkpoint_weights.pt` and the resume-classifier `bert_resume_model/`. A clone runs on the heuristic evaluator. (Startup now detects the missing weights and skips the DeBERTa download.)
5. **Client-side enforcement.** The session-integrity rules and the attention monitoring can be bypassed with DevTools, and the backend trusts the sanitised integrity record.
6. **The two rounds of a full interview aren't linked in the database.** Sessions lists them as two entries, and the combined results exist only live at the end of the interview.
7. **Question bank coverage (resolved: the old 5 hardcoded networking questions are gone).** The slide pipeline (§4.24) and the 422-question bank (§4.25) now drive both the standalone Technical Interview and Round 2. Remaining work: 41 most-asked topics (e.g. OSI model, DNS, paging, round robin, quick sort, hashing, SQL views) have no curated question yet and are listed in `question_bank/quality_review.md` for generation; the 30-question MCQ test (`mcq_tobedone.md`) is not built.

**Evaluation and ML**

8. **The QWK numbers are measured on synthetic, templated data.** Every training dataset came from `FakeGenerationClient` templates ("I used {concept} — {detail}."). The code notes that the trained concept head does not generalise to real paraphrases, and there is a documented train/serve domain gap.
9. **Grade cut-points are inconsistent:**

   | Location | Cut-points |
   |---|---|
   | Evaluators | 0.90 / 0.75 / 0.55 / 0.30 |
   | `model_dataset.score_to_tier` | 0.80 / 0.60 / 0.40 / 0.25 (its docstring wrongly claims these match the evaluators) |
   | Frontend `rdOverallGrade`, `session_history.session_grade` | 0.80 / 0.60 / 0.40 / 0.25 |

10. **Training vs inference differences:** the training mask ignores the category exclusion; `max_length` defaults to 256 but 128 is deployed.
11. **`TrainedEvaluator` leaves fields empty:** `resume_grounding_score`, `recommended_action` and `raw_model_output`. The hybrid inherits `recommended_action` from the heuristic's overall score, not the final score.
12. **`expected_concepts_registry` has only 4 entries**, so `concept_coverage` is empty for most turns. The UI removed the Concept Coverage row anyway.
13. **`hybrid_diagnostics.jsonl` grows without bound** in the source directory. The evaluator registry is not thread-safe and silently overwrites entries with the same name.
14. **`regenerate_promotion_decision.py` is hard-wired to Experiment 2's dataset**, so it would hit a BLOCKER on the deployed Experiment 4 checkpoint.
15. **Data coverage gaps:** only 6 of 10 reasoning types appear in the dataset (no debugging or scalability labels). `DatasetManifest` supports only one parent version.

**Resume Discussion**

16. **v2 has no adaptive controller.** Follow-ups (`realize_followup`), `probe_deeper` and `clarify` exist only in v1; evaluation never changes the next question.
17. **`topic_pool.select_next`'s diversity bonus can never change a selection** (category scores always differ by ≥ 10). `priority_boost` only reorders units within one category.
18. **v2 has no semantic question dedup** (only identity-level seed dedup), and `all_categories_covered()` is never consulted under the 10-question budget.
19. **Some templates don't name their project or role** (for example a `reflection` variant), which conflicts with doc §12.3. A forced overview on a deep dive can collide and fall back to "architecture".
20. **Stale code and docs:**
    - `question_realizer.realize` is annotated `-> InterviewQuestion` but returns a tuple.
    - `InterviewQuestion`'s docstring references a non-existent `QuestionRealizer` class.
    - `ReasoningType.DESIGN` and `TraceabilityError` are unused.
21. **`strong_answer._example_terms`** depends on the heuristic's exact evidence string format.

**Resume engine**

22. **Layout limits:** three or more columns and ruled tables are unsupported, and rows that all have right-aligned content can still be misread as two columns.
23. **Section detection limits:**
    - The contact fold is position-based, so it misses a main-column name banner in two-column layouts.
    - There are no labels for publications, teaching or awards.
    - Running headers fragment sections.
    - A section with a single entry can still fragment (`single_entry_sections_pdf`).
24. **Stale markers in code:**
    - `ProjectParser` still emits `-interview_seeds_not_implemented_until_milestone_5`.
    - Docstrings in `pipeline.py`, `factory.py`, `confidence.py` and `devtools/__init__.py` ("deleted at Milestone 7") are out of date.
    - The `DocumentModel.source_format` Literal lacks "txt".
    - `PipelineTrace.to_html()` is not implemented.
25. **Smaller parser issues:**
    - The certification stray sweep uses substring matching (short acronyms can false-match).
    - `graduation_year` takes the first year found.
    - The mapper's years calculation ignores "Present".
    - `CAP_RESUME_PARSER` is not consulted by `app.py`.

**Frontend**

26. **Speech warnings can talk over Resume Discussion dictation** (`speakAttentionWarning` checks only the technical recognizer's `isRecording`).
27. **Technical round gaps:** `loadQuestion` and `handleSubmission` have no try/catch (a network error leaves the typing indicator up), and `#subject-select` on the practice setup screen is never read.
28. **`/api/evaluate` quirks:** an empty fill-mask answer is counted correct (`"" in ref`), and scoring uses raw token overlap without stopword removal.
29. **Resume Discussion error handling:** `rdShowStageError` is a dead end with no retry button. A reply racing with termination can show a turn with grade "n/a".
30. **The single 8,600-line `index.html`** holds all CSS, markup and JS, which is hard to maintain. The practice setup screen (`#subject-selection-section`) still uses the older, pre-redesign styling.

**Supporting subsystems**

31. **The RAG integration is dead:**
    - `ingest_subject` is missing, and there's a NameError in `ingestor.py`.
    - The knowledge-base layout and subject name (`cn_unit1`) are stale.
    - The call signatures of `get_context_with_pages` and `generate_reference_answer` changed.
32. **Other RAG code problems:**
    - `code_evaluator.py` is truncated (SyntaxError).
    - `diagram_question_gen.py` and `diagram_pipeline.py` are missing.
    - `test_rag.py` and `test_system.py` are stale.
    - `tracking` has a KeyError in `main.view_progress`.
    - The BM25 query and corpus tokenizers differ.
33. **RoBERTa is archived** (`archive/Roberta/`, routes removed): it never ran in the app, and its `/adaptive/evaluate` ran question classifiers on *answers*.
34. **The resume classifier's BERT head is untrained** (random). Its README references files that don't exist.
35. **Dependency gaps:** there are no per-subsystem `requirements.txt` files. `graphviz`, `matplotlib`, `pytesseract`, `Pillow`, `rapidocr-onnxruntime` and `torchvision` are missing from `Requirements_Global.txt`.

**Slide RAG pipeline**

36. **Legacy quiz routes are dead code.** The UI now runs the question-bank interview (`/api/tech-interview/*`, §4.25); `/api/next_question` (`SAMPLE_QUESTIONS`), `/api/evaluate` and `/api/technical-sessions` are no longer called but remain in the backend. Grading limits: the NLI grader checks that points are *stated*, not that the facts are right (confidently wrong answers average ~0.2–0.3 on the LLM-written sets). On real, short, informal answers it is too strict: correct answers phrased differently from the key point can score low (the follow-up is the second chance). Some questions have weak key points that miss the main idea (e.g. `os.deadlock_avoidance.easy1`); they need rewriting or deactivating by hand, since the automatic "main idea missing" flag was mostly false alarms. First server start on a machine without the models downloaded is slow (downloads).
37. **Stage 3 (vision) has only been run on CN's picture-heavy, picture-only and table slides** (243 slides, ~10 s each; 222 produced text). On CN it improved retrieval with no measured harm: gold hit@5 0.96 → 1.00 (MRR 0.83 → 0.89), a 20-question diagram set hit@1 0.45 → 0.55 (MRR 0.62 → 0.73), probes unchanged. A spot-check found misreadings (a layer stack in the wrong order; numeric graph weights), so vision text is a **retrieval aid, not ground truth**. The other subjects' picture/table slides (~550) and all subjects' diagram-plus-text slides (~1,100) are not processed yet.
38. **OOAD's index predates the latest fixes.** OOAD was last built with extractor v3, before the "MCQ Solution" quiz fix, so its answer-key slides are still searchable and may have fed some generated questions; CN, DBMS, DSA and OS are current (DBMS/DSA at v5 with personal notes stripped and DSA's 255 picture-only slides OCR'd). Rebuild OOAD with `python -m slide_rag.build --subject ooad` (then re-map its topics).
39. **Extraction limits:**
    - Titles set in body-sized text (common in CN) are sometimes taken from a diagram caption.
    - OS deck naming stops after the "Signals" deck, so later sections carry the wrong deck breadcrumb (retrieval is unaffected).
    - Duplicate slides are only detected *within* a deck; CN repeats some slides across decks.
    - Personal notes are stripped only when they are PDF annotations; one note typed into DSA's slide text (p.1122, "see the rules from your notebook") remains.
    - OCR recovers prose but not tables or formulas (Stage 3 covers those).
40. **Evaluation limits:** the gold questions and their page labels were written by one person (the assistant) with a no-peeking rule; sets are small (22–27 per subject), so differences of a few points between settings are noise. CN and OS have no fair old-index baseline.
41. **Question-bank gaps:** 29 of 279 topics have no questions — 20 in CN (OSI and TCP/IP models, Encapsulation, Transmission media, Multiplexing, Principles of reliable data transfer, Stop-and-wait, 802.11, Private/public IP, Subnetting, IPv4 datagram, Forwarding vs routing, Router architecture, TCP segment, TCP reliable transfer, Socket programming, HTTP, Cookies, Email, URL-to-webpage), DBMS (Three-schema architecture, DELETE vs TRUNCATE vs DROP), DSA (Separate chaining, Dynamic programming & knapsack, Generating permutations), OOAD (OOP vs procedural, Access modifiers, final keyword, Aggregation vs composition). Causes: content mostly in diagrams (vision text is not accepted as evidence), a few wrong topic→slide mappings (e.g. reliable data transfer mapped to roadmap slides), and some not yet explained (HTTP, Cookies). Option agreed for later: allow vision text as evidence for diagram-only topics, with those questions marked NEEDS REVIEW.
42. **Question-bank accuracy limits:** checks verify that key points are supported by slide text, but the 8B judge is lenient on reasoning — a pilot hard question built on an invented schema had a wrong reference answer and passed the judge (invented examples are now banned). Hard questions (96) are flagged `needs_review` and mostly held back by the ranking (32 active). No human review of the bank has been done yet.

**Documentation drift**

41. **`README.md`:**
    - It says `GEMINI_API_KEY` is needed for resume upload; it isn't since the Milestone 7 cutover.
    - It says the heuristic evaluator is authoritative; Round 3 made DeBERTa authoritative.
    - It says to `pip install -r main_cap/cap/requirements.txt`, which doesn't exist.
    - It doesn't cover accounts, the database, session history, the Home/Sessions/Profile pages, the full two-round interview, or the session-integrity rules. This document does.
42. **`docs/architecture/ResumeDiscussion_v2.md`:**
    - It describes v1 behaviour: random jitter, a 12/20 question target, adaptive follow-ups, SBERT dedup.
    - Its evaluator chapters (§19.6 / §19.9) describe the v1 result shape.
43. **`WORKFLOW_INTEGRATION_GUIDE.md` (archived 2026-09-30):**
    - It documents endpoints that don't exist (`/predict`, `/rag/*`, `/workflow/interview`).
    - It names the wrong models: FLAN-T5 (actually Qwen2.5) and RoBERTa-base (actually distilroberta).
44. **Other docs:**
    - `WEBCAM_AND_GAZE_MONITORING.md` (archived 2026-09-30) differed from the code on the liveness challenge format, the watchdog, and head/gaze fusion.
    - `Experiment4_TrackB_APIFree.md` still says "pilot only".

---

## 8. Testing

| Suite | Location | How to run | Size / coverage |
|---|---|---|---|
| Resume engine | `main_cap/cap/resume_engine/tests/` | `python -m pytest resume_engine/tests -q` (from `main_cap/cap`) | 510 tests (incl. the Phase 1 tests and `test_integration_fixes.py`); golden corpus of 31 resume fixtures (PDF/DOCX; 3 expected-failure cases) plus seed-synthesis fixtures. Old-vs-new comparison and Round 1 smoke run: `integration_checks/` |
| Planning / discussion | `test_topic_pool.py` (32), `test_question_specification.py` (43), `test_question_families.py` (40), `test_question_realizer.py` (30), `test_discussion_policy.py` (28), `test_lifecycle_hardening.py` (24), `test_traceability.py` (22), `test_conversation_engine.py` (20, incl. 4 integrity), `test_conversation_memory.py`, `test_planner.py`, `test_coverage_tracker.py`, `test_legacy_topic_pool_adapter.py`, `test_integration_planning.py`, `test_interview_question.py` | `python -m pytest test_*.py` | Determinism, traceability, lifecycle invariants, anti-repetition, import boundaries |
| Evaluation | `test_hybrid_evaluator.py` (72), `test_heuristic_evaluator.py` (41), `test_evaluation_result.py` (38), `test_evaluation_engine.py` (26), `test_model_*.py`, `test_deployment_evaluator.py`, `test_reasoning_dimension_relevance.py`, `test_expected_concepts_registry.py`, `test_evaluator_*.py`, `test_evaluation_request.py` | pytest | Contracts, calibration bands, guardrail cases reproduced from real bugs, fallback, CORAL maths |
| Coaching | `test_strong_answer.py` (40), `test_concept_analysis.py` (11) | pytest | Grounded-only insertions, hide gates |
| ML research track | `test_training_experimentation.py` (46), `test_training_example.py` (34), `test_dataset_manifest.py` (26), `test_labeling_operations.py` (25), `test_prompt_assembler.py` (23), … | pytest | Schemas, splits, QWK, provenance, AST import-boundary checks |
| Accounts & login | `test_accounts.py` (31, incl. 6 profile-photo), `test_app_auth_guard.py` (8) | `python -m pytest test_accounts.py test_app_auth_guard.py -q` | Signup validation (every field rule, diploma path, consent), duplicate emails, unreadable resumes leave nothing behind, 413 limit, login/logout, disabled accounts, profile edits, resumes (upload, make-current, delete, cross-device download), user isolation, account deletion incl. DB-level cascade, one real PDF through the real resume engine; the login guard on every API route; saved-resume `/use` and main-page uploads saving to the account |
| Session history & Home | `test_session_history.py` (13), `test_insights_and_settings.py` (9) | pytest | Full Resume Discussion saved and reopened; terminated / abandoned (new interview, idle, restart); ownership of conversations and sessions; deletion; technical sessions incl. terminated; stats, trend, "Focus next" ranking and fallbacks; change password; consent toggle |
| Deployment | `test_deployment_evaluator.py` (6) | pytest | Hybrid activation; fallbacks; missing weights or an unapproved decision never load the model |
| Technical interview | `test_tech_interview.py` (19), `test_tech_interview_ui.js` | pytest / node | Selection, follow-up policy, live session, grader anchors on real models, API flow, frontend flow |
| Frontend | `test_report_*.js`, `test_session_integrity.js` (13), `test_startup_guard.js`, `test_typeline_race.js` | `node <file>` | Each test extracts the exact function source from `index.html` and runs it with Node `vm` + `assert` (no framework). The integrity tests stub the `interview*` hooks |

Tests that need the real `app.py` import `_app_test_setup.py`. It sets an in-memory database and a temporary upload folder, and stubs the DeBERTa bootstrap.
| Legacy | `test_e2e.py` | `python test_e2e.py` | A script with PASS/FAIL counters for v1; pytest collects nothing from it |
| Legacy RAG | `rag_system/rag_tester/test_*.py` | — | Stale (expect old layouts) |
| Slide RAG unit tests | `rag_system/rag_tester/slide_rag/tests/test_pipeline.py` (19, incl. personal-note stripping) | `python -m pytest slide_rag/tests -q` (from `rag_system/rag_tester`) | Synthetic slide PDFs built with PyMuPDF: header/footer and slide-number removal, title detection, diagram labels set aside, deck titles, contents/admin slides, incremental builds, "(contd.)" merging, title normalisation (incl. `IPv4`), generic stems, quiz detection, problem + solution stitching, section size cap, BM25 tokenizer parity |
| Slide RAG retrieval evaluation | `slide_rag/retrieval_eval.py`, `slide_rag/eval/gold_{cn,dbms,dsa,ooad,os}.json` | `python -m slide_rag.retrieval_eval` | 122 hand-labelled questions + 750 generated probes; results and ablations in §4.24 |

The Milestone 7 report recorded 416 passing tests at the time (resume engine plus the app-level selector, profile and e2e tests), and an earlier ML-track note recorded 1,213 passing tests across the whole suite. At the time of this update, the latest runs showed:
- **1241 passed, 17 skipped** for the whole `main_cap/cap` suite excluding the resume engine (`python -m pytest --ignore=resume_engine/tests`), **511** for the resume engine (2026-09-30);
- **6 passed** for deployment;
- all 9 frontend test files passing (incl. `test_tech_interview_ui.js`, `test_session_integrity.js`);
- the grader evaluations in §4.25 (tuning set, 400 held-out answers, the user's 40 answers; scripts in `grader_eval/`);
- **19 passed** for the slide RAG unit tests, and the retrieval evaluation results in §4.24. The question bank's checks were validated through five pilot rounds (§4.25), not unit tests.

The remaining suites weren't re-run for this update.

---

## 9. Glossary

| Term | Meaning |
|---|---|
| **Candidate Profile** | The structured `CandidateProfile` produced from a resume; the single source of truth downstream |
| **Resume Intelligence Engine** | The deterministic 8-stage local resume parser in `resume_engine/` that replaced the Gemini parser |
| **Resume Discussion** | The 10-question, resume-grounded interview (v2 = `conversation_engine`; v1 = `discussion_engine`) |
| **Technical Interview / Round 2** | The question-bank technical flow (main question, then a follow-up or clarification when needed; scores at the end). It is Round 2 of the full interview (8 questions), or standalone (10) |
| **Full Interview** | One continuous proctored session: Round 1 Resume Discussion → summary → Round 2 Technical → combined results |
| **Session (history)** | One saved interview round (`interview_sessions` row) with its turns; status `completed` / `terminated` / `abandoned` / `in_progress` |
| **Abandoned** | A session that was never finished (restart, a new interview started, or 2 h idle); its answered turns are kept |
| **Focus next** | Home-page list of the weaknesses that keep recurring in recent answers (`insights.py`) |
| **Profile session id** | `profile_<hex>`: a key into the in-memory `_candidate_profiles` for one interview, owned by one user |
| **QuestionSpecification / unit** | An immutable record of *what* to ask and *why*, traceable to one profile entry |
| **Category** | project_deep_dive, project_overview, experience, certification, skill_in_context |
| **Family** | A phrasing angle (overview, tradeoffs, debugging, …) with 2 hand-written variants |
| **ReasoningType** | The cognitive task a family tests (RECALL, TRADE_OFF_ANALYSIS, OWNERSHIP, …); drives which dimensions are scored |
| **Arc** | The per-category progression of families in `discussion_policy._ARC` |
| **Grounding** | The profile sub-object (project, experience or certification) a question must stay faithful to |
| **Traceability gate** | The check that a question or technical topic cites a real profile entry (shape gate + substance gate) |
| **Interview seed** | A project-specific question stub synthesized from evidence (metric, trade-off, tech, integration, concept probes) |
| **Gazetteer** | A curated static vocabulary list used for matching (technologies, job titles, sections, …) |
| **Observation** | A validation finding (`info` / `notice` / `warning`) that never blocks generation |
| **Confidence reasons (+/−)** | Explainable signals attached to a confidence score (`+` fired, `-` absent) |
| **PipelineTrace** | Optional per-stage timing and diagnostics object for the resume engine |
| **Shadow Mode** | Dev-only tooling comparing Gemini vs engine profiles without treating either as ground truth |
| **Evaluator / Evaluator Registry** | The stable scoring interface and the name → implementation lookup with an active pointer |
| **HeuristicEvaluator / HybridEvaluator / TrainedEvaluator** | Rule/SBERT-based / DeBERTa-primary combined / DeBERTa-only implementations |
| **Dimension** | A named score axis (technical_accuracy, completeness, communication, tradeoffs, ownership, …) |
| **Agreement band** | high (≥ 0.85) / medium (≥ 0.60) / low agreement between the heuristic and DeBERTa per dimension |
| **Plausibility guardrail** | A downgrade-only override of a DeBERTa dimension score when both signals flag it as implausible |
| **Missing reasoning** | Categorised gaps in *how* the candidate reasoned (tradeoff, example, testing, …) |
| **Concept coverage** | Per-concept status: DEMONSTRATED / SUPERFICIAL / OMITTED |
| **Evaluation Ledger** | Append-only per-session list of `EvaluationResult`s |
| **Coaching note / Improved Answer** | A deterministic first-person suggestion appended to (not replacing) the candidate's own answer |
| **CORAL** | Consistent Rank Logits: an ordinal-regression head predicting P(tier > k) with monotonic thresholds |
| **QWK** | Quadratic Weighted Kappa: an agreement metric for ordinal grades used for benchmarking and promotion |
| **Promotion decision** | The record approving a checkpoint for deployment (candidate QWK ≥ baseline + margin) |
| **Recipe / Quality tier** | The per-example generation targets / the intended answer quality (excellent … poor, off_topic, contradictory) |
| **Track B** | API-free (deterministic rewrite + SBERT drift check) data augmentation for Experiment 4 |
| **Specification-level split** | Train/val/test split by question specification to prevent topical leakage |
| **Session integrity / proctoring** | The full-screen, no-tab-switch, no-copy-paste rules, active for the whole interview; the first violation ends it |
| **Liveness** | A challenge (head turn left/right) confirming a live person is in front of the webcam |
| **RAG** | Retrieval-Augmented Generation: retrieve source material, then generate from it. Legacy: FAISS+BM25 over PDF pages + Qwen2.5-1.5B. New: the slide pipeline (§4.24) |
| **KB** | Knowledge base. Legacy: `rag_system/rag_tester/knowledge_base/` (one chunk per page). New: `knowledge_base_v2/` (slides → sections) |
| **Slide RAG pipeline** | `slide_rag/`: extract → classify → vision → sections → index → report, over faculty lecture slides |
| **Section (slide pipeline)** | A run of consecutive slides that teach one idea; the unit that is retrieved and cited (with its page range) |
| **Child / parent chunk** | Children (single slides, section openings) are searched; their parent sections are returned |
| **Incremental build** | A slide repeated with one more bullet each time; only the most complete version is kept |
| **Running header** | Text repeated at the top of most slides (the subject name); removed, or kept as the topic when deck-specific |
| **Vision stage (Stage 3)** | Qwen3-VL-2B on the GPU reading diagrams, tables, formulas and picture-only slides into text |
| **Topic list** | `topics/<subject>.txt`: the curated interview topics, each checked to have slides behind it |
| **Gold set / probe set** | Hand-labelled questions with their answer pages / auto-generated bullet → slide queries, used to score retrieval |
| **hit@k** | Share of queries whose top k results include a correct slide |
| **Question bank** | `question_bank/<subject>.json`: offline-generated, checked technical-interview questions (reference answer, quote-backed key points, prepared follow-ups); 422 questions across five subjects; each with a confidence rank, quality score and interview-frequency tier; interviews draw the curated top tier first (§4.25). An MCQ bank is planned (`mcq_tobedone.md`) |
| **Key point / quote** | A point a good answer must cover, plus the slide sentence that supports it (verified in code) |
| **Confidence / active** | A question's 0–1 trust score from its generation evidence; only questions at or above the threshold are `active` (used by the app) |
| **needs_review** | Flag on hard questions, whose reasoning the checks can't fully verify against the slides |
| **Judge (thinking mode)** | A second Qwen3 call that checks topic, trivia, quote support and answer correctness |
| **Ollama** | Local LLM server (llama.cpp engine) running `qwen3:8b` on the GPU for offline generation |
| **Blind-solve check** | Planned MCQ filter: the model answers its own question without seeing the key; mismatches are discarded |
| **SBERT / KeyBERT / NLI** | Sentence-BERT embeddings / keyphrase extraction / natural-language-inference cross-encoder |
