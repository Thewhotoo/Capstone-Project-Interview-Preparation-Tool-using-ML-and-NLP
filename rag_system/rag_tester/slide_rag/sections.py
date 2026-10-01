"""Stage 4 -- regroup consecutive slides into self-contained sections.

One idea usually spans several slides ("Deadlocks", "Deadlocks (contd.)",
a diagram slide, an example). A section is the unit that gets retrieved,
questioned and graded against.

A slide joins the current section when (same deck, and the section stays
under SECTION_MAX_WORDS):
  * its title matches after removing continuation markers ("(contd.)",
    "(more)", "- 2", "Part II" ...), or
  * it has no title and its content is similar to the section's last slide, or
  * its title shares the section's stem ("Hashing: Chaining" after
    "Hashing: Linear Probing") and the content is clearly related, or
  * it is the solution/answer slide of a worked problem.
Picture-only slides are attached to the section they sit in, so their page
is still cited and queued for the vision stage.
Dividers start a new section and become the "topic" breadcrumb for what
follows; deck changes always start a new section.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

import numpy as np

from .extract import SlideRecord

SECTION_MAX_WORDS = 450
UNTITLED_SIM = 0.35
STEM_SIM = 0.6

_CONT_RE = re.compile(
    r"\s*[\(\[]\s*(contd|cont'?d|cont|continued|cntd|more|continuation)\.?\s*[\)\]]\s*\.*$"
    r"|\s*[-–:,]?\s+(contd|cont'?d|cont|continued|cntd|continuation)\.*$"
    r"|(\s+|\s*[-–:]\s*)(part\s+)?\(?([ivx]{1,4}|\d{1,2})\)?\s*$", re.I)   # needs a separator: keeps "IPv4"
_GENERIC_STEMS = {"example", "examples", "problem", "exercise", "solution", "introduction", "note",
                  "notes", "summary", "recap", "questions", "question", "overview", "definition"}
_SOLUTION_RE = re.compile(r"\b(solution|answer|ans|solved|explanation)\b", re.I)


def normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[…]", "", t)
    prev = None
    while prev != t:
        prev = t
        t = _CONT_RE.sub("", t).strip(" .:-–|")
    return re.sub(r"\s+", " ", t)


def title_stem(title: str) -> str:
    t = normalize_title(title)
    stem = re.split(r"\s*[:–—]\s*|\s+-\s+", t)[0].strip()
    return "" if stem in _GENERIC_STEMS or len(stem) < 3 else stem


@dataclass
class Section:
    id: int
    subject: str
    pdf: str
    deck: int
    deck_title: str
    topic: str
    title: str
    pages: list[int] = field(default_factory=list)
    slide_types: dict = field(default_factory=dict)
    text: str = ""
    words: int = 0
    part: int = 1
    is_problem: bool = False
    unsolved: bool = False       # worked problem with no explicit "Solution/Answer" marker
    vision_pages: dict = field(default_factory=dict)   # page -> reasons

    @property
    def page_start(self) -> int:
        return min(self.pages)

    @property
    def page_end(self) -> int:
        return max(self.pages)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["page_start"], d["page_end"] = self.page_start, self.page_end
        return d


def _slide_words(s: SlideRecord) -> int:
    return len(s.full_text().split())


def build_sections(slides: list[SlideRecord], embeddings: np.ndarray, subject: str) -> list[Section]:
    """`embeddings[i]` is the L2-normalised embedding of slides[i].full_text()."""
    sections: list[Section] = []
    members: list[list[int]] = []       # slide indices per section
    topic_by_deck: dict[int, str] = {}

    def start(i: int, part: int = 1) -> None:
        s = slides[i]
        sections.append(Section(
            id=len(sections), subject=subject, pdf=s.pdf, deck=s.deck, deck_title=s.deck_title,
            topic=topic_by_deck.get(s.deck, "") or s.running_header, title=s.title, part=part))
        members.append([i])

    for i, s in enumerate(slides):
        if s.type == "divider":
            topic_by_deck[s.deck] = s.title
            continue
        if s.dropped:
            continue
        cur = members[-1] if members else None
        sec = sections[-1] if sections else None
        if cur is None or sec.deck != s.deck or sec.pdf != s.pdf:
            start(i)
            continue
        last = slides[cur[-1]]
        words = sum(_slide_words(slides[j]) for j in cur)

        if s.type == "image_only":
            cur.append(i)
            continue

        sim = float(embeddings[i] @ embeddings[cur[-1]])
        t_s, t_last = normalize_title(s.title), normalize_title(last.title)
        join = False
        if t_s and t_s == t_last:
            join = True
        elif not t_s:
            join = sim >= UNTITLED_SIM
        elif sec.is_problem or last.type == "problem":
            join = bool(_SOLUTION_RE.search(s.title)) or (t_s == normalize_title(sec.title))
        if not join and t_s:
            stem = title_stem(s.title)
            join = bool(stem) and stem == title_stem(last.title) and sim >= STEM_SIM
        if s.type == "problem" and last.type != "problem" and t_s != t_last:
            join = False                 # a new worked example starts its own section

        if join and words + _slide_words(s) > SECTION_MAX_WORDS:
            start(i, part=sec.part + 1)
            continue
        if join:
            cur.append(i)
        else:
            start(i)
        if sections[-1].is_problem is False and s.type == "problem":
            sections[-1].is_problem = True

    for sec, idx in zip(sections, members):
        _finalize(sec, [slides[j] for j in idx])
    # drop sections that ended up with no text at all (lone picture slides stay
    # only if nothing else exists for them -- they are still reported)
    return sections


def _finalize(sec: Section, ss: list[SlideRecord]) -> None:
    sec.pages = [s.page for s in ss]
    sec.slide_types = dict(Counter(s.type for s in ss))
    titled = [s.title for s in ss if s.title]
    if titled:
        sec.title = Counter(normalize_title(t) for t in titled).most_common(1)[0][0]
        # keep the original casing of the first slide with that normalised title
        sec.title = next(t for t in titled if normalize_title(t) == sec.title)
        sec.title = _CONT_RE.sub("", sec.title).strip(" .:-–") or sec.title
    parts = []
    head = normalize_title(sec.title)
    for s in ss:
        if s.type == "image_only":
            continue
        chunk = s.body_text()
        if s.title and normalize_title(s.title) != head:
            chunk = f"{s.title}\n{chunk}"
        if chunk.strip():
            parts.append(chunk.strip())
    sec.text = "\n\n".join(parts)
    sec.words = len(sec.text.split())
    sec.is_problem = sec.is_problem or any(s.type == "problem" for s in ss)
    sec.unsolved = sec.is_problem and not any(
        _SOLUTION_RE.search(s.full_text()) for s in ss)
    sec.vision_pages = {s.page: s.needs_vision for s in ss if s.needs_vision}
