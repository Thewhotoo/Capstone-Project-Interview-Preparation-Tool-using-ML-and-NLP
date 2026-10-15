# AI Resume-Grounded Interview Preparation Platform

A proctored mock-interview platform built around the candidate's **own resume**. It asks about the projects and jobs you actually list, then tests your core CS fundamentals, and gives you an explainable report. Everything runs **locally**: no paid API is needed at interview time.

> Full technical documentation: [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md) · New machine? Read [`SETUP_PREREQUISITES.md`](SETUP_PREREQUISITES.md) first.

---

## Features

- **Accounts and history.** Sign up with your academic details, a resume and an optional profile photo. Home shows your stats, score trend, a "Focus next" list of recurring weaknesses and recent sessions; every past interview can be reopened with its full report.
- **Full Interview (two proctored rounds).**
  1. **Round 1 · Resume Discussion:** 10 questions, each traceable to a specific project, job, certification or skill on your resume. Answers are scored across named dimensions (technical depth, completeness, ownership, communication…) with strengths, gaps and coaching.
  2. **Round 2 · Technical:** 8 concept questions across **Computer Networks, DBMS, DSA, OOAD and Operating Systems**, with a follow-up or clarification request when an answer is unclear or misses a key point.
  3. A combined final report.
- **Technical Interview:** the technical round on its own (10 questions).
- **Resume Intelligence Engine:** a local, deterministic 8-stage resume parser (PDF/DOCX/DOC/TXT) that builds a structured Candidate Profile.
- **422-question technical bank** generated offline from the faculty lecture slides. Every key point is backed by a verified slide quote. Each question carries a confidence rank, a hand-assigned quality score and an interview-frequency tier, so interviews draw the strongest questions on the most-asked topics first.
- **Answer evaluation.**
  - Round 1: a fine-tuned **DeBERTa-v3** evaluator blended with a deterministic heuristic evaluator (automatic heuristic-only fallback if the model file is absent), plus a non-answer filter so "idk" or keyword dumps can't score well.
  - Round 2: an **NLI grader** (`cross-encoder/nli-deberta-v3-base` + MiniLM) that marks each key point covered / partial / missing, with no LLM or GPU needed at interview time.
- **Proctoring.** Camera setup check before the rules, webcam attention and gaze monitoring, head-turn liveness checks, a warning when a second person is in frame or the picture is too dark or blurry (all with MediaPipe Face Landmarker, in the browser), and zero-tolerance full-screen / no-tab-switch / no-copy-paste rules.

---

## Project modules

| # | Module | Owner |
|---|---|---|
| 1 | Resume Intelligence & Resume Discussion: resume parsing, Candidate Profile, Round 1 questions | Mayuran |
| 2 | RAG, Technical Interview & Answer Evaluation: slide RAG, question bank, NLI grader, DeBERTa evaluator | Ninad |
| 3 | Webcam Monitoring & Proctoring: camera check, gaze/attention, liveness, session rules | Surya |
| 4 | Accounts, Data & User Interface: login, database, session history, dashboards and reports | Nandu |

