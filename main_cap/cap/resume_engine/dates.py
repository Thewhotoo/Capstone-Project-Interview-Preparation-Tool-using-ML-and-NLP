"""
Date-range parsing — Milestone 3 (Entity Parsing) shared utility. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

A thin `python-dateutil` wrapper shared by `ExperienceParser` (built now)
and `EducationParser` (Milestone 5) -- both need "find a date-range-shaped
substring in a line, parse it into structured start/end, and also keep the
original display string" (Section 1.3: today's `duration` string field
must survive unchanged for schema compatibility; the structured start/end
is new, internal-only, replacing `_calculate_total_years`'s best-effort
regex reparse of already-generated text with real parsed dates computed
once, at extraction time).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from dateutil import parser as dateutil_parser

# Explicit month-name alternation -- NOT a generic "any 3-9 letter word"
# class. Found during Milestone 3 validation: a generic word-length class
# false-matched "Engineer 2021" (the last word of a role title, directly
# followed by the actual start year on the same line) as if "Engineer"
# were a month name, corrupting both the extracted date AND the
# role/company split downstream. Real month names only.
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_MONTH_YEAR = rf"{_MONTH}\.?\s+\d{{4}}"

# One date-range-shaped substring: "<start> <separator> <end>", where <end>
# may be an actual date or "Present"/"Current". Separator is permissive
# (hyphen, en dash, em dash, or the word "to") since resumes vary.
_DATE_RANGE_PATTERN = re.compile(
    rf"(?P<start>{_MONTH_YEAR}|\d{{1,2}}/\d{{4}}|\d{{4}})"
    r"\s*(?:-|–|—|to)\s*"
    rf"(?P<end>Present|Current|{_MONTH_YEAR}|\d{{1,2}}/\d{{4}}|\d{{4}})",
    re.IGNORECASE,
)

_DATEUTIL_DEFAULT = datetime(1900, 1, 1)


@dataclass
class ParsedDateRange:
    display: str            # the original matched text, e.g. "Jan 2021 - Present"
    start: date | None       # None if the start half couldn't be parsed
    end: date | None         # None if ongoing (is_current) or unparseable
    is_current: bool         # True if the end half was "Present"/"Current"


def parse_date_range(text: str) -> ParsedDateRange | None:
    """Finds and parses the first date-range-shaped substring in `text`.
    Returns None if no such substring exists at all -- never raises on bad
    input. A found-but-partially-unparseable range still returns a
    ParsedDateRange with start/end as None where dateutil couldn't resolve
    them; the caller (ExperienceParser) decides how to react (lower
    confidence + an Observation, per the architecture doc's "Inconsistent
    dates" validation example) rather than this function failing loudly."""
    match = _DATE_RANGE_PATTERN.search(text)
    if not match:
        return None

    start_text = match.group("start")
    end_text = match.group("end")
    is_current = end_text.strip().lower() in ("present", "current")

    return ParsedDateRange(
        display=match.group(0),
        start=_try_parse(start_text),
        end=None if is_current else _try_parse(end_text),
        is_current=is_current,
    )


def _try_parse(text: str) -> date | None:
    try:
        return dateutil_parser.parse(text, default=_DATEUTIL_DEFAULT).date()
    except (ValueError, OverflowError):
        return None
