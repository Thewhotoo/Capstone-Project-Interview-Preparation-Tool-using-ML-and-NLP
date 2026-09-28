"""
ProjectParser — Stage 4 plugin for the Projects section (title, summary,
technologies, concepts). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

The highest fan-out Milestone 3 parser: `topic_pool.py` Priority 2 reads
`summary`/`technologies` directly; the future Cross-Reference Pass
(Milestone 5) and `traceability.py` both key off `title`; Confidence
Scoring (Milestone 6) rolls up Project confidences into the profile-level
score. `title` is therefore a hard correctness requirement, not just a
field: `traceability.find_project_by_title` does an exact, case-insensitive
match against it, so it must be extracted consistently.

`interview_seeds` is deliberately NOT implemented here -- it stays `[]`.
That's Milestone 4 (design) / Milestone 5 (implementation) work, per the
permanent graceful-degradation rule: no seeds rather than weak/generic
ones. The confidence formula below therefore omits the architecture doc's
fourth term (interview-seed template precondition satisfied, +0.2) --
documented, not silently patched; M3's ProjectParser confidence tops out
around 0.8, not 1.0, until Milestone 5 adds that term.
"""

from __future__ import annotations

import logging
import re

from resume_engine.concept_gazetteer import CONCEPTS
from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.parsers._entry_clustering import cluster_entries, strip_section_header_line
from resume_engine.technology_gazetteer import TECHNOLOGIES
from resume_engine.text_normalization import normalize_title
from resume_engine.validation import Observation

logger = logging.getLogger(__name__)

_TECH_LABEL_PATTERN = re.compile(r"^(?:tech(?:nolog(?:y|ies))?|stack|built with)\s*:\s*(.+)$", re.IGNORECASE)
_TECH_SPLIT_PATTERN = re.compile(r"[,;/|]| and ", re.IGNORECASE)

_SEM_MODEL_NAME = "all-MiniLM-L6-v2"

# Canonical-form lookup for the shared gazetteer.
_TECH_BY_LOWER: dict[str, str] = {t.lower(): t for t in TECHNOLOGIES}

# Gazetteer entries that are ALSO ordinary English words. A bare
# `\b<word>\b` match of one of these in prose ("we react to demand", "spring
# into action", "the service should go back", "rust never sleeps") is almost
# always the English word, not the technology -- so in unlabeled prose these
# require contextual evidence (see `_scan_line_techs`). NOT removed from the
# gazetteer (they are real technologies), and NOT guarded in EXPLICIT tech
# context (a "Tech:" line or a pipe tech tail), where they are unambiguous.
_AMBIGUOUS_TECH_LOWER: frozenset[str] = frozenset({
    "go", "r", "rest", "spark", "spring", "express", "swift", "rust", "react", "rails",
})

# A word immediately BEFORE an ambiguous match that signals technology usage
# ("built the API in Go", "using React", "written in Rust").
_TECH_CUE_PREV: frozenset[str] = frozenset({
    "in", "using", "with", "via", "on", "atop", "used", "built", "wrote",
    "written", "powered", "leveraged", "leveraging", "adopted", "adopting",
})
# A technology-typical noun immediately AFTER an ambiguous match ("REST API",
# "Spring framework"). Requires the match to also carry the canonical casing.
_TECH_FOLLOW_NOUN: frozenset[str] = frozenset({
    "api", "apis", "framework", "frameworks", "library", "libraries",
    "server", "backend", "frontend", "sdk", "orm", "middleware", "router",
})

_WORD_RE = re.compile(r"[A-Za-z0-9.+#]+")


def _prev_word(text: str) -> str:
    matches = _WORD_RE.findall(text)
    return matches[-1] if matches else ""


def _next_word(text: str) -> str:
    m = _WORD_RE.search(text)
    return m.group(0) if m else ""


