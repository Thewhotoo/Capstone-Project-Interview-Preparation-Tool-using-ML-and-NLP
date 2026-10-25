"""Grader regression benchmark: the technical grader vs every human-labelled answer set.

    python grader_eval/benchmark.py                  run, print, compare with baseline.json
    python grader_eval/benchmark.py --save-baseline  run and store the current numbers as the baseline
    python grader_eval/benchmark.py --show-worst     also print the worst disagreements per set
    python grader_eval/benchmark.py --llm            score with the background LLM re-grade blended in
                                                     (tech_interview/llm_judge.py; needs Ollama; verdicts
                                                     cached in llm_judge_cache.jsonl). Compared with
                                                     baseline_llm.json instead of baseline.json.

Answer sets (all labelled per key point covered/partial/missing + an `overall` 0..1):
  llm400   output_questions.json        400 LLM-written answers, 8 styles (round 2 eval)
  mine40   my_answers.json              40 answers typed by a team member (+ follow-up replies)
  team     real_set/*_answers.json      team answers written to the ANSWER_PROMPT.md brief
                                        (human-sounding styles + follow-up replies), checked by each member

The team set is split by question id (crc32 parity) into "tune" and "test" halves, so the same
question never sits in both. Tune thresholds on `team_tune`; report `team_test`.
Authors in FRESH_AUTHORS are reported as their own `fresh` set and never mixed into tune/test:
answers added after a round of grader/bank changes, so nothing was ever tuned on them.

Exit code 1 if any tracked metric is worse than baseline.json by more than its tolerance.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import zlib
from pathlib import Path

import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "main_cap" / "cap"))

from tech_interview.bank import load_bank          # noqa: E402
from tech_interview.followup import GOOD_SCORE      # noqa: E402
from tech_interview.grader import followup_covers, grade_answer   # noqa: E402
from tech_interview import llm_judge                 # noqa: E402

LLM_CACHE = HERE / "llm_judge_cache.jsonl"


def _judge_key(model, q, answer) -> str:
    """Changes when the model, the question's key points or the answer change."""
    return f"{model}|{q.id}|{zlib.crc32('|'.join(k.point for k in q.key_points).encode())}|{zlib.crc32(answer.encode())}"


class CachedJudge:
    """llm_judge.OllamaJudge with its verdicts cached per (model, question, answer)."""
    def __init__(self):
        self.judge_ = llm_judge.OllamaJudge()
        if not self.judge_.available():
            raise SystemExit("--llm needs Ollama running with " + self.judge_.model)
        self.cache = {}
        if LLM_CACHE.exists():
            for line in LLM_CACHE.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                self.cache[r["key"]] = r["out"]

    def judge_followup(self, followup, expected, point, reply):
        key = f"fu|{self.judge_.model}|{zlib.crc32(llm_judge.FU_SYSTEM.encode())}|{zlib.crc32(f'{followup}|{expected}|{point}|{reply}'.encode())}"
        if key not in self.cache:
            self.cache[key] = self.judge_.judge_followup(followup, expected, point, reply)
            with LLM_CACHE.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "out": self.cache[key]}) + "\n")
        return self.cache[key]

    def judge(self, q, answer):
        key = _judge_key(self.judge_.model, q, answer)
        if key not in self.cache:
            self.cache[key] = self.judge_.judge(q, answer)
            with LLM_CACHE.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "out": self.cache[key]}) + "\n")
        return self.cache[key]

BASELINE = HERE / "baseline.json"
GOOD_STYLES = {"good", "good_paraphrase", "good_own_words"}
WRONG_STYLES = {"confident_wrong"}
# metric -> (higher_is_better, tolerance before the benchmark fails)
FRESH_AUTHORS = {"surya"}   # added 2026-10-03, after the contradiction cap, repairs 1-3 and terms.py
TRACKED = {
    "keypoint_agreement": (True, 0.01),
    "decision_agreement": (True, 0.01),
    "pearson_r": (True, 0.02),
    "pair_order": (True, 0.02),
    "followup_accuracy": (True, 0.02),
    "mean_abs_diff": (False, 0.01),
    "confident_wrong_avg": (False, 0.02),
}


