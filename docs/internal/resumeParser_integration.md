# Integrating the friend's branch (`olderVersion_withNewResumeClassifier/`)

Status: **integration complete** (2026-09-30): steps 1–7 done, all tests pass. Rollback notes per step in `archive/`.

The branch copy (`olderVersion_withNewResumeClassifier/`, ~910 MB) was **deleted on 2026-09-30** after the integration. What the checks still need was kept in `integration_checks/data/`: his dataset (`overall_v5_1088/examples.jsonl`, `split.json`), the 58 tricky answers (`v4_diagnostic_58.jsonl`) and his original non-answer gate (`teammate_gate/`, for the comparison in `gate_check.py`). All four check scripts were re-run from there with the same results (gate 0/628 vs his 42/628; 151 answers QWK 0.86; 58 answers QWK 0.70, 57/61 pairs). The weights live in `main_cap/cap/deployed_model_overall_single_v5_1088/`. To compare against his branch again (e.g. `parse_all.py` on his resume engine), re-download it from GitHub. Paths below that start with `olderVersion_withNewResumeClassifier/` refer to that deleted copy.

Source: a ZIP of the friend's GitHub branch `maburan-new`, built on an **older** version of this
project. It must not be copied over ours: his `app.py` differs by ~2,400 lines and
`templates/index.html` by ~5,800 (our accounts, history, technical interview, …). Each of his
features is brought INTO our version.

---

## 1. What his branch contains

| Part | Where | Verdict |
|---|---|---|
| `resume_classifier_updated/` | root | **Identical** to our `resume_classifier/` (byte-for-byte). Nothing to take. The app doesn't use either. |
| **Resume engine rewrite** | `main_cap/cap/resume_engine/` | **Better** — his real "resume classifier" work (§2). |
| **Trained answer evaluator** (DeBERTa `overall_single_v5_1088`) | `deployed_model_overall_single_v5_1088/`, `overall_single_evaluator.py`, `overall_score_model.py`, `heuristic_diagnostics.py`, `deployment_evaluator.py` | **Better combined with ours**, erratic alone (§3). Round 1 (Resume Discussion) only. |
| **Non-answer / degeneracy gate** | `overall_single_evaluator.py` (`_is_non_answer`), `correctness_nli_scorer.degeneracy` | **Take** — fixes a real hole in ours (§4). |
| **Resume-specific questions** (`interview_seed` realization) | `question_realizer.py` (+ `topic_pool.py`, `discussion_policy.py`, `planner.py`, ~220 lines) | **Likely good, not yet measured** (§5). |
| **Honest end-of-session feedback** | `interview_feedback.py`, hook in `conversation_engine.py` | Nice-to-have; needs UI wiring (§5). |
| `resume_evidence_evaluator.py`, `correctness_nli_scorer.py` (scorer part) | root | **Skip** — his own docstrings say "NOT DEPLOYED" (experiments). |
| Training/dataset tooling (`build_*`, `run_*`, `colab_training/`, `v4_5000_*`, …) | root | Skip for the app (only for retraining). |
| His `app.py`, `index.html` | | Skip — older than ours. |

Size of the evaluator side: 26 new runtime modules + 27 new test files; 8 shared files changed
(`deployment_evaluator.py` 371 diff lines, `model_heads.py` 185, `model_backbone.py` 176,
`question_realizer.py` 117, `model_evaluator.py` 106, `model_dataset.py` 68, `conversation_engine.py` 67,
`topic_pool.py` 58, plus small ones: `discussion_policy`, `heuristic_evaluator`, `model_checkpoint_io`,
`evaluation_request`, `evaluation_engine`, `conversation_memory`, `planner`).

---

## 2. Resume engine — measured

**Changes:** 11 files rewritten (`dates`, `extractor`, `sections`, `section_gazetteer`,
`parsers/{_entry_clustering, certification, contact, education, experience, project, skills}`),
new `text_normalization.py`, 4 new test files (`test_phase1_{end_to_end, entry_segmentation,
generalization}.py`, `test_text_normalization.py`). ~930 added lines; the "only ours" lines are old
versions of functions he rewrote (his is a superset of ours). Nothing outside `resume_engine/`
changed (`candidate_profile_generator.py` identical, `candidate_profile_mapper.py` identical), so it
is a drop-in.

