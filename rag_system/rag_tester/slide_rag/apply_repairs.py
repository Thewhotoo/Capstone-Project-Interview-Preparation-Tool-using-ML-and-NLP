"""Apply a hand-written key-point repair batch to the question bank.

    python -m slide_rag.apply_repairs question_bank/repairs/batch1_2026-10-03.json [--dry-run]

A batch file maps question id -> fields to change:
  quality_score, quality_note, reference_answer, active, source_pages,
  question, difficulty                                     replace the question's field
  key_points: [ {point, quote?, followup?, followup_answer?}, ... ]
      in order; entry i updates existing key point i (fields not given are kept),
      entries beyond the existing ones add new points (quote, followup and
      followup_answer required). Missing trailing entries remove those points.

Each changed point drops its enrichment `variants` (paraphrases of the old wording);
a changed follow-up drops its `followup_replies`. Every point is checked against
its slide quote (MiniLM cosine, same 0.35 floor as qbank.py) and reported if weak.
`curated` is recomputed (active and score >= 8, or >= 7 on a most-asked topic) and the
batch name is recorded in the question's `repairs` list. Files keep their layout.

A NEW question (an id not in the bank) needs "new": true and the full question:
  subject, topic_id, topic, difficulty, question, reference_answer, quality_score,
  quality_note, source_pages, and key_points with point, quote, followup, followup_answer.
Unit, coverage and priority are copied from another question on the topic, or from the
topic map (knowledge_base_v2/<subject>/topic_map.json); it is marked hand-written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from slide_rag.interview_priority import tier

BANK = Path(__file__).resolve().parents[1] / "question_bank"
KB = Path(__file__).resolve().parents[1] / "knowledge_base_v2"
NEW_FIELDS = ("subject", "topic_id", "topic", "difficulty", "question", "reference_answer",
              "quality_score", "quality_note", "source_pages", "key_points")
HAND_WRITTEN_CONFIDENCE = 0.9   # selector weight; no generation evidence to rank a hand-written question by
POINT_QUOTE_SIM = 0.35


def curated(q: dict) -> bool:
    s = q.get("quality_score", 0)
    return q.get("active") is True and (s >= 8 or (tier(q["topic_id"]) == 3 and s >= 7))


def _new_question(qid: str, change: dict, index: dict) -> dict:
    missing = [f for f in NEW_FIELDS if f not in change]
    if missing:
        raise SystemExit(f"{qid}: a new question needs {missing}")
    if not qid.startswith(change["topic_id"] + "."):
        raise SystemExit(f"{qid}: id must start with its topic_id")
    sibling = next((q for q in index.values() if q["topic_id"] == change["topic_id"]), None)
    if sibling:
        meta = {k: sibling[k] for k in ("unit", "priority", "topic_coverage")}
    else:
        topics = json.loads((KB / change["subject"] / "topic_map.json").read_text(encoding="utf-8"))
        topics = topics if isinstance(topics, list) else list(topics.values())
        t = next((t for t in topics if t.get("id") == change["topic_id"]), None)
        if t is None:
            raise SystemExit(f"{qid}: topic {change['topic_id']} is not in the topic map")
        meta = {"unit": t.get("unit", ""), "priority": t.get("priority", "high"),
                "topic_coverage": t.get("coverage", "good")}
    q = {"id": qid, **{k: change[k] for k in ("subject", "topic_id", "topic")}, **meta,
         "question": change["question"], "difficulty": change["difficulty"],
         "reference_answer": change["reference_answer"], "key_points": [],
         "source_pages": change["source_pages"], "source_sections": change.get("source_sections", []),
         "runtime": "hand-written", "prompt_version": "hand", "review": "hand_written",
         "confidence": HAND_WRITTEN_CONFIDENCE, "confidence_signals": {"hand_written": 1.0},
         "active": change.get("active", True), "interview_priority": tier(change["topic_id"])}
    return q


def apply(batch_path: Path, dry_run: bool = False) -> None:
    batch = json.loads(batch_path.read_text(encoding="utf-8"))["questions"]
    name = batch_path.stem
    files = {p: json.loads(p.read_text(encoding="utf-8")) for p in sorted(BANK.glob("*.json"))}
    index = {q["id"]: q for items in files.values() for q in items}
    unknown = {qid for qid in set(batch) - set(index) if not batch[qid].get("new")}
    if unknown:
        raise SystemExit(f"unknown question ids: {sorted(unknown)}")
    for qid in sorted(set(batch) - set(index)):
        q = _new_question(qid, batch[qid], index)
        path = BANK / f"{q['subject']}.json"
        files[path].append(q)
        index[qid] = q

    checks = []
    for qid, change in batch.items():
        q = index[qid]
        for f in ("quality_score", "quality_note", "reference_answer", "active", "question", "difficulty",
                  "source_pages"):
            if f in change:
                q[f] = change[f]
        if "key_points" in change:
            old, new = q["key_points"], []
            for i, kp in enumerate(change["key_points"]):
                if i < len(old):
                    cur = dict(old[i])
                    if kp.get("point") and kp["point"] != cur.get("point"):
                        cur.pop("variants", None)
                    if kp.get("followup") and kp["followup"] != cur.get("followup"):
                        cur.pop("followup_replies", None)
                    cur.update(kp)
                else:
                    missing = [f for f in ("point", "quote", "followup", "followup_answer") if not kp.get(f)]
                    if missing:
                        raise SystemExit(f"{qid}: new key point {i} needs {missing}")
                    cur = dict(kp)
                new.append(cur)
                checks.append((qid, i, cur["point"], cur.get("quote", "")))
            q["key_points"] = new
        q["curated"] = curated(q)
        q["repairs"] = sorted(set(q.get("repairs", [])) | {name})

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    weak = 0
    for qid, i, point, quote in checks:
        if not quote:
            print(f"  WARN {qid} KP{i}: no slide quote")
            weak += 1
            continue
        a, b = model.encode([point, quote], normalize_embeddings=True)
        if float(a @ b) < POINT_QUOTE_SIM:
            print(f"  WARN {qid} KP{i}: point-quote similarity {float(a @ b):.2f} < {POINT_QUOTE_SIM}")
            weak += 1
    print(f"{len(batch)} questions, {len(checks)} key points checked, {weak} weak quote links")
    print("now curated:", sum(index[q]['curated'] for q in batch), "of", len(batch),
          "| inactive:", [q for q in batch if index[q].get("active") is not True])
    if dry_run:
        print("(dry run: nothing written)")
        return
    for path, items in files.items():
        newline = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
        with path.open("w", encoding="utf-8", newline=newline) as fh:
            fh.write(json.dumps(items, ensure_ascii=False, indent=1))
    print("written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply(Path(args.batch).resolve(), args.dry_run)