def _lenient_json(path: Path) -> list:
    """Parse a JSON array, keeping the complete objects of a truncated file."""
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for end in range(len(raw), 0, -1):
            if raw[end - 1] == "}":
                try:
                    items = json.loads(raw[:end].rstrip().rstrip(",") + "]")
                    print(f"  note: {path.name} is truncated; using its {len(items)} complete answers")
                    return items
                except json.JSONDecodeError:
                    continue
        raise


def load_sets() -> dict[str, list[dict]]:
    sets = {"llm400": json.loads((HERE / "output_questions.json").read_text(encoding="utf-8-sig")),
            "mine40": [x for x in json.loads((HERE / "my_answers.json").read_text(encoding="utf-8-sig"))
                       if x.get("answer", "").strip()]}
    team = []
    for path in sorted((HERE / "real_set").glob("*_answers*")):
        if path.suffix != ".json":   # e.g. a stray copy without an extension
            print(f"  skipped {path.name}: not a .json file")
            continue
        try:
            items = _lenient_json(path)
        except json.JSONDecodeError as exc:
            print(f"  skipped {path.name}: unreadable ({exc})")
            continue
        if not items or "answer" not in items[0]:
            print(f"  skipped {path.name}: no answers in it")
            continue
        author = path.stem.split("_")[0]
        team += [{**x, "author": author} for x in items if x.get("answer", "").strip()]
    sets["fresh"] = [x for x in team if x["author"] in FRESH_AUTHORS]
    team = [x for x in team if x["author"] not in FRESH_AUTHORS]
    sets["team_tune"] = [x for x in team if zlib.crc32(x["question_id"].encode()) % 2 == 0]
    sets["team_test"] = [x for x in team if zlib.crc32(x["question_id"].encode()) % 2 == 1]
    return sets


def evaluate(rows: list[dict], bank: dict, judge=None) -> tuple[dict, list[dict]]:
    graded, kp_total, kp_exact = [], 0, 0
    fu_n = fu_ok = wrong_fu_n = wrong_fu_accepted = 0
    for x in rows:
        q = bank.get(x["question_id"])
        if q is None:
            continue
        g = grade_answer(q, x["answer"])
        if judge is not None:   # the end-of-interview score: fast grade blended with the LLM re-grade
            record = {"answer": x["answer"], "score": g.score, "exchanges": [], "final_grade": g.to_dict(),
                      "key_points": [{"point": k.point} for k in q.key_points]}
            regrade = llm_judge.blended(record, judge.judge(q, x["answer"]))
            g.score = regrade["score"]
            g.covered, g.partial, g.missing = regrade["covered"], regrade["partial"], regrade["missing"]
        predicted = ["covered" if k.point in g.covered else "partial" if k.point in g.partial else "missing"
                     for k in q.key_points]
        labels = x.get("labels") or []
        if len(labels) == len(predicted):
            kp_total += len(labels)
            kp_exact += sum(a == b for a, b in zip(labels, predicted))
        fu = x.get("followup") or {}
        if fu.get("answer", "").strip() and isinstance(fu.get("correct"), bool):
            kp = next((k for k in q.key_points if k.followup == fu.get("question")), None)
            if kp is not None:
                verdict, _ = followup_covers(kp, fu["answer"], subject=q.subject)
                if judge is not None:   # the re-grade's rule: both graders must accept the reply
                    verdict = llm_judge.followup_verdict(
                        verdict, judge.judge_followup(kp.followup, kp.followup_answer, kp.point, fu["answer"]))
                fu_n += 1
                fu_ok += (verdict != "missing") == fu["correct"]
                if not fu["correct"]:
                    wrong_fu_n += 1
                    wrong_fu_accepted += verdict != "missing"
        graded.append({"id": x["question_id"], "style": x.get("style", "main"), "human": float(x["overall"]),
                       "grader": g.score, "answer": x["answer"], "author": x.get("author", "")})

    h = np.array([r["human"] for r in graded]); s = np.array([r["grader"] for r in graded])
    # pair ordering: answers to the SAME question whose human scores differ by >= 0.2
    pairs = agree = 0
    by_q: dict[str, list[dict]] = {}
    for r in graded:
        by_q.setdefault(r["id"], []).append(r)
    for rs in by_q.values():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                if abs(rs[i]["human"] - rs[j]["human"]) >= 0.2:
                    pairs += 1
                    agree += (rs[i]["human"] > rs[j]["human"]) == (rs[i]["grader"] > rs[j]["grader"])

    def style_avg(styles):
        v = [r["grader"] for r in graded if r["style"] in styles]
        return round(float(np.mean(v)), 3) if v else None

    m = {
        "answers": len(graded),
        "keypoint_agreement": round(kp_exact / kp_total, 3) if kp_total else None,
        "decision_agreement": round(float(np.mean((s >= GOOD_SCORE) == (h >= GOOD_SCORE))), 3),
        "pearson_r": round(float(np.corrcoef(s, h)[0, 1]), 3),
        "mean_abs_diff": round(float(np.abs(s - h).mean()), 3),
        "human_avg": round(float(h.mean()), 3),
        "grader_avg": round(float(s.mean()), 3),
        "pair_order": round(agree / pairs, 3) if pairs else None,
        "pairs": pairs,
        "good_avg": style_avg(GOOD_STYLES),
        "confident_wrong_avg": style_avg(WRONG_STYLES),
        "followup_accuracy": round(fu_ok / fu_n, 3) if fu_n else None,
        "followups": fu_n,
        "wrong_followups_accepted": round(wrong_fu_accepted / wrong_fu_n, 3) if wrong_fu_n else None,
    }
    return m, graded


