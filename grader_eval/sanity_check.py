"""Self-consistency check of the question bank against the grader (no labelled data needed).

    python grader_eval/sanity_check.py                 every curated (served) question
    python grader_eval/sanity_check.py --all           every active question
    python grader_eval/sanity_check.py --ids a b c     just these questions

For each question:
  own    = grader score of the question's OWN reference answer. A model answer must pass
           (>= 0.70, the move-on line); if not, a key point asks for something the reference
           answer doesn't say, or says in words the grader can't match -> fix the point or the reference.
  other  = highest score given to the reference answers of 3 OTHER questions from the same
           subject. These are on-topic but answer something else, so they should score low
           (< 0.50); if not, the key points are too generic.
Exit code 1 if any question fails either check.
"""
from __future__ import annotations

import argparse
import io
import random
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main_cap" / "cap"))

from tech_interview.bank import load_bank          # noqa: E402
from tech_interview.followup import GOOD_SCORE      # noqa: E402
from tech_interview.grader import grade_answer      # noqa: E402

OTHER_MAX = 0.50
N_OTHERS = 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ids", nargs="*")
    args = ap.parse_args()
    bank = load_bank(curated=False)
    pool = [q for q in bank if args.all or q.curated] if not args.ids else [q for q in bank if q.id in set(args.ids)]
    rng = random.Random(7)
    own_fail, other_fail = [], []
    for q in pool:
        g = grade_answer(q, q.reference_answer)
        same = [o for o in bank if o.subject == q.subject and o.id != q.id and o.topic_id != q.topic_id]
        others = [(grade_answer(q, o.reference_answer).score, o.id) for o in rng.sample(same, min(N_OTHERS, len(same)))]
        worst = max(others) if others else (0.0, "")
        if g.score < GOOD_SCORE:
            own_fail.append(q.id)
            print(f"OWN   {g.score:.2f}  {q.id}\n      not matched: {g.missing + g.partial}")
        if worst[0] >= OTHER_MAX:
            other_fail.append(q.id)
            print(f"OTHER {worst[0]:.2f}  {q.id}  (scored for the reference answer of {worst[1]})")
    print(f"\n{len(pool)} questions: {len(own_fail)} fail their own reference answer, "
          f"{len(other_fail)} give >= {OTHER_MAX} to another question's answer")
    return 1 if own_fail or other_fail else 0


if __name__ == "__main__":
    sys.exit(main())
