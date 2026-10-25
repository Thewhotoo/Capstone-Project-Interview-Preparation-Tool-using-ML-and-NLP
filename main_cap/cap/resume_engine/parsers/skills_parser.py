"""
SkillsParser — Stage 4 plugin for the Skills section. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Splits the explicit Skills section on common delimiters, normalizes each
token against the shared `technology_gazetteer.py` (same single source of
truth `ProjectParser` already uses, per the architecture doc's explicit
"must agree on one canonical gazetteer, not drift" requirement). A token
that doesn't match the gazetteer is still kept verbatim (resumes list
plenty of legitimate skills -- "Leadership", "Agile" -- outside a
technology-only vocabulary), just without the gazetteer-match confidence
boost. Cross-section "demonstrated in a project" tagging is NOT this
parser's job -- that's the Cross-Reference Pass (cross_reference.py).
"""

from __future__ import annotations

import re

from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import _group_into_lines, strip_section_header_line
from resume_engine.technology_gazetteer import TECHNOLOGIES
from resume_engine.validation import Observation

_SPLIT_PATTERN = re.compile(r"[,;|•·]")
_TECHNOLOGIES_LOWER = {t.lower(): t for t in TECHNOLOGIES}

# Category sub-labels that appear INSIDE a Skills section but whose values
# are not technical skills -- prose that was being comma-split into junk
# "skills" (e.g. an "Areas of Interest:" sentence). When such a label opens
# a line, that line AND its wrapped continuation lines are skipped, until
# the next real category label. Generic category names, never resume text.
_NON_SKILL_CATEGORIES: frozenset[str] = frozenset({
    "areas of interest", "area of interest", "interests", "interest",
    "hobbies", "hobbies and interests", "coursework", "relevant coursework",
    "courses", "objective", "summary", "achievements", "accomplishments",
    "awards", "activities", "extracurricular", "extra-curricular",
    "references", "languages spoken", "spoken languages",
    "soft skills", "soft skill", "interpersonal skills",
})

# A "Label: values" line's label is at most this many words -- longer means
# it's almost certainly not a category label but ordinary content.
_MAX_LABEL_WORDS = 4
# A single skill is short; a token longer than this is prose that slipped
# past the category filter (a backstop, not the primary guard).
_MAX_SKILL_WORDS = 6


def _spans_to_text(spans) -> str:
    """Reconstructs the section's text one VISUAL LINE at a time (grouping
    word-level `TextSpan`s by y0-proximity via `_entry_clustering._group_into_lines`
    -- the same line-grouping every other parser in this package already
    uses), joining lines with '\\n' so a genuine one-skill-per-line template
    still splits correctly, but words on the SAME line never do.

    Found during resume-intelligence-quality validation: `Section.spans`
    (sections.py) is word-granular (one `TextSpan` per PDF text run, not
    per physical line) -- joining every span directly with '\\n' put a line
    break between every word, including inside a single multi-word skill
    ("Hugging Face" -> "Hugging", "Face"; "VS Code" -> "VS", "Code"), since
    '\\n' is one of `_SPLIT_PATTERN`'s delimiters."""
    lines = _group_into_lines(list(spans))
    return "\n".join(line.text for line in lines if line.text)


# Words that make up skill-CATEGORY labels ("Core CS", "Cloud/DevOps", "Frameworks & Libraries").
# Used only to find where a second "Label:" starts on a line holding two label groups
# side by side ("Languages: Python, Java, C, SQL Core CS: DSA, OOP") -- the label is the
# longest run of these words right before the colon; the words before it are the
# previous group's last value ("SQL").
_LABEL_WORDS = frozenset(
    "core cs computer science backend frontend front end back full stack fullstack web mobile "
    "messaging tools tool databases database db cloud devops ai ml ai/ml cloud/devops data "
    "languages language programming frameworks framework libraries library developer platforms "
    "platform technologies technology technical skills concepts testing other misc design "
    "infrastructure observability security & and / - genai llm nlp apis api ui ux version control "
    "operating systems os scripting analytics visualization bi software engineering".split())
_LABEL_COLON = re.compile(r":")
_PAREN_GROUP = re.compile(r"([^,;|()]+?)\s*\(([^()]*)\)")
_DASH_QUALIFIER = re.compile(r"\s+[–—-]\s+\w+$")      # "MySQL/PostgreSQL – coursework" -> drop "– coursework"


def _logical_lines(text: str) -> list[str]:
    """Rejoins a visual line that wrapped mid-list: a line that doesn't end with a
    separator continues on the next one unless that next line starts a new labelled
    group ("React\\nQuery" -> "React Query"; "Data\\nStructures & Algorithms")."""
    out: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        starts_group = bool(re.match(r"^[•·▪●\-*]", line)) or (
            ":" in line and len(line.split(":", 1)[0].split()) <= _MAX_LABEL_WORDS)
        # only a comma-LIST line can wrap; a line with no separator at all is a
        # one-skill-per-line list ("Software Development" / "System Design")
        if (out and not starts_group and re.search(r"[,;|]", out[-1])
                and not re.search(r"[,;|:]\s*$", out[-1])):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _label_segments(line: str) -> list[tuple[str | None, str]]:
    """Splits one logical line into (label, values) groups, handling several
    "Label:" groups on the same line. A line without a short label is (None, line)."""
    parts = line.split(":")
    if len(parts) == 1:
        return [(None, line)]
    segments: list[tuple[str | None, str]] = []
    label = parts[0]
    for i in range(1, len(parts)):
        chunk = parts[i]
        if i < len(parts) - 1:
            # the next label sits at the end of this chunk, after its last value
            head, _, tail = chunk.rpartition(",")
            words = tail.split()
            n = 0
            while n < len(words) and words[len(words) - 1 - n].strip("•").lower() in _LABEL_WORDS:
                n += 1
            if n == 0:            # not a label -- e.g. a URL or "Note: ..." inside the values
                parts[i + 1] = chunk + ":" + parts[i + 1]
                continue
            value_part = ",".join([head] + ([" ".join(words[: len(words) - n])] if len(words) > n else []))
            segments.append((label, value_part))
            label = " ".join(words[len(words) - n:])
        else:
            segments.append((label, chunk))
    return segments


