"""
Entry clustering — Milestone 3 (Entity Parsing) shared utility. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Shared by `ExperienceParser` and `ProjectParser`: "structurally identical
entry-clustering approach... a bold/larger line (header) followed by body
text until the next such header or section end" (Section 4.4). A local,
self-contained implementation -- NOT an import from `sections.py`'s or
`layout.py`'s line-grouping helpers, both of which are frozen milestones.
The minor duplication (page/column-aware line grouping, near-identical to
`sections.py`'s own) is the accepted cost of respecting those freezes,
consistent with the same trade-off already made between Milestone 1 and
Milestone 2.

Leading underscore on the module name: this is parser-package-private
utility, not part of the public `resume_engine` surface any other stage
should import from.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

from resume_engine.document_model import TextSpan
from resume_engine.text_normalization import (
    contains_year,
    is_bare_date_line,
    is_open_list_end,
    looks_like_title,
    starts_with_action_verb,
    starts_with_bullet,
    starts_with_non_title_label,
    strip_leading_bullet,
    strip_leading_enumeration,
)

LINE_Y_TOLERANCE = 3.0        # points; spans within this y0 delta are one line
MIN_HEADER_FONT_RATIO = 1.05  # font_size >= body_font_size * this counts as "larger"
MIN_BOLD_CHAR_RATIO = 0.3     # fraction of a line's characters that must be bold to count the line as a bold header
# A line whose vertical whitespace above it exceeds the section's normal row
# pitch by this ratio AND this many absolute points reads as a blank-line
# separation before it -- a format-independent entry-boundary signal (a real
# gap on PDF/DOCX, and, since the extractor now preserves blank lines, on TXT
# too). Provisional, documented starting values, same discipline as the other
# thresholds in this package.
GAP_RATIO = 1.5
GAP_MIN_ABSOLUTE = 6.0


class _Line:
    __slots__ = ("spans", "y0", "page_num", "column_index")

    def __init__(self, spans: list[TextSpan]):
        self.spans = spans
        self.y0 = min(s.bbox[1] for s in spans)
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
        """True only when a MAJORITY of the line's characters are bold, not
        merely when the line contains any bold span at all.

        Found during Phase 1 real-world evaluation: some resumes bold a
        single emphasized word or acronym inside an otherwise-plain bullet
        (e.g. "...reporting directly to the **CTO**."). The old "any bold
        span" check treated that whole bullet as a bold header line,
        fragmenting one job into one spurious entry per bolded bullet. A
        genuine header line (e.g. "Acme Corp, Senior Engineer") is bold
        end-to-end; a character-count majority reliably tells the two
        apart without needing a stricter "fully bold" rule that a header
        with one non-bold punctuation span would fail."""
        total_chars = sum(len(s.text) for s in self.spans)
        if total_chars == 0:
            return False
        bold_chars = sum(len(s.text) for s in self.spans if s.is_bold)
        return (bold_chars / total_chars) >= MIN_BOLD_CHAR_RATIO


def _group_into_lines(spans: list[TextSpan]) -> list[_Line]:
    """Groups spans into visual lines, in order, never merging across a
    (page_num, column_index) change -- same shape as sections.py's grouping
    (Milestone 2), reimplemented locally per this module's docstring."""
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


def _local_body_font_size(lines: list[_Line]) -> float:
    """The median line-level font size within THIS section's own lines --
    the baseline `_is_entry_header_line` compares against, instead of
    `doc.body_font_size` (Milestone 1's document-WIDE modal font size,
    computed by raw span-token count across the whole document).

    Found during Phase 1 real-world evaluation: the document-wide
    statistic is a per-token count, not a per-line or area-weighted one,
    so an unrelated dense region elsewhere in the document (e.g. a
    comma-heavy inline skills paragraph, which produces many short-token
    spans) can out-vote the section's real body-bullet font size even
    though it occupies a small fraction of the page. On one real resume
    this made an entire Experience section's 9pt bullets register as
    "larger than body" against a document-wide mode of 7.2pt pulled from
    elsewhere in the document, splitting a single job into ~20 spurious
    entries (one per bullet/clause).

    Median over LINES (not a raw span-token mode) is used because it is
    robust to the common shape of one taller/bolder header line among
    several body lines, while still resolving sensibly for the shortest
    sections (see `test_entry_clustering.py`)."""
    if not lines:
        return 0.0
    return statistics.median(line.max_font_size for line in lines)


