# Review of `Team187_LLD_Implementation.pdf`: inaccuracies and fixes

Checked against the code on `main` / `ninad_latest` (2026-10-03). Each item gives **what the PDF says**, **what is actually true**, and **the fix**. Page numbers refer to the PDF.

**Priority:**
- 🔴 **Critical:** factually wrong; a reviewer comparing the document with the code or the demo would catch it.
- 🟠 **Important:** wrong detail, or inconsistent within the document.
- 🟡 **Minor:** template leftovers, wording, polish.

---

## 1. Critical (fix first)

| # | Where | PDF says | Actually | Fix |
|---|---|---|---|---|
| C1 | §3 intro (p.7) | The architecture was "chosen over a **modular monolith**" | The system **is** a modular monolith: one Flask process with separated modules, no separate services. The text then describes exactly that ("without the operational overhead of running separate services"), contradicting itself | "We chose a **modular monolith** (one Flask process, separated modules) over a plain monolith with no module boundaries (harder to extend and test) and microservices (more deployment and communication complexity than needed)" |
| C2 | §3.1, Fig 3.1b (p.8), and Fig 3.3 repeated in every module | Fig 3.1b is labelled "**Master class diagram**" | It is a **system architecture / component diagram**: boxes for subsystems, no classes, attributes, methods or UML relationships. Fig 3.1a is a flow overview, also not a class diagram. **The document has no actual class diagram anywhere** | Rename Fig 3.1b to "System architecture (component) diagram". Add a real UML class diagram (13 classes with attributes, methods and multiplicities; see `diagrams_information.md` §2). In each module section, replace the repeated Fig 3.3 with that module's own class diagram |
| C3 | Use-case diagram Fig 3.2 (p.9) + §3.5.2 (p.24) | "Monitor attention & liveness" **extends into** "Terminate on rule violation" | Attention and liveness monitoring **never ends an interview**; it only shows warnings and lowers the attention score. Termination comes from **session-rule** violations: tab or window switch, leaving full screen, copy/paste (`proctorViolation`) | Add a use case **"Enforce session rules"** (Proctor System). Make "Terminate on rule violation" «extend» **that**, not "Monitor attention". (This error was also in our `diagrams_information.md`; fixed there too) |
| C4 | Module numbering: Fig 3.1a (p.7) vs §3.4 / §3.5 vs project docs | Fig 3.1a: "M3 Proctoring + M4 UI", "M4 · Persistence". Text: §3.4 = **Module 3 Accounts**, §3.5 = **Module 4 Webcam**. README / PROJECT_DOCUMENTATION: Module 3 = Webcam (Surya), Module 4 = Accounts (Nandagopal) | Three different numberings | Pick one everywhere. Matching the project docs: **M1 Resume (Mayuran), M2 RAG + Tech Interview + Evaluation (Ninad), M3 Webcam & Proctoring (Surya), M4 Accounts, DB & UI (Nandagopal)**, and swap §3.4 / §3.5 order; or change the docs. Then fix the labels in Fig 3.1a |
| C5 | §4.2 (p.29) | DeBERTa "reaches QWK **0.86 against human-graded Round-1 answers**… the heuristic is retained **for cases the trained model is less confident about**" | QWK 0.86 is on the **151-answer held-out test split of the 1,088-example training dataset** (and 0.70 on a 58-answer stress set). The heuristic is a **fixed 20% weight on every answer** (`HEURISTIC_WEIGHT = 0.2`), not used conditionally | "The blended evaluator reaches QWK 0.86 on the 151-answer held-out test split (heuristic alone: 0.10) and 0.70 on a 58-answer stress set; the heuristic contributes a fixed 20% of every score and supplies the per-dimension feedback" |
| C6 | §4.2 (p.29) | "422-question bank (**132 of which are loaded into the live question-bank JSON files**…)" | **All 422** questions are in the JSON files. 279 are active, and the **curated** ones are served (`curated: true`, `CAP_CURATED_ONLY`); **now 156**, after the 2026-10-03 repairs | "422 generated → 279 active → **156 curated and served**" (update everywhere: p.14 "132 curated", Fig 3.1a "132 curated of 422") |
| C7 | §4.2 (p.29) | Round-2 grader "agree[s] with human judgement **89%** of the time" | 89% (now **91.8%**) is the same move-on decision on **400 LLM-written** test answers. On **human-style answers** it is **75–86%** (held-out team answers 75.3%, your own typed answers 75%) | Report both: "Same move-on decision as a human: 91.8% on 400 LLM-written answers, 75–86% on human-written answers (held-out half: 75.3%)" |
| C8 | §3.4 Sequence Fig 3.10 (p.22) | Step 16: one `POST /end` → server returns "combined report" | Two separate ends: `POST /api/resume-discussion-v2/end` **after Round 1** (missing in the figure), and `POST /api/tech-interview/<id>/end` after Round 2. The **combined report is built in the browser** (`rdRenderReport` with `combined`), not returned by the server | Add the Round-1 `/end` after the first loop. Rename step 16 `POST /tech-interview/<id>/end` → "Round 2 report", then a browser self-call "build combined report" |
| C9 | §3.5.3 classes (p.25–27) | `ProctorController` and `GazeMonitor` shown as classes with private members | `index.html` has **no JS classes**: these are plain functions plus module-level state (`proctorState = {armed, terminated, violation, blurSuspended}`, `webcamStream`, `attentionMetrics`) | Mark them «logical component» (or «module»), not classes, and say so in the description. Members: `proctorState.armed`, `proctorState.terminated`, `proctorState.violation` |

