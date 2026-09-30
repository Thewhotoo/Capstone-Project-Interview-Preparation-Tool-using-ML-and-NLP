"""Score v4_eval.py outputs against the V4 diagnostic gold grades.

    python integration_checks/score_v4.py v4_ours.json v4_theirs_model.json [...]

Gold overall = mean of the four gold dimension tiers / 4 (the friend's own
policy, colab_training/evaluate_on_v4_v5.py). Prints QWK, correlation,
pair-ordering, "strong answers crushed" (gold >= 0.75 scored <= 0.25),
"weak answers inflated" (gold < 0.5 scored >= 0.75), and the average of the
first two files as a combined evaluator.
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

V4 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "v4_diagnostic_58.jsonl")
K = ["technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership"]
rows = {json.loads(l)["example_id"]: json.loads(l) for l in open(V4, encoding="utf-8")}
gold = {i: np.mean([r["gold_labels"][d] / 4 for d in K]) for i, r in rows.items()}
groups = defaultdict(list)
for i in rows:
    groups[rows[i]["pair_group_id"]].append(i)


def tier(s):
    return 4 if s >= .8 else 3 if s >= .6 else 2 if s >= .4 else 1 if s >= .25 else 0


def qwk(a, b, n=5):
    O = np.zeros((n, n))
    for x, y in zip(a, b):
        O[x, y] += 1
    W = np.array([[(i - j) ** 2 / (n - 1) ** 2 for j in range(n)] for i in range(n)])
    E = np.outer(O.sum(1), O.sum(0)) / O.sum()
    return 1 - (W * O).sum() / (W * E).sum()


def report(label, p):
    ids = list(rows)
    ok = tot = 0
    for g in groups.values():
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                x, y = g[a], g[b]
                if gold[x] != gold[y]:
                    tot += 1
                    ok += (p[x] - p[y]) * (gold[x] - gold[y]) > 0
    print(f"{label:<40} QWK {qwk([tier(gold[i]) for i in ids], [tier(p[i]) for i in ids]):.2f}  "
          f"r {np.corrcoef([p[i] for i in ids], [gold[i] for i in ids])[0, 1]:.2f}  pairs {ok}/{tot}  "
          f"crushed {sum(p[i] <= .25 for i in ids if gold[i] >= .75)}/{sum(gold[i] >= .75 for i in ids)}  "
          f"inflated {sum(p[i] >= .75 for i in ids if gold[i] < .5)}/{sum(gold[i] < .5 for i in ids)}  "
          f"|err| {np.mean([abs(p[i] - gold[i]) for i in ids]):.2f}")


preds = []
for path in sys.argv[1:]:
    d = json.load(open(path))
    p = {r["example_id"]: r["score"] for r in d["rows"]}
    preds.append(p)
    report(f"{d['evaluator'][:38]}", p)
if len(preds) >= 2:
    report("average of first two", {i: (preds[0][i] + preds[1][i]) / 2 for i in rows})