def _scan_line_techs(text: str, *, ambiguous_needs_context: bool) -> list[str]:
    """Finds the gazetteer technologies present in a single line of text.

    Non-ambiguous technologies are accepted on a plain word-boundary match.
    Ambiguous ones (`_AMBIGUOUS_TECH_LOWER`) are accepted directly ONLY when
    `ambiguous_needs_context` is False (explicit tech context -- a labeled
    line / pipe tail). In prose (`ambiguous_needs_context=True`) an ambiguous
    match must be corroborated by:
      (b) an immediately-preceding technology-usage cue ("in Go", "using
          React"), OR
      (c) an immediately-following technology noun with canonical casing
          ("REST API"), OR
      (d) co-occurrence on the same line with another accepted technology,
          with canonical casing ("... Express and React").
    Otherwise the match is treated as the ordinary English word and dropped.
    """
    lower = text.lower()
    raw_matches = []  # (start, end, surface, canonical, is_ambiguous)
    for lower_name, canonical in _TECH_BY_LOWER.items():
        for m in re.finditer(r"\b" + re.escape(lower_name) + r"\b", lower):
            raw_matches.append((
                m.start(), m.end(), text[m.start():m.end()], canonical,
                lower_name in _AMBIGUOUS_TECH_LOWER,
            ))
    raw_matches.sort(key=lambda t: t[0])  # position order (stable output)

    accepted_flag = [False] * len(raw_matches)
    for idx, (start, end, surface, canonical, is_ambiguous) in enumerate(raw_matches):
        if not is_ambiguous or not ambiguous_needs_context:
            accepted_flag[idx] = True  # non-ambiguous, or explicit tech context
            continue
        prev = _prev_word(text[:start]).lower()
        nxt = _next_word(text[end:])
        if prev in _TECH_CUE_PREV:  # (b) "in Go", "using React"
            accepted_flag[idx] = True
        elif nxt.lower() in _TECH_FOLLOW_NOUN and surface == canonical:  # (c) "REST API"
            accepted_flag[idx] = True

    # (d) co-occurrence: an ambiguous match with canonical casing, on a line
    # that already yielded at least one accepted technology, is far more
    # likely the technology than the English word ("... Express and React").
    if any(accepted_flag):
        for idx, (start, end, surface, canonical, is_ambiguous) in enumerate(raw_matches):
            if is_ambiguous and ambiguous_needs_context and not accepted_flag[idx] and surface == canonical:
                accepted_flag[idx] = True

    accepted: list[str] = []
    seen: set[str] = set()
    for idx, (start, end, surface, canonical, is_ambiguous) in enumerate(raw_matches):
        if accepted_flag[idx] and canonical.lower() not in seen:
            seen.add(canonical.lower())
            accepted.append(canonical)  # emitted in position order
    return accepted


def _classify_pipe_tail(tokens: list[str]) -> tuple[list[str], str]:
    """A title's "| ..." tail (already split into raw tokens by
    `normalize_title`) is a TECHNOLOGY LIST only when at least one token is a
    recognised technology -- e.g. "React, Node.js, Redis" or "FastAPI,
    Redis". A lone non-technology phrase ("Distributed workflow
    orchestrator") is a DESCRIPTION, not a technology, and is returned as
    such so the caller can fold it into the summary instead of inventing a
    bogus technology. Returns (technologies, description)."""
    if not tokens:
        return [], ""
    if any(tok.lower() in _TECH_BY_LOWER for tok in tokens):
        return tokens, ""
    return [], " ".join(tokens).strip()


class _LazyKeyBERT:
    """Lazy singleton, private to this module -- same pattern as
    sections.py's `_LazySemanticModel` (Milestone 2), a separate copy
    rather than a shared import, per that module's own documented
    reasoning (each ML-touching module owns its lazy-load, never a crash
    if the model can't be loaded)."""

    _model = None

    @classmethod
    def get(cls):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                from keybert import KeyBERT

                sem_model = SentenceTransformer(_SEM_MODEL_NAME)
                cls._model = KeyBERT(model=sem_model)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("KeyBERT unavailable for ProjectParser concept extraction: %s", e)
                cls._model = False
        return cls._model if cls._model is not False else None


