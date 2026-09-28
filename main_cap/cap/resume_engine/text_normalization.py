"""
Text Normalization — Phase 1 (parser generalization) shared, dependency-free
utilities for cleaning up the common PDF-extraction artifacts that were
defeating Section Detection and Entry Clustering on real single-column
resumes.

DELIBERATELY GENERAL, NEVER RESUME-SPECIFIC: every function here keys off a
STRUCTURAL pattern (a drop-cap glyph split, a leading bullet glyph, a
leading enumeration, an action-verb-led sentence, an open trailing list),
never off any literal string from a particular resume. There is no filename
check, no per-candidate special case, and no hard-coded institution/company/
project name anywhere in this module.

Two consumers:
  - `sections.py` calls `normalize_heading` when classifying a header line,
    so a glyph-split heading ("T ECHNICAL   S KILLS") matches the gazetteer
    the same as its intended form ("TECHNICAL SKILLS"). The underlying
    spans are left untouched — only the text used for *matching* is
    normalized — so no downstream stage sees rewritten content.
  - the entry parsers (`project_parser.py`, `experience_parser.py`) call
    `normalize_title` / the bullet + action-verb helpers to clean displayed
    titles and to decide entry boundaries structurally rather than by font
    alone.

All thresholds/lexicons here are provisional starting values, the same
documentation discipline `sections.py` / `layout.py` already follow.
"""

from __future__ import annotations

import re

# ── Characters ──────────────────────────────────────────────────────────────
# Bullet glyphs that introduce a list item. A leading hyphen counts as a
# bullet ONLY when followed by whitespace ("- item"), never mid-word
# ("end-to-end"). En/em dashes are common bullet glyphs in real resumes.
_DOT_BULLETS = "•●▪‣◦·∙"
_DASH_BULLETS = "–—"  # en dash, em dash
_BULLET_LEAD_RE = re.compile(r"^\s*(?:[" + _DOT_BULLETS + _DASH_BULLETS + r"*]+|-(?=\s))\s*")
_ENUMERATION_RE = re.compile(r"^\s*(?:\(?\d{1,2}\)|\d{1,2}[.):])\s+")

