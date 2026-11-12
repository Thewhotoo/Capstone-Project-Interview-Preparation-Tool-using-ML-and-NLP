# 01 — Architecture & request flow

All paths relative to `main_cap/cap/` unless noted.

## Startup (`app.py`)
1. `model_warmup.use_local_models_only()` — if every HF model is cached, sets `HF_HUB_OFFLINE=1` (47 s → 9 s startup). Must run before any HF import.
2. `load_dotenv(main_cap/cap/.env)`.
3. `deployment_evaluator.bootstrap_production_evaluator()` — registers the active Round 1 evaluator (tiers in `03`).
4. `Flask(...)`, `TEMPLATES_AUTO_RELOAD=True` (edit index.html without restart).
5. `init_accounts(app)` (account_routes.py) → `configure_database` (auto Alembic upgrade, secret key, upload dir) + Flask-Login + accounts blueprint; 10 MB upload cap.
6. Blueprints: `sessions_bp` (session_routes.py), `speech_bp` (speech_to_text.py).
7. If live store is memory: `session_history.abandon_all_open_sessions()` (in_progress → abandoned). Redis: kept.
8. `before_request` guard: every `/api/*` except `/api/auth/login|signup` needs login → 401 JSON.
9. `__main__` only: `llm_requirement.ensure_llm_ready()` (starts `ollama serve` if installed, checks model pulled; exits with instructions; `CAP_ALLOW_NO_LLM=1` bypasses) → `model_warmup.start_background_warmup()` → `app.run(port=5000, threaded=True, use_reloader=False)`.
   `serve.py` does the same with waitress (`CAP_HOST/PORT/THREADS`).

## Layers
```
Browser (templates/index.html, vanilla JS, MediaPipe in-browser)
  │ /api/auth/*, /api/profile, /api/resumes*            → account_routes.py
  │ /api/classify-resume, /api/resumes/<id>/use          → app.py  (→ profile session in live store)
  │ /api/resume-discussion-v2/{start,reply,end}          → app.py  → conversation_engine + session_history
  │ /api/tech-interview/{start,<id>/answer,<id>/end}     → session_routes.py → tech_interview/ + session_history
  │ /api/sessions*, /api/insights                         → session_routes.py, insights.py
  │ /api/transcribe                                      → speech_to_text.py (faster-whisper base.en, CPU int8)
Flask ── live_store (memory | redis) ── DB via SQLAlchemy (SQLite | Postgres)
Background: 1-thread pools for LLM re-grades (Round 1: conversation_engine; Round 2: tech_interview/llm_judge) → Ollama
Offline: rag_system slide pipeline → question_bank/*.json (read-only at runtime)
```

## Live state (`live_store.py`)
- Plain-JSON records keyed by string; `TTL_SECONDS = 2h` (refreshed on each write); Redis keys prefixed `cap:`.
- `lock(key)`: per-key RLock (memory) or Redis lock (timeout 60 s, re-entrant per thread).
- `LocalCache` (512 items): per-process cache of rebuilt objects keyed by record `version`; store is source of truth.
- Keys in use:
  | key | owner | content |
  |---|---|---|
  | `profile:<sid>` | app.py | `{profile, user_id, resume_id}` loaded for one interview |
  | `conv:<conv_id>` | conversation_engine | `{version, profile, evaluator:[name,ver], adaptive_followups, turns:[{answer, evaluation, tech_consistency, followup}], current_question, ended}` |
  | `regrade:<conv_id>:<i>` | conversation_engine | finished Round 1 LLM re-grade (EvaluationResult json) |
  | `r1link:<conv_id>` / `r1by:<session_id>` | session_history | conv ↔ DB row link, question on screen |
  | `tech:<session_id>` | session_history | `{version, user_id, state: TechInterview.to_state()}` |
  | `techregrade:<session_id>:<i>` | tech_interview/llm_judge | blended re-grade dict |
  | `loginfail:email:<e>` / `loginfail:ip:<ip>` | account_routes | `{count}` TTL 15 min |
- Answered turns are NOT in the live store — they're in the DB immediately (`session_history`).

## Round 1 request flow
1. `POST /api/resumes/<id>/use` (or `/api/classify-resume` upload) → `_start_profile_session` → `profile_to_frontend_format(parsed_profile)` + `session_id` (`profile_<hex12>`).
2. `POST /api/resume-discussion-v2/start {session_id}` → checks owner → `conversation_engine.start_conversation(profile, enable_adaptive_followups=True)` → `session_history.begin_resume_discussion` (abandons other in-progress sessions of the user; creates DB row).
3. `POST .../reply {session_id: conv_id, answer}` → `owns_conversation` → `advance_conversation` (under lock: build_request → evaluate → queue LLM re-grade → maybe follow-up → else planner.advance + plan next) → `record_resume_discussion_turn`.
4. `POST .../end {session_id, integrity, attention_metrics}` → `end_conversation(..., wait_for_regrades=True)` (waits ≤ `CAP_REGRADE_WAIT_SECONDS`=30 s, swaps in re-grades, builds feedback) → `finish_resume_discussion` (applies re-grades to saved turns, status completed/terminated).
- Note: the reply/end payload key is `session_id` but carries the **conversation id**.

## Round 2 request flow (`session_routes.py`)
- `start {mode: standalone|round2}` → `load_bank()` → `technical_history(user)` (seen ids, per-topic mean) → `select_questions(n=10|8)` → `TechInterview` → `begin_tech_interview` → `{session, prompt}`.
- `<id>/answer {answer}` (truncated to 5000 chars) under `tech_interview_lock` → `interview.submit` → if a main question closed: `record_tech_interview_turn` + `llm_judge.queue` → `save_tech_interview` → `{prompt, finished, questions_answered}` (no scores shown live).
- `<id>/end` → `llm_judge.collect(wait 30 s)` → `apply_tech_regrades` → `finish_tech_interview` → report `{session, summary, questions[...]}`.

## Boundaries (enforced by tests)
- `conversation_engine.py` and `evaluation_engine.py` are the ONLY modules importing both planning types and evaluation types. `planner/topic_pool/question_realizer/discussion_policy/conversation_memory` must not import evaluation modules (import-graph asserted in `test_evaluation_engine.py`).
- `resume_engine/pipeline.py` depends only on Protocols; concrete wiring only in `resume_engine/factory.py`.
- conversation_engine is DB-free; routes call `session_history` around it.
- The evaluator is pinned per session (name stored in record); never re-resolved mid-session.

## Invariants
- Resume parsed ONCE at upload; `Resume.parsed_profile` reused for every interview.
- Every answered turn persisted before the response returns.
- Users only see their own data: every query filters by `current_user`; foreign ids → 404 (never 403).
- One interview at a time per user: starting a new one abandons any in-progress one.
- Session stale after 2 h idle → abandoned (checked lazily on `/api/sessions` and `/api/insights`).
