# Testing activities: August → October 2026

**Team:**
- **Mayuran** (Resume parsing, Round 1): blue
- **Ninad** (Technical interview, grading, infrastructure): green
- **Surya** (Webcam proctoring): orange
- **Nandu** (Accounts, UI, integration): purple
- **Whole team**: grey

## 1. Timeline: 12 testing activities

◆ = milestone. 👤 = manual, ⚙️ = automated.

| # | Dates | Activity | Who | Mode | Covers |
|---|---|---|---|---|---|
| 1 | Aug 4–12 | **Resume parser tests** ◆ New parser live | Mayuran | ⚙️ Automated | Parser golden-corpus tests (31 sample resumes), shadow testing of the new parser against the old one |
| 2 | Aug 11–19 | **Round 1 question review** | Mayuran | 👤 Manual | Round 1 question and report review on real resumes (plus the Aug 6 evaluator unit tests) |
| 3 | Aug 17–31 | **Webcam & liveness trials** | Surya | 👤 Manual | Webcam monitoring trials, liveness and threshold tuning |
| 4 | Aug 25 – Sep 2 | **Module integration testing** | Nandu | 👤 Manual | Integration testing steps 1–4 (plus the Aug 20 tab-lock check) |
| 5 | Sep 15–20 | **Scoring model validation** | Mayuran | ⚙️ Automated | DeBERTa-v3 Round 1 scorer validated against labelled answers (QWK 0.86) |
| 6 | Sep 28–29 | **Slide retrieval accuracy** | Ninad | ⚙️ Automated | Retrieval evaluation on 122 hand-labelled questions (correct slide in top 5 for 96–100%) |
| 7 | Sep 30 | **End-to-end system test** ◆ Full system running | Ninad | 👤 Manual | End-to-end live run (~0.3 s per answer), unit + integration suites, question bank review (282 → 132), grader check, camera setup check, frontend tests |
| 8 | Oct 1–3 | **User acceptance testing** | Whole team | 👤 Manual | Demo run-through, team answer collection (143), blind test (50), fabricated-answer check |
| 9 | Oct 2–3 | **Grader regression checks** | Ninad | ⚙️ Automated | Grader regression benchmark, question sanity check (12 → 0 failing) |
| 10 | Oct 15 | **Compatibility & recovery** | Ninad | ⚙️ Automated | SQLite + PostgreSQL tests (1,245), Docker tests (1,252), voice in 3 browsers, restart mid-interview, data migration check |
| 11 | Oct 16 | **One-command install** ◆ Install verified | Ninad | 👤 Manual | Fresh install test with `docker compose up` |
| 12 | Oct 23–24 | **Final benchmarks & full regression** | Ninad | ⚙️ Automated | Parser accuracy check, expert-graded (Mohler) benchmark, parser change review, speed benchmark (first answer 15.7 s → 0.55 s), full regression run (1,858 pass) |

**Totals:** 6 manual and 6 automated activities; the automated suite grows to **1,858 tests**.

## 2. Test methods followed, and why

Test **activities** (section 1) are what was tested and when. Test **methods** are the kinds of testing used; the last column shows which timeline activities used each one.

### Functional testing: does each feature do the right thing?

| Method | What we did | Why | Timeline # |
|---|---|---|---|
| **Unit** (automated) | pytest + Node.js tests for each function: parser, graders, question selection, accounts, report | Four people edit one codebase; a broken function is caught immediately | 1, 7 |
| **Integration** (manual + automated) | Full sessions after each integration step; tests that call the real API through to the database | Modules were built separately; checks they pass data correctly | 4, 7 |
| **System / end-to-end** (manual) | Complete interviews from signup to report; review of the questions and reports produced | Tests the product exactly as a candidate uses it | 2, 7, 11 |
| **Regression** (automated) | 31 sample resumes and ~630 labelled answers re-checked on every change; 1,858-test suite | Fixing one part often breaks another | 1, 9, 12 |
| **Validation & acceptance** (manual + automated) | AI parts measured against human labels (QWK 0.86, retrieval 96–100%); 193 answers written by the team | The AI must agree with real people, not just run | 5, 6, 8 |

### Non-functional testing: how well does it run?

| Method | What we did | Why | Timeline # |
|---|---|---|---|
| **Performance** | Timed live runs; old-vs-new speed test (first answer 15.7 s → 0.55 s) | Candidates must not wait after each answer | 7, 12 |
| **Reliability** | Server restarted in the middle of an interview; it carried on | A crash must not lose an interview in progress | 10 |
| **Security** (automated) | Login on every API route; users can't see each other's data; hashed passwords; upload limits | The app stores personal data | 7 |
| **Compatibility / portability** | 3 browsers; SQLite and PostgreSQL; Windows and Linux; one-command install | Must work on every user's browser and every server | 10, 11 |
| **Usability** | Webcam trials in low light, at different distances, while reading and typing | Proctoring must not flag honest behaviour | 3 |

## 3. Test environment and team roles

**Hardware and software**

