"""Retrieval evaluation: does the retrieved context come from the right slides?

Two query sets per subject:

  gold   -- slide_rag/eval/gold_<subject>.json, hand-written interview-style
            questions, each with the slide pages that answer it (labelled from
            the slide titles/content BEFORE looking at any retrieval output).
  probe  -- generated automatically from the slides themselves: for a random
            sample of content slides, the query is one of its bullet points
            and the expected page is that slide. Easier (the words are on the
            slide), but covers thousands of slides with no labelling effort.

Metrics for the top-k results of each query:
  section hit@k -- some retrieved section contains an expected page
  slide hit@k   -- the best-matching slide of some retrieved result IS an
                   expected page (stricter: pins the exact slide)
  MRR           -- mean reciprocal rank of the first section hit

The old page-level index (knowledge_base/, retrieval.py) is scored on the
same queries as a baseline. Its chunks record one page but a merged chunk
also holds the next page's text, so it is credited for page and page+1.

    python -m slide_rag.retrieval_eval                    # all subjects, gold + probe
    python -m slide_rag.retrieval_eval --subject dbms --show-misses
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from .retrieve import KB_DIR, SubjectIndex

EVAL_DIR = Path(__file__).resolve().parent / "eval"
BASE = Path(__file__).resolve().parent.parent


def load_gold(subject: str) -> dict[str, list[dict]]:
    """gold_<subject>.json -> "gold"; gold_<subject>_<name>.json -> "<name>" (e.g. "diagram")."""
    sets = {}
    for path in sorted(EVAL_DIR.glob(f"gold_{subject}*.json")):
        rest = path.stem[len(f"gold_{subject}"):]
        if rest and not rest.startswith("_"):
            continue                      # gold_cnx.json is another subject
        sets["gold" if not rest else rest[1:]] = json.loads(path.read_text(encoding="utf-8"))
    return sets


def make_probes(subject: str, n: int = 150, seed: int = 11, kb_dir: Path = KB_DIR) -> list[dict]:
    """One bullet from each of n random content slides; expected page = that slide."""
    slides = json.loads((kb_dir / subject / "slides.json").read_text(encoding="utf-8"))
    rng = random.Random(seed)
    pool = [s for s in slides if not s["dropped"] and s["type"] in ("concept", "concept_diagram", "table")]
    rng.shuffle(pool)
    probes = []
    for s in pool:
        items = [it["text"] for it in s["items"] if 7 <= len(it["text"].split()) <= 30]
        if not items:
            continue
        probes.append({"query": rng.choice(items), "pages": [s["page"]], "pdf": s["pdf"]})
        if len(probes) >= n:
            break
    return probes


def _score(results_pages: list[tuple[list[int], int]], expected: set[int], k: int):
    """results_pages: [(section_pages, best_page)] in rank order."""
    sec_rank = next((r for r, (pages, _) in enumerate(results_pages[:k], 1) if expected & set(pages)), None)
    slide_hit = any(best in expected for _, best in results_pages[:k])
    return sec_rank, slide_hit


def evaluate_v2(subject: str, queries: list[dict], k_values=(1, 3, 5), kb_dir: Path = KB_DIR, **search_kw) -> dict:
    idx = SubjectIndex(subject, kb_dir)
    rows = []
    for q in queries:
        res = idx.search(q["query"], top_k=max(k_values), **search_kw)
        rows.append((q, [(r["pages"], r["best_page"]) for r in res], res))
    return _summarise(rows, k_values)


def evaluate_old(subject: str, queries: list[dict], k_values=(1, 3, 5)) -> dict | None:
    sys.path.insert(0, str(BASE))
    try:
        import retrieval as old
    except Exception as exc:                       # pragma: no cover
        print("old retrieval unavailable:", exc)
        return None
    if not (old.KNOWLEDGE_BASE_DIR / subject / "index.faiss").exists():
        return None
    rows = []
    for q in queries:
        res = old.retrieve_relevant_content(subject, q["query"], top_k=max(k_values))
        rows.append((q, [([r["page"], r["page"] + 1], r["page"]) for r in res], res))
    return _summarise(rows, k_values)


def _summarise(rows, k_values) -> dict:
    out = {"n": len(rows)}
    misses = []
    for k in k_values:
        sec_hits = slide_hits = 0
        for q, rp, _ in rows:
            rank, slide_hit = _score(rp, set(q["pages"]), k)
            sec_hits += rank is not None
            slide_hits += slide_hit
        out[f"section_hit@{k}"] = round(sec_hits / max(len(rows), 1), 3)
        out[f"slide_hit@{k}"] = round(slide_hits / max(len(rows), 1), 3)
    kmax = max(k_values)
    rr = 0.0
    for q, rp, res in rows:
        rank, _ = _score(rp, set(q["pages"]), kmax)
        rr += 1 / rank if rank else 0
        if rank is None:
            misses.append({"query": q["query"], "expected": q["pages"],
                           "got": [(r.get("title") or ", ".join(r.get("headings", [])[:1]), r.get("pages") or [r.get("page")])
                                   for r in res[:3]]})
    out["mrr"] = round(rr / max(len(rows), 1), 3)
    out["misses"] = misses
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    ap.add_argument("--kb", default=str(KB_DIR))
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--alpha", type=float, default=0.6)
    ap.add_argument("--probes", type=int, default=150)
    ap.add_argument("--show-misses", action="store_true")
    ap.add_argument("--json", help="write full results here")
    args = ap.parse_args()
    kb = Path(args.kb)
    subjects = [args.subject] if args.subject else sorted(p.name for p in kb.iterdir() if (p / "manifest.json").exists())
    results = {}
    for subject in subjects:
        sets = {**load_gold(subject), "probe": make_probes(subject, args.probes, kb_dir=kb)}
        for name, qs in sets.items():
            if not qs:
                continue
            new = evaluate_v2(subject, qs, kb_dir=kb, rerank=not args.no_rerank, alpha=args.alpha)
            old = None if args.no_baseline else evaluate_old(subject, qs)
            results[f"{subject}/{name}"] = {"v2": new, "old": old}
            line = (f"{subject:5} {name:7} n={new['n']:3}  v2: sec@1={new['section_hit@1']:.2f} "
                    f"sec@5={new['section_hit@5']:.2f} slide@5={new['slide_hit@5']:.2f} mrr={new['mrr']:.2f}")
            if old:
                line += (f"   | old: page@1={old['section_hit@1']:.2f} page@5={old['section_hit@5']:.2f} "
                         f"mrr={old['mrr']:.2f}")
            print(line)
            if args.show_misses and name != "probe":
                for m in new["misses"]:
                    print(f"      MISS {m['query']!r} expected {m['expected']} got {m['got']}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
