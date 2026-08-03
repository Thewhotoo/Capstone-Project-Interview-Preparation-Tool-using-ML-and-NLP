"""
ContactParser — Stage 4 plugin for contact/header fields (candidate_name,
email, phone, linkedin, location). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Reads `sections["contact"]` (Milestone 2's Section Detection already does
the heavy lifting here: the pre-first-header block defaults to "contact",
and a document-wide email/phone/URL regex sweep tags any matching span
into "contact" regardless of where it structurally sits) plus
`doc.hyperlinks` (for a "LinkedIn" label hyperlinked to a URL with no
visible URL text -- a real gap in today's Gemini pipeline, per the
architecture doc).

Email/phone/URL regex patterns here are deliberately a small, local copy
of sections.py's near-identical patterns, NOT an import from it --
Milestone 2 is frozen, and the established precedent (Milestone 1's
layout.py vs. Milestone 2's sections.py) is that each milestone owns its
own copy of any structurally-needed pattern rather than reaching into a
frozen module.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.location_gazetteer import LOCATIONS

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_LINKEDIN_PATTERN = re.compile(r"linkedin\.com/\S+", re.IGNORECASE)

# Validation-derived, tunable (same discipline established in layout.py and
# sections.py) -- 80 comfortably separates an exact/near-exact location
# name from unrelated short text, per the same token_sort_ratio + str.lower
# combination that fixed Section Detection's case-sensitivity bug.
LOCATION_MATCH_THRESHOLD = 80


def _extract_email(text: str) -> str:
    match = _EMAIL_PATTERN.search(text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = _PHONE_PATTERN.search(text)
    return match.group(0).strip() if match else ""


def _extract_linkedin_from_text(text: str) -> str:
    match = _LINKEDIN_PATTERN.search(text)
    return match.group(0) if match else ""


def _extract_linkedin_from_hyperlinks(hyperlinks) -> str:
    for url, _bbox, _page in hyperlinks:
        if "linkedin.com" in url.lower():
            return url
    return ""


def _extract_location(lines: list[str]) -> tuple[str, float]:
    """Fuzzy-matches each candidate line against the location gazetteer,
    returns (best_match_text_as_found_in_resume, score). A line already
    identified as email/phone is skipped -- location matching only looks
    at the remaining short lines."""
    best_line = ""
    best_score = 0.0
    for line in lines:
        if not line.strip() or _EMAIL_PATTERN.search(line) or _PHONE_PATTERN.search(line):
            continue
        _, score, _ = process.extractOne(line, LOCATIONS, scorer=fuzz.token_sort_ratio, processor=str.lower)
        if score > best_score:
            best_score = score
            best_line = line.strip()
    return best_line, best_score


def _infer_candidate_name(lines_with_font_size: list[tuple[str, float]]) -> str:
    """The most prominent (largest font) line in the contact block that
    isn't itself an email/phone/URL match -- almost always the name banner
    Section Detection's leading-block rule (Milestone 2) folded in here."""
    candidates = [
        (text, size)
        for text, size in lines_with_font_size
        if text.strip()
        and not _EMAIL_PATTERN.search(text)
        and not _PHONE_PATTERN.search(text)
        and not _LINKEDIN_PATTERN.search(text)
    ]
    if not candidates:
        return ""
    return max(candidates, key=lambda pair: pair[1])[0].strip()


class ContactParser:
    entity_name = "contact"
    required_sections: tuple[str, ...] = ("contact",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("contact")
        if section is None or not section.spans:
            return ParserResult(entities=[], confidences=[], observations=[])

        full_text = " ".join(s.text for s in section.spans)
        lines_with_font_size: dict[str, float] = {}
        for span in section.spans:
            lines_with_font_size[span.text] = max(lines_with_font_size.get(span.text, 0.0), span.font_size)
        lines = list(lines_with_font_size.keys())

        email = _extract_email(full_text)
        phone = _extract_phone(full_text)
        linkedin = _extract_linkedin_from_text(full_text) or _extract_linkedin_from_hyperlinks(doc.hyperlinks)
        location, location_score = _extract_location(lines)
        candidate_name = _infer_candidate_name(list(lines_with_font_size.items()))

        reasons = []
        hits = 0
        for label, value in (
            ("candidate_name", candidate_name),
            ("email", email),
            ("phone", phone),
            ("linkedin", linkedin),
        ):
            if value:
                reasons.append(f"+{label}_found")
                hits += 1
            else:
                reasons.append(f"-{label}_not_found")
        if location and location_score >= LOCATION_MATCH_THRESHOLD:
            reasons.append(f"+location_gazetteer_match:{location_score:.0f}")
            hits += 1
        else:
            location = ""
            reasons.append("-location_not_found")

        entity = {
            "candidate_name": candidate_name,
            "email": email,
            "phone": phone,
            "linkedin": linkedin,
            "location": location,
        }
        score = hits / 5

        return ParserResult(entities=[entity], confidences=[Confidence(score=score, reasons=reasons)])