def _expand_parentheticals(segment: str) -> str:
    """"Python (FastAPI, Celery)" -> "Python, FastAPI, Celery"."""
    def expand(match: re.Match) -> str:
        inner = ", ".join(_DASH_QUALIFIER.sub("", p.strip()) for p in re.split(r"[,/]", match.group(2)) if p.strip())
        return f"{match.group(1).strip()}, {inner}"
    return _PAREN_GROUP.sub(expand, segment)


def _split_tokens(text: str) -> list[str]:
    """Turns a Skills section's text (visual lines joined by '\\n') into a
    deduped skill list. Processed one line at a time with a small state
    machine (Phase 1) so a non-skill category inside the section, and its
    wrapped continuation lines, are excluded rather than comma-split into
    junk skills:

      - A "Label: values" line whose label (<= _MAX_LABEL_WORDS words) is a
        NON-skill category ("Areas of Interest", "Soft Skills",
        "Coursework", ...) is skipped, and `accept_continuation` is turned
        OFF so the following unlabeled wrapped lines are skipped too.
      - A "Label: values" line with any OTHER short label ("Languages:",
        "Frameworks & Libraries:", ...) is a real skill category: its values
        are kept and `accept_continuation` is turned ON.
      - An unlabeled line is kept only while `accept_continuation` is ON
        (the wrapped continuation of a real skill category, or a plain
        comma-list before any label).

    Values are split on comma/semicolon/pipe/bullet, deduped
    case-insensitively (first-seen casing preserved -- the same convention
    `ProjectParser._extract_technologies` uses), and a token longer than
    `_MAX_SKILL_WORDS` words is dropped as prose (a backstop)."""
    tokens: list[str] = []
    seen: set[str] = set()
    accept_continuation = True  # a plain comma-list before any label is kept

    groups: list[str] = []
    for stripped in _logical_lines(text):
        for raw_label, values in _label_segments(stripped):
            if raw_label is not None:
                # Normalize internal whitespace before matching -- PDF word
                # spans reconstruct with multiple spaces ("Soft   Skills"), which
                # would otherwise never equal a single-spaced category name.
                label = " ".join(raw_label.replace("•", " ").split())
                if label and len(label.split()) <= _MAX_LABEL_WORDS:
                    if label.lower() in _NON_SKILL_CATEGORIES:
                        accept_continuation = False
                        continue
                    accept_continuation = True
                    groups.append(values)
                    continue
                values = f"{raw_label}:{values}"          # a long "label" is prose: keep the text
            if accept_continuation:
                groups.append(values)

    for segment in groups:
        segment = _expand_parentheticals(segment)
        for raw in _SPLIT_PATTERN.split(segment):
            token = raw.strip(" \t.")
            if ":" in token:
                token = token.rsplit(":", 1)[-1].strip(" \t.")
            if not token or len(token.split()) > _MAX_SKILL_WORDS:
                continue
            if "//" in token or token.lower().startswith(("http", "www.")):   # a link, not a skill
                continue
            key = token.lower()
            if key not in seen:
                seen.add(key)
                tokens.append(token)
    return tokens


def _canonicalize(token: str) -> tuple[str, bool]:
    """Returns (canonical_form, gazetteer_matched). An exact (case-
    insensitive) gazetteer hit is normalized to the gazetteer's own
    casing (e.g. "javascript" -> "JavaScript"); anything else is kept
    verbatim as the resume printed it."""
    canonical = _TECHNOLOGIES_LOWER.get(token.lower())
    if canonical is not None:
        return canonical, True
    return token, False


class SkillsParser:
    entity_name = "skills"
    required_sections: tuple[str, ...] = ("skills",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("skills")
        if section is None or not section.spans:
            return ParserResult(entities=[], confidences=[], observations=[])

        spans = strip_section_header_line(section.spans, section.raw_header_text)
        full_text = _spans_to_text(spans)
        tokens = _split_tokens(full_text)

        if not tokens:
            return ParserResult(
                entities=[],
                confidences=[],
                observations=[
                    Observation(
                        severity="notice",
                        category="empty_section",
                        message="Skills section detected but no parseable skills found inside it.",
                        entity_ref="skills",
                    )
                ],
            )

        # One Confidence per skill (interfaces.check_parser_conformance
        # requires len(entities) == len(confidences), 1:1, same contract
        # every other parser follows) -- a skill's own gazetteer-match
        # status is exactly the per-skill signal Section 7 of the
        # architecture doc describes ("high if found via gazetteer match
        # in an explicit Skills section; reduced otherwise").
        deduped: list[str] = []
        confidences: list[Confidence] = []
        seen: set[str] = set()
        for token in tokens:
            canonical, matched = _canonicalize(token)
            key = canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(canonical)

            reasons = [f"+listed_in_explicit_skills_section:{canonical}"]
            score = 0.7 + 0.2 * section.header_confidence
            if matched:
                reasons.append("+technology_gazetteer_match")
                score = min(1.0, score + 0.2)
            else:
                reasons.append("-not_a_gazetteer_technology")
            confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        return ParserResult(entities=deduped, confidences=confidences, observations=[])
