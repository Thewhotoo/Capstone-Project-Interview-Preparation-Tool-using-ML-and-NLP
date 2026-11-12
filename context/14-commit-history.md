# 14 — Commit history (main, oldest → newest)

> Generated from `git log` at `99bdba9` (2026-11-07), 178 commits. To extend:
> `git log --reverse --format="%ad|%h|%an|%s" --date=short 99bdba9..HEAD`.
> Authors: **Maburan** = Mayuran (resume engine, Round 1, DeBERTa research); **Ninad** = Round 2, RAG/bank,
> grader eval, infra, merges; **The Whoo / Thewhotoo** = the repo owner account (webcam/proctoring
> integration, repo setup); **SuryaSrikhar** = initial integrated upload.
> Note: Mayuran's 2026-10-23/24 commits appear **twice** with different hashes — once on main
> (`cf5fedc`..`a046431`) and once from his `maburan-new` branch, brought in by the 2026-10-26 merge
> (`e50453a` re-parented that branch on `84cfa89` so the two unrelated histories could merge; `f605979`).

## Phases

| Period | What happened | Key commits |
|---|---|---|
| 2026-04 → 07-13 | Repo created; integrated capstone uploaded; backend stabilised; parser benchmark + resume dataset | `7ef6ec8`, `6fb2540`, `3e67909`, `8afc3a0` |
| 07-16 → 07-29 | Gemini-based profile generation and the resume-discussion engine; first DeBERTa training experiments (Exp 2); Improved Answer feature; frontend upgrade | `13e4d14`, `458e5ef`, `6dd8b84`, `1b8ba34`, `8e6674c` |
| 08-04 → 08-19 | **Gemini parser replaced by the deterministic Resume Intelligence Engine** (shadow mode → cutover `21100ba`); HybridEvaluator; DeBERTa made primary (`d96af91`); rewrite augmentation (Exp 4, API-free Track B); many grounding fixes (no invented ownership/tradeoffs, grounded coaching, confidence rationale) | `e6cd24f`, `21100ba`, `1129d2e`, `d96af91`, `a5070ef`, `15d5160` |
| 08-20 → 09-02 | Owner account: tab locker, DSA, diagram support, **webcam/proctoring integration steps 1–4**; repo replaced with the integrated codebase (`20ab9de`) | `229e1f5`, `f55c4cf`, `20ab9de` |
| 09-08 → 09-20 | DeBERTa research: four-dimension training (V2/V3/V4, A/A2 loss ablations, B0 MLP) → **single overall-score evaluator**; v5_1088 trained on Colab and promoted to production | `3964424`, `f161411`, `7bbe625`, `06a2907` |
| 09-24 → 10-03 | Round 1 polish: question variety, project segmentation, evidence-based evaluation + fairness gates; v5 weights via Git LFS; Ninad's integrated "capstone latest" upload; adaptive follow-ups; answer gate (deflection), engagement attenuator, tech-consistency flag; typewriter speed-ups | `93d4810`, `f273919`, `c897608`, `5c687b6`, `dd24137`, `da697fb`, `403d578` |
| 10-15 → 10-16 | **Ninad: production infra** — grader reliability + bank repair, PostgreSQL, live store (memory/Redis), Docker Compose, copy_database; **Whisper voice input** in every browser | `43c719b`, `508a662`, `383818e`, `f6c7c5c`, `b04878a` |
| 10-23 → 10-25 | **Mayuran: ResumeEvidenceEvaluator promoted to Tier 0**, evidence scoring v2, background LLM re-grade + fact check (NLI-confirmed, both directions, second qwen check), parser fixes, benchmarks (Mohler, final test set); Ollama required at startup, install.py. **Ninad: bank repair batches 4–6 (served 156 → 311), Round 2 background LLM re-grade**; legacy/dead code removed | `cf5fedc`, `f3ae5ed`, `33ce0b6`, `0ea6d2a`, `02ecb55`, `8c158a5`, `31b3ed1`, `4641416` |
| 10-26 → 10-29 | **Merge of `maburan-new` into main**; dead code + stale docs removed; human-eval kit; **CI on GitHub Actions**; follow-up replies regenerated, Round 1 resend, login lockout; Round 2 holistic LLM score + **frontier-LLM comparison**; Whisper tech-vocabulary hint; Mayuran's setup work merged with **qwen3:8b first** and the `CAP_ALLOW_NO_LLM` opt-out | `f605979`, `e7013b8`, `9e2bc00`, `e40a21d`, `fa7a631`, `49d544d`, `88753fc` |
| 11-04 → 11-07 | Gemini's grades added to the frontier comparison; **contradiction cap needs the LLM to agree**; 28 real team answers as the `human_answers` test set | `3978a3c`, `99bdba9` |

