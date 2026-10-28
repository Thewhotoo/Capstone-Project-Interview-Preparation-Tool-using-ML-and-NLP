"""Compare the technical grader with frontier LLMs on the same labelled answers.

Free and reproducible: the export is a self-contained prompt (rubric, question, key points,
answer; no scores) that any chat model can grade in its web UI. Its JSON reply is imported
and scored against the same labels as our grader.

    python grader_eval/frontier_eval.py export --set fresh          -> frontier/fresh_prompt.md
        paste it into the model's chat (in parts if long); save its JSON reply
    python grader_eval/frontier_eval.py import --set fresh --model gpt-x --file reply.json
    python grader_eval/frontier_eval.py report --set fresh [--set team_test ...]

Reported per judge: per-point agreement with the labels, move-on decision (score >= 0.70)
agreement, Pearson r and mean gap to the labels' overall score, and pairs of answers to the
same question ordered like the labels. Our rows: the fast grader (live) and the fast + local
LLM blend (the final report; needs `benchmark.py --llm` to have filled llm_judge_cache.jsonl).
Caveat to state when reporting: the older sets' labels were drafted with an LLM; compare on
the human set (human_set/gold.json, set "human") for claims about human agreement.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "frontier"
sys.path.insert(0, str(HERE))

PROMPT_HEAD = """You are grading answers from a technical interview (CS fundamentals: networks, databases,
data structures, OOAD, operating systems). For each item you get the question, the key points a
complete answer must make, and the candidate's answer (often informal or spoken).

For each item return:
- "verdicts": one per key point, in order: "covered" (stated correctly, any wording), "partial"
  (partly, or vaguely without the mechanism) or "missing" (not stated, or stated wrongly);
- "score": the answer's overall quality from 0.0 to 1.0 (1.0 = complete and correct; a confident
  wrong answer scores near 0 even if it uses the right words).
Judge only what the answer says. Do not reward length, confidence or jargon.

Reply with ONLY a JSON array, one object per item, in order:
[{"id": "...", "verdicts": ["covered", "missing"], "score": 0.5}, ...]

