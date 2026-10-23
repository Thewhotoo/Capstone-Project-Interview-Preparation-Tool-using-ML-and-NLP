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

## Collecting human labels (the missing piece)

Every evaluator number above is measured against labels Claude wrote. Real answers labelled by people are
what turn "matches an LLM on our benchmark" into a defensible claim. About an hour of work:

1. **Interviews (~30 min total).** 4–6 people each do one Resume Discussion in the app with their own
   résumé (10 questions each, so 40–60 answers). Ask them to answer naturally, and to answer a couple of
   questions badly on purpose (vague, wrong, off-topic), so every score range is represented. They must
   tick the data-consent box; `collect_answers.py` skips anyone who didn't.
2. **Export:** `py -3.13 benchmarks/evaluator/collect_answers.py` (safe to re-run; only adds new answers).
3. **Label blind (~20 min per person):** two people each run
   `py -3.13 benchmarks/evaluator/label_answers.py --annotator <name>` and score every answer 0–4 using the
   rubric it prints. They should not discuss scores or look at the app's grades first.
4. **Check agreement:** `label_answers.py --agreement`. QWK between the two people is the realistic ceiling;
   an evaluator close to it is about as good as a second human grader.
5. **Score:** `score_evaluator.py --factcheck --by-kind` now also reports a `## human` section.

If the evaluator's ranking on real answers is well below the stress-set numbers, the stress sets are
missing a kind of answer that real candidates give. Add examples of that kind to a NEW held-out file
rather than tuning on the human set, which must stay a clean test.

## External human-graded benchmark: Mohler (2026-10-24)

`external/mohler_benchmark.py` — real student answers to data-structures questions, each graded 0–5 by two
computer-science graders (Mohler et al., ACL 2011; CC-BY-4.0). Independent of this project, so it tests
reference-based **correctness** grading (the knowledge gap) against humans. 496-answer stratified sample of
the ten consistently graded assignments:

| scorer vs the two graders' average | Pearson | Spearman | QWK |
|---|---|---|---|
| human grader 1 vs grader 2 (ceiling) | 0.62 | 0.60 | 0.54 |
| qwen2.5:3b given the reference answer | **0.65** | **0.65** | **0.56** |
| 0.25 × Technical Interview grader + 0.75 × qwen (weight picked on this data) | 0.68 | 0.70 | 0.60 |
| Technical Interview grader (NLI key points) | 0.44 | 0.50 | 0.23 |
| coverage-NLI correctness scorer | 0.28 | 0.30 | 0.17 |

The local 3B model agrees with the expert average about as well as one expert agrees with the other;
NLI-only grading does not.

## Realistic résumé answers, two annotators (2026-10-24)

`evaluator/private/resume_set_v1.json` (private) — 72 answers in natural candidate voices on the real
benchmark résumés' projects, labelled by two independent Claude annotators (the second, a separate agent,
saw only the rubric and the answers). Their agreement (QWK 0.97) is far above the human experts' 0.54 on
Mohler: same-model annotators share judgment, so treat these labels as consistent, not as human.

| evaluator | pairwise (within question) | Spearman | QWK |
|---|---|---|---|
| evidence v2 (no LLM) | 67% | 0.44 | 0.42 |
| evidence v2 + qwen fact check + grade blend | **83%** | 0.77 | 0.70 |
| qwen2.5:3b alone | 76% | **0.85** | **0.77** |

Our blend ranks answers to the same question better than the LLM alone; the LLM alone is better calibrated
across questions. The blend weight was not re-tuned on this set (it is a test set).

## Model choice and final configuration (2026-10-24)

Small models that fit a 4 GB laptop GPU, on the same 248 Mohler answers (Pearson vs the experts' average;
two experts agree at 0.59): **qwen3:4b 0.73**, phi3.5 0.64, qwen2.5:3b 0.54–0.58, gemma2:2b 0.44.
Grading prompts use a JSON schema (qwen3 otherwise echoes the question and runs out of tokens).

Tuned on `evaluator/dev_set.json` only (48 answers): qwen3:4b beats qwen2.5:3b in every blend design;
"reason first" / checklist prompts and an asymmetric guard gave no reliable gain; LLM blend weight 0.6
(same ranking as 0.5, better calibration). Then each test set was run once:

| test set | old: v2 + qwen2.5:3b, w 0.5 | **new: v2 + qwen3:4b, w 0.6** | qwen3:4b alone |
|---|---|---|---|
| stress (54) pairwise / QWK | 85% / 0.66 | **88% / 0.73** | – |
| holdout (40) pairwise / QWK | 79% / 0.66 | **84% / 0.69** | – |
| résumé, 2 annotators (72) pairwise / Spearman / QWK | 83% / 0.77 / 0.70 | **89% / 0.83 / 0.77** | 85% / 0.84 / 0.83 |

qwen3:4b only partly fits a 4 GB GPU (~28% runs on CPU, ~0.9 GB system RAM, ~3.5 s per call); it runs in
the background re-grade, and `fact_checker` falls back to qwen2.5:3b when qwen3 isn't installed.