def compare(results: dict, baseline: dict) -> list[str]:
    failures = []
    for name, m in results.items():
        b = baseline.get(name)
        if not b:
            continue
        for key, (higher_better, tol) in TRACKED.items():
            new, old = m.get(key), b.get(key)
            if new is None or old is None:
                continue
            worse = (old - new) if higher_better else (new - old)
            if worse > tol:
                failures.append(f"{name}.{key}: {old} -> {new}")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--show-worst", action="store_true")
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()

    bank = {q.id: q for q in load_bank(curated=False)}
    judge = CachedJudge() if args.llm else None
    baseline_file = HERE / "baseline_llm.json" if args.llm else BASELINE
    results, details = {}, {}
    for name, rows in load_sets().items():
        if rows:
            results[name], details[name] = evaluate(rows, bank, judge)

    cols = ["answers", "keypoint_agreement", "decision_agreement", "pearson_r", "mean_abs_diff", "human_avg",
            "grader_avg", "pair_order", "good_avg", "confident_wrong_avg", "followup_accuracy", "wrong_followups_accepted"]
    short = ["n", "kp_agree", "decision", "r", "|diff|", "human", "grader", "pair_ord", "good", "conf_wrong", "fu_acc", "fu_wrong_ok"]
    print("\n" + "set".ljust(11) + "".join(c.rjust(11) for c in short))
    for name, m in results.items():
        print(name.ljust(11) + "".join(("-" if m.get(c) is None else str(m[c])).rjust(11) for c in cols))

    if args.show_worst:
        for name, rows in details.items():
            print(f"\nWORST {name}")
            for r in sorted(rows, key=lambda r: -abs(r["grader"] - r["human"]))[:6]:
                print(f"  [{r['style']}] human {r['human']:.2f} grader {r['grader']:.2f} | {r['id']} | {r['answer'][:110]}")

    if args.save_baseline:
        baseline_file.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"\nbaseline saved to {baseline_file.name}")
        return 0
    if baseline_file.exists():
        failures = compare(results, json.loads(baseline_file.read_text(encoding="utf-8")))
        print("\nREGRESSIONS:\n  " + "\n  ".join(failures) if failures else "\nno regressions vs baseline")
        return 1 if failures else 0
    print("\n(no baseline yet: run with --save-baseline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
