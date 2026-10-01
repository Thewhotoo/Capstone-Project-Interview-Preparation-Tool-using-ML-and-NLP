"""Stage 8 -- per-subject diagnostic report (report.json + report.md).

Shows what the pipeline did to a subject so a different slide style shows up
immediately: slide types, what was dropped and why, what needs the vision
stage, section sizes, worked problems, and a few random sections to eyeball.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from .extract import SlideRecord
from .sections import Section


def build_report(subject: str, slides: list[SlideRecord], sections: list[Section],
                 boilerplate: set[str], out_dir: Path, sample: int = 6, seed: int = 7) -> dict:
    types = Counter(s.type for s in slides)
    dropped = Counter(s.dropped for s in slides if s.dropped)
    vision = Counter(r for s in slides if not s.dropped for r in s.needs_vision)
    vision_slides = sum(1 for s in slides if not s.dropped and s.needs_vision)
    words = sorted(sec.words for sec in sections)
    problems = [sec for sec in sections if sec.is_problem]
    decks = Counter((sec.deck, sec.deck_title) for sec in sections)
    empty_sections = sum(1 for sec in sections if not sec.text)
    rep = {
        "subject": subject,
        "pdfs": sorted({s.pdf for s in slides}),
        "slides": len(slides),
        "slide_types": dict(types.most_common()),
        "dropped": dict(dropped.most_common()),
        "content_slides": sum(1 for s in slides if not s.dropped),
        "needs_vision_slides": vision_slides,
        "needs_vision_by_reason": dict(vision.most_common()),
        "removed_running_text": sorted(boilerplate),
        "sections": len(sections),
        "sections_without_text": empty_sections,
        "section_words": {
            "mean": round(sum(words) / max(len(words), 1), 1),
            "median": words[len(words) // 2] if words else 0,
            "max": words[-1] if words else 0,
            "under_40": sum(1 for w in words if w < 40),
        },
        "slides_per_section_mean": round(sum(len(s.pages) for s in sections) / max(len(sections), 1), 2),
        "problems": {"sections": len(problems), "unsolved": sum(1 for p in problems if p.unsolved)},
        "decks": [{"deck": d, "title": t, "sections": n} for (d, t), n in sorted(decks.items())],
    }
    (out_dir / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

    rng = random.Random(seed)
    picks = rng.sample([s for s in sections if s.text], min(sample, len(sections)))
    md = [f"# Ingestion report: {subject}", ""]
    md += [f"- PDFs: {', '.join(rep['pdfs'])}",
           f"- Slides: {rep['slides']} ({rep['content_slides']} kept as content)",
           f"- Sections: {rep['sections']} (mean {rep['section_words']['mean']} words, "
           f"median {rep['section_words']['median']}, max {rep['section_words']['max']}, "
           f"{rep['section_words']['under_40']} under 40 words; "
           f"{rep['slides_per_section_mean']} slides per section)",
           f"- Needs vision stage: {vision_slides} slides {rep['needs_vision_by_reason']}",
           f"- Worked problems: {rep['problems']['sections']} sections, {rep['problems']['unsolved']} with no explicit "
           f"'Solution/Answer' marker (may still show working; Stage 7 must check before using them)",
           f"- OCR'd picture-only slides: {sum(1 for s in slides if s.ocr)}",
           f"- Personal notes (PDF annotations) removed: {sum(len(s.removed_notes) for s in slides)} lines "
           f"on {sum(1 for s in slides if s.removed_notes)} slides",
           f"- Removed running header/footer text: {rep['removed_running_text']}", "",
           "## Slide types", ""]
    md += [f"| {t} | {c} |" for t, c in types.most_common()]
    md += ["", "## Dropped", ""] + [f"| {t} | {c} |" for t, c in dropped.most_common()]
    md += ["", "## Decks", ""] + [f"- deck {d['deck']}: {d['title'] or '(untitled)'} -- {d['sections']} sections"
                                  for d in rep["decks"]]
    md += ["", "## Random sections", ""]
    for sec in picks:
        md += [f"### [{sec.id}] {sec.title}  (p.{sec.page_start}-{sec.page_end}, {sec.words} words, "
               f"types {sec.slide_types})", "", "```", sec.text[:1500], "```", ""]
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")
    return rep
