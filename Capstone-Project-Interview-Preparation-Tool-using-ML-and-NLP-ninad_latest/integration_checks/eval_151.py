"""Heuristic vs trained model vs averaged evaluator on the teammate's 151 held-out test answers.

    python integration_checks/eval_151.py

Uses the app in main_cap/cap (bootstrap must activate the averaged evaluator,
i.e. deployed_model_overall_single_v5_1088/ must hold the real weights) and the
dataset (copied from his branch's artifacts/overall_v5_1088/dataset into integration_checks/data/overall_v5_1088/).
Gold tier = score_to_tier(labels.overall_label.score), the teammate's own policy.
"""
import io
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CAP = os.path.join(ROOT, "main_cap", "cap")
DATA = os.path.join(ROOT, "integration_checks", "data", "overall_v5_1088")
sys.path.insert(0, CAP)
os.chdir(CAP)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import logging
logging.disable(logging.WARNING)

import deployment_evaluator
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluator_registry import get_active_evaluator
from question_families import ReasoningType
from question_specification import QuestionSpecification


def tier(s):
    return 4 if s >= .8 else 3 if s >= .6 else 2 if s >= .4 else 1 if s >= .25 else 0


def qwk(a, b, n=5):
    O = np.zeros((n, n))
    for x, y in zip(a, b):
        O[x, y] += 1
    W = np.array([[(i - j) ** 2 / (n - 1) ** 2 for j in range(n)] for i in range(n)])
    E = np.outer(O.sum(1), O.sum(0)) / O.sum()
    return 1 - (W * O).sum() / (W * E).sum()


deployment_evaluator.bootstrap_production_evaluator()
averaged = get_active_evaluator()
assert averaged.name.startswith("averaged-"), f"averaged evaluator not active: {averaged.name}"
evaluators = {"our heuristic": averaged.heuristic, "his model": averaged.model, "AVERAGE": averaged}

split = json.load(open(os.path.join(DATA, "split.json"), encoding="utf-8"))
test_ids = set(split["test_ids"])
rows = [json.loads(l) for l in open(os.path.join(DATA, "examples.jsonl"), encoding="utf-8")]
rows = [r for r in rows if r["metadata"]["example_id"] in test_ids]
gold = [r["labels"]["overall_label"]["score"] for r in rows]
words = [len(r["inputs"]["answer_text"].split()) for r in rows]
print(f"{len(rows)} test answers; gold/length correlation {np.corrcoef(gold, words)[0, 1]:.2f}")

preds = defaultdict(list)
t0 = time.time()
for i, r in enumerate(rows):
    inp = r["inputs"]
    req = EvaluationRequest(
        request_id=f"t{i}", requested_at="2026-09-30T00:00:00+00:00",
        specification=QuestionSpecification.model_validate(inp["specification"]),
        question_text=inp["question_text"], reasoning_type=ReasoningType(inp["reasoning_type"]),
        answer_text=inp["answer_text"], conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=tuple(inp.get("expected_concepts") or ()),
    )
    avg = averaged.evaluate(req)
    raw = dict(avg.raw_model_output)
    preds["our heuristic"].append(raw["heuristic_overall"])
    preds["his model"].append(raw["model_overall"])
    preds["AVERAGE"].append(avg.overall_score)
print(f"({time.time() - t0:.0f}s)")
g = [tier(x) for x in gold]
print(f"\n{'evaluator':<16}{'QWK':>6}{'exact':>7}{'within1':>9}{'r':>6}{'|err|':>7}{'len-corr':>9}")
for name, p in preds.items():
    t = [tier(x) for x in p]
    print(f"{name:<16}{qwk(g, t):6.2f}{np.mean(np.array(t) == np.array(g)):7.0%}{np.mean(abs(np.array(t) - np.array(g)) <= 1):9.0%}"
          f"{np.corrcoef(p, gold)[0, 1]:6.2f}{np.mean(np.abs(np.array(p) - np.array(gold))):7.2f}{np.corrcoef(p, words)[0, 1]:9.2f}")

json.dump({"gold": gold, "words": words, **{k: v for k, v in preds.items()}},
          open(os.path.join(ROOT, "integration_checks", "baseline_results", "eval151_scores.json"), "w"), indent=0)
