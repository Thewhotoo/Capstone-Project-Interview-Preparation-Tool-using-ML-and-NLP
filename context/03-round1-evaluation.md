# 03 — Round 1: answer evaluation

## Contracts
- `evaluator.py`: `Evaluator` Protocol — attrs `name, version, declared_dimensions, declared_reasoning_types, requires_network`; method `evaluate(EvaluationRequest) -> EvaluationResult`. Stateless. `check_conformance` runs once at registration if a sample request is given.
- `evaluator_registry.py`: module-global dict; `register_evaluator(e, make_active=True)`, `get_active_evaluator()`, `get_evaluator(name)`. Not thread-safe; same name overwrites.
- `evaluation_request.py`: frozen `EvaluationRequest(request_id, specification, question_text, reasoning_type, answer_text, conversation_context: ConversationContextSnapshot(prior_answers_for_this_spec, …), evaluation_focus, expected_concepts, answer_key)`.
- `evaluation_result.py`: frozen `EvaluationResult` (overall_score 0–1, grade, confidence(+source, rationale), reasoning (non-empty), dimensions[DimensionScore], strengths/weaknesses [EvidenceLinkedClaim(claim, dimension, evidence)], missing_reasoning, concept_coverage, suggested_improvements, recommended_topics, contradiction_detected, model/dataset versions, raw_model_output…).
- `evaluation_engine.py`: `build_request(...)` (the ONE boundary between planning and evaluation; looks up `expected_concepts` via `expected_concepts_registry` — only for SKILL_IN_CONTEXT (text_seed) and CERTIFICATION; none for project/experience) and `evaluate(evaluator, request) = apply_engagement(request, gate(request, evaluator.evaluate(request)))`. `EvaluationLedger` = append-only list per session.

## Active evaluator tiers (`deployment_evaluator.bootstrap_production_evaluator`)
| Tier | Evaluator | When |
|---|---|---|
| 0 | `ResumeEvidenceEvaluator` (scoring v2), name `resume-evidence-evaluator-v2` | default; `CAP_RESUME_EVIDENCE_EVALUATOR=0` skips. **This is what production uses.** |
| 1 | `AveragedEvaluator(HeuristicEvaluator, OverallSingleEvaluator)` = 0.8×DeBERTa v5_1088 + 0.2×heuristic | weights in `deployed_model_overall_single_v5_1088/` (≥1 MB, i.e. not an LFS pointer) + approved promotion; `CAP_TRAINED_EVALUATOR=0` skips. backbone deberta-v3-base, max_length 256 |
| 2 | `HybridEvaluator(Heuristic, TrainedEvaluator)` | `deployed_model/` with all 3 files — weights absent, never loads |
| 3 | `HeuristicEvaluator` | fallback |
Bootstrap never raises.

