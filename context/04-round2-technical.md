# 04 — Round 2: technical interview (`main_cap/cap/tech_interview/`)

Owner: Ninad. Routes in `session_routes.py`, persistence in `session_history.py` (see `01`, `06`).
Lengths: `TECH_INTERVIEW_LENGTHS = {"standalone": 10, "round2": 8}`; `MAX_ANSWER_CHARS = 5000`.

## bank.py
- Dir: `CAP_QUESTION_BANK_DIR` or `rag_system/rag_tester/question_bank/` (all `*.json`). `lru_cache` — **restart the app after editing the bank.**
- Loads only `active: true`. `CAP_CURATED_ONLY` (default 1) → serve only `curated: true` (falls back to all active if none). `question_by_id` sees all active.
- `CAP_GRADER_ENRICHMENT`: `off | replies (default) | all`. replies = use `followup_replies`; all = also key-point `variants` + `core_point` (measured to let wrong answers through → off).
- Dataclasses: `KeyPoint(point, followup, followup_answer, variants, followup_replies)`, `Question(id, subject, topic_id, topic, difficulty, text, reference_answer, key_points, confidence, source_pages, core_point, core_variants, curated, interview_priority)`.
- Current bank: 425 total, 323 active, 321 curated (cn 48, dbms 76, dsa 54, ooad 66, os 77). Curated difficulty: 104 easy / 192 medium / 25 hard. Priority tiers 3/2/1: 148/142/31.

## selector.py — `select_questions(bank, n, seen_ids, topic_scores, rng)`
Unseeded `random.Random()` (not deterministic, intentionally).
- `difficulty_plan(n)`: easy=max(1, round(.2n)), hard=max(1, round(.15n)) if n≥4, rest medium → 8: 2/5/1, 10: 2/6/2.
- Subjects shuffled, round-robin per slot. Never repeat a topic in a session.
- Candidate tiers relaxed in order: (subject+level+unseen) → (subject+unseen) → (level+unseen) → unseen → any.
- Weight = (0.5+confidence) × `INTERVIEW_PRIORITY_WEIGHT {3:6, 2:1, 1:0.2}` × (1 + 2·(1−avg topic score)) if user answered that topic before.
- Final list stable-sorted easy→medium→hard.

## grader.py — `grade_answer(question, answer)` → `Grade`
Models (lazy singletons, fail soft): `all-MiniLM-L6-v2` embed, `cross-encoder/nli-deberta-v3-base` NLI.
1. `analyse_clarity` → `Clarity(words, fillers, filler_ratio, dont_know (regex & ≤25 words), too_short (<8 words), vague, repetitive)`; `unclear` = filler_ratio ≥ .06 or vague or repetitive.
2. `strip_fillers`, `expand_terms` (terms.py, per-subject abbreviation expansion, both sides).
3. `_chunks`: sentences, adjacent pairs, 20/40-word windows (stride 10/20), whole answer.
4. Per key point: entail = max over chunks; sim = max cosine. `classify_point`:
   - sim < `CREDIT_SIM_FLOOR` .25 → missing
   - covered: e ≥ .60 or (e ≥ .20 and sim ≥ .80)
   - partial: e ≥ .05 and (sim ≥ .60 or e ≥ .30)
   - no NLI: sim ≥ .55 covered / ≥ .40 partial
   Optional variants (enrichment "all") checked against top-4 chunks, minus what the question alone implies.
5. kp_score = (covered + .5·partial)/n; `core_point` covered → floor .75.
6. ref = clip((ref_sim − .35)/(.80 − .35)); `combine(kp, ref) = .85·kp + .15·ref·min(1, kp/.5)`.
7. Caps: dont_know & nothing covered → ≤ .1; too_short → ≤ .5; **contradiction cap**: NLI P(reference contradicts whole answer) ≥ .50 → ≤ .20 (`CONTRA_THRESHOLD`, `CONTRA_CAP`).
`followup_covers(key_point, reply, subject)` → covered/partial/missing: dont_know → missing; yes/no rule for polar questions; near-match (sim ≥ .85) with a known `followup_replies` → covered; NLI over [point + claims of expected answer], also reply read with the question minus question-alone entailment; covered ≥ .50, partial ≥ .20 or sim ≥ .60.

## followup.py — `decide(...)` → `Decision(kind next|clarify|probe, text, key_point, reason)`
`MAX_FOLLOWUPS = 2` (clarifications count), `GOOD_SCORE = 0.70`.
Order: dont_know → next · limit reached → next · score ≥ .70 and clear → next · unclear and not yet clarified → clarify (3 rotating templates) · first missing-then-partial point with a prepared followup not yet asked → probe · else next.

## session.py — `TechInterview`
- `prompt()` → `{number, total, subject, subject_label, topic, difficulty, question_id, kind: question|clarify|followup, text, main_question?}`.
- `submit(answer)`: main answer graded; clarify reply → re-grade `answer + clarification`; follow-up reply → `followup_covers`, recovered point earns `RECOVERED_CREDIT = 0.75` of full credit (`_apply_recovered`, keeps contradiction cap).
- Closed question record: `question_id, subject(_label), topic_id, topic, difficulty, question, answer, score, covered/partial/missing, first_grade, final_grade, exchanges[{kind, prompt, answer, key_point?, verdict?, scores?, expected?}], closed_because, reference_answer, key_points, source_pages`.
- `to_state()/from_state()` full JSON (questions stored whole, so bank edits can't alter a live interview).
- `summary()`: average, by_subject, by_difficulty, followups_asked, weak_topics (<.5).

## llm_judge.py — background re-grade (local Ollama)
- `CAP_TECH_LLM_GRADE` auto (default; Ollama check every 300 s) | 1 | 0. `CAP_TECH_JUDGE_MODEL` or first of `(qwen3:8b, qwen3:4b)`. temp 0, num_ctx 4096, JSON schema, think=False. Timeouts 60 s (120 s cold).
- `judge()` → per-point verdicts, `wrong` flag, holistic `score` 0–1. `judge_followup()` per follow-up reply.
- `followup_verdict(fast, llm)`: accept only if BOTH accept (less generous wins).
- `blended(record, judged)`: holistic += .85·(gain from follow-up recoveries); same dont_know/too_short caps; `score = 0.6·holistic + 0.4·fast score` (`LLM_WEIGHT`); cap .20 if `wrong` OR (fast contradiction cap AND LLM holistic < .5 — `CONTRADICTION_CAP_BELOW`, added 2026-11-07). Report's covered/partial/missing come from the LLM verdicts.
- `queue(session_id, index, question, record)` → 1-thread pool → store `techregrade:<sid>:<i>`; `collect(sid, count, wait)`.
- Applied by `session_history.apply_tech_regrades` (sets `record["llm_grade"]`, `fast_verdict` on exchanges, updates saved turns).

## Measured (grader_eval, see 09)
fresh (never tuned) set: fast grader decision 66% / r .55 → with LLM blend 80% / r .85. Frontier LLMs ~86–88% / r .93–.95.

## Recipes
- Tune a threshold → run `python grader_eval/benchmark.py` (fast) and `--llm` (blend); it fails on regression vs `baseline*.json`; judge on `fresh`/`human_answers`, not tuning sets. Update baseline with `--save-baseline` only when intended.
- Add an abbreviation → one line in `terms.py` `TERMS[subject]`.
- Fix a bad question → a repair batch (see `08`), then `python grader_eval/sanity_check.py --ids <id>`.
- Tests: `test_tech_interview.py`, `test_grader_benchmark.py`, `test_tech_interview_ui.js`.
