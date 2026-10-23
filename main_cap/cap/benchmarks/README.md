# Benchmarks

Measure the parser and the answer evaluator against reference labels, so claims like "as good as an LLM" become numbers.
Run everything from `main_cap/cap` with the Python that has the engine deps (`py -3.13`).

`private/` folders are gitignored: they hold real people's résumés-derived gold and real answers.

## Parser — `parser/score_parser.py`

Field-level accuracy of the live `resume_engine` against hand-labelled gold.
Gold: `parser/gold_templates.json` (8 fictional Canva templates) + `parser/private/gold_real.json` (7 real résumés).
Résumé PDFs are read from `$PARSER_BENCH_ROOT` (default `~/Downloads`).

```
py -3.13 benchmarks/parser/score_parser.py --errors              # run the engine, print every miss
py -3.13 benchmarks/parser/score_parser.py --predictions x.json  # score another parser / an LLM's output
```

Baseline, 2026-10-23 (15 résumés):

| field | real (7) | templates (8) |
|---|---|---|
| name / email / phone | 1.00 / 1.00 / 1.00 | 0.88 / 1.00 / 1.00 |
| projects F1 | 0.91 | 1.00 |
| project technologies F1 | 0.81 | 1.00 |
| skills F1 | 0.90 | 0.42 |
| education F1 | 0.57 | 0.80 |
| experience F1 | 0.53 | 0.18 |
| certifications F1 | 0.80 | 0.54 |

Main failure modes: company/role swapped or company left empty; school-level education dropped; inline
certification lists merged into one string; multi-column templates scramble experience and skills.

## Evaluator — `evaluator/score_evaluator.py`

Agreement of each answer evaluator with labels on the 0–4 tier rubric (see `label_answers.py`).
Main metric is **pairwise**: of two answers to the same question with different labels, how often does
the evaluator rank them the right way. `len_rho` shows how much the evaluator rewards length.

```
py -3.13 benchmarks/evaluator/score_evaluator.py --by-kind
py -3.13 benchmarks/evaluator/score_evaluator.py --judge llm=llm_scores.json   # compare an LLM judge
```

Sources:
- `evaluator/stress_set.json` — 54 contrastive answers over 6 projects, labelled by Claude *before* any
  evaluator was run. Used to design evidence scoring v2, so it is no longer an unbiased test.
- `evaluator/stress_set_holdout.json` — 40 fresh answers over 5 new projects, written after v2 was designed
  and before it was run on them. Don't tune on it; write a new one if you do.
- `evaluator/private/human_items.jsonl` — real answers. Collect + label them:
  ```
  py -3.13 benchmarks/evaluator/collect_answers.py          # export answered turns from instance/app.db
  py -3.13 benchmarks/evaluator/label_answers.py --annotator <you>
  py -3.13 benchmarks/evaluator/label_answers.py --agreement # inter-annotator QWK = the realistic ceiling
  ```

Baseline on the stress set, 2026-10-23:

| evaluator | pairwise | spearman | qwk | len_rho (labels: +0.36) |
|---|---|---|---|---|
| heuristic | 67% | +0.42 | 0.30 | +0.88 |
| v5_1088 | 74% | +0.48 | 0.46 | +0.53 |
| evidence (live) | 73% | +0.45 | 0.39 | +0.57 |

Mean score by answer kind (0–100): the live evidence evaluator gives fluent-but-wrong answers 60 vs 64 for
strong ones, and generic textbook answers 59 vs 58 for short correct ones — it cannot tell correct from
plausible-sounding. v5 rates answers built around tech that isn't on the résumé at 87.

### Evidence scoring v2 (2026-10-23)

`resume_evidence_evaluator.py` now defaults to scoring v2 (`CAP_EVIDENCE_SCORING=v1` rolls back).
Similarity only gates "is it on topic"; the score comes from explanation (reasoning connectives, weighted by
question type), specificity (implementation-level terms from `implementation_vocabulary.py`, acronyms,
technical compounds), concrete detail and grounded ownership, with keyword-list and textbook penalties.

Fresh held-out set (40 answers, 5 projects):

| evaluator | pairwise | spearman | qwk |
|---|---|---|---|
| evidence v1 | 61% | +0.22 | 0.21 |
| evidence v2 | 72% | +0.43 | 0.51 |
| v5_1088 | 72% | +0.53 | 0.41 |

Mean score by kind, v1 -> v2: keyword list 24 -> 11, textbook 49 -> 26, short-correct 56 -> 58 vs honest-partial
58 -> 34 (now ordered correctly), short-wrong 54 -> 23. **Still unsolved:** fluent-but-wrong 65 vs strong 67
(needs knowledge), strong answers score only ~67 (range still compressed), unsupported-tech 52 (the tech
gazetteer doesn't know GPT-4/LangChain etc.).
