# Production infrastructure: PostgreSQL, Redis, Docker (progress)

Tracks adding a production mode to the app, in this order:
1. **PostgreSQL** as the main database;
2. **Redis** for live interview state;
3. **Docker** to run the app, PostgreSQL and Redis with one command.

Started **2026-10-15**. Status marks: ✅ done, 🟡 in progress, ⬜ not started.

---

## Goal

```
          ┌──► Redis       live interview state: current question, follow-up count (expires after ~2 h)
App ──────┤
          └──► PostgreSQL  permanent record: accounts, resumes, sessions, every answered turn
```

- **Redis and PostgreSQL never talk to each other directly.** The app talks to both.
- **Answered turns go to the database as they happen,** as they do today. When an interview ends, its Redis record is deleted and the session is marked completed or terminated in the database.
- **Why:** any app worker can serve any request, so the app can run several workers or servers, and an interview survives a server restart. The NFRs this improves are scalability, availability, concurrency and portability. The cost is operational simplicity.

**Ground rule: the simple mode stays the default.** `python app.py` with SQLite and in-memory state must keep working unchanged. Production mode is switched on only by environment variables or by `docker compose up`.

| Setting | Simple mode (default) | Production mode |
|---|---|---|
| `CAP_DATABASE_URL` | unset → SQLite `instance/app.db` | `postgresql+psycopg://user:pass@host:5432/cap` |
| `CAP_LIVE_STORE` | unset / `memory` | `redis` (+ `CAP_REDIS_URL=redis://host:6379/0`) |
| Server | `python app.py` (Flask dev server) | `waitress` (Windows / Docker) with several threads or workers |

---

## Status

| Step | Status | Estimate |
|---|---|---|
| 0 · Prerequisites | ✅ Docker 29.8.2 + WSL 2 running; packages installed | ~30 min |
| 1 · PostgreSQL | ✅ Done 2026-10-15: all tests + a live end-to-end run pass on PostgreSQL 16 | ~½ day |
| 2 · Redis for live state | ⬜ | ~3–5 days |
| 3 · Docker setup | ⬜ | ~½ day |

---

## Step 0 · Prerequisites

- [x] Add `psycopg[binary]`, `redis` and `waitress` to `Requirements_Global.txt` (new "Production mode" section) and install them (psycopg 3.3.6, redis 8.1.0, waitress 3.0.2).
- [x] Install **Docker Desktop** (`winget install Docker.DockerDesktop`, then restart the PC). It's needed for development too: Redis has no native Windows build, and running PostgreSQL in a container avoids a system install.
- [x] Check: `docker --version` (29.8.2) and `docker run hello-world` (OK; Docker has 16 CPUs and ~7.4 GB RAM). WSL 2 had to be installed first (`wsl --install --no-distribution` + restart).
- [x] Work on a new branch: `prod-infra`, created from `43c719b` after the pending work was committed and pushed to `ninad_latest` and `main`.

## Step 1 · PostgreSQL

What exists: `database.py` already reads `CAP_DATABASE_URL` (SQLite by default) and has a SQLite-only connection hook (`_configure_sqlite`, which already checks the connection type). There are 3 Alembic migrations in `main_cap/cap/migrations/versions/`, which use `batch_alter_table` (this works on PostgreSQL too).

**Code scan (2026-10-15, before Docker):** the app is already close to database-neutral. There's no raw SQL, no SQLite-only functions, and the `PRAGMA` hook in `database.py` only runs on SQLite connections. Things to watch on PostgreSQL:
- **String lengths are enforced.** SQLite ignores `String(20)` etc.; PostgreSQL rejects longer values. Signup validation matches every column; the resume upload name is already cut to 255. Question-bank values fit (longest topic 40/50, id 52/300). **Risk found:** Round 1 project names and source ids come from parsed resumes and could exceed 300, so they are now trimmed.
- **Timezones.** Datetimes are stored as UTC in `DateTime` columns without a timezone. If the PostgreSQL session timezone isn't UTC, timezone-aware values could be shifted, so force `timezone=UTC` on the connection (`?options=-c%20timezone%3DUTC` or an engine option). `iso_utc()` already tags naive values as UTC.
- **Case-sensitive text comparison.** Already handled: emails are lowercased at signup (`account_schemas.py`) and at login (`account_routes.py`).
- **The migrations' `batch_alter_table`** is a no-op wrapper on PostgreSQL, so it should be fine; verify by running them.

- [x] Start PostgreSQL: `docker run -d --name cap-postgres -e POSTGRES_USER=cap -e POSTGRES_PASSWORD=cap -e POSTGRES_DB=cap -p 5432:5432 -v cap-pgdata:/var/lib/postgresql/data postgres:16` (data kept in the `cap-pgdata` volume). Restart it later with `docker start cap-postgres`.
- [x] Migrations on PostgreSQL: all 3 ran unchanged through `database.configure_database` (tables users, student_profiles, resumes, interview_sessions, session_turns; head `a7c3e91f2b40`). The container's timezone is already UTC. Next: start the full app with `CAP_DATABASE_URL` set.
- [x] Fix SQLite-only code: the connection hook and migrations needed nothing. Added: UTC pinned on PostgreSQL connections (`database.py`), and interview text trimmed to its column length before saving (`models._fit_strings_to_columns`). A test proves PostgreSQL rejected an over-long resume-derived value without it (`StringDataRightTruncation`).
- [x] Tests runnable on PostgreSQL: `CAP_TEST_DATABASE_URL` (`_test_db.py`), with separate databases `cap_test` (real app) and `cap_test_unit` (per-test create/drop), created if missing and emptied each run. The default is still in-memory SQLite.
- [x] Full app suite: **1,245 passed, 18 skipped on both SQLite and PostgreSQL**. Checked that rows were really written to PostgreSQL, with timestamps in UTC.
- [x] Live check: `python app.py` with `CAP_DATABASE_URL` set to PostgreSQL, driven end to end by the smoke script (sign-up with resume + photo, a 10-question Round 1, Round 2 (8), the standalone technical interview (10), history, reopen, insights, logout): **all pass**. 3 sessions and 28 turns were saved in PostgreSQL with their scores. (Account deletion is covered by the test suite.)
- [x] Documented: PROJECT_DOCUMENTATION §2 (Databases), §4.19 (`CAP_TEST_DATABASE_URL`), §8 (running the tests on PostgreSQL); README config table. SETUP_PREREQUISITES is left for step 3 (Docker).

