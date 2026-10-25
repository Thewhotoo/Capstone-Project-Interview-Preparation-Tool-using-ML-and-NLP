"""
Label real answers in private/human_items.jsonl on the 0-4 tier rubric.

Blind by design: the evaluator's score is never shown while labelling.
Each annotator labels independently (--annotator NAME); agreement between
annotators is the ceiling any evaluator can reasonably reach.

    py -3.13 benchmarks/evaluator/label_answers.py --annotator mayuran          # label in the terminal
    py -3.13 benchmarks/evaluator/label_answers.py --export-sheet riya.csv      # or: blind CSV for Excel/Sheets
    py -3.13 benchmarks/evaluator/label_answers.py --import-sheet riya.csv --annotator riya
    py -3.13 benchmarks/evaluator/label_answers.py --agreement
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_evaluator import HUMAN_ITEMS, qwk, spearman  # noqa: E402

RUBRIC = """\
  4 excellent  correct, specific to THIS project, explains why/how, shows real ownership
  3 good       correct and specific, but brief or missing the why
  2 partial    on topic and plausible, but vague or only half the answer
  1 poor       generic/textbook, keyword list, or mostly unsupported by the resume
  0 worthless  non-answer, off-topic, or technically wrong
  Judge correctness and specificity. Do NOT reward length, confidence or jargon."""


def _load():
    return [json.loads(l) for l in HUMAN_ITEMS.read_text(encoding="utf-8").splitlines() if l.strip()]


def _save(rows):
    tmp = HUMAN_ITEMS.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(HUMAN_ITEMS)


def label(annotator: str):
    rows = _load()
    todo = [r for r in rows if not any(l["annotator"] == annotator for l in r.get("labels", []))]
    print(f"{len(todo)} answers left for {annotator!r}.\n\n{RUBRIC}\n")
    for n, r in enumerate(todo, 1):
        g = r["grounding"]
        print("=" * 78)
        print(f"[{n}/{len(todo)}] PROJECT: {g['title']}")
        print(textwrap.fill("RESUME: " + (g.get("summary") or "")[:600], 78))
        print(f"\nQ: {r['question']}\n")
        print(textwrap.fill("A: " + r["answer"], 78))
        while True:
            choice = input("\ntier 0-4, s=skip, q=quit > ").strip().lower()
            if choice in {"0", "1", "2", "3", "4", "s", "q"}:
                break
        if choice == "q":
            break
        if choice == "s":
            continue
        r.setdefault("labels", []).append(
            {"annotator": annotator, "tier": int(choice), "at": datetime.now(timezone.utc).isoformat()})
        _save(rows)  # save after every label so nothing is lost
    print("saved.")


SHEET_COLUMNS = ["item_id", "project", "resume_says", "question", "answer", "score_0_to_4", "notes"]


def export_sheet(path: str, annotator: str | None, seed: int = 7):
    """Writes a blind, shuffled CSV for labelling in Excel / Google Sheets (no Python
    needed). Never contains the app's own score. With --annotator, skips answers
    that person already labelled."""
    rows = _load()
    todo = [r for r in rows if not annotator or not any(l["annotator"] == annotator for l in r.get("labels", []))]
    random.Random(seed).shuffle(todo)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:   # BOM so Excel shows accents correctly
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for r in todo:
            g = r["grounding"]
            writer.writerow({"item_id": r["item_id"], "project": g["title"], "resume_says": (g.get("summary") or "")[:600],
                             "question": r["question"], "answer": r["answer"], "score_0_to_4": "", "notes": ""})
    print(f"wrote {len(todo)} answers to {path}\n\nRubric to send with it:\n{RUBRIC}")


def import_sheet(path: str, annotator: str):
    rows = _load()
    by_id = {r["item_id"]: r for r in rows}
    added = skipped = 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for line in csv.DictReader(fh):
            score = (line.get("score_0_to_4") or "").strip()
            r = by_id.get((line.get("item_id") or "").strip())
            if r is None or score not in {"0", "1", "2", "3", "4"}:
                skipped += 1
                continue
            r["labels"] = [l for l in r.get("labels", []) if l["annotator"] != annotator]   # re-import replaces
            r["labels"].append({"annotator": annotator, "tier": int(score), "at": datetime.now(timezone.utc).isoformat(),
                                **({"notes": line["notes"].strip()} if (line.get("notes") or "").strip() else {})})
            added += 1
    _save(rows)
    print(f"imported {added} labels for {annotator!r} ({skipped} rows skipped: blank/invalid score or unknown id)")


def agreement():
    rows = _load()
    annotators = sorted({l["annotator"] for r in rows for l in r.get("labels", [])})
    print(f"items={len(rows)}  labelled={sum(bool(r.get('labels')) for r in rows)}  annotators={annotators}")
    for i, a in enumerate(annotators):
        for b in annotators[i + 1:]:
            pairs = []
            for r in rows:
                la = {l["annotator"]: l["tier"] for l in r.get("labels", [])}
                if a in la and b in la:
                    pairs.append((la[a], la[b]))
            if len(pairs) < 5:
                print(f"{a} vs {b}: only {len(pairs)} shared items")
                continue
            x, y = zip(*pairs)
            exact = sum(p == q for p, q in pairs) / len(pairs)
            within1 = sum(abs(p - q) <= 1 for p, q in pairs) / len(pairs)
            print(f"{a} vs {b}: n={len(pairs)} qwk={qwk(list(x), list(y)):.2f} "
                  f"spearman={spearman(x, y):+.2f} exact={exact:.0%} within-1={within1:.0%}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator")
    ap.add_argument("--agreement", action="store_true")
    ap.add_argument("--export-sheet", metavar="CSV", help="write a blind CSV to label in Excel/Google Sheets")
    ap.add_argument("--import-sheet", metavar="CSV", help="read a filled-in CSV back (needs --annotator)")
    args = ap.parse_args()
    if not HUMAN_ITEMS.exists():
        sys.exit(f"{HUMAN_ITEMS} not found - run collect_answers.py first")
    if args.export_sheet:
        export_sheet(args.export_sheet, args.annotator)
    elif args.import_sheet:
        if not args.annotator:
            ap.error("--import-sheet needs --annotator NAME")
        import_sheet(args.import_sheet, args.annotator)
    elif args.agreement:
        agreement()
    elif args.annotator:
        label(args.annotator)
    else:
        ap.error("pass --annotator NAME or --agreement")