## ResumeEvidenceEvaluator (`resume_evidence_evaluator.py`)
Philosophy: résumé questions are experiential → technical correctness can't be verified without an answer key, so it scores *evidence*, never length/tone.
`compute_evidence(request)` → `EvidenceBreakdown`:
- `relevance` = rescaled SBERT sim(answer, question) [0.10–0.32]; `grounding` = rescaled sim(answer, grounding text) [0.08–0.33]
- `on_topic` = rescale(max(raw rel, raw grounding), 0.08, 0.22) — **gate only**
- `concreteness` = 0.4·min(1, numbers/2) + 0.6·min(1, 1.5·share of résumé terms used)
- `substance` = min(1, reasoning connectives/2) ("because", "instead of", "trade-off", …)
- `specificity` = min(1, (implementation_vocabulary terms not in question + 0.5·acronyms/hyphen-compounds)/3)
- `ownership`: 0.2 if no first-person/action clause; 0.15 if contradicts résumé; else 0.30+0.70·max(grounding, concreteness)
- flags: generic_textbook, keyword_list, non_answer, degenerate:*, self_correction, mentions_technology_not_in_grounding:X (gazetteer tech not in this project's grounding), unsupported_or_conflicting_ownership, contradicts_solo_ownership_claim, contradicts_prior_answer (NLI vs prior answers same spec)
`_compose_overall_v2`: `asks_why` (reasoning_type in trade_off_analysis/debugging/optimization/explanation/reflection) → quality = .35 substance + .35 specificity + .15 concreteness + .15 ownership; else .15/.50/.20/.15. overall = on_topic·(0.10+0.90·quality), then ×0.55 generic, ×0.50 keyword list, ×0.75 unsupported ownership, ×0.5 contradicts solo, ×0.6 unlisted tech, ×0.85 contradicts prior, ×0.45 factual_error_confirmed; non-answer/degenerate cap 0.10.
If a fact checker is injected: `+ LLM rubric grade` → `overall = 0.6·llm + 0.4·evidence` (`LLM_BLEND_WEIGHT`).
Grades: ≥.90 excellent, ≥.75 good, ≥.55 adequate, ≥.30 weak, else poor. Confidence = evidence strength. Dimensions come from `HeuristicDiagnosticsEngine` (4 canonical: technical_correctness, depth_specificity, relevance_completeness, grounding_ownership) — display only. `CAP_EVIDENCE_SCORING=v1` rolls back.
Evidence is cached (64 LRU) so the background re-grade only adds LLM calls.

## Post-processing applied to every evaluator
- `answer_gate.py` `check_answer` → cap at 0.1 / "poor", clear strengths, add weakness. Reasons: too_short (<3 tokens), non_answer ("idk/not sure/…" with <6 content words, ≤40 words), deflection (every sentence ends "?"), control chars, markup_or_code (with function-word ratio <.25), non_linguistic, keyword_dump, comma_list, repetitive (windowed TTR <.45 or bigram repeat >.30).
- `answer_engagement.py`: echo detector. If SBERT sim(answer, question) ≥ 0.55, multiplier = min(1, novelty/0.25) where novelty = share of answer content words not in question. Downward only. (An off-topic detector was tried and rejected — see docstring.)

## Background LLM re-grade (conversation_engine)
- Enabled by `CAP_FACT_CHECK`: `auto` (default; checks Ollama every 300 s) | `1` | `0`. Only for ResumeEvidenceEvaluator v2 sessions and scores > 0.10.
- One worker thread; regrader = `ResumeEvidenceEvaluator(scoring="v2", fact_checker=OllamaFactChecker(), name="resume-evidence-evaluator-v2+llm")`, run through the same `evaluate()` (gate applies). Result stored at `regrade:<conv>:<i>`.
- At `/end`: wait ≤30 s total; finished ones replace ledger results; `session_history._apply_regrades` overwrites `overall_score, grade, confidence, confidence_rationale, reasoning` and sets `llm_regraded: true` on saved turns.

## Fact checker (`fact_checker.py`, `OllamaFactChecker`)
- Model: `CAP_FACT_CHECK_MODEL` or first installed of `PREFERRED_MODELS = (qwen3:8b, qwen3:4b, qwen2.5:3b)`; `CAP_OLLAMA_URL` default localhost:11434; `think=False` for qwen3; JSON-schema-constrained output; temp 0.
- `check()`: LLM lists false general claims → a claim is CONFIRMED only if not a personal flip, not a technology-choice swap, NLI (`nli-deberta-v3-small`) contradiction ≥0.5 in BOTH directions, and a second LLM call says "incorrect". Only confirmed claims penalise/shown.
- `grade()`: 0–4 rubric → /4.
- `llm_requirement.ensure_llm_ready()` uses this class at startup.

## Other Round 1 helpers
- `heuristic_evaluator.py` — legacy "heuristic-v1" (SBERT similarity + NLI contradiction + marker lists); supplies shared helpers (`_semantic_similarity`, `_grounding_text`, `_grounding_terms`, `_rescale`, `_contradiction_flag`, `_LazyModels`). Grade cutpoints same as above.
- `strong_answer.py` — deterministic "coaching note" appended to candidate's own answer (`build_improved_answer`, `coaching_note`).
- `concept_analysis.concept_coverage_percent(result)` — None if no concept pool.
- `tech_consistency_flag.py` — informational: does the stack the candidate describes contradict the project's listed technologies (NLI contra ≥0.85 and support ≤0.20, plus guards). Never touches score.
- `interview_feedback.build_feedback(evaluations, timeline, tech_consistency)` — end-of-session text; says plainly it doesn't verify facts.
- `averaged_evaluator.py`, `overall_single_evaluator.py`, `overall_score_model.py`, `hybrid_evaluator.py`, `model_*.py` — DeBERTa path (see `10`).
- `correctness_nli_scorer.py`, `answer_key*.py` — reference-anchored scorer; `degeneracy()` is used by the evidence evaluator; answer keys almost never present.

## Benchmarks
`benchmarks/evaluator/score_evaluator.py` (pairwise ranking, QWK, len_rho) on `stress_set.json` (tuned on), `stress_set_holdout.json` (don't tune), `dev_set.json`, `final_test_set.json`, fact-check sets. `benchmarks/README.md` has results. External: `benchmarks/external/mohler_benchmark.py`.

## Tests
`test_resume_evidence_evaluator.py`, `test_answer_gate.py`, `test_answer_engagement.py`, `test_fact_checker.py`, `test_llm_regrade.py`, `test_evaluation_engine.py`, `test_deployment_evaluator.py`, `test_displayed_dimensions.py`, `test_tech_consistency_flag.py`, `test_strong_answer.py`, `test_interview_feedback.py`.