---

## 2. Important: wrong details in the class / method sections

### Module 1: Resume Intelligence & Round 1 (§3.2)
| # | PDF says | Actually | Fix |
|---|---|---|---|
| I1 | `ResumePipeline` data members: `extractor`, `sections: list[Section]`, `trace: PipelineTrace`, all "private" | `ResumePipeline` is a **dataclass with 8 injected stage collaborators**: `extractor, layout_reconstructor, section_detector, parser_runner, cross_reference_engine, normalizer, validation_engine, confidence_engine`. It stores no `sections` or `trace` (trace is a `run()` argument). Python has no `private` | List the 8 stage fields (type = the stage Protocol). Access "public (dataclass field)" |
| I2 | `run(file_path, trace=None) -> DocumentModel`; purpose "return the populated **Candidate Profile**" (contradicts its own return type) | `run(file_path, source_format, trace=None) -> AnnotatedCandidateProfile`; `candidate_profile_mapper.map_to_candidate_profile()` then builds the `CandidateProfile` | Fix the signature and return type; add the mapper step to the pseudo-code |
| I3 | `_timed(stage, fn, *args)` | `_timed(stage_name, pipeline_trace, fn, *args, enrich=None, **kwargs)`; records only when a trace is active | Fix the signature; pseudo-code `if trace: trace.record(...)` |
| I4 | `Planner` members `profile`, `topic_pool`, `rejected` | Only one attribute, `pool: TopicPool`; `rejected` is a **property** delegating to the pool | Members: `pool: TopicPool`. Mention `rejected` as a read-only property |
| I5 | `plan_next` pseudo-code: `if all_categories_covered(): return None; category = next_uncovered_category…` | `return self.pool.select_next(state.last_category, state.recent_source_ids)`: deterministic scoring (category priority × 10, +100 uncovered category, +2 priority boost, +1 category change, −3 recently used item). Returns None only when **no unasked units remain**; `all_categories_covered()` is never consulted | Replace the pseudo-code with the scoring rule |
| I6 | `ConversationState` = "categories asked so far, turn count" | `ConversationState(last_category, recent_source_ids)` | Fix |
| I7 | `advance` outcome "covered / skipped / **needs follow-up**" | `UnitStatus` lifecycle is UNASKED → ACTIVE → COVERED or SKIPPED; there is no "needs follow-up" status, and v2 asks no follow-ups in Round 1 | Fix the list of outcomes |
| I8 | §3.2.2: "the Resume Intelligence Engine is the include-relationship target that the full-interview use case depends on" | Not in the diagram: "Take Full Interview" includes "Answer question" and "Camera setup check" | Either add «include» "Parse resume" (from "Sign up & upload resume") to the diagram, or drop the sentence |