# The Unicode replacement character and a couple of common mojibake code
# points PyMuPDF emits when a dash/bullet glyph can't be decoded. Mapped to
# a plain hyphen (their overwhelmingly common intended meaning in a resume
# title, e.g. "Chronos <?> Distributed Task System"); leading/trailing ones
# are stripped rather than left as a dangling separator.
_MOJIBAKE_TO_DASH = ("�",)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_TRAILING_YEAR_RE = re.compile(r"[\s,\-–—]*\b(?:19|20)\d{2}\s*(?:[-–—]\s*(?:present|current))?\s*$", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Whitespace-collapse + mojibake repair, safe to apply to any text.
    Replacement-character mojibake becomes a hyphen; runs of whitespace
    collapse to a single space. Does NOT rewrite words, strip content, or
    change case — the conservative floor every other helper builds on."""
    if not text:
        return ""
    for ch in _MOJIBAKE_TO_DASH:
        text = text.replace(ch, "-")
    text = re.sub(r"\s+", " ", text).strip()
    # Collapse a dangling separator left where a mojibake glyph sat at an
    # edge, or doubled separators created by the replacement above.
    text = re.sub(r"\s*-\s*-\s*", " - ", text)
    text = text.strip(" -–—,")
    return text.strip()


def repair_glyph_split(text: str) -> str:
    """Repairs the "drop-cap"/small-caps extraction artifact where a
    heading's first letter is emitted as its own run, e.g.
    "T ECHNICAL   S KILLS" -> "TECHNICAL SKILLS", "A BOUT M E" -> "ABOUT ME".

    Structural rule, not a word list: a single UPPERCASE letter immediately
    followed by an ALL-CAPS token (length >= 2) is the split first letter of
    that token and is glued back on; a run of 2+ consecutive single
    uppercase letters (the tail case, "M E" -> "ME") is glued into one word.
    Both are patterns that only occur in this rendering artifact, never in
    ordinary prose (which mixes case), so this never fires on body text —
    and `sections.py` only ever calls it on short, header-candidate lines
    anyway. Initials like "M S" in a NAME line are never passed here (name
    handling lives in contact_parser, not header classification)."""
    if not text:
        return ""
    tokens = text.split()
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if (
            len(tok) == 1 and tok.isalpha() and tok.isupper()
            and nxt is not None and len(nxt) >= 2 and nxt.isupper() and nxt.isalpha()
        ):
            merged.append(tok + nxt)
            i += 2
            continue
        merged.append(tok)
        i += 1

    # Second pass: glue a run of 2+ consecutive single uppercase letters into
    # one word ("A BOUT M E" -> after pass 1 "ABOUT M E" -> "ABOUT ME").
    out: list[str] = []
    j = 0
    while j < len(merged):
        if len(merged[j]) == 1 and merged[j].isalpha() and merged[j].isupper():
            run = [merged[j]]
            k = j + 1
            while k < len(merged) and len(merged[k]) == 1 and merged[k].isalpha() and merged[k].isupper():
                run.append(merged[k])
                k += 1
            if len(run) >= 2:
                out.append("".join(run))
                j = k
                continue
        out.append(merged[j])
        j += 1
    return " ".join(out)


def normalize_heading(text: str) -> str:
    """The text a header line should be MATCHED as: mojibake-cleaned and
    glyph-split-repaired. Idempotent on already-clean headings
    ("Experience" -> "Experience", "TECHNICAL SKILLS" -> "TECHNICAL
    SKILLS")."""
    return repair_glyph_split(clean_text(text))


def strip_leading_bullet(text: str) -> str:
    """Removes a single leading bullet/dash glyph (+ following whitespace).
    Leaves mid-word hyphens ("end-to-end") intact."""
    return _BULLET_LEAD_RE.sub("", text, count=1).strip()


def strip_leading_enumeration(text: str) -> str:
    """Removes a leading list number a resume prints before a project title,
    e.g. "1. Chronos" -> "Chronos", "2) Foo" -> "Foo"."""
    return _ENUMERATION_RE.sub("", text, count=1).strip()


def starts_with_bullet(text: str) -> bool:
    """True if the line opens with a bullet/dash glyph (a list item) — such
    a line is never a section heading and never an entry title on its own."""
    return bool(_BULLET_LEAD_RE.match(text or ""))


# Past-tense / gerund action verbs a resume bullet (a sub-point describing
# what the candidate did) overwhelmingly starts with. A generic lexical
# class — an entry TITLE is a noun phrase and essentially never opens with
# one of these, so a line that does is body, not a new entry. Not tied to
# any specific resume.
_ACTION_VERBS: frozenset[str] = frozenset({
    "developed", "developing", "built", "building", "created", "creating",
    "designed", "designing", "implemented", "implementing", "engineered",
    "engineering", "architected", "architecting", "owned", "owning", "led",
    "leading", "managed", "managing", "used", "using", "uses", "utilized",
    "debugged", "debugging", "reasoned", "reasoning", "deployed", "deploying",
    "contributed", "contributing", "worked", "working", "integrated",
    "integrating", "analyzed", "analyzing", "optimized", "optimizing",
    "improved", "improving", "reduced", "reducing", "increased", "increasing",
    "wrote", "writing", "tested", "testing", "maintained", "maintaining",
    "shipped", "shipping", "researched", "researching", "focus", "focused",
    "prepare", "prepared", "handled", "handling", "collaborated",
    "collaborating", "spearheaded", "achieved", "delivered", "automated",
    "orchestrated", "streamlined", "refactored", "prototyped", "trained",
})

# Line-leading labels that mark a metadata/sub-content line inside an entry
# (never an entry title): a tech/tools list, a repo/demo link, etc.
_NON_TITLE_LABELS: frozenset[str] = frozenset({
    "tech", "technologies", "technology", "tools", "stack", "built",
    "languages", "frameworks", "libraries", "databases", "database",
    "github", "gitlab", "link", "links", "repo", "repository", "demo",
    "live", "source", "code", "url", "website", "skills",
})


def _first_word(text: str) -> str:
    stripped = strip_leading_bullet(text)
    match = re.match(r"[A-Za-z][A-Za-z'&/-]*", stripped)
    return match.group(0).lower() if match else ""


def starts_with_action_verb(text: str) -> bool:
    """True if the (bullet-stripped) line opens with a resume action verb —
    i.e. it's a sub-point sentence, not an entry title."""
    return _first_word(text) in _ACTION_VERBS


def starts_with_non_title_label(text: str) -> bool:
    """True if the line opens with a metadata label ("Tools:", "GitHub:",
    "Tech stack:") — content within an entry, never the entry title."""
    return _first_word(text) in _NON_TITLE_LABELS


def is_open_list_end(text: str) -> bool:
    """True if a line ends mid-list (trailing comma or pipe) — the next
    visual line is its wrapped continuation, not a new entry (e.g. a
    technology list that overflowed onto a second line)."""
    return bool(re.search(r"[,|]\s*$", text or ""))


def looks_like_title(text: str, *, max_words: int = 12) -> bool:
    """A structural title test: short-ish, doesn't open lowercase, isn't a
    full sentence ending in a period. Used only as ONE positive signal
    among several in entry-boundary detection."""
    stripped = strip_leading_bullet(strip_leading_enumeration(text)).strip()
    if not stripped:
        return False
    if stripped[0].islower():
        return False
    words = stripped.split()
    if len(words) > max_words:
        return False
    if stripped.endswith(".") and len(words) > 6:
        return False
    return True


def contains_year(text: str) -> bool:
    return bool(_YEAR_RE.search(text or ""))


def is_bare_date_line(text: str) -> bool:
    """True if the whole line is essentially just a year or year-range
    (e.g. "2026", "2023 - Present", "2023 – 2027") — the date printed on
    its own line directly under an entry title."""
    t = clean_text(text).lower()
    if not t:
        return False
    return bool(re.fullmatch(r"(?:19|20)\d{2}(?:\s*[-–—to]+\s*(?:present|current|(?:19|20)\d{2}))?", t))


def split_title_and_tech_tail(title: str) -> tuple[str, list[str]]:
    """Splits a project title of the shape "Name | Tech, Tech, Tech" into
    ("Name", ["Tech", ...]). Many single-column resumes append the tech
    stack to the title line after a pipe; without this the whole tail
    becomes part of the title AND the technologies are missed. Returns the
    title unchanged with [] when there is no pipe."""
    if "|" not in title:
        return title.strip(), []
    head, _, tail = title.partition("|")
    techs = []
    for raw in re.split(r"[,/;]| and ", tail):
        # Drop decorative/icon glyphs (Font-Awesome contact/skill icons that
        # extract as stray symbols like "\x8c", "\x87") that ride along on
        # the last token of a tech tail, keeping only tech-name-legal
        # characters.
        tok = re.sub(r"[^A-Za-z0-9 .+#/&()\-]", "", raw).strip()
        if tok:
            techs.append(tok)
    return head.strip(), techs


def normalize_title(title: str) -> tuple[str, list[str]]:
    """Cleans a raw entry title for display and returns any technologies
    parsed out of a "| ..." tail. Order: mojibake clean -> strip leading
    bullet -> strip leading enumeration -> split off tech tail -> drop a
    trailing standalone year/"- Present". Purely structural."""
    cleaned = clean_text(title)
    cleaned = strip_leading_bullet(cleaned)
    cleaned = strip_leading_enumeration(cleaned)
    head, techs = split_title_and_tech_tail(cleaned)
    head = _TRAILING_YEAR_RE.sub("", head).strip(" ,-–—|")
    return head.strip(), techs