def _line_role(
    line: _Line,
    body_font_size: float,
    prev_line_text: str = "",
    next_line_text: str = "",
) -> str:
    """Classifies a line as ``"content"``, ``"strong_header"``, or
    ``"title"`` -- the input to the entry-start walk in ``cluster_entries``.

    Phase 1 robustness rewrite. The prior boolean `_is_entry_header_line`
    required a FORMATTING (bold/larger) or a year/pipe signal for a line to
    count as an entry start. On plain-text resumes (and flat/ATS PDFs) those
    signals are absent, so dateless/pipeless/boldless project entries -- the
    dominant real-world shape -- collapsed into a single merged entry, and
    every project's technologies were attributed to the first one. The fix
    keeps ALL the structural NEGATIVE signals (they reliably identify
    body/continuation lines) but splits the positive decision into two
    tiers, so a title-like line can start an entry WITHOUT a formatting or
    date signal -- with the start-vs-continuation ambiguity resolved from
    context by the caller, not by demanding a formatting cue up front.

    NEGATIVE -> ``"content"`` (never an entry start):
      - opens lowercase (a wrapped sentence fragment);
      - opens with a resume action verb ("Developed ...", "Owned ...");
      - opens with a metadata label ("Tools:", "GitHub:", "Tech stack:");
      - the PREVIOUS line ended mid-list (trailing comma/pipe) -- a wrapped
        continuation;
      - is not title-like on its pre-"|" head (too long, sentence, etc.).

    ``"strong_header"`` (a confident entry start; gated by the title-head
    check above): carries a "|" tech delimiter, OR a year / a bare-date next
    line, OR bold / larger-than-local-body font. This is the exact set the
    old boolean accepted -- the PDF/DOCX/date/pipe happy path is unchanged.

    ``"title"`` (a title-like line with NO strong signal): a *candidate*
    entry start. Whether it actually starts a new entry or continues the
    current one (e.g. a one-line description directly under a bare title) is
    genuinely context-dependent -- the caller decides using blank-line gaps
    and whether the current entry has accrued body yet.

    All signals are structural and generic -- no resume-specific text."""
    text = line.text
    analysis = strip_leading_enumeration(strip_leading_bullet(text)).strip()
    if not analysis:
        return "content"

    # ── Negative signals: body/continuation, never an entry start ──
    if analysis[0].islower():
        return "content"
    if starts_with_action_verb(text) or starts_with_non_title_label(text):
        return "content"
    if prev_line_text and is_open_list_end(prev_line_text):
        return "content"
    # A line ending in a full stop is a sentence (a body/summary line), not an
    # entry title -- the same rule sections.py applies to section headers. (A
    # trailing comma is NOT rejected: that is a wrapped tech-list header, e.g.
    # "Foo | HTML, CSS, React,".) Without this a short body sentence like "Did
    # some real work here." reads as title-like and can hijack the entry.
    if analysis.rstrip().endswith("."):
        return "content"

    # Measure "titleishness" on the part BEFORE any "|" technology tail: a
    # real title like "Foo Platform | React, Node, Express" is short, but the
    # whole line (title + tail) can exceed the word cap and be wrongly
    # rejected. The tail is the technology list, not part of the title.
    title_head = text.split("|", 1)[0]
    if not looks_like_title(title_head):
        return "content"

    # ── Tier 1: strong entry-start signals (unchanged happy path) ──
    if "|" in text:
        return "strong_header"
    if contains_year(analysis) or (next_line_text and is_bare_date_line(next_line_text)):
        return "strong_header"
    if body_font_size > 0:
        if line.is_bold or line.max_font_size >= body_font_size * MIN_HEADER_FONT_RATIO:
            return "strong_header"
    elif line.is_bold:
        return "strong_header"

    # ── Tier 2: title-like, but no strong signal -- a context-dependent
    # candidate the caller resolves with gaps/neighbours. A BULLETED line is
    # excluded here: a list item with no strong entry signal is a sub-point
    # (the common case), not a weak title. Bulleted lines can still be entry
    # starts, but only via the strong signals above (e.g. a bullet+year entry
    # marker) -- exactly the pre-existing contract. Without this exclusion a
    # wrapped bullet whose lead verb is outside the action-verb lexicon (e.g.
    # "- Migrated a billing module to microservices,") would be mistaken for a
    # new entry. ──
    if starts_with_bullet(text):
        return "content"
    return "title"