**Tests:**
- ours on our engine: 420 passed
- his on his engine: 497 passed (+77)
- **our 420 on his engine: 419 passed**; the 1 "failure" is intended — "Hobbies And Interests" is now
  recognised as a section (`interests`) instead of `unknown` (his `test_sections.py` expects that).

**Same 41 resumes through both** (10 real `parser_tests/resumes/*.pdf` + 31 golden corpus; the 3
deliberate unreadable fixtures fail identically on both; ~11–12 s for all 41 either way):

| Extracted | Ours | His |
|---|---|---|
| Jobs, real resumes | 20 | 27 |
| Jobs, golden corpus | 21 | **34** |
| Education, real | 5 | 9 |
| Projects, real | 7 | 9 |
| Certifications, real | 13 | 18 |
| Skills, real | 178 | 168 (sentence junk removed) |
| Identical output | 21 / 41 files | |

**His wins:**
- Ours often keeps only the FIRST job: golden `dense_long_ats_resume` 1 → 4, `narrow_sidebar_ats_photo`
  1 → 4, `ragged_single_column_pdf` 1 → 3, `right_aligned_dates_ats` 1 → 3, `mixed_layout_two_page` 1 → 2,
  `canva_style_two_column` 1 → 2.
- Finds missing sections: real/007 0 → 1 education + 2 jobs; real/003, real/009 education found;
  golden academic/overleaf education `''` → "State University".
- Skills no longer contain whole sentences (real/004, 006, 009, golden docx_table_sidebar).
- Job title and dates kept together (real/008; ours split dates into separate "jobs").
- Project titles without stray years (real/010); junk job "Let's work together." gone (real/006);
  second project found (real/006).

**His regressions — fix these after dropping it in (each with a test):**
- [x] Address / bullet lines become jobs: real/002 ("Gravity Tech | 123 Anywhere St., Any City",
      "Performed system analysis | debugging…"), real/008 ("Conducted a test for software bugs and speed").
      Causes: the dash inside a date range counted as a title separator (so a job header and the address
      line under it looked like sibling entries); sentence-like bullet lines whose lead verb isn't in the
      action-verb lexicon passed as titles. Fixed: `strip_date_ranges` before `_title_separator`;
      `reads_as_sentence` on the weak "title" tier.
- [x] Junk certifications: real/009 ("Giggling Platypus Co.", "01 Jun 2052- present",
      "Designed and implemented a new", "microservice architecture using Borcelle to"). Cause: every line
      of the section became a certification. Fixed: `_is_not_a_certification_name` (dates, company-suffix
      lines, sentence fragments). "Rimberio | 2050" remains (indistinguishable from "Name | year").
- [x] Running footer "Page 1" as a job (golden `repeated_running_header_pdf`). Fixed: `is_page_marker`.
      ("Borcelle | 2050" ×2 in real/009 are REAL jobs — company | year in a template that prints the
      role elsewhere — so they stay.)
- [x] Name lost: golden `repeated_running_header_pdf` ("Jordan Example - Resume" → "Jordan Example" now);
      real/003 letter-spaced name: the PDF gives no word boundary, so it falls back to the old output
      "J U L I A N A S I L V A".
- [x] Education split into two entries: real/010. Cause: a glyph-only "•" line counted as body. Fixed.
- [x] A bullet line taken as a project: real/010 ("SQL knowledge required; …"). Fixed by `reads_as_sentence`.
- [x] Phone with a stray suffix: real/003 "123-456-7890 123" → "123-456-7890".
- [x] Found in the live run (pre-existing in BOTH engines): "March, 2022 - March, 2025" (comma after the
      month) was not recognised as a date, so it stayed in the role and the header split into role
      "Software Developer March, 2022" / company "March, 2025" -> question "You worked as Software
      Developer March, 2022 at March, 2025". Fixed in `dates.py` (`_MONTH_YEAR` allows the comma) and
      `experience_parser.py` (removes the date range as printed). Only real/002 changed.
