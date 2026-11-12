# 11 — Infra, configuration, testing

## Running modes
| | `python app.py` (dev) | `docker compose up --build -d` (prod mode) |
|---|---|---|
| Server | Flask dev server, port 5000 | waitress `serve.py` (`CAP_HOST=0.0.0.0`, `CAP_PORT`, `CAP_THREADS=8`) |
| DB | SQLite `instance/app.db` | Postgres 16 (volume `pgdata`) |
| Live store | memory (restart ends interviews) | Redis 7 AOF (volume `redisdata`) |
| LLM | Ollama localhost | Ollama on host via `host.docker.internal:11434` |
Both refuse to start without Ollama + a qwen model unless `CAP_ALLOW_NO_LLM=1` (`llm_requirement.py`). In Docker the container exits and `restart: unless-stopped` retries.

## Docker
- `Dockerfile`: python:3.12.10-slim; CPU torch 2.13.0; installs `Requirements_Global.txt` up to the line "Slide pipeline and question-bank rebuild" (sed), pinned by `docker/constraints.txt`; `docker/download_models.py` bakes HF models into `HF_HOME=/opt/hf`; copies only `main_cap/cap/` + `question_bank/` (`.dockerignore` is an allow-list); non-root user `cap`; healthcheck `/health`.
- `docker-compose.yml`: services app/postgres/redis; DB and Redis not published; DeBERTa weights mounted read-only from the repo; `app-data` volume on `instance/`. `.env` (from `.env.example`): `CAP_PORT, POSTGRES_PASSWORD, CAP_SECRET_KEY, CAP_THREADS`.
- `docker compose down -v` deletes all data.

## install.py (repo root, stdlib only)
pip install requirements → install Ollama (winget / script / brew) → start it, pull `qwen3:8b` if NVIDIA GPU ≥ 7.5 GB else `qwen3:4b` → check LFS weights + LLM. `--skip-pip` for Docker users.

## CI (`.github/workflows/tests.yml`)
On every push/PR, ubuntu, Python 3.12: CPU torch + app requirements + pytest/faiss/bm25 → cache & download HF models → `pytest` in `main_cap/cap` (both suites in one run) → slide_rag tests → node JS tests. `CAP_FACT_CHECK=0`, `CAP_TECH_LLM_GRADE=0`; no LFS weights (heuristic/evidence fallback).

## Environment variables (all optional)
| Var | Default | Effect |
|---|---|---|
| `CAP_DATABASE_URL` | sqlite instance/app.db | DB URL |
| `CAP_UPLOAD_DIR` | instance/uploads | resume files |
| `CAP_SECRET_KEY` | generated file | Flask secret |
| `CAP_LIVE_STORE` / `CAP_REDIS_URL` | memory / redis://localhost:6379/0 | live state |
| `CAP_HOST` / `CAP_PORT` / `CAP_THREADS` | 127.0.0.1 / 5000 / 8 | serve.py |
| `CAP_RESUME_EVIDENCE_EVALUATOR` | 1 | 0 → skip Tier 0 |
| `CAP_EVIDENCE_SCORING` | v2 | v1 rollback |
| `CAP_TRAINED_EVALUATOR` | 1 | 0 → skip DeBERTa tier |
| `CAP_FACT_CHECK` | auto | Round 1 LLM re-grade (auto/1/0) |
| `CAP_FACT_CHECK_MODEL` | first of qwen3:8b, qwen3:4b, qwen2.5:3b | Round 1 LLM; also startup check |
| `CAP_FACT_CHECK_TIMEOUT` | 30 | seconds per call |
| `CAP_OLLAMA_URL` | http://localhost:11434 | both rounds |
| `CAP_ALLOW_NO_LLM` | unset | start without Ollama |
| `CAP_REGRADE_WAIT_SECONDS` | 30 | /end wait for re-grades (both rounds) |
| `CAP_TECH_LLM_GRADE` / `CAP_TECH_JUDGE_MODEL` | auto / first of qwen3:8b, qwen3:4b | Round 2 re-grade |
| `CAP_CURATED_ONLY` | 1 | serve only curated bank questions |
| `CAP_GRADER_ENRICHMENT` | replies | off/replies/all |
| `CAP_QUESTION_BANK_DIR` | rag_system/rag_tester/question_bank | bank dir |
| `CAP_MODEL_WARMUP` | 1 | background model loading |
| `CAP_WHISPER_MODEL` | base.en | speech-to-text |
| `CAP_RESUME_PARSER` | engine | gemini path (not consulted by app.py) |
| `CAP_DEBUG_SAVE_GEMINI_RESPONSES` | off | legacy, writes PII |
| `GEMINI_API_KEY` | unset | research tooling only |
| `HF_HUB_OFFLINE` | auto-set when all models cached | |
| `CAP_SKIP_MODEL_TESTS` / `CAP_TEST_DATABASE_URL` | — | tests |

## Models used at runtime (HF cache)
`all-MiniLM-L6-v2`, `cross-encoder/nli-MiniLM2-L6-H768` (Round 1 heuristics), `cross-encoder/nli-deberta-v3-base` (Round 2 grader), `cross-encoder/nli-deberta-v3-small` (fact-check confirm, tech consistency), `Systran/faster-whisper-base.en`, `microsoft/deberta-v3-base` (only if LFS weights present). Listed in `model_warmup.REQUIRED_MODELS` and `docker/download_models.py` — keep both in sync when adding a model.

## Testing
- `main_cap/cap/conftest.py`: sets `CAP_FACT_CHECK=0`, `CAP_TECH_LLM_GRADE=0`; resets login-fail counters per test.
- `_app_test_setup.py`: import this (not `app`) in tests needing the app — in-memory SQLite or `CAP_TEST_DATABASE_URL`, temp upload dir, stubs `bootstrap_production_evaluator`; `SAMPLE_PROFILE`. `_test_db.py`, `_planning_test_fixtures.py`.
- `resume_engine/tests/conftest.py` + `golden_corpus/`.
- Test data: `test_data/voice_answer.webm`.
- Commands in `00-INDEX.md`. `python -m pytest -q` in main_cap/cap runs both suites: 1898 pass / 22 skip (1429 + 491 collected, 2026-11-12); slide_rag 19; 11 JS files.

## Dependencies
`Requirements_Global.txt` is the only requirements file (sections per subsystem; lower bounds). Exact versions: `docker/constraints.txt`. Missing from it: `rapidocr-onnxruntime`, `torchvision` (slide pipeline only).