**Done when:** all tests pass on both databases, and SQLite is still the default.

## Step 2 · Redis for live interview state

The five in-memory stores to move:

| Store | File | Holds | Difficulty |
|---|---|---|---|
| `_candidate_profiles`, `_profile_owners` | `app.py` | The loaded Candidate Profile per profile session, and its owner | Easy (plain dicts) |
| `_live` | `session_history.py` | Which DB session a Round 1 conversation is recording into | Easy |
| `_live_tech` | `session_history.py` | The live technical session (questions, follow-ups, grades) | Medium |
| `_conversations` | `conversation_engine.py` | The Round 1 conversation: planner, topic pool, memory, evaluation ledger, pinned evaluator | Hard (complex objects; rebuild the planner by replaying turns) |

- [ ] Add `live_store.py`: one interface (`get`, `set` with TTL, `delete`), with a **memory** backend (default, today's behaviour) and a **Redis** backend (`CAP_LIVE_STORE=redis`).
- [ ] Move the stores over, easiest first: profiles → `_live` → `_live_tech` → `_conversations`.
- [ ] Each request: load state → update → save. Use a per-interview lock so two quick requests can't overwrite each other.
- [ ] TTL of ~2 h on every live record; delete it when an interview ends.
- [ ] Tests: unit tests for both backends; every interview flow run with the memory backend and with Redis.
- [ ] Multi-worker test: 2 app processes against one Redis with requests alternating between them; restart the server halfway through an interview, and the interview must continue.

**Done when:** a Full Interview completes across 2 workers and survives a restart halfway through, and the memory backend still passes every existing test.

## Step 3 · Docker setup

- [ ] `Dockerfile`: Python 3.12 slim, CPU-only PyTorch, the requirements, models downloaded at build time (the container then needs no internet), and `waitress` as the server.
- [ ] `docker-compose.yml`: `app` + `postgres:16` + `redis:7`, named volumes for the database and uploads, health checks, and environment variables set for production mode.
- [ ] `.dockerignore` (archive/, instance/, caches, weights unless provided).
- [ ] Optional: mount the trained Round 1 weights file if present.
- [ ] Check from a clean state: `docker compose up --build` → `http://localhost:5000` → sign up, Full Interview, history. Then `docker compose restart app` mid-interview, and the interview continues.
- [ ] Docs: README ("Simple mode" vs "Production mode"), SETUP_PREREQUISITES (Docker Desktop), PROJECT_DOCUMENTATION (§3.6 deployment, §4.19 config).

**Done when:** a fresh `docker compose up` gives a working app at `localhost:5000` with everything working.

**Deployment note:** only the server needs Docker; users just open the site in a browser. The webcam only works on **HTTPS** (or `localhost`), so any public deployment needs HTTPS. Hugging Face Spaces and tunnels provide it.

---

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-10-15 | Keep SQLite + in-memory as the default; production mode is opt-in | `python app.py` must keep working for teammates and reviewers with zero setup |
| 2026-10-15 | `psycopg` 3 (not psycopg2) | Current driver; ships binary wheels for Windows and Python 3.12 |
| 2026-10-15 | `waitress` as the production server | Gunicorn doesn't run on Windows; waitress works both on Windows and in Docker |
| 2026-10-15 | Redis backend behind a `live_store` interface | The memory backend keeps today's behaviour and the tests unchanged; Redis is a config switch |

## Log

- **2026-10-15:** Plan written. Installed `psycopg[binary]` 3.3.6, `redis` 8.1.0 and `waitress` 3.0.2, and added them to `Requirements_Global.txt`. Docker isn't installed yet.
- **2026-10-15:** Docker Desktop is being installed (on C:, ~6–10 GB needed for this project). Scanned the code for SQLite-specific parts; the findings are under Step 1.
- **2026-10-15:** Docker ready (WSL 2 installed, engine running). Pulled `postgres:16` (642 MB) and `redis:7` (182 MB). Started `cap-postgres`; all 3 migrations ran on PostgreSQL with no changes.
- **2026-10-15:** Committed the two weeks of pending work as `43c719b`, after a full test run (1,244 app tests + 18 skipped, 511 resume-engine, 9/9 frontend, 19 slide-pipeline). Pushed it to `ninad_latest` and `main` (a fast-forward, no force). Moved the internal notes to `docs/internal/`; `interview_prep.md` and the Team187 PDF are git-ignored. Created the branch `prod-infra`.
- **2026-10-15:** **Step 1 done.** Tests run on PostgreSQL through `CAP_TEST_DATABASE_URL`; the connection is pinned to UTC; over-long text is trimmed (a new test fails on PostgreSQL without the fix). 1,245 tests pass on both databases, and a live end-to-end run passes on PostgreSQL. Next: step 2 (Redis).