- Verified in the PDFs that his changes are right where they differ from the old engine: phones print
  "+123-456-7890"; graduation years are the END of "2016 – 2020" / "2009 – 2013" (old took the start).

Real resumes contain personal data: parsed outputs are NOT stored in the repo; regenerate them (§7).

---

## 3. Trained evaluator — measured

**Weights file:** `deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt`, 735,421,149 bytes,
sha256 `277ad4f69834991275c715727cfa58444284b23eb9e54cdf102964f4543a3cef` (matches the LFS pointer).
Installed in his tree; the placeholder is kept as `best_checkpoint_weights.pt.lfs-pointer`. His app
activates it as Tier 1 (`overall-single-deberta_v3_base_overall_single_v5_1088_epoch8`).
His evaluator tests: 48 passed. His reported metrics **reproduced exactly** once the dataset arrived (§6):
validation QWK 0.864, test QWK 0.853, within-1 97.4% (n = 151).

**Held-out check:** his `artifacts/v4_diagnostic/v4_diagnostic_58.jsonl` — 58 hand-graded stress-test
answers on hypothetical projects, never trained on (README: "NOT wired into any training pipeline").
Gold overall = mean of the 4 gold dimension tiers (his own policy).

| On the 58 | Ours today (heuristic-v1) | His model | **Average of both** |
|---|---|---|---|
| QWK vs gold | 0.23 | 0.42 | **0.58** |
| Correlation | 0.35 | 0.56 | **0.63** |
| Better answer ranked higher (pairs) | 41 / 61 | 46 / 61 | **53 / 61** |
| Strong answers (gold ≥ 0.75) crushed to ≤ 0.25 | 0 / 31 | **4 / 31** | 0 / 31 |
| Weak answers (gold < 0.5) scored ≥ 0.75 | **5 / 8** | 0 / 8 | 0 / 8 |
| Mean abs. error | 0.16 | 0.19 | **0.12** |
| Time for 58 (GPU) | 10.8 s | 15.7 s | |

His heuristic (without weights) scores exactly like ours on this set.

- His model catches confident wrong answers ("GBTs simply can't overfit": ours 0.89, his 0.25;
  "I just removed the mutex": ours 0.67, his 0.25).
- It is erratic: excellent answers crushed (composite-index answer, gold 0.94 → **0.10**; PyTorch
  define-by-run answer, gold 0.88 → **0.10**). His own `correctness_nli_scorer.py` notes the model
  "learned answer LENGTH as a proxy for quality (training label/length correlation r = 0.61)".
- **Plan: average his model with our heuristic** (our `hybrid_evaluator.py` slot is meant for a
  trained + heuristic combination). The average was picked on these same 58 answers — re-check it on
  his 151-answer test set (dataset now in hand, §6).
- Cost: ~1.5 GB RAM/VRAM more, ~0.3 s per answer on GPU (more on CPU); every machine needs the 735 MB
  file (otherwise the app falls back to the heuristic — safe, but no gain).

---

## 4. Non-answer gate — measured

Same question ("How did you make sure interview answers weren't lost if the server restarted?"),
project grounding "Interview Coach":

| Answer | Ours today | His (model + gate) |
|---|---|---|
| "idk" | 0.16 poor | 0.00 poor |
| "I'm not sure, I don't remember." | 0.24 poor | 0.00 poor |
| gibberish | 0.26 poor | 0.00 poor |
| **keyword dump** ("Flask SQLite Python REST API JWT Docker Redis …") | **0.79 good** ❌ | 0.00 poor |
| off-topic (football) | 0.18 poor | 0.00 poor |
| a good, concrete answer | 0.94 excellent | 0.75 good |

The gate is deterministic (no model): `_is_non_answer` + `correctness_nli_scorer.degeneracy`
(empty / keyword-dump / gibberish). It can be applied to our current evaluator without the weights.

---

