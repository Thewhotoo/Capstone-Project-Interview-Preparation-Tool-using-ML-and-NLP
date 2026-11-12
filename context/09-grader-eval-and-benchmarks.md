# 09 — Grader evaluation & benchmarks

## Round 2 grader: `grader_eval/` (Ninad)
Run from repo root.
```bash
python grader_eval/benchmark.py                 # fast grader vs every labelled set; compares with baseline.json, fails on regression
python grader_eval/benchmark.py --llm           # with the LLM blend (needs Ollama; verdicts cached in llm_judge_cache.jsonl) vs baseline_llm.json
python grader_eval/benchmark.py --show-worst    # worst disagreements
python grader_eval/benchmark.py --save-baseline # only when an intended change improves things
python grader_eval/sanity_check.py [--all|--ids ...]   # bank self-consistency (no labels)
python grader_eval/human_eval.py answers|labels|gold --people ninad,mayuran,surya,nandu
python grader_eval/frontier_eval.py export|import|report --set fresh [--model X --file reply.json]
```
Sets (each answer labelled per key point covered/partial/missing + `overall` 0–1):
| set | file | nature | use |
|---|---|---|---|
| llm400 | `output_questions.json` (from `questions.json` + `PROMPT.md`) | 400 LLM answers, 8 styles | tuning |
| mine40 | `my_answers.json` | 40 typed by a team member (+ follow-up replies) | tuning |
| team_tune / team_test | `real_set/*_answers.json` (`ANSWER_PROMPT.md`) | LLM answers in human styles, labels corrected by members | tune / held-out |
| fresh | (in benchmark) | **never tuned on** | headline number |
| human_answers | `human_set/human_answers.json` | 28 real team answers, LLM-labelled | test (added 2026-11-07) |
| human | `human_set/gold.json` (from human_eval) | real answers, blind 2-person labels | claims about humans |
- Benchmark skips "stale" answers whose question was rewritten after labelling (`label_basis.json`).
- Metrics: keypoint_agreement, decision_agreement (score ≥ .70 move-on), pearson_r, mean_abs_diff, pair_order, good_avg, confident_wrong_avg, followup_accuracy, wrong_followups_accepted.

Current baselines (fast → with LLM blend):
| set | decision | r | mean abs diff | confident-wrong avg |
|---|---|---|---|---|
| llm400 | .918 → .934 | .873 → .965 | .126 → .079 | .133 → .068 |
| fresh | .66 → .80 | .55 → .848 | .235 → .13 | .291 → .166 |
| human_answers | — → .75 | — → .64 | — → .107 | |
Frontier (fresh): Gemini/Claude ~86–88% decision, r .93–.95 (`grader_eval/frontier/`).
Rule: tune on llm400/mine40/team_tune; judge on fresh/team_test/human sets.
Test: `main_cap/cap/test_grader_benchmark.py`.

## Round 1: `main_cap/cap/benchmarks/` (Mayuran)
Run from `main_cap/cap`. See `benchmarks/README.md`.
- `parser/score_parser.py [--errors] [--predictions x.json]` — resume parser field F1 (gold_templates.json + private real gold; PDFs from `$PARSER_BENCH_ROOT`).
- `evaluator/score_evaluator.py [--by-kind] [--judge llm=file]` — pairwise ranking / spearman / QWK / len_rho for Round 1 evaluators. Sets: `stress_set.json` (designed v2 on it — biased), `stress_set_holdout.json` (don't tune), `dev_set.json` (chose LLM weight .6), `final_test_set.json`, `factcheck_{dev,test}_set.json`. `collect_answers.py` exports real turns from app.db; `label_answers.py` for human labels + agreement.
- `external/mohler_benchmark.py` — Mohler short-answer dataset (LLM model choice: qwen3:4b r .73 vs experts .59).
- qwen3:8b vs 4b (Round 1): final test pairwise 84% → 94%, QWK .79 → .86.
