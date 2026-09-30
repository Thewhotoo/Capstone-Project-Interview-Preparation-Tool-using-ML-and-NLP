"""Topic lists -> slide sections (topic_map.json) with a coverage report.

Reads topics/<subject>.txt ("Name | hints | priority", priority optional, "low" =
rarely asked in interviews; "#" lines are unit headers), searches
the subject's index with "name: hints", and keeps the sections the MS MARCO
cross-encoder scores as relevant to the topic NAME (so a long hint list cannot
inflate the match). Coverage:

  good     best section scores >= GOOD_SCORE
  thin     best section scores >= THIN_SCORE
  missing  nothing relevant -- the topic gets no questions

Output: knowledge_base_v2/<subject>/topic_map.json and topic_coverage.md.

    python -m slide_rag.topics                 # all subjects
    python -m slide_rag.topics --subject os
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .retrieve import KB_DIR, SubjectIndex, _reranker

TOPICS_DIR = Path(__file__).resolve().parent.parent / "topics"
CANDIDATES = 8           # sections retrieved per topic
MAX_SECTIONS = 4         # sections kept per topic
GOOD_SCORE = 3.0         # cross-encoder logit (topic name vs section)
THIN_SCORE = 0.0
KEEP_MARGIN = 2.5        # keep sections within this many logits of the best one (tighter = less topic drift)


@dataclass
class Topic:
    id: str
    subject: str
    name: str
    hints: list[str]
    unit: str = ""
    priority: str = "high"      # "low" = rarely asked in interviews -> one question only
    sections: list[int] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    coverage: str = "missing"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def load_topics(subject: str) -> list[Topic]:
    topics, unit, seen = [], "", set()
    for raw in (TOPICS_DIR / f"{subject}.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            unit = line.lstrip("# ").strip()
            continue
        name, _, rest = line.partition("|")
        hints, _, priority = rest.partition("|")
        name = name.strip()
        tid = f"{subject}.{slug(name)}"
        if tid in seen:
            continue
        seen.add(tid)
        topics.append(Topic(id=tid, subject=subject, name=name, unit=unit,
                            priority="low" if priority.strip().lower() == "low" else "high",
                            hints=[h.strip() for h in hints.split(",") if h.strip()]))
    return topics


_STOP = {"and", "the", "of", "in", "vs", "for", "with", "to", "a", "an", "basics", "concepts", "types"}


def _mentions(t: Topic, hit: dict) -> bool:
    """Does the section's text contain the topic name's key terms (stem match) or a multi-word hint?"""
    text = f"{hit['title']}\n{hit['text']}".lower()
    words = [w for w in re.findall(r"[a-z0-9+#]+", t.name.lower()) if w not in _STOP and len(w) > 2]
    if words and all(w[:6] in text for w in words):
        return True
    return any(len(h.split()) >= 2 and h.lower() in text for h in t.hints)


def map_subject(subject: str, kb_dir: Path = KB_DIR) -> list[Topic]:
    idx = SubjectIndex(subject, kb_dir)
    ce = _reranker()
    topics = load_topics(subject)
    for t in topics:
        query = f"{t.name}: {', '.join(t.hints)}" if t.hints else t.name
        hits = idx.search(query, top_k=CANDIDATES)
        if not hits:
            continue
        # score against the name plus a few hints: bare short names ("Tries") score poorly on their own,
        # while the full hint list could inflate a weak match
        ce_query = f"{t.name} ({', '.join(t.hints[:3])})" if t.hints else t.name
        scores = ce.predict([(ce_query, f"{h['title']}\n{h['text']}"[:2000]) for h in hits])
        ranked = sorted(zip((float(s) for s in scores), hits), key=lambda x: -x[0])
        best = ranked[0][0]
        kept = [(s, h) for s, h in ranked if s >= THIN_SCORE and s >= best - KEEP_MARGIN][:MAX_SECTIONS]
        if not kept:
            # lexical fallback: the cross-encoder under-scores some short or oddly worded topics;
            # accept retrieved sections whose own text contains the topic's key terms (as "thin")
            kept = [(s, h) for s, h in ranked if _mentions(t, h)][:2]
            if kept:
                best = max(best, THIN_SCORE)
        t.sections = [h["section_id"] for _, h in kept]
        t.scores = [round(s, 2) for s, _ in kept]
        t.pages = sorted({p for _, h in kept for p in h["pages"]})
        t.coverage = "good" if best >= GOOD_SCORE else ("thin" if best >= THIN_SCORE else "missing")
    out = kb_dir / subject
    (out / "topic_map.json").write_text(json.dumps([asdict(t) for t in topics], indent=1, ensure_ascii=False),
                                        encoding="utf-8")
    _report(subject, topics, idx, out)
    return topics


def _report(subject: str, topics: list[Topic], idx: SubjectIndex, out: Path) -> None:
    counts = {c: sum(t.coverage == c for t in topics) for c in ("good", "thin", "missing")}
    md = [f"# Topic coverage: {subject}", "",
          f"{len(topics)} topics: {counts['good']} good, {counts['thin']} thin, {counts['missing']} missing", "",
          "| Coverage | Topic | Unit | Best score | Sections (pages) |", "|---|---|---|---|---|"]
    order = {"missing": 0, "thin": 1, "good": 2}
    for t in sorted(topics, key=lambda t: (order[t.coverage], t.unit)):
        secs = "; ".join(f"{idx.sections[s]['title'][:40]} (p.{idx.sections[s]['page_start']}"
                         f"-{idx.sections[s]['page_end']})" for s in t.sections)
        md.append(f"| {t.coverage} | {t.name} | {t.unit} | {t.scores[0] if t.scores else '-'} | {secs} |")
    (out / "topic_coverage.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    args = ap.parse_args()
    subjects = [args.subject] if args.subject else sorted(p.stem for p in TOPICS_DIR.glob("*.txt"))
    for s in subjects:
        topics = map_subject(s)
        c = {k: sum(t.coverage == k for t in topics) for k in ("good", "thin", "missing")}
        print(f"{s:5} {len(topics):3} topics: {c['good']} good, {c['thin']} thin, {c['missing']} missing")


if __name__ == "__main__":
    main()