### Module 2: Slide RAG, Technical Interview & Evaluation (§3.3)
| # | PDF says | Actually | Fix |
|---|---|---|---|
| I9 | DeBERTa-v3 "**regression** model / regression head" (§1.1, §3.3, Appendix A) | `OverallScoreModel`: DeBERTa-v3-base + **one CORAL ordinal head** (5 tiers), not regression | "fine-tuned DeBERTa-v3-base with a CORAL ordinal head (5 grade tiers)" |
| I10 | `AveragedEvaluator` member `float model_weight (const) = 0.2` "weight given to the trained model" | Module constant **`HEURISTIC_WEIGHT = 0.2`**; the model's weight is **0.8** | Fix the name and meaning |
| I11 | `AveragedEvaluator.evaluate` pseudo-code returns `EvaluationResult(score, grade, reconcile(h, m))` | Takes the **heuristic's** result and replaces score and grade with the 0.8 / 0.2 blend; keeps the heuristic's dimensions and feedback; stores both raw scores in `raw_model_output`; **falls back to the heuristic** if the model raises. The non-answer gate is applied **afterwards** in `evaluation_engine.evaluate`, not inside it | Rewrite the pseudo-code accordingly; move `answer_gate` out of "combined by AveragedEvaluator" in §1.1 |
| I12 | "Method 2" of `AveragedEvaluator` is `grade_answer()` | `grade_answer` is a **function in `tech_interview/grader.py`**, unrelated to `AveragedEvaluator` | Move it under a "grader (module)" entry for Round 2 |
| I13 | `grade_answer` pseudo-code: entailment from the **best-similarity chunk** | Entailment is the **max over all chunks** (sentences, sentence pairs, 20/40-word windows). Since 2026-10-03 also: **abbreviation expansion** (`terms.py`), **similarity floor** (no credit if similarity < 0.25), **contradiction cap** (reference contradicts the answer ≥ 0.5 → score ≤ 0.2), and clarity caps ("I don't know" ≤ 0.1, too short ≤ 0.5) | Update the pseudo-code: thresholds covered (entail ≥ 0.6, or ≥ 0.2 with sim ≥ 0.8), partial, score = 0.85 × key points + 0.15 × reference similarity, then the caps |
| I14 | `TechInterview.submit` pseudo-code returns `{grade, followup: current.question.followup_question}` | `Question` has no `followup_question`. The follow-up text comes from `followup.decide()` → `Decision(kind = next / clarify / probe, text, key_point)`: a key point's prepared follow-up, or a clarification template. `submit` returns **`{record, prompt, finished}`**; no grade is sent to the browser (no live scores) | Rewrite the pseudo-code and output; add the **clarify** branch and the "don't know → next" rule |
| I15 | `summary()` returns `{questions, overall_score, by_topic}` | Returns `{mode, questions_planned, questions_answered, average_score, by_subject, by_difficulty, followups_asked, weak_topics}`; the `/end` route returns `{session, summary, questions}` | Fix |
| I16 | `TechInterview.questions`: "the **8** questions" | 8 in the full interview's Round 2, **10** in the standalone Technical Interview (`mode`) | "8 (round2) or 10 (standalone)" |
| I17 | p.14: "2 easy / 5 medium / 1 hard per session" | True for Round 2 (8). Standalone (10) = 2 / 6 / 2. Selection is also weighted toward the most-asked topics (×6 / ×1 / ×0.2) and the user's weak topics, never repeats a seen question, and uses 8 distinct topics | Add these selection rules |
| I18 | Sequence Fig 3.7, alt branch "[all key points covered] → next question" | Moves on when **score ≥ 0.70 and the answer is clear**, on "I don't know", or after 2 follow-ups, not only when every point is covered. A third branch exists: **clarification request** for unclear answers | Change the guard to `[score ≥ 0.70 and clear]` and add an `[unclear] → clarify` branch |
| I19 | §4.2: retrieval "**tuned from** 68–82% up to 96–100% hit@5" | 68–82% is the **old page-per-chunk index**, a different system, measured on DBMS, DSA and OOAD only; the slide pipeline **replaced** it | "The new slide pipeline reaches 96–100% hit@5 versus 68–82% for the old page-per-chunk index (DBMS, DSA, OOAD)" |

