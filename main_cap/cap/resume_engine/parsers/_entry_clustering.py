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

from dataclasses import dataclass, field

from resume_engine.document_model import TextSpan

LINE_Y_TOLERANCE = 3.0        # points; spans within this y0 delta are one line
MIN_HEADER_FONT_RATIO = 1.05  # font_size >= body_font_size * this counts as "larger"


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
        return any(s.is_bold for s in self.spans)


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


def _is_entry_header_line(line: _Line, body_font_size: float) -> bool:
    """Bold or larger than body text -- deliberately narrower than
    sections.py's section-header pre-filter (no ALL-CAPS signal): within an
    Experience/Projects section, entry headers ("Acme Corp, Senior
    Engineer", a project title) are typically Title Case, not all-caps, and
    reusing the ALL-CAPS signal here would risk the same false-positive
    class Milestone 2 documented (a short all-caps body word like "AWS"
    inside a bullet)."""
    if body_font_size <= 0:
        return line.is_bold
    return line.is_bold or line.max_font_size >= body_font_size * MIN_HEADER_FONT_RATIO


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

    if not any(_is_entry_header_line(line, body_font_size) for line in lines):
        return [
            Entry(
                header_spans=lines[0].spans,
                body_spans=[s for l in lines[1:] for s in l.spans],
                header_is_corroborated=False,
            )
        ]

    entries: list[Entry] = []
    current: Entry | None = None
    for line in lines:
        if _is_entry_header_line(line, body_font_size):
            current = Entry(header_spans=line.spans)
            entries.append(current)
        elif current is not None:
            current.body_spans.extend(line.spans)
        # A body line before any header is dropped -- shouldn't happen
        # given the fallback above guarantees at least one header exists,
        # but stays a documented no-op rather than an exception if it did.
    return entries
