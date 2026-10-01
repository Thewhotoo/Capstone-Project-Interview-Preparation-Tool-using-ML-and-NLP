"""Stage 2 -- slide classification and cleaning.

Assigns every slide a type and removes slides that carry no teachable
content, without deleting anything: removed slides keep a `dropped` reason
so the report can show exactly what was taken out and why.

Types
  deck_title       first slide of a merged deck ("<course> - Unit 2", "Prof. ...")
  contents         contents / outline / syllabus slides (kept aside for naming)
  admin            thank-you, references, course objectives, acknowledgements
  quiz             in-slide MCQ ("1. What is ...? A) ... B) ...") -- not indexed for
                   retrieval (it asks, it doesn't teach), saved to quiz.json as
                   faculty-written examples for question generation
  divider          a title with (almost) no body -- marks a topic boundary
  image_only       no usable text at all (scanned / picture slide)
  image_heavy      mostly picture, little text survives
  problem          worked example / exercise / numerical
  code             code or pseudocode dominates
  table            contains a rebuilt table
  concept_diagram  real text plus a significant figure
  concept          text-driven concept slide

Cleaning
  * incremental builds -- consecutive slides with the same title where one's
    text is contained in the next; only the most complete version is kept
  * exact duplicates within a deck (reused slides)
"""
from __future__ import annotations

import re

from .extract import SlideRecord, normalize_key

_ADMIN_TITLE_RE = re.compile(
    r"^(thank(s| you)|any questions|questions\s*\??$|q\s*&\s*a|references?|text\s*-?\s*books?|reference\s*books?|"
    r"bibliography|acknowledg|course\s+(objectives?|outcomes?)|learning\s+outcomes?|credits?$|"
    r"web\s+references?|suggested\s+reading|further\s+reading)", re.I)
_CONTENTS_TITLE_RE = re.compile(
    r"^(contents?|table\s+of\s+contents|agenda|outline|course\s+(outline|content)|syllabus|topics?\s+(covered|to\s+be\s+covered)|"
    r"unit\s*[-–:]?\s*\d+\s*(syllabus|topics|contents)|overview\s+of\s+(the\s+)?(unit|course|module)"
    r"|unit\s*[-–:]\s*\d+\b|roadmap)\b", re.I)   # "Unit – 4 Network Layer ..." roadmap slides
_DECK_TITLE_RE = re.compile(r"department\s+of\s+computer\s+science|\bprof\.|\bdr\.\s|\bprofessor\b", re.I)
_PROBLEM_RE = re.compile(
    r"\b(example|examples|problem|problems|exercise|numerical|solution|solutions|solved|question|questions|"
    r"practice|quiz|worked|illustration|trace|tracing|dry\s*run)\b", re.I)
_PROBLEM_BODY_RE = re.compile(r"^\s*(find|calculate|compute|consider|given|determine|solve|show that|draw)\b", re.I)
_QUIZ_Q_RE = re.compile(r"^\s*(q\s*\d*[.:)]|\d{1,2}\s*[.)])\s*.+\?", re.I)
_QUIZ_OPT_RE = re.compile(r"(?:^|\s)\(?[A-Da-d][.)]\s+\S")
_COURSE_CODE_RE =re.compile(r"\bUE\d{2}[A-Z]{2}\d{3}[A-Z]{0,2}\b\s*[-–:]?\s*", re.I)
_EMAIL_RE = re.compile(r"\S+@\S+\.\w+")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _content_chars(s: SlideRecord) -> int:
    return len(s.title) + len(s.body_text())


