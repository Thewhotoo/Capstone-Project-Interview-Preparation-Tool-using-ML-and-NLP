"""
Normalization — Stage 6. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.6.

Runs after Cross-Reference (interview_seeds and demonstrated-skill tags
already attached) and before Validation. Three responsibilities, exactly
as scoped in Section 4.6:

1. Unicode (`NFKC`) + whitespace cleanup on every string field -- resumes
   routinely carry smart quotes, non-breaking spaces, and stray control
   characters surviving from PDF extraction.
2. Date-range display-string canonicalization (separator normalization
   only -- the month/year tokens themselves are never reformatted, per
   Section 1.3's "same shape today's Gemini output has" contract).
3. Technology de-aliasing + case-insensitive deduplication, with the
   dedup event itself logged as an `info` Observation (never silently
   invisible) -- directly implements the "duplicate technologies"
   validation example from Section 8.

Never introduces a `None` anywhere (Section 1.3's sentinel convention);
never changes a field's TYPE, only its content.
"""

from __future__ import annotations

import re
import unicodedata

from resume_engine.interfaces import ParserResult
from resume_engine.pipeline_trace import PipelineTrace
from resume_engine.technology_gazetteer import TECHNOLOGIES
from resume_engine.validation import Observation

_WHITESPACE_PATTERN = re.compile(r"[ \t ]+")
_DASH_PATTERN = re.compile(r"\s*[-–—]\s*")

# Multi-resume-validation fix (bullet/glyph leakage): a small, approved,
# non-exhaustive set of Unicode list-marker glyphs, stripped ONLY when
# LEADING a field value (after surrounding whitespace is ignored) -- never
# mid-string. These are the PDF's own genuine bullet/sub-bullet glyphs
# (extraction is correct), extracted as their own span and concatenated
# directly onto the next span's text by an earlier pipeline stage with no
# concept of "this is list punctuation, not content" -- e.g. a project
# titled "Patient OS v2" rendered as a bullet-list item comes through as
# "• Patient OS v2". Deliberately NOT a broad Unicode blacklist:
# dashes (-/en dash/em dash), accented characters, and any glyph appearing
# mid-string are never touched by this pattern.
_LEADING_LIST_MARKER_PATTERN = re.compile("^[•◦▪‣·]+\\s*")

# Small, deliberately non-exhaustive alias map -- same maintenance
# philosophy as every other gazetteer in this engine (a one-line,
# reviewable diff to extend, not a design change). Canonicalizes to the
# shared `technology_gazetteer.py`'s own casing.
_TECHNOLOGY_ALIASES: dict[str, str] = {
    "js": "JavaScript", "ts": "TypeScript", "py": "Python",
    "postgres": "PostgreSQL", "psql": "PostgreSQL",
    "k8s": "Kubernetes", "mongo": "MongoDB",
    "reactjs": "React", "react.js": "React",
    "nodejs": "Node.js", "node": "Node.js",
    "golang": "Go", "vuejs": "Vue", "vue.js": "Vue",
}
_TECHNOLOGIES_LOWER = {t.lower(): t for t in TECHNOLOGIES}

_STRING_FIELDS_BY_ENTITY_TYPE: dict[str, tuple[str, ...]] = {
    "contact": ("candidate_name", "email", "phone", "linkedin", "location"),
    "experience": ("company", "role", "summary"),
    "projects": ("title", "summary"),
    "education": ("degree", "major", "institution", "graduation_year"),
}


def _strip_control_and_replacement_chars(value: str) -> str:
    """Removes Unicode category `Cc` control characters (C0 + C1, e.g. the
    `\\x80` icon-font-glyph artifact found in real resume PDFs) and the
    replacement character U+FFFD (Unicode's own "could not decode this
    glyph" sentinel -- never legitimate content) anywhere in the string.
    Category-based, not an enumerated blacklist: catches every Cc control
    character, not just the ones observed so far. Never touches ordinary
    punctuation, dashes, or accented/non-English letters, none of which
    are Cc or U+FFFD."""
    return "".join(ch for ch in value if ch != "�" and unicodedata.category(ch) != "Cc")


def clean_text(value: str) -> str:
    """Control/replacement-char removal + Unicode NFKC + whitespace
    collapse + leading list-marker strip + trim. Public (not
    underscore-prefixed) since the Validation Layer (Stage 7) and its
    tests reasonably want the same normalization primitive rather than a
    second copy -- both stages are Milestone 6's own new code, not a
    frozen-module boundary the way parsers/project_parser.py is.

    Multi-resume-validation fix (bullet/glyph leakage): PDF extraction
    faithfully -- and unavoidably -- surfaces broken icon/bullet-font
    glyphs verbatim (see `_strip_control_and_replacement_chars` and
    `_LEADING_LIST_MARKER_PATTERN`). This is the single, central place
    every entity field (experience, projects, education, contact, skills,
    certifications) already passes through, so cleaning here benefits
    every downstream consumer (question generation, evaluation, improved
    answers, coaching, the report) with no other call site changed."""
    if not value:
        return value
    stripped = _strip_control_and_replacement_chars(value)
    normalized = unicodedata.normalize("NFKC", stripped)
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized).strip()
    normalized = _LEADING_LIST_MARKER_PATTERN.sub("", normalized)
    return normalized.strip()


