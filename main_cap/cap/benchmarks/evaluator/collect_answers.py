"""
Export real résumé-interview answers from the app database into the human benchmark.

Reads session_turns + the session's résumé parsed_profile from instance/app.db and
appends one row per answered turn to private/human_items.jsonl (gitignored - real
people's answers). Rows already present (same item_id) are left untouched, so it is
safe to re-run after every batch of mock interviews. Labels are added afterwards with
label_answers.py.

Only users who gave training/data consent are exported unless --ignore-consent.

    py -3.13 benchmarks/evaluator/collect_answers.py [--db instance/app.db]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "private" / "human_items.jsonl"
VALID_REASONING = {"recall", "explanation", "application", "trade_off_analysis", "debugging",
                   "design", "optimization", "reflection", "ownership"}


def _grounding(profile: dict, ref: str) -> dict | None:
    """Find the project / experience entry the turn was about."""
    for p in profile.get("projects") or []:
        if p.get("title") == ref:
            return {k: p.get(k) or ([] if k in ("technologies", "concepts") else "")
                    for k in ("title", "summary", "technologies", "concepts")}
    for e in profile.get("experience") or []:
        if ref and ref in (e.get("company"), e.get("role")):
            return {"title": e.get("company") or e.get("role"), "summary": e.get("summary", ""),
                    "technologies": [], "concepts": []}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(HERE.parents[1] / "instance" / "app.db"))
    ap.add_argument("--ignore-consent", action="store_true")
    args = ap.parse_args()

    existing = set()
    if OUT.exists():
        existing = {json.loads(l)["item_id"] for l in OUT.read_text(encoding="utf-8").splitlines() if l.strip()}

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT t.session_id, t.turn_number, t.question_text, t.answer_text, t.reasoning_type,
               t.project_reference, t.source_id, t.is_followup, t.overall_score,
               r.parsed_profile, u.consent_data, u.consent_training
        FROM session_turns t
        JOIN interview_sessions s ON s.id = t.session_id
        JOIN users u ON u.id = s.user_id
        LEFT JOIN resumes r ON r.id = s.resume_id
        WHERE s.session_type = 'resume_discussion' AND t.answer_text IS NOT NULL AND trim(t.answer_text) != ''
        ORDER BY t.session_id, t.turn_number""").fetchall()

    added = skipped_consent = skipped_grounding = 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as fh:
        for r in rows:
            item_id = f"hb_s{r['session_id']}_t{r['turn_number']}"
            if item_id in existing:
                continue
            if not args.ignore_consent and not (r["consent_data"] or r["consent_training"]):
                skipped_consent += 1
                continue
            profile = json.loads(r["parsed_profile"]) if r["parsed_profile"] else {}
            grounding = _grounding(profile, r["project_reference"] or r["source_id"] or "")
            if grounding is None:
                skipped_grounding += 1
                continue
            fh.write(json.dumps({
                "item_id": item_id, "source": "human", "kind": "real",
                "question_id": f"s{r['session_id']}::{grounding['title']}",
                "grounding": grounding, "question": r["question_text"],
                "reasoning_type": r["reasoning_type"] if r["reasoning_type"] in VALID_REASONING else "explanation",
                "answer": r["answer_text"], "is_followup": bool(r["is_followup"]),
                "live_score_at_time": r["overall_score"], "labels": [],
            }, ensure_ascii=False) + "\n")
            added += 1
    print(f"added {added} new answers -> {OUT}  (already present: {len(existing)}, "
          f"no consent: {skipped_consent}, no grounding found: {skipped_grounding})")


if __name__ == "__main__":
    main()
