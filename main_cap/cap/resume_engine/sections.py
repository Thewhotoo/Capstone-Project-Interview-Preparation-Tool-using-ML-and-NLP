"""
Section Detection — Stage 3. See docs/architecture/ResumeIntelligenceEngine.md
Section 4.3 for the full 4-tier cascade design.

`HeuristicSectionDetector` operates on the already-linearized
`DocumentModel.spans` Milestone 1 produces (correct reading order,
`column_index`/`page_num` resolved). It groups spans into visual lines
(page/column-aware -- never merging across a page or column boundary,
unlike layout.py's per-band grouping which doesn't need that check since
it's already scoped to one band at a time), classifies each line as a
header or not, and walks the resulting sequence to build `Section`s.
Continuation across pages falls out of this directly: a section simply
keeps collecting lines -- from any page -- until the next header-like line
appears, with no special-casing for page boundaries.

This module deliberately does NOT import anything from layout.py, even
though `_group_into_lines` there is conceptually similar -- Milestone 1 is
frozen and not to be touched or refactored to share code with Milestone 2.
The minor duplication is the accepted cost of respecting that freeze.

All thresholds below (word count, font-size ratio, fuzzy-match score
cutoffs) are proposed starting values, explicitly provisional and subject
to revision once validated against a diverse golden corpus -- the same
documentation discipline established for layout.py's MIN_BAND_BALANCE_RATIO
and MAX_PITCH_RATIO, applied here from the start rather than retrofitted.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from resume_engine.document_model import DocumentModel, TextSpan
from resume_engine.section_gazetteer import SECTION_ALIASES

logger = logging.getLogger(__name__)

# Same model and lazy-singleton-with-graceful-fallback pattern already
# established in heuristic_evaluator.py's _LazyModels -- reused here rather
# than inventing a second convention, and NOT shared as an import (that
# module's own docstring explains why its copy isn't shared with
# discussion_engine.py's; the same reasoning applies to not reaching across
# into resume_engine from the legacy evaluator code).
_SEM_MODEL_NAME = "all-MiniLM-L6-v2"

# Tunable, documented constants -- validation-derived starting points, not
# intrinsic properties of resume typography (see module docstring).
LINE_Y_TOLERANCE = 3.0          # points; spans within this y0 delta are one line
MAX_HEADER_WORDS = 6            # a header line is short; longer lines are never candidates
MIN_HEADER_FONT_RATIO = 1.05    # font_size >= body_font_size * this counts as "larger"
FUZZY_CONFIDENT_THRESHOLD = 85  # rapidfuzz score (0-100) for a confident gazetteer match (Tier 2)
FUZZY_WEAK_THRESHOLD = 55       # below this, gazetteer match is too weak to trust at all (-> Tier 4)
EMBEDDING_SIMILARITY_FLOOR = 0.55  # cosine similarity floor for Tier 4 to accept a label.
                                    # Empirically (see architecture doc Section 4.3's
                                    # implementation note), 0.5 let "Hobbies And Interests"
                                    # (0.509, unrelated) through as a false "projects" match
                                    # while "Where I have Worked" (0.598, a genuine paraphrase
                                    # of "experience") stayed comfortably clear -- 0.55 sits
                                    # with margin between the two observed data points.

# Flat, gazetteer-independent alias -> canonical-label lookup, built once at
# import time. rapidfuzz matches the candidate line's text against every
# known alias string across all labels; the winning alias's label wins.
_ALIAS_TO_LABEL: dict[str, str] = {
    alias: label for label, aliases in SECTION_ALIASES.items() for alias in aliases
}
_ALL_ALIASES: list[str] = list(_ALIAS_TO_LABEL.keys())


@dataclass
class Section:
    """One labeled region of the document, e.g. "experience" or "projects"."""

    label: str  # canonical: "contact", "summary", "experience", "projects",
                # "education", "skills", "certifications", or "unknown"
    raw_header_text: str
    spans: list[TextSpan] = field(default_factory=list)
    header_confidence: float = 0.0
    header_match_reason: str = ""  # e.g. "alias_gazetteer_fuzzy:87", "embedding_fallback:0.81"


class _Line:
    """One visual line: spans grouped by y0 proximity, never crossing a
    page or column boundary (unlike layout.py's per-band line grouping,
    which is already scoped to one page/band and doesn't need that check)."""

    __slots__ = ("spans", "y0", "y1", "x0", "page_num", "column_index")

    def __init__(self, spans: list[TextSpan]):
        self.spans = spans
        self.y0 = min(s.bbox[1] for s in spans)
        self.y1 = max(s.bbox[3] for s in spans)
        self.x0 = min(s.bbox[0] for s in spans)
        self.page_num = spans[0].page_num
        self.column_index = spans[0].column_index

    @property
    def text(self) -> str:
        return " ".join(s.text for s in sorted(self.spans, key=lambda s: s.bbox[0])).strip()

    @property
    def max_font_size(self) -> float:
        return max(s.font_size for s in self.spans)

    @property
    def is_bold(self) -> bool:
        return any(s.is_bold for s in self.spans)

    @property
    def style_name(self) -> str | None:
        for s in self.spans:
            if s.style_name:
                return s.style_name
        return None


def _group_into_document_lines(spans: list[TextSpan]) -> list[_Line]:
    """Groups the full, already-linearized document's spans into visual
    lines, in order, never merging across a (page_num, column_index)
    change -- only y0-proximity within a run that shares both."""
    groups: list[list[TextSpan]] = []
    for span in spans:
        if groups:
            last = groups[-1][-1]
            same_block = span.page_num == last.page_num and span.column_index == last.column_index
            if same_block and abs(span.bbox[1] - last.bbox[1]) <= LINE_Y_TOLERANCE:
                groups[-1].append(span)
                continue
        groups.append([span])
    return [_Line(group) for group in groups]


def _is_candidate_header_line(line: _Line, body_font_size: float) -> bool:
    """The structural pre-filter (Section 4.3 Tiers 2/3): a header line is
    short, standalone (already guaranteed -- it's its own _Line), and
    visually distinguished from body text. Visual distinction is checked
    three ways, not just font size: some real resumes (plain/ATS-style
    templates) use same-size, non-bold, ALL-CAPS text for headers instead
    of bigger/bolder text -- excluding that pattern would miss a very
    common real-world case, not a rare edge case."""
    text = line.text
    if not text or len(text.split()) > MAX_HEADER_WORDS:
        return False
    larger = body_font_size > 0 and line.max_font_size >= body_font_size * MIN_HEADER_FONT_RATIO
    all_caps = text.isupper() and any(c.isalpha() for c in text)
    return larger or line.is_bold or all_caps


def _is_docx_heading_style(line: _Line) -> bool:
    return line.style_name is not None and line.style_name.lower().startswith("heading")


def _is_header_line(line: _Line, body_font_size: float) -> bool:
    """Tier 1 (DOCX style) is a near-certain header signal on its own,
    bypassing the structural pre-filter entirely; Tiers 2/3's structural
    check (`_is_candidate_header_line`) is what everything else -- PDF
    always, DOCX without an applied Heading style -- relies on."""
    return _is_docx_heading_style(line) or _is_candidate_header_line(line, body_font_size)


def _fuzzy_match_label(text: str) -> tuple[str, float]:
    """Best gazetteer match for `text`, as (canonical_label, score 0-100).

    Uses `token_sort_ratio`, not rapidfuzz's default `WRatio` -- empirically
    (see docs/architecture/ResumeIntelligenceEngine.md Section 4.3's
    implementation note), `WRatio`'s partial/substring weighting badly
    over-matches short header-like phrases that merely share one common
    word with an alias (e.g. "Volunteer Work Abroad" scored 85.5 against
    "Work History" via WRatio -- confidently, wrongly, "experience").
    `token_sort_ratio` (order-independent whole-phrase similarity) does not
    exhibit this failure mode on the same test phrases while still scoring
    genuine matches (including reordered ones) at or near 100.

    `processor=str.lower` is required, not optional: an ALL-CAPS header
    ("CONTACT", "SKILLS") -- one of the most common real-world header
    conventions, and exactly the pattern `_is_candidate_header_line`'s
    all-caps signal exists to catch -- scored as low as 13-25 against the
    Title-Case gazetteer without it (case-sensitive comparison), forcing
    every all-caps header through the unreliable Tier 4 fallback instead of
    matching confidently at Tier 2. Found during Milestone 2's own
    golden-corpus validation pass; fixed immediately as an unambiguous
    correctness bug, not a design trade-off requiring separate sign-off."""
    if not _ALL_ALIASES:  # defensive; unreachable with a non-empty gazetteer
        return "unknown", 0.0
    best_alias, score, _ = process.extractOne(
        text, _ALL_ALIASES, scorer=fuzz.token_sort_ratio, processor=str.lower
    )
    return _ALIAS_TO_LABEL[best_alias], score


class _LazySemanticModel:
    """Lazy singleton, private to this module -- see the module-level
    comment for why this isn't shared with heuristic_evaluator.py's own
    copy. Caches the gazetteer's alias embeddings alongside the model
    itself, since the alias list never changes at runtime."""

    _model = None
    _alias_embeddings = None

    @classmethod
    def get(cls):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                cls._model = SentenceTransformer(_SEM_MODEL_NAME)
            except Exception as e:  # pragma: no cover - environment-dependent
                logger.warning("SentenceTransformer unavailable for Section Detection Tier 4: %s", e)
                cls._model = False
        return cls._model if cls._model is not False else None

    @classmethod
    def alias_embeddings(cls):
        model = cls.get()
        if model is None:
            return None
        if cls._alias_embeddings is None:
            cls._alias_embeddings = model.encode(_ALL_ALIASES)
        return cls._alias_embeddings


def _embedding_match_label(text: str) -> tuple[str, float] | None:
    """Tier 4, last resort: cosine similarity of `text` against every
    gazetteer alias's embedding. Returns (label, similarity) for the best
    match, or None if SBERT is unavailable -- the caller falls back to
    "unknown" in that case, never crashes (Section 7's graceful-degradation
    requirement)."""
    model = _LazySemanticModel.get()
    if model is None:
        return None
    alias_embeddings = _LazySemanticModel.alias_embeddings()
    from sentence_transformers.util import cos_sim

    text_embedding = model.encode([text])
    similarities = cos_sim(text_embedding, alias_embeddings)[0]
    best_index = int(similarities.argmax())
    return _ALIAS_TO_LABEL[_ALL_ALIASES[best_index]], float(similarities[best_index])


def _classify_header_line(line: _Line) -> tuple[str, float, str]:
    """Returns (label, confidence, reason). Tiers 2/3 are one call, per the
    module docstring: a single fuzzy-match with a graduated confidence,
    rather than two literally separate matching passes -- behaviorally
    identical to the documented cascade. Tier 4 (SBERT) is tried only when
    the gazetteer match is too weak to trust at all."""
    text = line.text
    label, score = _fuzzy_match_label(text)
    docx_style = _is_docx_heading_style(line)

    if score >= FUZZY_CONFIDENT_THRESHOLD:
        confidence = 0.98 if docx_style else 0.9
        reason = f"alias_gazetteer_fuzzy:{score:.0f}"
        if docx_style:
            reason = f"docx_style_match:{line.style_name};{reason}"
        return label, confidence, reason

    if score >= FUZZY_WEAK_THRESHOLD:
        reason = f"alias_gazetteer_weak:{score:.0f}"
        if docx_style:
            reason = f"docx_style_match:{line.style_name};{reason}"
        return label, 0.4, reason

    embedding_result = _embedding_match_label(text)
    if embedding_result is not None:
        emb_label, emb_score = embedding_result
        if emb_score >= EMBEDDING_SIMILARITY_FLOOR:
            reason = f"embedding_fallback:{emb_score:.2f}"
            if docx_style:
                reason = f"docx_style_match:{line.style_name};{reason}"
            return emb_label, 0.4, reason

    return "unknown", 0.2, "no_confident_match"


def _build_sections(lines: list[_Line], body_font_size: float) -> list[Section]:
    """Walks the document's lines in order, starting a new `Section` at
    every header-like line and appending everything else to whichever
    section is currently open. This is also the entire mechanism for
    cross-page/column continuation (module docstring): a section keeps
    collecting lines from wherever they occur until the next header.

    Contact special case, part 1 (Section 4.3): the block before the first
    header defaults to "contact", not "unknown" -- and so does any
    header-like-but-unrecognized line (e.g. a large-font name banner) that
    appears before the first *confidently labeled* section, since that's
    almost always the name/contact block, not a real section boundary of
    its own. Once a real section has started, an unrecognized header-like
    line reverts to being its own "unknown" section as usual -- this
    folding only applies to the leading block. Part 2 (the email/phone/URL
    regex safety net) is a separate pass, `_apply_contact_safety_net`,
    since it's document-wide and independent of this walk."""
    sections: list[Section] = []
    leading = Section(
        label="contact",
        raw_header_text="",
        spans=[],
        header_confidence=1.0,
        header_match_reason="pre_first_header_block",
    )
    current = leading
    found_real_section = False

    for line in lines:
        if _is_header_line(line, body_font_size):
            label, confidence, reason = _classify_header_line(line)
            if label == "unknown" and not found_real_section:
                current.spans.extend(line.spans)
                continue
            if label != "unknown":
                found_real_section = True
            current = Section(
                label=label,
                raw_header_text=line.text,
                spans=list(line.spans),
                header_confidence=confidence,
                header_match_reason=reason,
            )
            sections.append(current)
        else:
            current.spans.extend(line.spans)

    if leading.spans:
        sections.insert(0, leading)
    return sections


_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+|(?:linkedin|github)\.com/\S+", re.IGNORECASE)


def _looks_like_contact_info(text: str) -> bool:
    return bool(_EMAIL_PATTERN.search(text) or _PHONE_PATTERN.search(text) or _URL_PATTERN.search(text))


def _apply_contact_safety_net(sections: list[Section], all_spans: list[TextSpan]) -> list[Section]:
    """Contact special case, part 2 (Section 4.3): any span anywhere in the
    document containing an email/phone/URL pattern is added to "contact"
    IN ADDITION to wherever it structurally landed -- catching contact info
    misplaced in a sidebar or footer that would otherwise be attached to
    an unrelated section. `Section.spans` is just a list of references, not
    an exclusive partition, so a span legitimately belonging to two
    sections at once is a deliberate design choice, not a bug (see the
    architecture doc's implementation note)."""
    matching_spans = [s for s in all_spans if _looks_like_contact_info(s.text)]
    if not matching_spans:
        return sections

    contact_section = next((s for s in sections if s.label == "contact"), None)
    if contact_section is None:
        contact_section = Section(
            label="contact",
            raw_header_text="",
            spans=[],
            header_confidence=1.0,
            header_match_reason="contact_pattern_sweep",
        )
        sections = [contact_section, *sections]

    already_present = {id(s) for s in contact_section.spans}
    for span in matching_spans:
        if id(span) not in already_present:
            contact_section.spans.append(span)
            already_present.add(id(span))
    return sections


class HeuristicSectionDetector:
    """Concrete `interfaces.SectionDetector` implementation. The full
    4-tier cascade (DOCX style match, alias gazetteer fuzzy match, SBERT
    embedding fallback) plus the contact special case are implemented here
    (see docs/architecture/ResumeIntelligenceEngine.md Section 4.3)."""

    def detect(self, doc: DocumentModel, trace=None) -> list[Section]:
        lines = _group_into_document_lines(doc.spans)
        sections = _build_sections(lines, doc.body_font_size)
        return _apply_contact_safety_net(sections, doc.spans)