**Step 3 results (2026-09-30):** `main_cap/cap/answer_gate.py`, applied in `evaluation_engine.evaluate`
(the one function every Round 1 answer passes through, whichever evaluator is active). A gated reply is
capped at 0.1 / "poor", its strengths cleared, and one weakness explains why. Adapted from his gate with
fixes, measured by `integration_checks/gate_check.py` on 628 genuine answers (400 + 100 LLM-written,
the user's 40 answers + follow-ups, the 58 Round 1 diagnostic answers) and 16 junk replies:

| | Ours | His original |
|---|---|---|
| Genuine answers wrongly zeroed | **0 / 628** | 42 / 628 (7%) |
| Junk caught | **16 / 16** | 14 / 16 |
| Tricky genuine sentences zeroed | 0 | 5 ("…pass through…", "a SELECT … full table scan", "I passed all the tests", "return the cached value", "List<String> …; here List is …") |

His version matched words inside words ("pass" in "passed"/"pass through"), treated prose words as code
("return the", "select … from"), measured repetition over the whole answer (long answers fail) and treated
any "I don't know" phrase as a non-answer even with real content after it. Ours: whole words; code/markup
only with no explanation around it; repetition over 20-word windows; a "don't know" reply only when fewer
than 6 content words remain outside its "don't know" clauses (≤ 40 words).
Through the real Round 1 path: keyword dump 0.79 good → **0.10 poor**; "idk"/"not sure"/gibberish → 0.10;
a good answer unchanged (0.94). Tests: `test_answer_gate.py` (5); full app suite 1156 passed / 17 skipped;
Round 1 completes on all 38 resumes.

**Step 4 results (2026-09-30):** his `question_realizer.py`, `topic_pool.py`, `discussion_policy.py`,
`planner.py`, `conversation_memory.py`, `test_discussion_policy.py` copied in (pure additions over ours);
`conversation_engine.py` now passes `recent_source_ids=memory.recent_source_ids()` to `plan_next` (his only
change there besides step 6's feedback). Three behaviours: resume-specific seed questions rendered verbatim
(not on a project's first mention), a soft "same family used in the last 3 turns" avoidance, and a soft
recent-source cooldown (`_RECENT_SOURCE_PENALTY = 3`, below one priority tier).
Two fixes on top (his version, read question by question, had them): seeds say "in this project", which is
ambiguous once questions move between projects ("Why did you use Python in this project?" asked about two
projects reads as a repeat) -> `_name_the_project` ("... in FairEdge Data Agent?"); and runs of 3–5 seed
questions in a row ("Why did you use X?") -> never two verbatim seeds back to back.
Measured with `integration_checks/question_quality.py` over 38 resumes (110 questions):

| | Before | His as-is | With fixes |
|---|---|---|---|
| Near-identical question repeated | 2 | 1 | **0** |
| Same question family within 3 turns | 26 | 12 | **6** |
| Consecutive turns on the same resume item | 33 | 20 | **20** |
| Resume-specific (seed) questions | 0 | 15 | **9** (named, alternating) |
| Distinct resume items per interview | 2.31 | 2.38 | 2.38 |

Tests: `test_round1_question_quality.py` (5). Full app suite 1161 passed / 17 skipped; engine 510; JS pass;
Round 1 completes on all 38. Backup of the six planner files before this step:
`archive/round1_planner_backup_2026-09-30/` (copy back to undo).

**Step 5 results (2026-09-30):**
- Brought in his `overall_single_evaluator.py`, `overall_score_model.py`, `heuristic_diagnostics.py`,
  `evaluation_dimensions.py`, `answer_key.py` (+ their tests) and his extended `model_backbone.py`,
  `model_heads.py`, `evaluation_request.py` (optional `answer_key` field, schema v3),
  `heuristic_evaluator.py` (adds `warm_up_models`). Not taken: `correctness_nli_scorer.py` and its
  answer-key registry (his "NOT DEPLOYED" experiment), his `deployment_evaluator.py` (his A2/v3 tiers).
- New `averaged_evaluator.py`: **score = 0.8 × his model + 0.2 × our heuristic**; the heuristic's
  dimensions/strengths/weaknesses/feedback are kept (the Round 1 report is unchanged), both component
  scores are stored in `raw_model_output`, and a model error on a turn falls back to the heuristic.
- `deployment_evaluator.py`: new first tier `_try_activate_averaged_v5` (model folder
  `main_cap/cap/deployed_model_overall_single_v5_1088/`, weights copied there, sha256 verified). Skips
  cleanly (-> previous behaviour) when the weights are missing, are a git-LFS pointer, the promotion
  isn't approved, loading fails, or `CAP_TRAINED_EVALUATOR=0`.
- **His model's internal non-answer gate is disabled** (`overall_single_evaluator.py`): it had caused the
  "crushed excellent answers" in §3 (e.g. composite-index answer, gold 0.94 -> 0.10, and three others);
  the central `answer_gate` (step 3) handles non-answers. With it off, his model alone on the 58 hard
  cases goes 0.42 -> 0.70 QWK with 0 crushed answers.
- **Why 80/20, not 50/50:** on his 151 test answers (dataset now in hand) the heuristic scores QWK 0.10,
  so a 50/50 mean drags his 0.86 down to 0.68. Swept on both sets
  (`integration_checks/eval_151.py`, `v4_eval.py` + `score_v4.py`, components in `baseline_results/`):

| | his 151 test answers | 58 hard cases | pairs ordered right | crushed / inflated |
|---|---|---|---|---|
| heuristic alone (before) | 0.10 | 0.23 | 41 / 61 | 0 / 5 |
| model alone (gate off) | 0.86 | 0.70 | 50 / 61 | 0 / 0 |
| 50 / 50 | 0.68 | 0.71 | 57 / 61 | 0 / 0 |
| **80 / 20 (used)** | **0.86** (within-1 98%) | **0.70** | **57 / 61** | **0 / 0** |

- Through the real Round 1 path: "idk" 0.03, "not sure" 0.05, gibberish 0.05, keyword dump 0.10,
  off-topic 0.04 (was 0.18), a good answer 0.79 "good" (heuristic alone gave it 0.94).
- Cost: server start +~4 s (model load, once); ~0.1 s more per answer on the GPU.
- Tests: `test_averaged_evaluator.py` (6) + his evaluator tests; full app suite 1225 passed / 17 skipped;
  engine 510; JS pass; Round 1 completes on all 38 resumes **with the model active**.
- Caveat kept: the model's score tracks answer length (r = 0.70 on his test set, same as his labels).
- Backup / off-switch: `archive/evaluator_backup_2026-09-30/README.md`.
- **Teammates:** copy the 735 MB `best_checkpoint_weights.pt` into
  `main_cap/cap/deployed_model_overall_single_v5_1088/`; without it the app silently uses the heuristic.

**Step 6 results (2026-09-30):** `main_cap/cap/interview_feedback.py`, adapted from his: his version read his
evaluator's four canonical dimensions, which our reports don't carry (it would have treated every dimension as 0
and told everyone everything was weak). Ours maps the heuristic's dimensions (depth <- `technical_depth`,
relevance <- `completeness`, grounding <- `ownership` + `resume_grounding`), averages each only over answers that
report it, and **ignores non-answers** (a gated keyword dump keeps high dimension scores; his version praised an
all-junk session as "grounded in your own work"). `conversation_engine.end_conversation` adds
`summary["feedback"]` (saved with the session). Round 1 report: headline and summary come from it (fallback: the old
per-grade text for older sessions), its focus tips lead "Before Your Next Interview", and its scope note ("does not
verify factual correctness") is shown; History re-renders saved feedback. Real sessions: all-good -> "Strong session
— specific, grounded answers."; all-junk -> "Most questions weren't really answered." (no strengths); mixed -> "A
mixed session with clear room to go deeper." Tests: `test_interview_feedback.py` (6).

**Step 7 — final pass (2026-09-30):** app suite **1231 passed / 17 skipped / 0 failed** (twice); resume engine 510;
frontend 9/9; slide pipeline 19. Integration checks on the finished code: gate 0/628 genuine answers zeroed;
question quality 0 repeats, 6 family repeats, 9 seed questions; his 151 test answers QWK 0.86; Round 1 completes on
all 38 resumes with the trained model active; real-app API run (signup with a real PDF -> Round 1 -> end) returns the
feedback and History keeps it. Also fixed during the pass: proctoring now arms when the Round 1 session starts (Alt+Tab
while the first question typed out used to go unnoticed). Remaining manual item: the user's browser check.

## 5. Not yet measured

- (done in step 4 — kept for reference) **`question_realizer.py` "evidence-specific seed realization"**: asks the resume's own
  `interview_seeds` (concrete project questions from `seed_synthesis.py`) verbatim instead of generic
  family templates (family `interview_seed`, never registered, so it can't collide with the arc logic).
  Check: generate Round 1 plans for the 10 real resumes with/without it and compare questions.
- **`interview_feedback.py`**: builds the Round 1 report narrative from per-turn signals instead of
  fixed templates; adds a `feedback` block to `end_conversation`'s summary. Our report UI
  (`rdRenderReport`) would need to show it.

---

## 6. Still needed from the friend

**Nothing — everything needed is in hand (2026-09-30).**

- [x] **Weights file** (735 MB LFS): downloaded by the user from GitHub, size and sha256 verified against
      the LFS pointer, installed at
      `olderVersion_withNewResumeClassifier/main_cap/cap/deployed_model_overall_single_v5_1088/best_checkpoint_weights.pt`
      (copied to `main_cap/cap/deployed_model_overall_single_v5_1088/`, which the app uses).
- [x] **Dataset** (`examples.jsonl` + `split.json`, received from him directly): placed where his loader
      reads them, `olderVersion_withNewResumeClassifier/main_cap/cap/artifacts/overall_v5_1088/dataset/`
      (now kept at `integration_checks/data/overall_v5_1088/`).
      1,088 examples, split 787 / 150 / 151, every split id present, no id in two splits;
      **his own `dataset_loader_v5.verify_dataset_integrity` passes**.
- [x] **His reported metrics reproduced exactly** on this machine with his script
      (`colab_training/evaluate_overall_v5.py --weights … --checkpoint-json …`, GPU, report written to
      `deployed_model_overall_single_v5_1088/evaluate_overall_v5_report.json`):
      validation QWK 0.8643 (n=150); test QWK **0.8529**, accuracy 0.6225, MAE 0.404, within-1 0.9735 (n=151).
- Optional, not needed: real Round 1 answers he tested with.

**Caveat for step 5 (from the same report):** word count vs predicted score correlates **0.696** on the
test set (his training labels: 0.72), i.e. the model largely tracks answer length, as his own
`correctness_nli_scorer.py` notes. Part of the 0.85 reflects "longer = better" in his data. Consistent with
the 58-answer stress test (§3: excellent answers crushed, confident-wrong caught) and with the plan to
**average** it with the heuristic evaluator rather than use it alone. Step 5 should re-run both the
151-answer test (his split, now reproducible) and the 58-answer set on the averaged evaluator.

---

## 7. Plan (in order) and progress

| # | Step | Effort | Needs weights? | Status |
|---|---|---|---|---|
| 1 | Copy his `resume_engine/` (11 files + `text_normalization.py` + 4 test files) over ours; run all suites; re-run the 41-resume comparison | ~30 min | no | [x] 2026-09-30 |
| 2 | Fix the §2 regressions (one test each); re-run the comparison | 2–4 h | no | [x] 2026-09-30 |
| 3 | Port the non-answer gate into our evaluator path; re-run §4 table | ~1 h | no | [x] 2026-09-30 |
| 4 | Measure and then port `question_realizer` seed questions (+ planner/topic_pool/discussion_policy deltas) | 2–3 h | no | [x] 2026-09-30 |
| 5 | Port his trained evaluator (runtime modules + model loading changes) and **average** it with the heuristic via the hybrid slot; fall back cleanly without the file; re-run §3 (and the 151-answer set if available); full Round 1 run | 3–5 h | yes | [x] 2026-09-30 |
| 6 | `interview_feedback` into the Round 1 report UI | 2–3 h | no | [x] 2026-09-30 |
| 7 | Update `PROJECT_DOCUMENTATION.md`; all test suites; browser check of both Home cards | ~1 h | | [x] 2026-09-30 (browser check: user) |

Core (1–3, 5): ~1 working day. Everything: ~1.5–2 days.

**Backup of the old parser:** `archive/resume_engine_backup_2026-09-30/` (exact copy, 420 tests
passed on it). Restore with `python archive/resume_engine_backup_2026-09-30/restore_old_parser.py`
(moves the current engine aside, never deletes).

**Step 1 results (2026-09-30):** engine files now identical to his; engine tests 497 passed; full app
suite (`python -m pytest --ignore=resume_engine/tests`) 1151 passed, 17 skipped (weights-dependent,
same as before), 0 failed; the 41 resumes parse identically to his engine; Round 1 end-to-end
(`integration_checks/round1_smoke.py`) completes on all 38 readable resumes with no errors.
Round 1 questions across the 38: 91 → 120 (real resumes 49 → 65; none fewer). Some of the new
questions come from the §2 junk entries — step 2.

**Step 2 results (2026-09-30):** fixes in `text_normalization.py` (`is_page_marker`,
`strip_date_ranges`, `reads_as_sentence`), `parsers/_entry_clustering.py`,
`parsers/certification_parser.py`, `parsers/contact_parser.py`; 11 regression tests in
`resume_engine/tests/test_integration_fixes.py`. Engine tests 508 passed; full app suite 1151
passed / 17 skipped / 0 failed; frontend JS tests pass; Round 1 completes on all 38 readable resumes.
vs his unfixed engine only the 6 affected resumes changed, each exactly as intended; vs the OLD
engine the result is better or equal on every resume (experience golden 21 → 33, real education
5 → 8, sentence junk gone from skills, dates attached to jobs). Round 1 questions: old 91 → final
110 (his unfixed 120, of which the extra 10 were junk-driven).

**Live check through the real app (2026-09-30):** real resumes 002/008/010/007 via the real signup
upload (no mocks) → `/api/resumes/<id>/use` → `/api/resume-discussion-v2/start|reply|end`: all 200, sensible
grounded questions (008 asks about all three jobs; 007 now gets an interview — 0 questions with the old
engine). Engine tests 510; full app suite 1151 passed / 17 skipped.

**Known issues NOT caused by his engine (seen in the live run, present with the old engine too):**
- "as ForGood.ai [ ]": that resume prints the role on a separate line and an icon glyph after the
  company, so the question uses the company as the role.
- "as Instant Chartz App at Morcelle Program": template with role/company in swapped positions.
- 010: Q5 repeats Q2's wording ("How did you structure … what did the overall architecture look like?")
  — a question-planner repetition, not parsing. Candidate for step 4 (question realizer).

Rules while integrating: bring features INTO our version (never copy his `app.py` / `index.html`);
one heavy job at a time; keep his folder untouched (work on copies); after each step run the
relevant check below and record the numbers here.

---

## 8. How to re-run the checks

Scripts in `integration_checks/` (baselines in `integration_checks/baseline_results/`):

```
cd "C:\PESU\placement prep\capstone_latest"

# Resume engines on the same 41 resumes (writes parsed profiles; contains personal data -> keep out of the repo)
python integration_checks/parse_all.py "C:/PESU/placement prep/capstone_latest/main_cap/cap" <out>/parsed_ours.json
# (needs his branch re-downloaded; the local copy was deleted 2026-09-30)
python integration_checks/parse_all.py "<his branch>/main_cap/cap" <out>/parsed_theirs.json
python integration_checks/compare_parsed.py <out>/parsed_ours.json <out>/parsed_theirs.json

# Evaluators on the 58-answer V4 diagnostic set (mode: production = whatever the tree activates, heuristic = HeuristicEvaluator)
python integration_checks/v4_eval.py "<cap dir>" production <out>/v4_x.json
python integration_checks/score_v4.py integration_checks/baseline_results/v4_ours.json integration_checks/baseline_results/v4_theirs_model.json

# Non-answer behaviour of whatever evaluator a tree activates
python integration_checks/degenerate.py "<cap dir>"

# Engine tests
cd main_cap/cap; python -m pytest resume_engine/tests -q
```
