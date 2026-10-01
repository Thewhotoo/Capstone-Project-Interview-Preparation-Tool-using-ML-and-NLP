"""Rank the question bank by confidence and hold back the weakest questions.

Every question gets a confidence score (0-1) from the evidence recorded while it
was generated (.qbank_cache). The bank is sorted best-first, and questions below
the threshold get "active": false -- the app only uses active questions; held-back
ones stay in the file for human review (the JSON equivalent of commenting them out).

Signals (each 0-1):
  support     key points kept / key points the model proposed (dropped = unverifiable)
  judge       1 - share of key points the thinking-mode judge said their quote does not support
  quotes      mean fuzzy match of the key-point quotes against the slides' own text
  grounding   verified key points, capped at 4 (more independent evidence = better)
  first_try   1.0 if accepted on the first attempt, 0.85 after a retry
  coverage    1.0 if the topic is well covered by slides, 0.85 if thin
confidence = weighted mean of the signals x difficulty factor
             (easy 1.0, medium 0.95, hard 0.85: hard answers reason beyond single slide
              sentences, which the checks cannot fully verify)

    python -m slide_rag.rank_bank                  # rank all subjects, threshold 0.80
    python -m slide_rag.rank_bank --threshold 0.75
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

from rapidfuzz import fuzz

from .qbank import BANK_DIR, CACHE, _load, _norm, _slide_text

WEIGHTS = {"support": 0.30, "judge": 0.25, "quotes": 0.15, "grounding": 0.15, "first_try": 0.10, "coverage": 0.05}
DIFFICULTY_FACTOR = {"easy": 1.0, "medium": 0.95, "hard": 0.85}
DEFAULT_THRESHOLD = 0.80


def _cache_records(subject: str) -> dict[tuple[str, str], dict]:
    """(topic_id, "<level><slot>") -> cached generation record of the accepted question."""
    out = {}
    for f in glob.glob(str(CACHE / subject / "*.json")):
        m = re.search(r"__s(\d+)-(easy|medium|hard)__", Path(f).name)
        if not m:
            continue
        rec = json.loads(Path(f).read_text(encoding="utf-8"))
        if rec.get("question") is None:
            continue
        out[(rec["topic"]["id"], f"{m.group(2)}{int(m.group(1)) + 1}")] = rec
    return out


def score(q: dict, rec: dict | None, slide_text: str) -> tuple[float, dict]:
    kept = len(q["key_points"])
    signals = {"support": 1.0, "judge": 1.0, "first_try": 1.0}
    if rec:
        final = rec["attempts"][-1]
        proposed = len((final.get("raw") or {}).get("key_points", [])) or kept
        signals["support"] = min(1.0, kept / proposed) if proposed else 1.0
        unsupported = (final.get("judge") or {}).get("unsupported_points") or []
        signals["judge"] = 1.0 - min(1.0, len(unsupported) / proposed) if proposed else 1.0
        signals["first_try"] = 1.0 if len(rec["attempts"]) == 1 else 0.85
    ratios = [fuzz.partial_ratio(_norm(p["quote"]), slide_text) / 100 for p in q["key_points"]]
    signals["quotes"] = sum(ratios) / len(ratios) if ratios else 0.0
    signals["grounding"] = min(kept, 4) / 4
    signals["coverage"] = 1.0 if q.get("topic_coverage") == "good" else 0.85
    base = sum(WEIGHTS[k] * signals[k] for k in WEIGHTS)
    conf = base * DIFFICULTY_FACTOR.get(q["difficulty"], 0.9)
    return round(conf, 3), {k: round(v, 3) for k, v in signals.items()}


def rank_subject(subject: str, threshold: float) -> tuple[int, int]:
    bank_file = BANK_DIR / f"{subject}.json"
    bank = json.loads(bank_file.read_text(encoding="utf-8"))
    topics, sections, slides = _load(subject)
    by_topic = {t["id"]: t for t in topics}
    records = _cache_records(subject)
    for q in bank:
        slot = q["id"].rsplit(".", 1)[-1]
        text = _slide_text(by_topic[q["topic_id"]], sections, slides)
        q["confidence"], q["confidence_signals"] = score(q, records.get((q["topic_id"], slot)), text)
        q["active"] = q["confidence"] >= threshold
    bank.sort(key=lambda q: (not q["active"], -q["confidence"]))
    bank_file.write_text(json.dumps(bank, indent=1, ensure_ascii=False), encoding="utf-8")
    _report(subject, bank, threshold)
    return sum(q["active"] for q in bank), len(bank)


def _report(subject: str, bank: list[dict], threshold: float) -> None:
    active = [q for q in bank if q["active"]]
    held = [q for q in bank if not q["active"]]
    md = [f"# Question bank: {subject}", "",
          f"- **Active (used by the app): {len(active)}** · held back for review: {len(held)} "
          f"(confidence threshold {threshold})",
          "- Sorted by confidence, best first. Held-back questions are kept below, not deleted.", ""]

    def block(q):
        lines = [f"### [{q['topic']}] {q['question']}",
                 f"*confidence {q['confidence']:.2f} · {q['difficulty']} · slides {q['source_pages'][:6]}"
                 + (" · ⚠ NEEDS REVIEW" if q.get("review") == "needs_review" else "") + "*", "",
                 f"**Reference:** {q['reference_answer']}", "",
                 "**Key points** (slide quote → follow-up → expected answer):"]
        for p in q["key_points"]:
            lines.append(f"- **{p['point']}**  \n  quote: \"{p['quote']}\"  \n"
                         f"  follow-up: _{p['followup'] or '(generic clarification)'}_"
                         + (f"  \n  expected: {p['followup_answer']}" if p["followup_answer"] else ""))
        return lines + [""]

    md.append("## Active questions")
    md.append("")
    for q in active:
        md += block(q)
    md += ["---", "", "## Held back (low confidence — not used by the app)", ""]
    for q in held:
        md += block(q)
    (BANK_DIR / f"{subject}_report.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = ap.parse_args()
    for s in ("cn", "dbms", "dsa", "ooad", "os"):
        a, n = rank_subject(s, args.threshold)
        print(f"{s:5} active {a:3} / {n:3}")


if __name__ == "__main__":
    main()
