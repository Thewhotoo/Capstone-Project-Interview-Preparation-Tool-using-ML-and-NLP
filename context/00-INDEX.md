# Project context — START HERE

> Context pack for Claude Code sessions (committed in `context/`). Personal settings live in each person's own
> `CLAUDE.local.md` at the repo root (not committed).
> Verified against commit `99bdba9` (2026-11-07). To see what changed since:
> `git log --oneline 99bdba9..HEAD` and `git diff 99bdba9 -- <paths in the file you're reading>`.
> Facts here come from the CODE. Where docs/docstrings disagree, see `12-gotchas-and-drift.md`.

**Read next: `13-status-and-decisions.md`** (current state + open work), then the file for your task below.

## What this project is
PESU capstone: an **AI resume-grounded mock-interview platform**, fully local (no paid API at interview time).
A "Full Interview" = one proctored full-screen session:
1. **Round 1 – Resume Discussion**: 10 questions, each traceable to a project/job/cert/skill on the candidate's resume (+ up to 2 adaptive follow-ups).
2. **Round 2 – Technical**: 8 questions (CN, DBMS, DSA, OOAD, OS) from a slide-grounded question bank, with follow-ups/clarifications.
3. Combined report. Also: standalone Technical Interview (10 q), accounts, history, Home stats, "Focus next".

Team / module owners: (1) Resume engine + Round 1 — Mayuran · (2) RAG, Round 2, grading, grader eval, infra — **Ninad (the usual user)** · (3) Webcam/proctoring — Surya · (4) Accounts/DB/UI — Nandu.

## Run / test (cheat sheet)
```bash
# dev (SQLite, in-memory live store, Flask dev server) — requires Ollama + qwen3:8b/4b unless CAP_ALLOW_NO_LLM=1
cd main_cap/cap && python app.py                      # http://localhost:5000
# prod-like
docker compose up --build -d                          # app(waitress)+postgres16+redis7; Ollama on host
# tests (from main_cap/cap)
python -m pytest -q                                   # both suites: 1898 pass, 22 skip (1429 + 491 collected)
python -m pytest --ignore=resume_engine/tests -q      # app suite only
python -m pytest resume_engine/tests -q               # resume engine only
for f in test_*.js; do node "$f"; done                 # frontend (extracts functions from index.html)
cd ../../rag_system/rag_tester && python -m pytest slide_rag/tests -q
# CAP_SKIP_MODEL_TESTS=1 skips tests that load real models; conftest forces CAP_FACT_CHECK=0, CAP_TECH_LLM_GRADE=0
```
Python 3.12. All app code lives flat in `main_cap/cap/` (modules import each other by bare name; run from that dir).

## Repo map (top level)
- `main_cap/cap/` — the Flask app + every runtime module + research scripts + tests (flat dir).
  - `resume_engine/` resume parser package · `tech_interview/` Round 2 package · `templates/index.html` whole UI
  - `migrations/` Alembic · `benchmarks/` Round 1 parser/evaluator benchmarks · `colab_training/`, `artifacts/` research data
  - `deployed_model_overall_single_v5_1088/` DeBERTa weights (Git LFS, 735 MB)
- `rag_system/rag_tester/` — offline slide pipeline (`slide_rag/`) + **`question_bank/*.json` (read by the app)**.
- `grader_eval/` — Round 2 grader benchmark, labelled sets, human eval, frontier-LLM comparison.
- `docs/architecture/` — old milestone design docs (partly stale). `PROJECT_DOCUMENTATION.md` (1.9k lines, mostly accurate, some drift).
- `Dockerfile`, `docker-compose.yml`, `docker/`, `.github/workflows/tests.yml`, `install.py`, `Requirements_Global.txt` (only requirements file).
- `parser_tests/resumes/` — 10 real resumes (PII) committed.

## Conventions worth following
- **Docstrings are long and explain WHY + measured numbers.** Changes to thresholds are justified with a benchmark result in the comment. Keep that style.
- Pydantic frozen models for contracts; `Protocol` (structural) interfaces + registries (evaluators, resume parsers, question families).
- Every optional/ML piece **fails soft**: never break an interview (try/except → fallback, logged).
- Determinism in Round 1 planning (no `random`, `zlib.crc32` not `hash()`), required for replay from the live store.
- Env-var switches are `CAP_*`, parsed tolerant (`0/false/no/off`). Full list: `11-infra-config-testing.md`.
- Tests: pytest + unittest style, `test_<module>.py` beside the module. JS tests in node with `vm` extraction.

## Working rules for Claude (follow these every session)
- **Commit or push only when the user asks**, under the user's own git identity (personal details, e.g. Ninad's
  commit identity and no-attribution rule, are in that person's local `CLAUDE.local.md`). Push to `origin main`.
  Force-push only when asked, and only with `--force-with-lease`.
- **Never commit** `interview_prep.md`, the Team187 PDF or `CLAUDE.local.md` (local only).
- **Zero cost**: no paid APIs. Frontier models are used only through their free chat (user pastes prompts).
- **Never tune on `fresh`** (nor team_test / human_answers). Tune on llm400 / mine40 / team_tune; measure held-out once.
  Report numbers honestly, including when something got worse; LLM-made labels are always described as such.
- **Archive, don't delete** files without asking (move to the session scratchpad or an archive folder).
- **One heavy GPU job at a time** (Ollama re-grades, benchmarks); use the GPU, not RAM. If memory is tight, stop jobs.
- Don't change UI typing/typewriter speed except in Round 1.
- Keep `PROJECT_DOCUMENTATION.md` up to date when behaviour changes; keep the docstring style (WHY + measured numbers).
- After a commit, check CI (public API:
  `curl -s "https://api.github.com/repos/Thewhotoo/Capstone-Project-Interview-Preparation-Tool-using-ML-and-NLP/actions/runs?per_page=1"`;
  `gh` is not logged in).
- **Keep this pack current**: when you change how an area works, update its file here and `13-status-and-decisions.md`;
  append new commits to `14-commit-history.md`. Bump the "Verified against commit" line.
- User style: short, plain answers; outcome first; give a recommendation rather than a menu.

## Which file to read
| Task touches… | Read |
|---|---|
| Request flow, startup, live store, how pieces connect | `01-architecture.md` |
| Which Round 1 question gets asked / how it's phrased / follow-ups | `02-round1-planning.md` |
| Round 1 scoring, evaluator tiers, answer gate, LLM re-grade, fact check | `03-round1-evaluation.md` |
| Round 2: bank loading, selection, NLI grader, follow-ups, LLM judge | `04-round2-technical.md` |
| Resume parsing (PDF/DOCX → CandidateProfile) | `05-resume-engine.md` |
| DB tables, accounts/auth API, session history, insights, all HTTP routes | `06-data-accounts-api.md` |
| `index.html`: screens, flow, proctoring, gaze, report rendering | `07-frontend.md` |
| Question bank format, regenerating/repairing it, slide RAG | `08-slide-rag-and-bank.md` |
| Measuring grader quality, baselines, labelled sets | `09-grader-eval-and-benchmarks.md` |
| DeBERTa training, synthetic data, experiments (mostly legacy) | `10-ml-research-track.md` |
| Docker, CI, env vars, install, test setup | `11-infra-config-testing.md` |
| Known stale docs, small bugs, traps | `12-gotchas-and-drift.md` |
| Where things stand: headline numbers, decisions and why, open to-dos, paper notes | `13-status-and-decisions.md` |
| Commit history by phase + every commit | `14-commit-history.md` |