def _extract_technologies(title_line: str, body_lines: list[str]) -> tuple[list[str], bool]:
    """Entry-local technology extraction. Sources, in order:
      (a) EXPLICIT "Tech:"/"Stack:"/"Built with:" labeled lines -- the
          candidate declared these as technologies, so every token is kept
          verbatim (even ones outside the gazetteer, e.g. "JWT", "gRPC"),
          exactly as before;
      (b) the TITLE line and the entry's PROSE body -- gazetteer matches with
          the ambiguous-English-word guard applied (see `_scan_line_techs`),
          so "Chronos - Python workflow orchestrator" yields Python while
          "we react to demand" does not yield React.

    Title-aware (Phase 1): the title line is scanned too, so a technology
    named only in the title is not lost. Entry-local: only this entry's own
    title + body are seen, never a neighbouring entry's -- the invariant that
    keeps one project's technologies off another. Returns (technologies,
    had_labeled_line); deduped case-insensitively, first-seen form kept."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            found.append(name)

    had_labeled_line = False
    prose_lines: list[str] = [title_line] if title_line else []
    for line in body_lines:
        match = _TECH_LABEL_PATTERN.match(line.strip())
        if match:
            had_labeled_line = True
            for token in _TECH_SPLIT_PATTERN.split(match.group(1)):
                token = token.strip()
                if token:
                    _add(token)
        else:
            prose_lines.append(line)

    for line in prose_lines:
        for canon in _scan_line_techs(line, ambiguous_needs_context=True):
            _add(canon)

    return found, had_labeled_line


def _extract_concepts(text: str) -> list[str]:
    """KeyBERT proposes candidate keyphrases; only phrases matching
    `concept_gazetteer.py` are kept -- bounded, deterministic given fixed
    model weights (no open-ended generation). Returns [] if KeyBERT is
    unavailable, never raises."""
    model = _LazyKeyBERT.get()
    if model is None or not text.strip():
        return []
    try:
        pairs = model.extract_keywords(text, keyphrase_ngram_range=(1, 3), stop_words="english", top_n=10)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("KeyBERT extraction failed: %s", e)
        return []

    matched = []
    phrases_lower = [p[0].lower() for p in pairs]
    for concept in CONCEPTS:
        concept_lower = concept.lower()
        if any(concept_lower in phrase or phrase in concept_lower for phrase in phrases_lower):
            matched.append(concept)
    return matched


class ProjectParser:
    entity_name = "projects"
    required_sections: tuple[str, ...] = ("projects",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        section = sections.get("projects")
        if section is None or not section.spans:
            return ParserResult(entities=[], confidences=[], observations=[])

        entry_spans = strip_section_header_line(section.spans, section.raw_header_text)
        entries = cluster_entries(entry_spans, doc.body_font_size)
        if not entries:
            return ParserResult(
                entities=[],
                confidences=[],
                observations=[
                    Observation(
                        severity="notice",
                        category="empty_section",
                        message="Projects section detected but no parseable entries found inside it.",
                        entity_ref="projects",
                    )
                ],
            )

        result_entities = []
        result_confidences = []
        observations = []

        for index, entry in enumerate(entries):
            # Phase 1: clean the raw title (strip a leading bullet/number, a
            # mojibake separator, and a trailing standalone year) and pull
            # any technologies off a "Name | Tech, Tech" tail -- otherwise
            # the whole tail contaminated the title AND those technologies
            # were missed. Purely structural (text_normalization.py), no
            # resume-specific rule.
            title, tail_tokens = normalize_title(entry.header_text)
            # A "| ..." title tail is a technology list only when it actually
            # names a technology; a lone descriptive phrase ("| Distributed
            # workflow orchestrator") is a DESCRIPTION, folded into the
            # summary rather than fabricated into a technology (Phase 1D).
            tail_techs, tail_description = _classify_pipe_tail(tail_tokens)
            body_text = " ".join(entry.body_lines)

            # Title-aware + collision-guarded extraction over the entry's own
            # title and prose; explicit "Tech:" lines kept verbatim.
            technologies, had_labeled_line = _extract_technologies(title, entry.body_lines)
            # Merge the (validated) title-tail technologies first (title order
            # preserved), deduped case-insensitively against the rest.
            if tail_techs:
                existing = {t.lower() for t in technologies}
                technologies = [t for t in tail_techs if t.lower() not in existing] + technologies
            concepts = _extract_concepts(body_text)
            summary_lines = [
                line for line in entry.body_lines if not _TECH_LABEL_PATTERN.match(line.strip())
            ]
            if tail_description:
                summary_lines = [tail_description, *summary_lines]
            summary = " ".join(summary_lines).strip()

            reasons = []
            score = 0.0
            if entry.header_is_corroborated:
                reasons.append("+title_formatting_corroborated")
                score += 0.4
            else:
                reasons.append("-title_not_formatting_corroborated")
            if technologies:
                reasons.append(f"+technologies_extracted:{len(technologies)}")
                score += 0.25
                if had_labeled_line:
                    reasons.append("+explicit_tech_label_found")
            else:
                reasons.append("-no_technologies_extracted")
            reasons.append(f"+section_confidence:{section.header_confidence:.2f}")
            score += 0.15 * section.header_confidence
            reasons.append("-interview_seeds_not_implemented_until_milestone_5")

            if not title:
                observations.append(
                    Observation(
                        severity="notice",
                        category="missing_title",
                        message=f"Project entry at index {index} has no extractable title.",
                        entity_ref=f"projects[{index}]",
                    )
                )
            if not technologies:
                observations.append(
                    Observation(
                        severity="info",
                        category="missing_technologies",
                        message=f"Project '{title}' has no technologies listed.",
                        entity_ref=f"projects[{index}]",
                    )
                )

            result_entities.append(
                {
                    "title": title,
                    "summary": summary,
                    "technologies": technologies,
                    "concepts": concepts,
                    "interview_seeds": [],
                }
            )
            result_confidences.append(Confidence(score=round(score, 4), reasons=reasons))

        return ParserResult(entities=result_entities, confidences=result_confidences, observations=observations)
