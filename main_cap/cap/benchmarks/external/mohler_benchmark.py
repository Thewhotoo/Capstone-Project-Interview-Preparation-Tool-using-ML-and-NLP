"""
External, human-graded benchmark: the Mohler / Texas short-answer grading dataset.

2,273 real student answers (1,700+ used, see EXCLUDED_SETS) to data-structures questions (University of North
Texas), each graded 0-5 by TWO computer-science graders, with the instructor's
reference answer (Mohler et al., ACL 2011; CC-BY-4.0, via Hugging Face
Viswa45/ASAG). Unlike benchmarks/evaluator/, these labels are independent of
this project: they test the reference-based CORRECTNESS grading path (the
Technical Interview grader and the coverage-NLI correctness scorer), i.e. the
part that needs subject knowledge.

Each scorer runs in its own process and caches its scores (memory-safe on a
small laptop); `report` reads the caches. All scorers are compared on the same
stratified sample (default 8 answers per question); the human-vs-human ceiling
also uses every answer.

    py -3.13 benchmarks/external/mohler_benchmark.py fetch
    py -3.13 benchmarks/external/mohler_benchmark.py score tech_grader
    py -3.13 benchmarks/external/mohler_benchmark.py score coverage_nli
    py -3.13 benchmarks/external/mohler_benchmark.py score qwen        # needs Ollama running
    py -3.13 benchmarks/external/mohler_benchmark.py report
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE.parents[1]
sys.path.insert(0, str(CAP))
DATA = HERE / "data" / "mohler_open_ended.json"
CACHE = HERE / "data" / "scores"
PER_QUESTION = 8
SEED = 13


# ------------------------------------------------------------------ data

def fetch():
    rows = []
    for offset in range(0, 2400, 100):
        url = ("https://datasets-server.huggingface.co/rows?dataset=Viswa45/ASAG&config=raw"
               f"&split=open_ended&offset={offset}&length=100")
        for attempt in range(3):
            try:
                page = json.loads(urllib.request.urlopen(url, timeout=30).read())
                break
            except Exception:
                time.sleep(2)
        got = [r["row"] for r in page.get("rows", [])]
        rows += got
        if len(got) < 100:
            break
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(rows), encoding="utf-8")
    print(f"saved {len(rows)} answers to {DATA}")


def _clean(text: str) -> str:
    return " ".join(re.sub(r"<br\s*/?>", " ", text or "").split())


# The two exams (E11, E12) mix 0-10 and 0-5 grades in this release, and their published
# averages don't consistently follow from the two grades -- so only the ten assignments
# (E01-E10), where both graders used 0-5 throughout, are used.
EXCLUDED_SETS = ("E11", "E12")


def load_rows() -> list[dict]:
    rows = [r for r in json.loads(DATA.read_text(encoding="utf-8")) if r["id"].split(".")[0] not in EXCLUDED_SETS]
    for r in rows:
        r["student_answer"] = _clean(r["student_answer"])
        r["instructor_answer"] = _clean(r["instructor_answer"])
    return rows


def sample(rows: list[dict]) -> list[dict]:
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r)
    rng = random.Random(SEED)
    picked = []
    for q in sorted(by_q):
        group = list(by_q[q])
        rng.shuffle(group)
        picked += group[:PER_QUESTION]
    return picked


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in re.split(r"(?<=[.!?;])\s+", text) if len(s.strip().split()) >= 2]
    return parts or [text]


# ---------------------------------------------------------------- scorers (each returns 0..1)

def scorer_tech_grader():
    """The live Technical Interview grader: instructor answer sentences as key points."""
    from tech_interview.bank import KeyPoint, Question
    from tech_interview.grader import grade_answer

    def score(r):
        q = Question(id=r["id"], subject="ds", topic_id="", topic="", difficulty="medium", text=r["question"],
                     reference_answer=r["instructor_answer"],
                     key_points=tuple(KeyPoint(point=s, followup="", followup_answer="") for s in _sentences(r["instructor_answer"])),
                     confidence=1.0)
        return grade_answer(q, r["student_answer"]).score
    return score


def scorer_coverage_nli():
    """correctness_nli_scorer.CoverageNLIScorer: technical_correctness against the reference."""
    from answer_key import AnswerKey
    from correctness_nli_scorer import CoverageNLIScorer
    scorer = CoverageNLIScorer()

    def score(r):
        key = AnswerKey(key_points=tuple(_sentences(r["instructor_answer"])), reference_answer=r["instructor_answer"])
        return scorer.score_answer(r["student_answer"], key)["technical_correctness"]
    return score


_QWEN_PROMPT = """You grade a student's short answer in a data structures course.
Compare it with the instructor's reference answer and score it 0-5:
5 completely correct, 4 mostly correct with a small gap, 3 partly correct, 2 a little correct,
1 mostly wrong but related, 0 wrong or irrelevant. Different wording is fine if the meaning is right.
Reply with JSON only: {"score": <0-5>}"""


def scorer_qwen():
    """Local LLM baseline (qwen2.5:3b via Ollama), given the reference answer."""
    from fact_checker import OllamaFactChecker
    llm = OllamaFactChecker()

    def score(r):
        user = f"QUESTION: {r['question']}\nREFERENCE ANSWER: {r['instructor_answer']}\nSTUDENT ANSWER: {r['student_answer']}"
        try:
            s = float(llm._chat(_QWEN_PROMPT, user, 20).get("score"))
        except Exception:
            return None
        return max(0.0, min(5.0, s)) / 5.0
    return score


SCORERS = {"tech_grader": scorer_tech_grader, "coverage_nli": scorer_coverage_nli, "qwen": scorer_qwen}


def run_scorer(name: str):
    rows = sample(load_rows())
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    score = SCORERS[name]()
    start = time.time()
    for i, r in enumerate(rows, 1):
        if r["id"] in done:
            continue
        done[r["id"]] = score(r)
        if i % 25 == 0:
            path.write_text(json.dumps(done))          # resumable
            print(f"{name}: {i}/{len(rows)} ({time.time() - start:.0f}s)", flush=True)
    path.write_text(json.dumps(done))
    print(f"{name}: done, {len(done)} scores")


# ------------------------------------------------------------------ metrics

def pearson(a, b):
    n = len(a); ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = math.sqrt(sum((x - ma) ** 2 for x in a)); vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return cov / (va * vb) if va and vb else float("nan")


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i]); ranks = [0.0] * len(xs); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2
        i = j + 1
    return ranks


def spearman(a, b):
    return pearson(_ranks(a), _ranks(b))


def rmse(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))


def qwk(a, b, k=6):
    a = [int(round(x)) for x in a]; b = [int(round(x)) for x in b]
    o = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        o[x][y] += 1
    n = len(a); ha = [sum(r) for r in o]; hb = [sum(o[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = (i - j) ** 2 / (k - 1) ** 2
            num += w * o[i][j]; den += w * ha[i] * hb[j] / n
    return 1 - num / den if den else float("nan")


def fit_linear(pred, gold):
    """Least-squares a*pred+b. Reported separately ('calibrated'): a scorer's raw 0..1
    scale need not match the graders' 0-5 habits, and Pearson/Spearman ignore scale anyway."""
    n = len(pred); mp, mg = sum(pred) / n, sum(gold) / n
    var = sum((p - mp) ** 2 for p in pred)
    a = sum((p - mp) * (g - mg) for p, g in zip(pred, gold)) / var if var else 0.0
    return a, mg - a * mp