### Module 3/4: Accounts & DB (§3.4)
| # | PDF says | Actually | Fix |
|---|---|---|---|
| I20 | `record_turn(session, question, answer, evaluation)` that increments `questions_answered` | No such function. `session_history.record_resume_discussion_turn(conversation_id, answer, reply)` and `record_tech_interview_turn(session, record)`; `questions_answered = len(session.turns)` (recomputed, not incremented) | Use the real function names and logic |
| I21 | Sign-up sequence step 7b "save User, Profile, Resume" | Order: validate → duplicate email (409) → resume saved to `_pending/` and parsed → User + StudentProfile created → file moved to `resumes/<user_id>/` → Resume row (current, with `parsed_profile`) → commit + login. Any failure rolls back and removes the file | Add the 409 branch and "store file + parsed profile" |

### Module: Webcam (§3.5)
| # | PDF says | Actually | Fix |
|---|---|---|---|
| I22 | `proctorArm` pseudo-code: `if not fullscreen(): requestFullscreen(); return` | Browsers only allow full screen from a user click, so it shows a **"Return to full screen" overlay** (`proctorRequireFullscreen`); it also returns if no interview session is active | Fix the pseudo-code |
| I23 | `proctorViolation` records `{type, label, at_turn, occurred_at}` | Also records **`round`** (which round the violation happened in) | Add `round` |
| I24 | Class / description sections omit the 2026-09-30 additions | Second-person detection (up to 2 faces), prominent red/amber alerts (second person; too dark or blurry), spoken warnings muted while a mic is on, head-turn liveness (blink challenge disabled) | Add them to the description and to `GazeMonitor` (as a logical component) |

---

## 3. Inconsistent numbers

| # | Item | PDF | Correct (code LOC = non-blank source lines in git, excluding tests) | Fix |
|---|---|---|---|---|
| N1 | Mayuran LOC | ~25,800 | 13,618 code + 8,796 tests | Use one basis for all four |
| N2 | Ninad LOC | ~23,498 | 23,498 code + 9,078 tests | — |
| N3 | Nandagopal LOC | ~9,179 | 9,179 code + 2,321 tests | — |
| N4 | Surya LOC | **~5,162** | **2,162** code + 235 tests | Typo or a different basis |
| N5 | Hours (~110 / 120 / 110 / 95) | stated as fact | Not measurable from the repository | [TEAM INPUT NEEDED]: confirm, or drop |
| N6 | Curated questions | 132 (p.14, p.29, Fig 3.1a) | **156** (after the 2026-10-03 repairs) | Update |
| N7 | "Project ~85% complete" (p.29) | — | Judgement call | Keep only if the team agrees |

---

## 4. Diagram-by-diagram

| Figure | Verdict | Fixes |
|---|---|---|
| **3.1a LLD overview** | Mostly accurate flow | Module labels (C4); "132 curated" → 156 (C6); in M2, `followup.decide` → "next · clarify · probe"; show `answer_gate` *after* `AveragedEvaluator` inside `evaluation_engine` (it is); add the grader's caps (contradiction, similarity floor) if space allows |
| **3.1b "Master class diagram"** | Good **architecture** diagram, mislabelled | Rename (C2). "Question Bank 422 slide-verified Qs" → "422 generated · 156 served". Optionally add the Web Speech API (browser) |
| **3.1c Package diagram** | Correct | Add «use» Web API → Evaluation (via the conversation engine), or note that Round 1 owns that dependency. Fine as is |
| **3.2 Use case** | One wrong relationship | C3. Optional: add "Manage profile & resumes". «supplies questions» is not a standard UML stereotype; use a note or «trace» |
| **3.4 Sign-up sequence** | Correct apart from I21 | Add the 409 duplicate-email branch |
| **3.7 Technical answer + follow-up** | Branch guard too narrow | I18 (score ≥ 0.70 guard + clarify branch); step 11 "save turn" happens only when the question closes |
| **3.10 Full interview** | Missing the Round-1 end call; combined report source wrong | C8 |
| **3.13 Proctoring violation** | Correct | Optional: `POST /end` → name both endpoints (`/resume-discussion-v2/end` or `/tech-interview/<id>/end`, whichever round is running) |
| **3.14 Deployment** | Correct | `face_landmarker.task` (the model file) is served by **Flask** `/static`, only the MediaPipe JS library comes from the CDN; add the Hugging Face Hub (first-run model download) and the Google speech service (Web Speech API) under Cloud |