Details, main files and LOC per module: [`PROJECT_DOCUMENTATION.md` §1.1](PROJECT_DOCUMENTATION.md#11-the-four-main-modules).

---

## Quick start (Docker, recommended)

Docker builds everything for you: Python, every package and every model go into the image, and the app runs with PostgreSQL and Redis. Nothing to install except Docker.

**You need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (on Windows it also needs WSL 2), [Git LFS](https://git-lfs.com) for the trained Round 1 evaluator, about 8 GB RAM and 10 GB free disk, and a browser with a webcam. Full list: [`SETUP_PREREQUISITES.md`](SETUP_PREREQUISITES.md).

```bash
git lfs install                  # once per machine, before cloning
git clone https://github.com/Thewhotoo/Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP.git
cd Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP
docker compose up --build -d     # first time ~15 min (downloads ~3 GB); later starts take seconds
```

Open **http://localhost:5000**, sign up with a resume, and start an interview from Home. `docker compose logs -f app` shows the server starting (Ctrl+C stops watching, not the app).

| Task | Command (from the repository root) |
|---|---|
| Stop | `docker compose down` (your data is kept) |
| Start again | `docker compose up -d` |
| After pulling or changing code | `docker compose up --build -d` (rebuilds only the code layer, seconds) |
| Logs | `docker compose logs -f app` |
| Database shell | `docker compose exec postgres psql -U cap cap` |

- **Your data** (accounts, resumes, sessions, interviews in progress) lives in Docker volumes and is kept across `down` / `up` and rebuilds. **`docker compose down -v` deletes it.**
- **The trained Round 1 evaluator** is mounted from `main_cap/cap/deployed_model_overall_single_v5_1088/` (Git LFS, below). Without it Round 1 uses the heuristic evaluator; the startup log says which one is active.
- **Optional settings** (port, database password, secret key, threads): copy `.env.example` to `.env`.
- **Bringing over data from a non-Docker install** (the SQLite file and its resumes): with the stack running, from the repository root:
  ```bash
  docker compose cp main_cap/cap/instance/app.db app:/tmp/app.db
  docker compose cp main_cap/cap/instance/uploads app:/tmp/uploads
  docker compose exec app python copy_database.py --from sqlite:////tmp/app.db --from-uploads /tmp/uploads --replace
  ```
  `--replace` first deletes everything already in the Docker database.

### Without Docker (for development and running the tests)

Needed only to work on the code or run the test suite. **Requirements:** Python 3.12, about 8 GB RAM and internet on the first run (about 2 GB of models download then). Node.js only for the frontend tests. Details: [`SETUP_PREREQUISITES.md`](SETUP_PREREQUISITES.md).

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # no NVIDIA GPU: small CPU-only PyTorch
pip install -r Requirements_Global.txt
cd main_cap/cap
python app.py                    # http://localhost:5000
```

| | Docker (default) | `python app.py` |
|---|---|---|
| Install | Docker only | Python 3.12 + packages + models |
| Database | PostgreSQL | SQLite file (`main_cap/cap/instance/`, created automatically) |
| Interviews in progress | Redis; survive a restart | Process memory; a restart ends them |
| Server | waitress (`serve.py`) | Flask development server |

### Round 1 evaluator weights (Git LFS)

The trained Round 1 evaluator's weights (`best_checkpoint_weights.pt`, ~735 MB) are stored with **Git LFS** (used by both ways of running). Run `git lfs install` **before cloning**, or `git lfs pull` afterwards. Without Git LFS you get a small pointer file instead of the model. Details, and the monthly download allowance: [`SETUP_PREREQUISITES.md`](SETUP_PREREQUISITES.md).

```
main_cap/cap/deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt
```

Without the real file the app still runs: Round 1 falls back to the heuristic evaluator (the startup log says which evaluator is active).

---

## Configuration

All optional; set as environment variables.

| Variable | Default | Effect |
|---|---|---|
| `CAP_DATABASE_URL` | `sqlite:///main_cap/cap/instance/app.db` | Database: SQLite by default, or PostgreSQL (`postgresql+psycopg://user:password@host:5432/dbname`) |
| `CAP_UPLOAD_DIR` | `main_cap/cap/instance/uploads` | Where uploaded resumes are stored |
| `CAP_SECRET_KEY` | generated once into `instance/secret_key` | Flask session secret; set explicitly in production |
| `CAP_TRAINED_EVALUATOR` | on | `0` forces the heuristic Round 1 evaluator |
| `CAP_CURATED_ONLY` | `1` | Technical interviews use the hand-reviewed top tier of the bank; `0` widens to every active question |
| `CAP_GRADER_ENRICHMENT` | `replies` | How much of the offline bank enrichment the technical grader uses (`off` / `replies` / `all`) |
| `CAP_QUESTION_BANK_DIR` | `rag_system/rag_tester/question_bank` | Where the question bank is read from |
| `CAP_MODEL_WARMUP` | on | `0` disables background model loading at startup |
| `CAP_WHISPER_MODEL` | `base.en` | Speech-to-text model for voice answers (faster-whisper name, e.g. `small.en`: more accurate on some voices, about 3x slower) |
| `CAP_LIVE_STORE` | `memory` | Where interviews in progress are kept: `memory` (one process) or `redis` (shared by several workers, survives restarts) |
| `CAP_REDIS_URL` | `redis://localhost:6379/0` | Redis server for `CAP_LIVE_STORE=redis` |
| `CAP_HOST` / `CAP_PORT` / `CAP_THREADS` | `127.0.0.1` / `5000` / `8` | Production server `python serve.py` (waitress) |
| `GEMINI_API_KEY` | unset | Only for optional developer tooling (parser shadow mode, experiment scripts); **not** needed to run the app |

The server port is 5000 (set in `app.run` at the bottom of `main_cap/cap/app.py`).

---

## Tests

```bash
cd main_cap/cap
python -m pytest --ignore=resume_engine/tests -q     # app: 1241 passed, 17 skipped
python -m pytest resume_engine/tests -q              # resume engine: 511 passed
for f in test_*.js; do node "$f"; done               # frontend: 9 test files

cd ../../rag_system/rag_tester
python -m pytest slide_rag/tests -q                  # slide pipeline: 19 passed
```

Some grader tests load the real models; set `CAP_SKIP_MODEL_TESTS=1` to skip them.

Evaluation scripts:
- `grader_eval/`: technical grader vs hand-labelled answers.
- `integration_checks/`: resume engine, non-answer filter and Round 1 evaluator comparisons.

---

## Repository layout

```
.
├── main_cap/cap/                  Flask app (the thing you run)
│   ├── app.py                     Entry point and HTTP routes
│   ├── account_routes.py          Sign up / login / profile / resumes / profile photo
│   ├── session_routes.py          Session history + technical interview API
│   ├── conversation_engine.py     Round 1 orchestration (planner → question → evaluation → feedback)
│   ├── planner.py, topic_pool.py, question_realizer.py, discussion_policy.py   Round 1 question planning
│   ├── resume_engine/             Local 8-stage resume parser
│   ├── evaluation_engine.py, answer_gate.py, averaged_evaluator.py,
│   │   overall_single_evaluator.py, heuristic_evaluator.py                   Round 1 answer evaluation
│   ├── interview_feedback.py      End-of-session feedback text
│   ├── tech_interview/            Technical interview: bank, selector, NLI grader, follow-ups, session
│   ├── deployed_model_overall_single_v5_1088/   Trained Round 1 evaluator (weights via Git LFS)
│   ├── templates/index.html       The whole web UI (incl. proctoring and webcam monitoring)
│   └── static/models/             MediaPipe Face Landmarker model
├── rag_system/rag_tester/
│   ├── slide_rag/                 Offline slide pipeline + question-bank generation, ranking, enrichment
│   └── question_bank/             The technical question bank (one JSON per subject) + quality review
├── grader_eval/                   Technical grader evaluation sets and scripts
├── integration_checks/            Before/after comparison scripts and data
├── resume_classifier/             Resume text extraction for DOCX/DOC/TXT
├── parser_tests/                  Parser benchmark scripts (the test resumes themselves are not in git)
├── docs/architecture/             Earlier design documents
├── Dockerfile, docker-compose.yml, .dockerignore, .env.example   Production mode in Docker
└── docker/                        Model download script and pinned versions for the image
```

Not in git (see `.gitignore`): the database and uploads, the lecture slides and the search indexes built from them, generation caches, and personal test resumes.

---

## Rebuilding the question bank (optional, offline)

Only needed to change the bank; the app just reads `question_bank/*.json`. Requires the lecture slides locally and [Ollama](https://ollama.com) with `qwen3:8b` (GPU recommended). From `rag_system/rag_tester`:

```bash
python -m slide_rag.build                 # slides → knowledge_base_v2
python -m slide_rag.qbank                 # generate questions (resumable)
python -m slide_rag.rank_bank             # rank and activate
python -m slide_rag.enrich_bank           # follow-up replies for the grader
python -m slide_rag.interview_priority    # interview-frequency tiers
```

---

## Documentation

- [`SETUP_PREREQUISITES.md`](SETUP_PREREQUISITES.md): everything a new machine needs (system, models, weights file, browser, question-bank rebuild).
- [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md): architecture, every subsystem, design decisions, measured results, limitations and a glossary.
- [`docs/internal/resumeParser_integration.md`](docs/internal/resumeParser_integration.md): how the improved resume engine and trained evaluator were integrated and measured.
- [`rag_system/rag_tester/question_bank/quality_review.md`](rag_system/rag_tester/question_bank/quality_review.md): per-question quality scores and the topics still to cover.
- [`docs/internal/mcq_tobedone.md`](docs/internal/mcq_tobedone.md): the planned 30-question MCQ test.

## Team workflow

`main` is the stable branch; work on feature branches and merge through pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

- **Port 5000 in use:** stop the other process, or change the port in `app.run` in `main_cap/cap/app.py`.
- **Round 1 shows the heuristic evaluator:** the weights file is missing or is only an LFS pointer (run `git lfs pull`), or `CAP_TRAINED_EVALUATOR=0` is set. Check the startup line `Production evaluator ACTIVE: ...`.
- **Slow first start:** the models are downloading; later starts load them offline.
- **Camera check fails:** allow camera access in the browser and press Retry; the interview can't start without a camera.