def report():
    rows = load_rows()
    g1 = [r["score_grader_1"] for r in rows]; g2 = [r["score_grader_2"] for r in rows]
    print(f"# Mohler benchmark\n\n{len(rows)} answers, {len({r['question'] for r in rows})} questions; "
          f"mean human score {sum(r['score_avg'] for r in rows) / len(rows):.2f}/5\n")
    print("| scorer | n | Pearson | Spearman | RMSE (0-5) | RMSE calibrated | QWK |")
    print("|---|---|---|---|---|---|---|")
    print(f"| human grader 1 vs grader 2 (all) | {len(rows)} | {pearson(g1, g2):.3f} | {spearman(g1, g2):.3f} | "
          f"{rmse(g1, g2):.3f} | - | {qwk(g1, g2):.3f} |")
    picked = sample(rows)
    h1 = [r["score_grader_1"] for r in picked]; h2 = [r["score_grader_2"] for r in picked]
    print(f"| human grader 1 vs grader 2 (sample) | {len(picked)} | {pearson(h1, h2):.3f} | {spearman(h1, h2):.3f} | "
          f"{rmse(h1, h2):.3f} | - | {qwk(h1, h2):.3f} |")
    for name in SCORERS:
        path = CACHE / f"{name}.json"
        if not path.exists():
            continue
        scores = json.loads(path.read_text())
        pairs = [(scores[r["id"]] * 5, r["score_avg"]) for r in picked if scores.get(r["id"]) is not None]
        if len(pairs) < 20:
            continue
        pred, gold = [p for p, _ in pairs], [g for _, g in pairs]
        a, b = fit_linear(pred, gold)
        cal = [min(5, max(0, a * p + b)) for p in pred]
        print(f"| {name} vs human average | {len(pairs)} | {pearson(pred, gold):.3f} | {spearman(pred, gold):.3f} | "
              f"{rmse(pred, gold):.3f} | {rmse(cal, gold):.3f} | {qwk(cal, gold):.3f} |")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "fetch":
        fetch()
    elif cmd == "score":
        run_scorer(sys.argv[2])
    else:
        report()
