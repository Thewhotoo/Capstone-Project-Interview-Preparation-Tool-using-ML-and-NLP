"""Compare the technical-interview grader with hand-checked labels.

    python grader_eval/run_grader_eval.py [answers files...]
        default: every output_*.json here (round 2: output_batch1..4.json);
        tuning set: python grader_eval/run_grader_eval.py tuning_set/answers.json

Inputs: questions.json (exported from the active bank) and the labelled answers
(format in PROMPT.md). Writes results.json (every answer, per point) and prints:
per-key-point agreement, score vs `overall` correlation, per-style results and
the worst mismatches.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "main_cap" / "cap"))

from tech_interview.bank import load_bank          # noqa: E402
from tech_interview.followup import GOOD_SCORE      # noqa: E402
from tech_interview.grader import grade_answer      # noqa: E402

LEVELS = ("missing", "partial", "covered")


def main(*answer_files: str) -> None:
    bank = {q.id: q for q in load_bank(curated=False)}   # every active question, not just the curated ones
    paths = [HERE / f for f in answer_files] or sorted(HERE.glob("output_*.json"))
    answers = [a for p in paths for a in json.loads(p.read_text(encoding="utf-8-sig"))]
    print("answers:", len(answers), "from", ", ".join(p.name for p in paths))
    rows = []
    for a in answers:
        q = bank[a["question_id"]]
        g = grade_answer(q, a["answer"])
        predicted = []
        for k in q.key_points:
            predicted.append("covered" if k.point in g.covered else "partial" if k.point in g.partial else "missing")
        rows.append({**a, "topic": q.topic, "subject": q.subject, "score": g.score, "predicted": predicted,
                     "point_scores": [g.point_scores[k.point] for k in q.key_points],
                     "key_points": [k.point for k in q.key_points], "unclear": g.clarity.unclear})
    ((paths[0].parent if answer_files else HERE) / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    # per key point
    confusion = Counter()
    for r in rows:
        for gold, pred in zip(r["labels"], r["predicted"]):
            confusion[(gold, pred)] += 1
    total = sum(confusion.values())
    exact = sum(v for (g, p), v in confusion.items() if g == p)
    binary = sum(v for (g, p), v in confusion.items() if (g == "missing") == (p == "missing"))
    print(f"\nKEY POINTS ({total})")
    print(f"  exact agreement (covered/partial/missing): {exact / total:.0%}")
    print(f"  said something vs missing (binary):        {binary / total:.0%}")
    print("  confusion (rows = your label, cols = grader):")
    print("             " + "".join(p.rjust(9) for p in LEVELS))
    for g in LEVELS:
        print("   " + g.ljust(9) + " " + "".join(str(confusion[(g, p)]).rjust(9) for p in LEVELS))
    tp = confusion[("covered", "covered")]
    pred_cov = sum(confusion[(g, "covered")] for g in LEVELS)
    gold_cov = sum(confusion[("covered", p)] for p in LEVELS)
    print(f"  'covered' precision {tp / pred_cov:.0%} (when it says covered, is it?)  "
          f"recall {tp / gold_cov:.0%} (of truly covered points, how many it finds)")

    # overall score
    s = np.array([r["score"] for r in rows]); o = np.array([r["overall"] for r in rows])
    rank = lambda x: np.argsort(np.argsort(x))
    print(f"\nANSWER SCORES ({len(rows)})")
    print(f"  Pearson r {np.corrcoef(s, o)[0, 1]:.2f}   Spearman {np.corrcoef(rank(s), rank(o))[0, 1]:.2f}   "
          f"mean |diff| {np.abs(s - o).mean():.2f}")
    agree = sum((si >= GOOD_SCORE) == (oi >= GOOD_SCORE) for si, oi in zip(s, o))
    print(f"  good-answer decision (>= {GOOD_SCORE}) agrees: {agree}/{len(rows)}")

    print("\nBY STYLE                 n   your avg  grader avg  point agreement")
    by = defaultdict(list)
    for r in rows:
        by[r["style"]].append(r)
    for style, rs in sorted(by.items(), key=lambda kv: -np.mean([r["overall"] for r in kv[1]])):
        pts = [(g == p) for r in rs for g, p in zip(r["labels"], r["predicted"])]
        print(f"  {style:<20}{len(rs):>4}{np.mean([r['overall'] for r in rs]):>10.2f}"
              f"{np.mean([r['score'] for r in rs]):>12.2f}{np.mean(pts):>12.0%}")

    print("\nWORST MISMATCHES")
    for r in sorted(rows, key=lambda r: -abs(r["score"] - r["overall"]))[:10]:
        print(f"  [{r['style']}] yours {r['overall']:.2f} grader {r['score']:.2f} | {r['subject']}: {r['topic']}")
        print(f"     A: {r['answer'][:160]}")
        for kp, g, p, ps in zip(r["key_points"], r["labels"], r["predicted"], r["point_scores"]):
            if g != p:
                print(f"     you {g:<8} grader {p:<8} (entail {ps['entailment']}, sim {ps['similarity']}) {kp[:70]}")


if __name__ == "__main__":
    main(*sys.argv[1:])