---

## 5. Template leftovers and formatting (minor)

| # | Issue | Fix |
|---|---|---|
| T1 | TOC still has template placeholders ("Class Name 1", "Data Members 1", "Method 1/2") and wrong page numbers (almost everything "4/5/6/7") | Regenerate the TOC from the real headings |
| T2 | Section numbering broken: classes under §3.3 are numbered **3.2.4.x**, under §3.4 **3.2.5.x**, under §3.5 **3.2.6.x**; sequence sections are numbered 3.2.5 / 3.2.6 / 3.2.7 | Renumber: 3.3.3.x, 3.4.3.x, 3.5.3.x; sequences 3.3.4, 3.4.4, 3.5.4 |
| T3 | "For Example" (template text) left above every class and sequence figure; "…" placeholders under each module heading | Delete |
| T4 | The same use-case table (Take Full Interview / Monitor attention) is pasted into all four modules | Each module lists its own use cases (Module 1: Sign up & upload resume, Answer Round-1 question; Module 2: Take Technical Interview, Answer follow-up, Generate question bank; Accounts: Log in, View report & history, Manage profile; Webcam: Camera setup check, Monitor attention, Enforce session rules, Terminate) |
| T5 | "Packaging and Deployment Diagrams" sections show only the deployment diagram | Add the package diagram (Fig 3.1c) reference to each, or retitle "Deployment" |
| T6 | Access modifiers "private / public" throughout | Python and JS (as used here) don't enforce them; say "public attribute", or "internal (underscore)" for `_current` etc. |
| T7 | §3.4 module heading in TOC "Module 3 – Accounts" vs §3.5 "Module 4 – Webcam" | Follow C4 |
| T8 | References [1]–[10] are never cited in the text | Cite them where used (SBERT [1] in §3.3, DeBERTaV3 [2], MultiNLI [3], reranker [4], RAG [5], Qwen3 [6], FAISS [7], BM25 [8], MediaPipe face mesh [9], QWK [10]) |
| T9 | Missing references | Add: MediaPipe framework (Lugaresi et al., 2019), Hugging Face Transformers (Wolf et al., 2020), MiniLM (Wang et al., 2020), CORAL ordinal regression (Cao et al., 2020), Qwen3-VL-2B (vision stage) |
| T10 | Appendix C change history: "Panel Review 1 asked for application-speed improvements and stronger proctoring" | [TEAM INPUT NEEDED]: confirm against the actual Review 1 remarks |

---

## 6. Things the PDF gets right (keep)
- Overview, scope, constraints and assumptions (§1–2) are accurate, apart from §1.1's "regression" and the gate placement (I9, I11).
- `User.check_password`, `User.current_resume`, `InterviewSession` members and `to_dict(include_turns=False)` match the code.
- `computeAttentionScore` pseudo-code matches exactly (100 − 4·warnings − 6·face-absent − 5·liveness failures − min(20, 0.25·seconds away)).
- `initializeGazeMonitoring` behaviour, the deployment diagram, the package diagram and the sign-up and violation sequences are essentially correct.
- The traceability matrix is consistent with the module split.

## 7. Suggested order of work
1. C1–C9 (critical).
2. Renumbering and TOC (T1–T3, C4).
3. Section 2 method and pseudo-code fixes (I1–I24).
4. Numbers (Section 3).
5. Diagram touch-ups (Section 4).
6. References (T8–T9).