| Layer | What we used |
|---|---|
| Machines | Team laptops on Windows 11; main test laptop with an NVIDIA RTX 5050 (8 GB), used only for offline question generation. The app itself is tested on CPU |
| Runtime | Python 3.12, Node.js 24, Flask; Docker Desktop with Linux containers |
| Databases | SQLite (development and tests, an in-memory test database), PostgreSQL 16 and Redis 7 (production, in Docker) |
| Browsers and devices | Chrome, Edge and Brave; built-in laptop webcams and microphones |
| Model training | Google Colab GPU (Round 1 scoring model) |

**Test data**
- **Resumes:** 10 real resumes, 31 golden-corpus sample resumes, and 15 hand-labelled resumes for parser accuracy.
- **Answers:**
  - 193 answers written by team members;
  - ~630 labelled answers for the grader benchmark;
  - 122 hand-labelled search questions;
  - 496 expert-graded student answers (Mohler).

**Role of each member**

| Member | Module | Testing role |
|---|---|---|
| **Mayuran** | Resume parsing, Round 1 | Parser golden-corpus and shadow tests, Round 1 question review, scoring-model validation, parser accuracy and expert-graded benchmarks |
| **Ninad** | Technical interview, grading, infrastructure | Retrieval accuracy, question bank review, grader regression benchmark, end-to-end runs, database / Docker / restart / browser tests, speed benchmark, full regression runs |
| **Surya** | Webcam proctoring | Webcam and liveness trials, camera setup check in different lighting and distances; wrote the blind answer set |
| **Nandu** | Accounts, UI, integration | Integration testing after each merge step, tab-lock and session checks; wrote team answers |
| **Whole team** | | User acceptance: wrote answers in their own words and compared them with the grader |

## 4. Benefits and drawbacks of this approach

**Benefits**
- 1,858 automated tests catch breaks within minutes of a change.
- AI accuracy is measured against human labels, including a blind set never used for tuning.
- Real resumes, webcams and browsers, on the same setup as production (PostgreSQL, Redis, Docker).
- Zero cost: all tools are free and open source.

**Drawbacks**
- No continuous integration: tests are run by hand before pushing.
- Small human test data, mostly from our own team.
- No load testing or formal security audit.

## 5. Test tools used

| Purpose | Tool | Automated | Open source |
|---|---|---|---|
| Python unit, integration and regression tests | **pytest**, unittest, unittest.mock | ✅ | ✅ |
| API and database tests | **Flask test client**, SQLAlchemy, in-memory SQLite | ✅ | ✅ |
| Frontend tests | **Node.js** (built-in `assert`) | ✅ | ✅ |
| Accuracy metrics (QWK, correlation, hit@5) | **NumPy** + our own metric code | ✅ | ✅ |
| Fuzzy text matching for parser and quote checks | **rapidfuzz** | ✅ | ✅ |
| Grader and retrieval benchmarks | Our own scripts (`benchmark.py`, `sanity_check.py`, `retrieval_eval.py`) | ✅ | ✅ |
| Production-like test environment | **Docker / Docker Compose**, PostgreSQL 16, Redis 7 | ✅ | ✅ |
| Version control and test data | **Git**, GitHub, Git LFS | | ✅ |
| Manual browser testing | Chrome, Edge, Brave and their developer tools (console, network) | | Chromium-based |
| Webcam testing | MediaPipe Face Landmarker in the browser | | ✅ |
| Offline question generation for test content | **Ollama** + Qwen3-8B | | ✅ |

---

## Prompt for the image generator

Create a clean horizontal **timeline infographic** titled **"Testing Activities: August – October 2026"**.

- **Axis:** one horizontal line from **August** to **October 2026**, split into three labelled phases: **August: Module testing**, **September: System testing**, **October: Acceptance & production testing**.
- **Cards:** 12 small rounded cards placed at their dates, alternating above and below the axis so none overlap. Each card shows the **date**, a **bold title** and a small **mode icon** (person = manual, gear = automated). Card colour = who did it:
  1. **Aug 4–12** · Resume parser tests · gear · **blue**
  2. **Aug 11–19** · Round 1 question review · person · **blue**
  3. **Aug 17–31** · Webcam & liveness trials · person · **orange**
  4. **Aug 25 – Sep 2** · Module integration testing · person · **purple**
  5. **Sep 15–20** · Scoring model validation · gear · **blue**
  6. **Sep 28–29** · Slide retrieval accuracy · gear · **green**
  7. **Sep 30** · End-to-end system test · person · **green**
  8. **Oct 1–3** · User acceptance testing · person · **grey**
  9. **Oct 2–3** · Grader regression checks · gear · **green**
  10. **Oct 15** · Compatibility & recovery · gear · **green**
  11. **Oct 16** · One-command install · person · **green**
  12. **Oct 23–24** · Final benchmarks & full regression · gear · **green**
- **Milestones:** three diamonds on the axis with short labels:
  - **Aug 12**: "New parser live"
  - **Sep 30**: "Full system running"
  - **Oct 16**: "Install verified"
- **Legend:** small, in one corner:
  - colours: Mayuran blue, Ninad green, Surya orange, Nandu purple, Whole team grey;
  - icons: person = manual, gear = automated.
- **Style:** flat, minimal, white background, large readable sans-serif text, lots of spacing, no 3D, no people.