def _clean_duration(value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return cleaned
    return _DASH_PATTERN.sub(" - ", cleaned)


def canonicalize_technology(tech: str) -> str:
    alias = _TECHNOLOGY_ALIASES.get(tech.lower())
    if alias is not None:
        return alias
    gazetteer_form = _TECHNOLOGIES_LOWER.get(tech.lower())
    if gazetteer_form is not None:
        return gazetteer_form
    return tech


def _dedupe_technologies(technologies: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Returns (deduped_canonical_list, merges) -- merges is a list of
    (kept, dropped) original-text pairs, one entry per collapsed
    duplicate, used to log an `info` Observation per merge rather than
    silently dropping the signal that the source resume had a
    duplicate."""
    result: list[str] = []
    kept_by_key: dict[str, str] = {}
    merges: list[tuple[str, str]] = []
    for tech in technologies:
        canonical = canonicalize_technology(tech)
        key = canonical.lower()
        if key in kept_by_key:
            if tech != kept_by_key[key]:
                merges.append((kept_by_key[key], tech))
            continue
        kept_by_key[key] = tech
        result.append(canonical)
    return result, merges


def _normalize_dict_entity(entity: dict, entity_name: str) -> Observation | None:
    for field_name in _STRING_FIELDS_BY_ENTITY_TYPE.get(entity_name, ()):
        if isinstance(entity.get(field_name), str):
            entity[field_name] = clean_text(entity[field_name])

    if entity_name == "experience" and isinstance(entity.get("duration"), str):
        entity["duration"] = _clean_duration(entity["duration"])

    observation = None
    if entity_name == "projects":
        if isinstance(entity.get("technologies"), list):
            deduped, merges = _dedupe_technologies(entity["technologies"])
            entity["technologies"] = deduped
            if merges:
                kept, dropped = merges[0]
                observation = Observation(
                    severity="info",
                    category="duplicate_technologies_merged",
                    message=f"Merged duplicate technology entries: {dropped!r} -> {kept!r}.",
                    entity_ref=f"projects[title={entity.get('title', '')!r}]",
                )
        if isinstance(entity.get("concepts"), list):
            entity["concepts"] = [clean_text(c) if isinstance(c, str) else c for c in entity["concepts"]]
        if isinstance(entity.get("interview_seeds"), list):
            entity["interview_seeds"] = [
                clean_text(s) if isinstance(s, str) else s for s in entity["interview_seeds"]
            ]

    return observation


def _normalize_flat_string_result(result: ParserResult, entity_name: str, apply_technology_aliasing: bool) -> None:
    """Skills/certifications entities are flat `list[str]` (the public
    schema shape, `Section 1.3`), each with a matching 1:1 `Confidence` --
    normalized and deduped IN LOCKSTEP with their confidences so that
    invariant survives this stage, keeping the higher-scoring
    confidence when a normalization-induced collision merges two
    entries (e.g. "JS" and "JavaScript" both alias to "JavaScript")."""
    canonical_by_key: dict[str, tuple[str, "object"]] = {}
    order: list[str] = []
    merges: list[tuple[str, str]] = []

    for raw_entity, confidence in zip(result.entities, result.confidences):
        cleaned = clean_text(raw_entity) if isinstance(raw_entity, str) else raw_entity
        canonical = canonicalize_technology(cleaned) if apply_technology_aliasing else cleaned
        key = canonical.lower()
        if key in canonical_by_key:
            existing_canonical, existing_confidence = canonical_by_key[key]
            merges.append((existing_canonical, raw_entity))
            if confidence.score > existing_confidence.score:
                canonical_by_key[key] = (canonical, confidence)
            continue
        canonical_by_key[key] = (canonical, confidence)
        order.append(key)

    result.entities = [canonical_by_key[key][0] for key in order]
    result.confidences = [canonical_by_key[key][1] for key in order]
    if merges:
        kept, dropped = merges[0]
        result.observations.append(
            Observation(
                severity="info",
                category="duplicate_entries_merged",
                message=f"Merged duplicate entries: {dropped!r} -> {kept!r}.",
                entity_ref=entity_name,
            )
        )


class DefaultNormalizer:
    """Concrete `interfaces.Normalizer` implementation."""

    def normalize(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> dict[str, ParserResult]:
        for entity_name, result in parser_results.items():
            if not result.entities:
                continue
            if entity_name in ("skills", "certifications"):
                _normalize_flat_string_result(
                    result, entity_name, apply_technology_aliasing=(entity_name == "skills")
                )
                continue
            for entity in result.entities:
                if not isinstance(entity, dict):
                    continue
                observation = _normalize_dict_entity(entity, entity_name)
                if observation is not None:
                    result.observations.append(observation)

        return parser_results