def _gap_flags(lines: list[_Line]) -> list[bool]:
    """For each line, True when the vertical whitespace directly above it is
    markedly larger than the section's normal row pitch -- i.e. a blank line
    separates it from the previous line. This is the single format-
    independent boundary signal resumes reliably carry (a real gap on
    PDF/DOCX; preserved by the TXT extractor's blank-line handling). Only
    meaningful WITHIN one page/column run: a page or column change is never a
    semantic blank line, so it is never reported as a gap.

    The threshold is derived from the section's OWN median row pitch (robust
    to font size / line-height differences between resumes), the same
    per-section-median discipline `_local_body_font_size` already uses."""
    n = len(lines)
    flags = [False] * n
    deltas: list[float] = []
    for i in range(1, n):
        prev, cur = lines[i - 1], lines[i]
        if cur.page_num == prev.page_num and cur.column_index == prev.column_index:
            d = cur.y0 - prev.y0
            if d > 0:
                deltas.append(d)
    if not deltas:
        return flags
    deltas.sort()
    median = deltas[len(deltas) // 2]
    threshold = max(median * GAP_RATIO, median + GAP_MIN_ABSOLUTE)
    for i in range(1, n):
        prev, cur = lines[i - 1], lines[i]
        same_block = cur.page_num == prev.page_num and cur.column_index == prev.column_index
        if same_block and (cur.y0 - prev.y0) > threshold:
            flags[i] = True
    return flags


_TITLE_SEP_DASH_RE = re.compile(r"\s[\-–—]\s")  # a spaced hyphen / en / em dash


def _title_separator(text: str) -> str:
    """The title/description separator a line uses, normalised to a KIND so
    two entries that use the same shape compare equal: ``"|"`` for a pipe,
    ``"-"`` for any spaced hyphen/en/em dash, or ``""`` when the line has no
    such separator. Used purely as a parallel-structure signal (do adjacent
    title lines share a separator shape?), never to alter the displayed
    title. A comma is deliberately NOT a title separator (it delimits list
    items, not title/description)."""
    if "|" in text:
        return "|"
    if _TITLE_SEP_DASH_RE.search(text):
        return "-"
    return ""


def _entry_start_flags(lines: list[_Line], body_font_size: float) -> list[bool]:
    """The heart of Phase 1 segmentation: walk the section's lines and mark
    which ones START a new entry. Combines the per-line role
    (`_line_role`) with two contextual signals -- a blank-line gap above the
    line, and whether the currently-open entry has accrued any body yet.

    Rules (a title-like/strong line is a new entry when):
      - no entry is open yet (the section's first entry), OR
      - a blank line separates it from the previous line (`_gap_flags`), OR
      - the current entry already has body -- a fresh title after a prior
        entry's description/bullets is the next entry.
    A title-like/strong line that is adjacent (no gap) to the current entry's
    start with NO body in between is FOLDED into that entry: this is the
    multi-line-header / title+one-line-description shape (e.g. an education
    entry's institution line and its degree line, or a project's name line
    and its tagline), NOT two entries. This is what prevents over-
    segmentation while the gap/body signals prevent under-segmentation."""
    n = len(lines)
    roles = [
        _line_role(
            lines[i],
            body_font_size,
            prev_line_text=lines[i - 1].text if i > 0 else "",
            next_line_text=lines[i + 1].text if i + 1 < n else "",
        )
        for i in range(n)
    ]
    gaps = _gap_flags(lines)

    starts = [False] * n
    open_entry = False
    body_since_start = False
    current_sep = ""
    for i in range(n):
        role = roles[i]
        if role == "content":
            start = False
            if open_entry:
                body_since_start = True
        else:  # "strong_header" or "title"
            if not open_entry:
                start = True
            elif gaps[i]:
                start = True
            elif body_since_start:
                # A fresh title after the current entry's body -> next entry.
                start = True
            else:
                # Adjacent to the current entry's start, nothing between.
                # Normally a multi-line header / one-line description (fold),
                # UNLESS this line repeats the start line's own title-
                # separator shape ("Name - desc" under "Name - desc", or
                # "Name | ..." under "Name | ..."). A shared, non-trivial
                # separator is parallel structure -- a sibling entry, not a
                # continuation -- and lets adjacent same-shaped entries with
                # no blank line and no body between them still be separated.
                this_sep = _title_separator(lines[i].text)
                start = bool(this_sep) and this_sep == current_sep
        if start:
            open_entry = True
            body_since_start = False
            current_sep = _title_separator(lines[i].text)
        starts[i] = start
    return starts


@dataclass
class Entry:
    """One clustered entry: the header line's spans, plus every span
    belonging to its body (everything until the next header or section
    end)."""

    header_spans: list[TextSpan]
    body_spans: list[TextSpan] = field(default_factory=list)
    header_is_corroborated: bool = True  # False only for the whole-section fallback entry
    # (cluster_entries' docstring) -- ProjectParser's title confidence
    # needs this: a free-text title has no gazetteer to check against, so
    # "was this line actually bold/larger" is its only formatting signal
    # (architecture doc Section 4.4).

    @property
    def header_text(self) -> str:
        return " ".join(s.text for s in sorted(self.header_spans, key=lambda s: s.bbox[0])).strip()

    @property
    def body_lines(self) -> list[str]:
        """Body text grouped back into lines (not one flattened string) --
        callers that want per-line structure (e.g. to find a labeled
        "Tech:" line) need this; callers that just want prose join it."""
        lines = _group_into_lines(self.body_spans)
        return [line.text for line in lines if line.text]


def strip_section_header_line(spans: list[TextSpan], raw_header_text: str) -> list[TextSpan]:
    """`Section.spans` (sections.py, Milestone 2) always starts with the
    detected header line's OWN spans -- e.g. an "experience" Section's
    spans begin with the "Experience" header line itself, not just its
    entries. Without stripping it, `cluster_entries` treats the section
    header as if it were a bogus first entry (found during Milestone 3
    validation). Matches by exact line text against `raw_header_text`
    rather than just dropping "the first line", since a label detected
    more than once (cross-page continuation via
    `pipeline._group_sections_by_label`, or Milestone 2's documented
    running-header fragmentation) can concatenate more than one header hit
    into one Section's spans."""
    if not raw_header_text:
        return spans
    lines = _group_into_lines(spans)
    return [s for line in lines if line.text != raw_header_text for s in line.spans]


def cluster_entries(spans: list[TextSpan], body_font_size: float) -> list[Entry]:
    """Walks `spans` (already in linear reading order -- a Section's own
    spans, which are already correctly ordered by Milestone 1's Layout
    Reconstruction) and groups them into entries: a header-like line starts
    a new entry, everything else joins the currently-open entry's body.

    `body_font_size` (the document-wide statistic from `doc.body_font_size`)
    is used only as a last-resort fallback for a degenerate empty-lines
    input; the header/body threshold itself is `_local_body_font_size`,
    computed from this section's own lines (see that function's docstring
    for why the document-wide statistic is unreliable here).

    Graceful fallback: if NO line in `spans` is structurally header-like
    (a legitimate case -- some plain-ATS templates use zero bold/size
    variation anywhere, not just at the document-section-header level),
    the entire input becomes ONE entry (first line as header, rest as
    body) rather than silently producing zero entries from a section that
    clearly has content. This mirrors the "fail visibly and gracefully,
    never fabricate absence" principle from Milestones 1-2."""
    lines = _group_into_lines(spans)
    if not lines:
        return []

    local_body_font_size = _local_body_font_size(lines) or body_font_size

    # Which lines START an entry -- a multi-signal decision (role + blank-line
    # gap + body-accrued context), see `_entry_start_flags`. This subsumes the
    # old per-line boolean AND the separate run-collapse pass into one walk.
    starts = _entry_start_flags(lines, local_body_font_size)

    if not any(starts):
        # Genuine last resort: nothing in this section reads as an entry start
        # at all (a structureless prose blob, no title-like line anywhere).
        # One entry, explicitly NOT formatting-corroborated so downstream
        # confidence reflects the uncertainty -- never silently fabricated as
        # a confident boundary. With Tier-2 title detection above, real
        # multi-entry sections no longer reach this path.
        return [
            Entry(
                header_spans=lines[0].spans,
                body_spans=[s for l in lines[1:] for s in l.spans],
                header_is_corroborated=False,
            )
        ]

    entries: list[Entry] = []
    current: Entry | None = None
    for idx, line in enumerate(lines):
        if starts[idx]:
            current = Entry(header_spans=line.spans)
            entries.append(current)
        elif current is not None:
            current.body_spans.extend(line.spans)
        # A body line before the first entry start is dropped -- a documented
        # no-op (any(starts) is True here, so at least one entry exists).
    return entries