def classify_slide(s: SlideRecord, boilerplate_titles: set[str]) -> str:
    body = s.body_text()
    body_chars = len(body)
    title = s.title.strip()
    visual = s.content_image_frac + s.diagram_frac

    whole = f"{title}\n{body}\n{s.largest_text}"
    if _DECK_TITLE_RE.search(whole) and 15 <= _content_chars(s) < 450 and not s.code and not s.tables:
        return "deck_title"          # before contents: title slides are often named "Unit 1: ..."
    if title and _CONTENTS_TITLE_RE.search(title):
        return "contents"
    if title and _ADMIN_TITLE_RE.search(title):
        return "admin"
    if _content_chars(s) < 15:
        return "image_only"
    if not title and body_chars < 200 and _EMAIL_RE.search(body):
        return "admin"
    # in-slide quiz MCQ: "1. What is ...?" followed by A) B) C) options, or an "MCQ Solution" slide
    if re.search(r"\bmcqs?\b", title, re.I):
        return "quiz"
    if (_QUIZ_Q_RE.search(title) or _QUIZ_Q_RE.search(body.split("\n")[0] if body else "")) \
            and len(_QUIZ_OPT_RE.findall(f"{title}\n{body}")) >= 2:
        return "quiz"
    if (title and body_chars < 25 and not s.code and not s.tables
            and visual < 0.1 and normalize_key(title) not in boilerplate_titles):
        return "divider"
    first_items = " ".join(it["text"] for it in s.items[:2])
    if _PROBLEM_RE.search(title) or _PROBLEM_BODY_RE.search(first_items):
        return "problem"
    if s.code and len(s.code) >= 0.5 * max(body_chars, 1):
        return "code"
    if s.tables:
        return "table"
    if visual >= 0.3 and body_chars < 200:
        return "image_heavy"
    if visual >= 0.12 or len(s.labels) >= 5:
        return "concept_diagram"
    return "concept"


def _vision_reasons(s: SlideRecord) -> list[str]:
    reasons = ["ocr_text"] if s.ocr else []      # OCR gets prose, not tables/formulas
    if s.type in ("image_only", "image_heavy"):
        reasons.append(s.type)
    elif s.type == "concept_diagram" or (s.type == "problem" and s.content_image_frac + s.diagram_frac >= 0.12):
        reasons.append("diagram")
    if s.type == "table" or (s.tables and any(not c for row in s.tables for c in row)):
        reasons.append("table")
    if s.formula_suspect:
        reasons.append("formula")
    return reasons


def _deck_name(s: SlideRecord, subject_names: set[str]) -> str:
    text = s.largest_text or s.title or ""
    for name in subject_names:
        text = re.sub(re.escape(name), "", text, flags=re.I)
    text = _COURSE_CODE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" -–:|")
    return text[:80]


def classify_and_clean(slides: list[SlideRecord], boilerplate: set[str]) -> list[SlideRecord]:
    """Classify, assign decks, collapse incremental builds and duplicates (in place)."""
    subject_names = {b for b in boilerplate if len(b) > 6}
    deck = 0
    deck_title = ""
    prev_pdf = None
    content_seen = False           # has the current deck had any non-title slide yet?
    for s in slides:
        if s.title and normalize_key(s.title) in boilerplate:
            s.title = ""                 # a running header that slipped into the title slot
        s.type = classify_slide(s, boilerplate)
        if s.pdf != prev_pdf:
            prev_pdf = s.pdf
            deck += 1
            deck_title = ""
            content_seen = False
        if s.type == "deck_title":
            # a title slide opens a new deck, unless the deck has only had title slides so far
            if content_seen:
                deck += 1
                deck_title = ""
                content_seen = False
            name = _deck_name(s, subject_names)
            if name and not _DECK_TITLE_RE.search(name):
                deck_title = name
        else:
            content_seen = True
        s.deck = deck
        s.deck_title = deck_title
        if s.type in ("deck_title", "contents", "admin", "quiz"):   # quizzes are kept in quiz.json
            s.dropped = s.type
        s.needs_vision = _vision_reasons(s)

    # incremental builds: same title, text contained in the next slide's text
    for a, b in zip(slides, slides[1:]):
        if a.dropped or b.dropped or a.deck != b.deck:
            continue
        if normalize_key(a.title) != normalize_key(b.title):
            continue
        ta, tb = _tokens(a.body_text()), _tokens(b.body_text())
        if not ta:
            continue
        if len(ta & tb) >= 0.9 * len(ta) and len(tb) >= len(ta):
            a.dropped = "incremental_build"

    # exact duplicates within a deck (reused slides)
    seen: dict[tuple[int, str], int] = {}
    for s in slides:
        if s.dropped or s.type == "image_only":
            continue
        key = (s.deck, normalize_key(s.full_text()))
        if len(key[1]) < 30:
            continue
        if key in seen:
            s.dropped = "duplicate"
        else:
            seen[key] = s.page
    return slides