ITEMS
"""


def _rows(set_name: str) -> list[dict]:
    import benchmark as B
    from tech_interview.bank import load_bank
    bank = {q.id: q for q in load_bank(curated=False)}
    basis = json.loads(B.LABEL_BASIS.read_text(encoding="utf-8"))["questions"] if B.LABEL_BASIS.exists() else {}
    rows = []
    for i, x in enumerate(B.load_sets()[set_name]):
        q = bank.get(x["question_id"])
        if q is None or B._stale(x["question_id"], q, basis):
            continue
        rows.append({"id": f"{set_name}-{i:03d}", "x": x, "q": q})
    return rows


def export(set_name: str) -> None:
    OUT.mkdir(exist_ok=True)
    parts = [PROMPT_HEAD]
    for r in _rows(set_name):
        pts = "\n".join(f"  {k + 1}. {p.point}" for k, p in enumerate(r["q"].key_points))
        parts.append(f"\n[{r['id']}]\nQUESTION: {r['q'].text}\nKEY POINTS:\n{pts}\nANSWER: {r['x']['answer']}\n")
    path = OUT / f"{set_name}_prompt.md"
    path.write_text("".join(parts), encoding="utf-8")
    print(f"{path.relative_to(HERE.parent)}: {len(parts) - 1} items")


def import_(set_name: str, model: str, file: Path) -> None:
    raw = file.read_text(encoding="utf-8").strip()
    raw = raw[raw.find("["): raw.rfind("]") + 1]
    items = {d["id"]: d for d in json.loads(raw)}
    rows = _rows(set_name)
    missing = [r["id"] for r in rows if r["id"] not in items]
    out = {r["id"]: items[r["id"]] for r in rows if r["id"] in items}
    OUT.mkdir(exist_ok=True)
    (OUT / f"{set_name}__{model}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{model}: {len(out)} items imported" + (f", {len(missing)} missing" if missing else ""))


def _metrics(rows, scores, verdicts=None):
    from tech_interview.followup import GOOD_SCORE
    h = np.array([r["x"]["overall"] for r in rows], dtype=float)
    s = np.array(scores, dtype=float)
    kp_tot = kp_ok = 0
    if verdicts is not None:
        for r, v in zip(rows, verdicts):
            lab = r["x"].get("labels") or []
            if v is not None and len(lab) == len(v):
                kp_tot += len(lab)
                kp_ok += sum(a == b for a, b in zip(lab, v))
    pairs = agree = 0
    by = {}
    for r, sc in zip(rows, s):
        by.setdefault(r["x"]["question_id"], []).append((r["x"]["overall"], sc))
    for rs in by.values():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                if abs(rs[i][0] - rs[j][0]) >= 0.2:
                    pairs += 1
                    agree += (rs[i][0] > rs[j][0]) == (rs[i][1] > rs[j][1])
    return {"n": len(rows), "kp": round(kp_ok / kp_tot, 3) if kp_tot else None,
            "decision": round(float(np.mean((s >= GOOD_SCORE) == (h >= GOOD_SCORE))), 3),
            "r": round(float(np.corrcoef(s, h)[0, 1]), 3), "gap": round(float(np.abs(s - h).mean()), 3),
            "pairs": round(agree / pairs, 3) if pairs else None}


def report(sets: list[str]) -> None:
    import benchmark as B
    from tech_interview import llm_judge
    from tech_interview.grader import grade_answer
    judge = None
    try:
        judge = B.CachedJudge()
    except SystemExit:
        print("(Ollama not available: the blend row uses only cached LLM verdicts)")
    for set_name in sets:
        rows = _rows(set_name)
        fast_s, fast_v, blend_s, blend_v = [], [], [], []
        for r in rows:
            q, x = r["q"], r["x"]
            g = grade_answer(q, x["answer"])
            fast_s.append(g.score)
            fast_v.append(["covered" if k.point in g.covered else "partial" if k.point in g.partial else "missing"
                           for k in q.key_points])
            out = None
            if judge is not None:
                rec = {"answer": x["answer"], "score": g.score, "exchanges": [], "final_grade": g.to_dict(),
                       "key_points": [{"point": k.point} for k in q.key_points]}
                out = llm_judge.blended(rec, judge.judge(q, x["answer"]))
            blend_s.append(out["score"] if out else g.score)
            blend_v.append([out["llm_verdicts"][k.point] for k in q.key_points] if out else None)
        table = {"ours: fast grader (live)": _metrics(rows, fast_s, fast_v)}
        if judge is not None:
            table["ours: fast + local LLM (report)"] = _metrics(rows, blend_s, blend_v)
        for f in sorted(OUT.glob(f"{set_name}__*.json")):
            got = json.loads(f.read_text(encoding="utf-8"))
            keep = [i for i, r in enumerate(rows) if r["id"] in got]
            sub = [rows[i] for i in keep]
            table[f.stem.split("__", 1)[1]] = _metrics(
                sub, [float(got[r["id"]]["score"]) for r in sub], [got[r["id"]].get("verdicts") for r in sub])
        print(f"\n{set_name}")
        print("  " + "judge".ljust(34) + "".join(c.rjust(9) for c in ("n", "kp", "decision", "r", "gap", "pairs")))
        for name, m in table.items():
            print("  " + name.ljust(34) + "".join(("-" if m[c] is None else str(m[c])).rjust(9)
                                                  for c in ("n", "kp", "decision", "r", "gap", "pairs")))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "import", "report"])
    ap.add_argument("--set", action="append", required=True)
    ap.add_argument("--model")
    ap.add_argument("--file", type=Path)
    a = ap.parse_args()
    if a.cmd == "export":
        for s in a.set:
            export(s)
    elif a.cmd == "import":
        import_(a.set[0], a.model, a.file)
    else:
        report(a.set)
