"""Human evaluation set for the technical (Round 2) grader: real answers, blind human labels.

Every answer and every label in this set comes from a person. Three steps:

1. answer sheets: each person answers questions from the served bank in their own words
       python grader_eval/human_eval.py answers --people A,B,C --per-person 50
   -> grader_eval/human_set/answers_<person>.csv  (fill the "answer" column; type it the way
      you would say it in an interview; leave a question blank to skip it)

2. label sheets: every answer is labelled blind by two people who did NOT write it
       python grader_eval/human_eval.py labels --people A,B,C
   -> grader_eval/human_set/labels_<person>.csv  (no grader scores are shown anywhere;
      answers are shuffled and nobody labels their own; author i's answers go to the
      next two people in the list, so with 4 people each labels 2 x 50 answers)
   For each answer: kp1..kp4 = c (covered) / p (partial) / m (missing) for each listed
   point, and overall = 0-4 (rubric in the sheet's first rows).

3. results: inter-annotator agreement and the gold set the benchmark reads
       python grader_eval/human_eval.py gold --people A,B,C
   -> prints agreement (per point: Cohen's kappa; overall: quadratic weighted kappa,
      Pearson) and writes grader_eval/human_set/gold.json, where each answer's label is
      the agreed per-point label (ties -> partial) and the mean overall score / 4.

`benchmark.py` reports the gold set as its own "human" set. Questions come from the
served (curated) bank, stratified by subject and difficulty, with a fixed seed.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "human_set"
sys.path.insert(0, str(HERE.parent / "main_cap" / "cap"))

MAX_POINTS = 4
LABEL = {"c": "covered", "p": "partial", "m": "missing"}
RUBRIC = [
    "overall: 4 = complete and correct; 3 = mostly right, one point missing or vague;",
    "2 = about half right; 1 = little that is right; 0 = wrong, off-topic or no answer.",
    "kp columns: c = the answer states this point correctly (any wording); p = partly or vaguely;",
    "m = not stated, or stated wrongly. Judge what the answer says, not its length or confidence.",
]


def _bank():
    from tech_interview.bank import load_bank
    return load_bank(curated=True)


def _people(s: str) -> list[str]:
    people = [p.strip() for p in s.split(",") if p.strip()]
    if len(people) < 2:
        raise SystemExit("need at least two people, so every answer gets a label from someone else")
    return people


def make_answer_sheets(people: list[str], per_person: int, seed: int) -> None:
    rng = random.Random(seed)
    by_cell = defaultdict(list)
    for q in _bank():
        by_cell[(q.subject, q.difficulty)].append(q)
    for qs in by_cell.values():
        rng.shuffle(qs)
    # round-robin over subject x difficulty cells, so every sheet is balanced
    cells, picked = sorted(by_cell), []
    while len(picked) < per_person * len(people) and any(by_cell.values()):
        for c in cells:
            if by_cell[c]:
                picked.append(by_cell[c].pop())
    OUT.mkdir(exist_ok=True)
    for i, person in enumerate(people):
        mine = picked[i::len(people)][:per_person]
        path = OUT / f"answers_{person}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["question_id", "subject", "question", "answer"])
            for q in mine:
                w.writerow([q.id, q.subject, q.text, ""])
        print(f"{path.name}: {len(mine)} questions")


def _read_answers(people):
    rows = []
    for person in people:
        path = OUT / f"answers_{person}.csv"
        if not path.exists():
            raise SystemExit(f"missing {path.name}")
        with path.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["answer"].strip():
                    rows.append({"question_id": r["question_id"], "answer": r["answer"].strip(), "author": person})
    for i, r in enumerate(rows):
        r["answer_id"] = f"h{i:04d}"
    return rows


def make_label_sheets(people: list[str], seed: int) -> None:
    bank = {q.id: q for q in _bank()}
    answers = _read_answers(people)
    (OUT / "pool.json").write_text(json.dumps(answers, indent=1, ensure_ascii=False), encoding="utf-8")
    labellers = {p: [people[(i + k) % len(people)] for k in (1, 2)][:len(people) - 1]
                 for i, p in enumerate(people)}
    for person in people:
        mine = [a for a in answers if person in labellers[a["author"]]]
        random.Random(f"{seed}-{person}").shuffle(mine)
        path = OUT / f"labels_{person}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            for line in RUBRIC:
                w.writerow(["#", line])
            w.writerow(["answer_id", "question", "answer"]
                       + [c for k in range(1, MAX_POINTS + 1) for c in (f"point{k}", f"kp{k}")] + ["overall"])
            for a in mine:
                q = bank[a["question_id"]]
                pts = [k.point for k in q.key_points][:MAX_POINTS]
                cells = [c for p in pts for c in (p, "")] + ["", ""] * (MAX_POINTS - len(pts))
                w.writerow([a["answer_id"], q.text, a["answer"]] + cells + [""])
        print(f"{path.name}: {len(mine)} answers to label")


def _read_labels(person):
    out = {}
    with (OUT / f"labels_{person}.csv").open(encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if r and r[0] != "#"]
    head, rows = rows[0], rows[1:]
    for r in rows:
        d = dict(zip(head, r))
        if not d.get("overall", "").strip():
            continue
        kps = []
        for k in range(1, MAX_POINTS + 1):
            if d.get(f"point{k}", "").strip():
                v = d.get(f"kp{k}", "").strip().lower()[:1]
                if v not in LABEL:
                    raise SystemExit(f"{person} {d['answer_id']}: kp{k} must be c, p or m")
                kps.append(LABEL[v])
        out[d["answer_id"]] = {"labels": kps, "overall": int(d["overall"])}
    return out


def _kappa(a, b, cats):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def _qwk(a, b, k=5):
    import numpy as np
    o = np.zeros((k, k))
    for x, y in zip(a, b):
        o[x, y] += 1
    w = np.array([[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)])
    e = np.outer(o.sum(1), o.sum(0)) / o.sum()
    return round(1 - (w * o).sum() / (w * e).sum(), 3)


def make_gold(people: list[str]) -> None:
    import numpy as np
    pool = {a["answer_id"]: a for a in json.loads((OUT / "pool.json").read_text(encoding="utf-8"))}
    labels = {p: _read_labels(p) for p in people}
    print("labelled:", {p: len(v) for p, v in labels.items()})
    for i, a in enumerate(people):
        for b in people[i + 1:]:
            both = sorted(set(labels[a]) & set(labels[b]))
            if not both:
                continue
            ka = [x for aid in both for x in labels[a][aid]["labels"]]
            kb = [x for aid in both for x in labels[b][aid]["labels"]]
            oa = [labels[a][aid]["overall"] for aid in both]
            ob = [labels[b][aid]["overall"] for aid in both]
            print(f"{a} vs {b}: {len(both)} answers | per-point kappa {_kappa(ka, kb, list(LABEL.values()))} | "
                  f"overall QWK {_qwk(oa, ob)} | Pearson {round(float(np.corrcoef(oa, ob)[0, 1]), 3)}")
    gold = []
    for aid, a in pool.items():
        got = [labels[p][aid] for p in people if aid in labels[p]]
        if len(got) < 2:
            continue
        kps = []
        for votes in zip(*[g["labels"] for g in got]):
            top = max(set(votes), key=votes.count)
            kps.append(top if votes.count(top) > len(votes) / 2 else "partial")
        gold.append({"question_id": a["question_id"], "style": "human", "answer": a["answer"],
                     "author": "human", "labels": kps,
                     "overall": round(sum(g["overall"] for g in got) / len(got) / 4, 3),
                     "annotators": len(got)})
    (OUT / "gold.json").write_text(json.dumps(gold, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"gold.json: {len(gold)} answers with at least two labels")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["answers", "labels", "gold"])
    ap.add_argument("--people", required=True, help="comma-separated names or initials")
    ap.add_argument("--per-person", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    people = _people(a.people)
    {"answers": lambda: make_answer_sheets(people, a.per_person, a.seed),
     "labels": lambda: make_label_sheets(people, a.seed),
     "gold": lambda: make_gold(people)}[a.step]()
