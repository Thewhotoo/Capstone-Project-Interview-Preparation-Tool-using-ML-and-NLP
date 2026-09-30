"""Grade the user's own answers (my_answers.json) and compare with their scores.

    python grader_eval/run_my_answers.py            both halves
    python grader_eval/run_my_answers.py test       held-out half only

Split: even positions = "tune" (used when adjusting the grader),
odd positions = "test" (never looked at while tuning).
Main answers: grader score vs your `overall`, and whether both put the answer
on the same side of the move-on line (0.70).
Follow-ups: does the grader accept the reply (anything but "missing") exactly
when you marked it correct?
"""
import io
import json
import sys
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "main_cap" / "cap"))

from tech_interview.bank import load_bank          # noqa: E402
from tech_interview.followup import GOOD_SCORE      # noqa: E402
from tech_interview.grader import followup_covers, grade_answer   # noqa: E402


def main(which: str = "both") -> None:
    bank = {q.id: q for q in load_bank(curated=False)}   # every active question, not just the curated ones
    items = [x for x in json.loads((HERE / "my_answers.json").read_text(encoding="utf-8-sig")) if x["answer"].strip()]
    halves = {"tune": items[0::2], "test": items[1::2]}
    for name, rows in halves.items():
        if which not in ("both", name):
            continue
        scores, overall, fu_ok, fu_n, lines = [], [], 0, 0, []
        for x in rows:
            q = bank[x["question_id"]]
            g = grade_answer(q, x["answer"])
            scores.append(g.score); overall.append(x["overall"])
            fu = x.get("followup") or {}
            verdict = ""
            if fu.get("answer", "").strip() and isinstance(fu.get("correct"), bool):
                kp = next((k for k in q.key_points if k.followup == fu["question"]), None)
                if kp is not None:
                    verdict, _ = followup_covers(kp, fu["answer"])
                    fu_n += 1
                    fu_ok += (verdict != "missing") == fu["correct"]
            lines.append(f"  you {x['overall']:.2f}  grader {g.score:.2f}  | follow-up you {'ok ' if fu.get('correct') else 'bad'} grader {verdict or '-':<8}| {q.topic}")
        s, o = np.array(scores), np.array(overall)
        agree = int(sum((a >= GOOD_SCORE) == (b >= GOOD_SCORE) for a, b in zip(s, o)))
        print(f"\n{name.upper()} ({len(rows)} answers)")
        print(f"  Pearson r {np.corrcoef(s, o)[0, 1]:.2f}   mean |diff| {np.abs(s - o).mean():.2f}   "
              f"your avg {o.mean():.2f} vs grader avg {s.mean():.2f}")
        print(f"  same move-on decision (>= {GOOD_SCORE}): {agree}/{len(rows)}")
        print(f"  follow-ups judged right: {fu_ok}/{fu_n}")
        print("\n".join(lines))


if __name__ == "__main__":
    main(*sys.argv[1:])
