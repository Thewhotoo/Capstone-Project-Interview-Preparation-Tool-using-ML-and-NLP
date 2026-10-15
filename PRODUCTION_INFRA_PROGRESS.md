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
| 2 · Redis for live state | ✅ Done 2026-10-15: two servers share one interview; it survives a restart | ~3–5 days (took 1 day) |
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

## Step 2 · Redis for live interview state ✅

**Design (as built):** `main_cap/cap/live_store.py` has one interface (`get`, `put` with a 2 h TTL, `delete`, re-entrant `lock`) and two backends: **memory** (default) and **Redis** (`CAP_LIVE_STORE=redis`, `CAP_REDIS_URL`). Both store **plain JSON**, so the default mode runs the production code path too. A per-process `LocalCache` reuses rebuilt objects while the stored record's version is unchanged.

| Store (before) | Now | How it is restored |
|---|---|---|
| `app._candidate_profiles`, `_profile_owners` | `profile:<id>` = `{profile, user_id, resume_id}` | Plain data |
| `session_history._live` | `r1link:<conversation id>` + reverse `r1by:<session id>` | Plain data |
| `session_history._live_tech` | `tech:<session id>` = `{version, user_id, state}` | `TechInterview.to_state()` / `from_state()`: questions stored whole, grades, pending follow-up; nothing regraded |
| `conversation_engine._conversations` | `conv:<id>` = `{version, profile, evaluator, turns: [{answer, evaluation}], current_question, ended}` | **Replay**: new Planner from the profile, every answered turn through the same planning steps; evaluations restored, never recomputed |

Why replay is safe: planning is deterministic (crc32, no `random` or `hash()`). This was checked: the same questions came out under 3 different `PYTHONHASHSEED` values on 11 resumes, and the replay takes about 1 ms per conversation. Planning also never depends on scores. If a replay doesn't reach the stored question on screen, the conversation is treated as expired, never continued wrongly.

- [x] `live_store.py` (memory + Redis backends, TTL, re-entrant lock, `LocalCache`).
- [x] All five stores moved: profiles → `_live` → `_live_tech` → `_conversations`.
- [x] Each request: lock → load → update → save (Round 1: inside `conversation_engine`; technical: `session_history.tech_interview_lock` in `session_routes`).
- [x] TTL 2 h on every record; records deleted when an interview ends or is abandoned. This also fixes a leak: profile sessions used to be kept forever.
- [x] Startup: with Redis, unfinished interviews are **not** abandoned (other workers may be running them); with memory, as before.
- [x] `serve.py`: production server (waitress; `CAP_HOST`, `CAP_PORT`, `CAP_THREADS`).
- [x] Tests: `test_live_store.py`. The store contract runs on both backends (Redis when `CAP_TEST_REDIS_URL` is set). Round 1 and the technical interview are rebuilt from their record before **every** answer, and they match an uninterrupted run exactly (questions, scores, report); a rebuild never re-evaluates; a record that no longer replays → 404.
- [x] Full app suite: **SQLite + memory 1,254 passed / 22 skipped** (the 4 Redis-only tests skipped); **PostgreSQL + memory 1,254 / 22**; **PostgreSQL + Redis 1,258 passed / 18 skipped**. All 9 frontend test files pass.
- [x] Redis for development: `docker run -d --name cap-redis -p 6379:6379 redis:7` (later: `docker start cap-redis`).
- [x] **Multi-worker test (live):** two `serve.py` processes (ports 5001/5002) sharing PostgreSQL + Redis + secret key + upload folder. Sign-up → 10-question Round 1 → 10-question technical interview, with **every request alternating between the servers**, and **server B killed and restarted mid-interview**: all passed; both sessions saved as completed. Script: `scratchpad/smoke/multiworker.py` (not in the repo).
- [x] Found and fixed along the way: `migrations/env.py` applied alembic.ini's logging config at every startup, which silenced the app's own log lines (in every mode). It now applies only to command-line migrations.
- [x] Docs: PROJECT_DOCUMENTATION §2, §3.1, §3.6, §4.10, §4.19, §4.26 (new), §7, glossary; README config table.

**Done when:** a Full Interview completes across 2 workers and survives a restart halfway through, and the memory backend still passes every existing test. ✅

**Not moved (not used by the UI):** the legacy v1 discussion engine (`discussion_engine.py`) and the legacy RAG question pool keep their own in-memory state.

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
- **2026-10-15:** **Step 2 done.** Live interview state moved to `live_store.py` (memory or Redis); Round 1 is rebuilt by deterministic replay, and the technical interview by `to_state`/`from_state`. Added `serve.py` (waitress). Two servers sharing PostgreSQL + Redis ran one interview with alternating requests and a mid-interview restart: all pass. Fixed the startup logging that alembic was silencing. Next: step 3 (Docker).