## All commits

| Date | Hash | Author | Message |
|---|---|---|---|
| 2026-04-20 | `7ef6ec8` | The Whoo | Initial commit |
| 2026-07-05 | `6fb2540` | SuryaSrikhar | Add integrated capstone project |
| 2026-07-05 | `b48c040` | SuryaSrikhar | Update project title in README |
| 2026-07-12 | `3e67909` | Maburan | Backend stabilization and parser improvements |
| 2026-07-13 | `8afc3a0` | Maburan | Add parser benchmarking framework and resume dataset |
| 2026-07-16 | `13e4d14` | Maburan | Implement Gemini-based candidate profile generation and resume discussion architecture |
| 2026-07-23 | `458e5ef` | Maburan | Minimized API calls, discussion engine introduced |
| 2026-07-23 | `d0f8369` | Maburan | Architecture document |
| 2026-07-25 | `2c70abb` | Maburan | Whole lot of stuff |
| 2026-07-25 | `bf05e12` | Maburan | Repository hygiene pass: untrack generated/session artifacts, expand .gitignore |
| 2026-07-25 | `6dd8b84` | Maburan | Experiment 2 |
| 2026-07-25 | `56cf260` | Maburan | Add Experiment 2 training script |
| 2026-07-25 | `45c7d13` | Maburan | Checkpoint selection introduced into pipeline |
| 2026-07-25 | `ea05977` | Maburan | Tune experiment 2 training configuration |
| 2026-07-26 | `1a7d094` | Maburan | Reduced batch size to 4 |
| 2026-07-26 | `ba9c786` | Maburan | Out |
| 2026-07-27 | `1b8ba34` | Maburan | Ship Improved Answer feature; README, README parity, and audit cleanup |
| 2026-07-29 | `8e6674c` | Maburan | Upgraded frontend. |
| 2026-08-04 | `e6cd24f` | Maburan | Started replacing LLM based parsing with an actual parser |
| 2026-08-05 | `cbd3859` | Maburan | Shadow testing resume intelligence engine. |
| 2026-08-05 | `3217267` | Maburan | Resume Engine updates. |
| 2026-08-06 | `80ad6dd` | Maburan | Fix evaluation scoring: recalibrate similarity, proportional dimension weighting, concrete feedback evidence |
| 2026-08-06 | `1129d2e` | Maburan | Add HybridEvaluator: runs both evaluators, never blends scores |
| 2026-08-06 | `b9ecd14` | Maburan | Wire HybridEvaluator into production bootstrap |
| 2026-08-06 | `cef83ef` | Maburan | Update README for the Hybrid Evaluator production wiring |
| 2026-08-06 | `c720a6f` | Maburan | Recalibrate heuristic evaluator toward realistic interviewer expectations |
| 2026-08-06 | `c55a04d` | Maburan | HybridEvaluator round 2: per-dimension agreement bands + real confidence formula |
| 2026-08-07 | `5e53458` | Maburan | Attempting to better the dataset. |
| 2026-08-08 | `f217849` | Maburan | Stage 1A fixes: proportional severity mapping + reasoning-target completeness fallback |
| 2026-08-08 | `cbf3aa4` | Maburan | Experiment 4: rewrite augmentation pipeline (dataset-generation only) |
| 2026-08-11 | `49568c4` | Maburan | fix: scope concept evaluation to question target and fix resume-parser/report bugs |
| 2026-08-12 | `d4e007f` | Maburan | fix: reconstruct certification parser word-per-span lines |
| 2026-08-12 | `21100ba` | Maburan | feat: complete deterministic resume parser cutover |
| 2026-08-12 | `efc89dc` | Maburan | feat: harden resume parser shadow mode diagnostics |
| 2026-08-12 | `d96af91` | Maburan | feat: make DeBERTa the primary evaluation model |
| 2026-08-12 | `a5070ef` | Maburan | feat: Experiment 4 Track B -- API-free deterministic rewrite augmentation |
| 2026-08-12 | `5c6b05c` | Maburan | chore: ignore deployed-model rollback backup snapshots |
| 2026-08-17 | `c5e8b15` | Maburan | feat: add evaluator plausibility guardrail |
| 2026-08-17 | `ce40300` | Maburan | feat: fix experience parsing without role invention |
| 2026-08-17 | `9bc0f97` | Maburan | feat: fix project technology extraction |
| 2026-08-17 | `8474ad8` | Maburan | feat: prevent unsupported skill ownership in questions |
| 2026-08-17 | `e814801` | Maburan | feat: prevent unsupported skill tradeoff questions |
| 2026-08-17 | `15d5160` | Maburan | feat: ground followups and evaluation dimensions |
| 2026-08-17 | `efc8ca0` | The Whoo | Saving my current work before switching branches |
| 2026-08-17 | `37df6e6` | Maburan | feat: ground improved answers in resume evidence |
| 2026-08-17 | `0aaa46e` | Maburan | feat: ground coaching in evaluator evidence |
| 2026-08-17 | `7757149` | Maburan | feat: clarify partial concept coverage |
| 2026-08-17 | `df00308` | Maburan | feat: surface evaluator confidence rationale |
| 2026-08-18 | `0a6bbdb` | Maburan | feat: sanitize resume extraction artifacts |
| 2026-08-18 | `9ba406d` | Maburan | feat: prevent sentence-seed question garbling |
| 2026-08-18 | `e339235` | Maburan | feat: fix role company disambiguation |
| 2026-08-18 | `ca1c726` | Maburan | fix: present improved answer as separate Your Answer / Coaching Note |
| 2026-08-18 | `7366f04` | Maburan | feat: make Coaching Note content specific and question-relevant |
| 2026-08-19 | `5409ed4` | Maburan | fix: eliminate typewriter/session race and polish report presentation |
| 2026-08-19 | `7b009cc` | Maburan | feat: remove concept coverage from report |
| 2026-08-20 | `229e1f5` | The Whoo | Tab locker |
| 2026-08-23 | `4e9326b` | The Whoo | DSA |
| 2026-08-25 | `66b861b` | The Whoo | Diagram Support |
| 2026-08-25 | `e127adb` | The Whoo | Integration step 1 |
| 2026-08-25 | `21db3f3` | The Whoo | Integration step 1 |
| 2026-08-25 | `f2b8c3c` | The Whoo | Integration step 2 |
| 2026-09-01 | `839afb2` | Thewhotoo | Integration Step 3 |
| 2026-09-01 | `0c52388` | Thewhotoo | Integration Step 3 |
| 2026-09-01 | `0acc13b` | Thewhotoo | Integration Step 3 |
| 2026-09-01 | `f55c4cf` | Thewhotoo | Integration Step 4 : Final and Complete of Webcam Interface |
| 2026-09-02 | `a3eb879` | Thewhotoo | Integration Step 4 : Final and Complete of Webcam Interface |
| 2026-09-02 | `20ab9de` | Thewhotoo | Replace repository with current codebase |
| 2026-09-08 | `e7d098c` | Maburan | Prepare four-dimension DeBERTa training for Colab |
| 2026-09-08 | `c0130ae` | Maburan | Publish frozen four-dimension training artifacts |
| 2026-09-08 | `ba1784e` | Maburan | Add V2 experiment selector to the four-dimension training entrypoint |
| 2026-09-08 | `c92449a` | Maburan | Publish frozen V2 training artifacts (v2_targeted_50 + V2 split) |
| 2026-09-09 | `7240070` | Maburan | feat: add V3 grounding-enriched four-dimension training |
| 2026-09-09 | `0d632b8` | Maburan | feat: add Experiment A loss weighting ablation |
| 2026-09-13 | `41b3b0e` | Maburan | feat: add Experiment A2 smoothed loss weighting |
| 2026-09-13 | `7f6cc0b` | Maburan | chore: publish frozen V4 diagnostic benchmark artifacts |
| 2026-09-13 | `fa62ee4` | Maburan | feat: add A2-on-V4 inference and analysis workflow |
| 2026-09-13 | `fb97e54` | Maburan | chore: add private per-dimension MLP architecture experiment B0 |
| 2026-09-13 | `299a960` | Maburan | chore: add isolated B0 V4 diagnostic inference tooling |
| 2026-09-13 | `b5a2aad` | Maburan | feat: prepare A2 production deployment cutover (checkpoint pending) |
| 2026-09-15 | `3964424` | Maburan | feat: add single overall score evaluator architecture |
| 2026-09-15 | `f161411` | Maburan | feat: deploy single overall DeBERTa evaluator |
| 2026-09-20 | `84bcc17` | Maburan | Add Colab overall-score training package |
| 2026-09-20 | `7bbe625` | Maburan | Add v5_1088 controlled training experiment (dataset merge + train/eval scripts) |
| 2026-09-20 | `7ecd216` | Maburan | Add v5_short_quality_calibration_80 builder script (85 examples, final version) |
| 2026-09-20 | `06a2907` | Maburan | Promote v5_1088 overall evaluator to production |
| 2026-09-24 | `5db7627` | Maburan | Speed up question typewriter animation |
| 2026-09-24 | `ec04072` | Maburan | Improve resume interview question variety |
| 2026-09-29 | `fe1bdb1` | Maburan | Fix resume project segmentation and technology attribution |
| 2026-09-30 | `93d4810` | Maburan | Add evidence-based interview evaluation, fairness gates, and honest feedback |
| 2026-09-30 | `7e90470` | Maburan | Complete the runnable app: setup files + remaining supporting modules |
| 2026-09-30 | `f273919` | Maburan | Ship v5 evaluator weights via git-LFS |
| 2026-09-30 | `90315d9` | Maburan | Ship v5_1088 dataset (examples + split) for eval reproduction |
| 2026-09-30 | `c897608` | Ninad | Capstone latest: resume-grounded interview platform (ninad_latest) |
| 2026-09-30 | `692f57a` | Ninad | Add the Round 1 evaluator weights via Git LFS |
| 2026-09-30 | `59d6c0c` | Ninad | Document the project's four main modules |
| 2026-10-01 | `5c687b6` | Maburan | Add adaptive follow-up probing to the resume interview |
| 2026-10-01 | `4340f3c` | Maburan | Fix answer-insensitivity at the root: substantive-answer gate + probe throttle |
| 2026-10-01 | `33dae7e` | Maburan | Demo-harden: fix garbled adaptive follow-up probe text |
| 2026-10-01 | `84cfa89` | Ninad | Add review docs and faster round 1 typing |
| 2026-10-02 | `b160c44` | Maburan | Integrate main's full project as base; overlay our resume-interview module |
| 2026-10-02 | `32bb5d1` | Maburan | Remove stale orphan tests of replaced research code |
| 2026-10-02 | `dd24137` | Maburan | Close the deflection gap in answer_gate: gate pure question-back replies |
| 2026-10-02 | `da697fb` | Maburan | Add answer-engagement attenuator: kill question-echo scoring at the root |
| 2026-10-02 | `1ffe8a1` | Maburan | Speed up the resume-interview question typewriter animation |
| 2026-10-02 | `d169def` | Maburan | Speed up resume-interview question typewriter further (0.3 -> 0.12) |
| 2026-10-02 | `3c9f56b` | Maburan | Enable Jinja template auto-reload so front-end edits take effect without restart |
| 2026-10-02 | `1aa7353` | Maburan | Drive the question typewriter off requestAnimationFrame (time-based reveal) |
| 2026-10-03 | `403d578` | Maburan | Add a resume-tech-consistency flag, surfaced in end-of-session feedback |
| 2026-10-15 | `43c719b` | Ninad | Improve technical grader reliability and repair question bank |
| 2026-10-15 | `508a662` | Ninad | Support PostgreSQL as the production database |
| 2026-10-15 | `383818e` | Ninad | Keep live interview state in a shared store (memory or Redis) |
| 2026-10-15 | `f6c7c5c` | Ninad | Run production mode with Docker Compose (app + PostgreSQL + Redis) |
| 2026-10-15 | `617bd38` | Ninad | Add copy_database.py and store resume paths portably |
| 2026-10-15 | `4b60a48` | Ninad | Fix voice input: click on/off, keep listening through pauses, ask for the mic up front |
| 2026-10-15 | `b04878a` | Ninad | Voice answers in every browser: record in the page, transcribe on the server with Whisper |
| 2026-10-15 | `eb0fd88` | Ninad | Docs: how to start and stop the Docker stack safely |
| 2026-10-15 | `0f0e93a` | Ninad | Docs: make Docker the default way to run the app |
| 2026-10-16 | `e22171b` | Ninad | Docs: Docker as the default way to run in PROJECT_DOCUMENTATION |
| 2026-10-23 | `cf5fedc` | Maburan | Promote the resume-evidence evaluator to Tier 0 and show only robust dimensions |
| 2026-10-23 | `cf8bf33` | Maburan | Resume parser: running headers, all-caps acronyms, fuzzy headers, name fallback |
| 2026-10-23 | `c577fb7` | Maburan | Resume parser: two-line experience headers, inline cert bullets, more vocab |
| 2026-10-23 | `f3ae5ed` | Maburan | Evidence scoring v2 + optional local-LLM fact check and grade blend |
| 2026-10-23 | `65565b9` | Maburan | Add parser and evaluator benchmarks |
| 2026-10-23 | `33ce0b6` | Maburan | Re-grade answers with the local LLM in the background (CAP_FACT_CHECK=1) |
| 2026-10-23 | `05eaf6c` | Maburan | Resume parser: colon-bullet projects, wrapped-bullet entries, skills lines |
| 2026-10-23 | `356c79e` | Maburan | Fact check: confirm flagged claims with NLI instead of the LLM's own verdict |
| 2026-10-23 | `cff8c67` | Maburan | Benchmarks README: protocol for collecting human labels |
| 2026-10-23 | `a33c52b` | Maburan | Human-label tooling: spreadsheet labelling, training consent, multi-machine ids |
| 2026-10-24 | `d9c7c3f` | Maburan | Benchmarks: Mohler human-graded correctness set + two-annotator resume set |
| 2026-10-24 | `3b98157` | Maburan | Benchmarks README: Mohler human-graded results and two-annotator resume-set results |
| 2026-10-24 | `f5fbf9e` | Maburan | Turn the LLM re-grade on by default when Ollama is available |
| 2026-10-24 | `a201f4e` | Maburan | Fact check: a swapped technology choice is not a false claim |
| 2026-10-24 | `0ea6d2a` | Maburan | Grade with qwen3:4b (falls back to qwen2.5:3b), LLM weight 0.6, schema outputs |
| 2026-10-24 | `7fe2690` | Maburan | Fact check: confirm only claims contradicted in both directions |
| 2026-10-24 | `5c3a0e5` | Maburan | Benchmarks: final test set (42 answers, 7 projects), run once for reported numbers |
| 2026-10-24 | `54d2893` | Maburan | Report wording: say when an AI fact-checker checked the answers |
| 2026-10-24 | `b35e951` | Maburan | Tech-consistency warning needs the answer to name an unlisted technology |
| 2026-10-24 | `a046431` | Maburan | Bring over the resume-evidence evaluator and tech-consistency flag from maburan-new |
| 2026-10-23 | `3a22a23` | Maburan | Promote the resume-evidence evaluator to Tier 0 and show only robust dimensions |
| 2026-10-23 | `39dc49d` | Maburan | Resume parser: running headers, all-caps acronyms, fuzzy headers, name fallback |
| 2026-10-23 | `0909246` | Maburan | Resume parser: two-line experience headers, inline cert bullets, more vocab |
| 2026-10-23 | `cd6d78c` | Maburan | Evidence scoring v2 + optional local-LLM fact check and grade blend |
| 2026-10-23 | `bde68ac` | Maburan | Add parser and evaluator benchmarks |
| 2026-10-23 | `ddffe92` | Maburan | Re-grade answers with the local LLM in the background (CAP_FACT_CHECK=1) |
| 2026-10-23 | `dfbf518` | Maburan | Resume parser: colon-bullet projects, wrapped-bullet entries, skills lines |
| 2026-10-23 | `39e9378` | Maburan | Fact check: confirm flagged claims with NLI instead of the LLM's own verdict |
| 2026-10-23 | `af62388` | Maburan | Benchmarks README: protocol for collecting human labels |
| 2026-10-23 | `e5a434b` | Maburan | Human-label tooling: spreadsheet labelling, training consent, multi-machine ids |
| 2026-10-24 | `df5eeba` | Maburan | Benchmarks: Mohler human-graded correctness set + two-annotator resume set |
| 2026-10-24 | `228be31` | Maburan | Benchmarks README: Mohler human-graded results and two-annotator resume-set results |
| 2026-10-24 | `e8e95c4` | Maburan | Turn the LLM re-grade on by default when Ollama is available |
| 2026-10-24 | `3115406` | Maburan | Fact check: a swapped technology choice is not a false claim |
| 2026-10-24 | `59f5954` | Maburan | Grade with qwen3:4b (falls back to qwen2.5:3b), LLM weight 0.6, schema outputs |
| 2026-10-24 | `908063c` | Maburan | Fact check: confirm only claims contradicted in both directions |
| 2026-10-24 | `eecab2b` | Ninad | Docs and setup for the resume-evidence evaluator and the optional LLM re-grade |
| 2026-10-24 | `833887a` | Ninad | Docs: production infrastructure (PostgreSQL, Redis, Docker) under module 2 |
| 2026-10-24 | `1869388` | Maburan | Fact check: confirm a flagged claim only if qwen3 also calls it incorrect |
| 2026-10-25 | `02ecb55` | Maburan | Make the local LLM (Ollama) a requirement to start the app |
| 2026-10-25 | `8c158a5` | Maburan | One-command setup (install.py) and no opt-out from the local LLM |
| 2026-10-25 | `31b3ed1` | Ninad | Question bank: hand-repair batches 4-6, served pool 156 -> 311 |
| 2026-10-25 | `4641416` | Ninad | Round 2: background local-LLM re-grade of technical answers |
| 2026-10-25 | `8c24e85` | Ninad | Remove internal notes and the finished production-infra progress log from the repo |
| 2026-10-25 | `5e88656` | Ninad | Remove legacy code the app no longer reaches and one-off scripts |
| 2026-10-26 | `b5f29a3` | Ninad | Round 2: LLM point verdicts and follow-up check in the report; cover every most-asked topic |
| 2026-10-26 | `e50453a` | Ninad | maburan-new as of 1869388 (2026-10-24), parented on its integration base 84cfa89 so it merges into main |
| 2026-10-26 | `f605979` | Ninad | Merge Mayuran's maburan-new branch into main (all files and history) |
| 2026-10-26 | `691b3ab` | Ninad | Remove outdated Markdown docs; fix merge duplicates |
| 2026-10-26 | `e7013b8` | Ninad | Remove dead code: legacy files restored by the merge and the unshipped A2 research |
| 2026-10-26 | `467c4bf` | Ninad | Human evaluation kit for the technical grader: real answers, blind labels by two others |
| 2026-10-26 | `9e2bc00` | Ninad | CI: run every test suite on GitHub Actions; benchmark skips answers on rewritten questions |
| 2026-10-26 | `98d1f1e` | Ninad | CI: report failing tests as annotations |
| 2026-10-26 | `e40a21d` | Ninad | Follow-up replies regenerated, Round 1 resend after network errors, login lockout |
| 2026-10-27 | `a66b3e3` | Maburan | Merge main into maburan-new; the local LLM is required in Docker too |
| 2026-10-28 | `fa7a631` | Ninad | Round 2 overall LLM score, frontier-LLM comparison, and documentation brought up to date |
| 2026-10-28 | `49d544d` | Ninad | Voice answers: give Whisper a tech-vocabulary hint |
| 2026-10-29 | `88753fc` | Ninad | Merge Mayuran's setup work (install.py, local-LLM startup check); qwen3:8b first for both rounds |
| 2026-11-04 | `3978a3c` | Ninad | Frontier comparison: add Gemini's grades on the fresh set |
| 2026-11-07 | `99bdba9` | Ninad | Round 2: contradiction cap needs the LLM to agree; 28 real team answers as a test set |
