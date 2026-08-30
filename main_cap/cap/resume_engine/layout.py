"""
Layout Reconstruction — Stage 2. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.2.

`ColumnAwareLayoutReconstructor` resolves single- vs. two-column layouts
into one correct reading order per page via gap-analysis clustering
(k in {1, 2}) -- deliberately simple, explainable, and testable rather than
a learned layout model, per the architecture doc's explicit mandate.
Three-or-more-column layouts and true ruled-table sections remain an
explicit non-goal: the algorithm below degrades them to a low-confidence
"ambiguous" or "single_column" read rather than mis-parsing them silently.

Column classification is done directly on each span's left edge (x0),
*before* any y-proximity line-grouping -- grouping into lines first would
merge same-row spans from two different columns into one line and destroy
the x0 signal columns are detected from. Line-grouping only happens after
a column split is decided, scoped to each band (or to the whole page for
single_column/ambiguous), purely to establish reading order and corroborate
the split.

A candidate split is corroborated by a small set of independent, named
`CorroborationSignal`s (line count, balance, row-pitch continuity, y-range
overlap), combined by one explicit policy function (`_evaluate_corroboration`,
currently: all must pass). This structure -- not any single signal -- is
the actual extension point for future work: a semantic signal (e.g. "this
candidate band's text looks date/label-heavy vs. prose," once Section
Detection or content classification exists) is one more function appended
to `GEOMETRIC_SIGNALS`, requiring no change to `_classify_page` or the
combination policy itself.

Row-pitch continuity was added after a Milestone 1 validation pass found
the original balance-ratio-only guard both accepted inline right-aligned
dates as a false second column and rejected a genuine short sidebar (see
docs/architecture/ResumeIntelligenceEngine.md Section 4.2's implementation
note and Milestone1_ValidationReport.md). A real column's own rows are
spaced at roughly the page's normal single-line cadence; a value that only
rides along on *some* of the other column's rows (like a date printed once
per job entry) is spaced much further apart, because it's missing on every
row that doesn't have one -- line count alone can't tell these apart, since
both cases can have the same number of lines. Balance ratio was **kept**
rather than replaced (explicit direction: don't drop a corroborating signal
without evidence it contributes nothing across a much larger corpus than
this one) and its threshold recalibrated -- see `MIN_BAND_BALANCE_RATIO`
below for the specific data this was based on.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import median

from resume_engine.document_model import DocumentModel, TextSpan
from resume_engine.pipeline_trace import PipelineTrace

# Tunable, documented constants -- one-line reviewable diffs, per the
# architecture doc's confidence-scoring philosophy (Section 7), rather than
# magic numbers buried in the algorithm. MIN_BAND_BALANCE_RATIO and
# MAX_PITCH_RATIO in particular are VALIDATION-DERIVED, not intrinsic
# properties of resume geometry -- see each constant's comment for the
# specific observed data behind its current value, and revisit both if a
# larger golden corpus than the ~22 fixtures used so far suggests otherwise.
LINE_Y_TOLERANCE = 3.0          # points; spans within this y0 delta are treated as one line
COLUMN_GAP_RATIO = 0.12         # min horizontal gap to consider, as a fraction of page width
MIN_CORROBORATING_LINES = 3     # both candidate bands must have at least this many lines
MIN_BAND_Y_OVERLAP_RATIO = 0.5  # bands must run in parallel down the page, not header/footer
MIN_BAND_BALANCE_RATIO = 0.1    # smaller band's line count / larger band's. Validation data
                                 # (Milestone1_ValidationReport.md addendum): every genuine
                                 # two-column fixture observed sits at >=0.375; the one known
                                 # genuine short-sidebar case sits at 0.15; the one known false
                                 # positive (inline right-aligned dates) sits at 0.375 too, so
                                 # balance ratio alone never actually distinguished it -- that's
                                 # what MAX_PITCH_RATIO is for. 0.1 sits with deliberate margin
                                 # below the observed 0.15 rather than tuned tightly to it, since
                                 # a single data point isn't enough to pin an exact floor.
MAX_PITCH_RATIO = 1.5           # larger band-internal row pitch / smaller. Validation data:
                                 # the one known false positive (inline right-aligned dates)
                                 # measured 2.0; every known genuine two-column fixture measured
                                 # ~1.0. 1.5 sits with margin between them, not derived from a
                                 # larger statistical sample -- guards against a value that only
                                 # appears on SOME of the other band's rows (e.g. a date printed
                                 # once per job entry) being misread as a genuine, continuously-
                                 # flowing second column; see the module docstring above.


class _Line:
    """One y-clustered group of spans, with the bounding box of the group."""

    __slots__ = ("spans", "y0", "y1", "x0", "x1")

    def __init__(self, spans: list[TextSpan]):
        self.spans = spans
        self.y0 = min(s.bbox[1] for s in spans)
        self.y1 = max(s.bbox[3] for s in spans)
        self.x0 = min(s.bbox[0] for s in spans)
        self.x1 = max(s.bbox[2] for s in spans)


def _group_into_lines(spans: list[TextSpan]) -> list[_Line]:
    """Groups spans that are already confined to one column (or the whole
    page, for single-column text) into lines by y0 proximity."""
    ordered = sorted(spans, key=lambda s: s.bbox[1])
    groups: list[list[TextSpan]] = []
    for span in ordered:
        if groups and abs(span.bbox[1] - groups[-1][0].bbox[1]) <= LINE_Y_TOLERANCE:
            groups[-1].append(span)
        else:
            groups.append([span])
    return [_Line(group) for group in groups]


def _row_pitch(lines: list["_Line"]) -> float | None:
    """Median gap between consecutive row y0s within one band -- the band's
    own row-to-row cadence. Median (not mean) so one larger paragraph-break
    gap doesn't distort an otherwise single-spaced band. None if there
    aren't at least two rows to measure a gap from."""
    if len(lines) < 2:
        return None
    ordered = sorted(lines, key=lambda l: l.y0)
    gaps = [b.y0 - a.y0 for a, b in zip(ordered, ordered[1:])]
    return median(gaps)


def _page_width_estimate(spans: list[TextSpan]) -> float:
    """No true page-width geometry is stored on DocumentModel (deliberately
    -- nothing downstream needs it beyond this ratio), so the rightmost
    extent of any span on the page is used as a self-contained proxy for
    the page's usable content width."""
    return max((s.bbox[2] for s in spans), default=0.0)


@dataclass
class CorroborationSignal:
    """One independent piece of evidence for or against a candidate column
    split, in the same explainable spirit as `Confidence.reasons`
    (confidence.py) -- every signal states its own name, whether it passed,
    and why, so a rejection or acceptance is never a single opaque number."""

    name: str
    passed: bool
    detail: str


def _line_count_signal(left_lines: list[_Line], right_lines: list[_Line]) -> CorroborationSignal:
    passed = len(left_lines) >= MIN_CORROBORATING_LINES and len(right_lines) >= MIN_CORROBORATING_LINES
    return CorroborationSignal(
        "line_count",
        passed,
        f"line_count_left_{len(left_lines)}_right_{len(right_lines)}_min_{MIN_CORROBORATING_LINES}",
    )


def _balance_signal(left_lines: list[_Line], right_lines: list[_Line]) -> CorroborationSignal:
    balance = min(len(left_lines), len(right_lines)) / max(len(left_lines), len(right_lines))
    passed = balance >= MIN_BAND_BALANCE_RATIO
    return CorroborationSignal("balance", passed, f"balance_ratio_{balance:.2f}_min_{MIN_BAND_BALANCE_RATIO}")


def _pitch_continuity_signal(left_lines: list[_Line], right_lines: list[_Line]) -> CorroborationSignal:
    left_pitch = _row_pitch(left_lines)
    right_pitch = _row_pitch(right_lines)
    if left_pitch is None or right_pitch is None:
        return CorroborationSignal("pitch_continuity", False, "pitch_continuity_insufficient_lines_to_measure")
    pitch_ratio = max(left_pitch, right_pitch) / min(left_pitch, right_pitch)
    passed = pitch_ratio <= MAX_PITCH_RATIO
    return CorroborationSignal(
        "pitch_continuity", passed, f"pitch_ratio_{pitch_ratio:.2f}_max_{MAX_PITCH_RATIO}"
    )


def _y_overlap_signal(left_lines: list[_Line], right_lines: list[_Line]) -> CorroborationSignal:
    left_y0, left_y1 = min(l.y0 for l in left_lines), max(l.y1 for l in left_lines)
    right_y0, right_y1 = min(l.y0 for l in right_lines), max(l.y1 for l in right_lines)
    overlap = min(left_y1, right_y1) - max(left_y0, right_y0)
    shorter_extent = min(left_y1 - left_y0, right_y1 - right_y0)
    ratio = (overlap / shorter_extent) if shorter_extent > 0 else 0.0
    passed = shorter_extent > 0 and ratio >= MIN_BAND_Y_OVERLAP_RATIO
    return CorroborationSignal("y_overlap", passed, f"y_overlap_ratio_{ratio:.2f}_min_{MIN_BAND_Y_OVERLAP_RATIO}")


# The actual extension point: today every entry here is geometric, but the
# name and shape are deliberately not geometry-specific -- a future semantic
# signal (e.g. "this candidate band's text is date/label-heavy vs. prose,"
# once Section Detection or content classification exists) is one more
# (left_lines, right_lines) -> CorroborationSignal function appended here --
# no change needed to _classify_page or _evaluate_corroboration's
# combination policy to add one.
CORROBORATION_SIGNALS = [_line_count_signal, _balance_signal, _pitch_continuity_signal, _y_overlap_signal]


def _evaluate_corroboration(
    left_lines: list[_Line], right_lines: list[_Line]
) -> tuple[bool, list[CorroborationSignal]]:
    """Combination policy: ALL signals must pass.

    This strict-AND policy is intentionally provisional for Milestone 1,
    scoped to a purely geometric signal set where every signal is either
    clearly satisfied or clearly not. It's expected to evolve once semantic
    corroboration (see CORROBORATION_SIGNALS above) enters the mix -- at
    that point, forcing every signal to pass independently is likely too
    conservative (e.g. strong semantic evidence should be able to outweigh
    one borderline geometric signal), and this function's body would move
    to a confidence- or weighted-evidence-based policy instead, without
    touching the signal functions themselves or their caller."""
    signals = [fn(left_lines, right_lines) for fn in CORROBORATION_SIGNALS]
    return all(s.passed for s in signals), signals


class _PageLayout:
    """One page's classification: which lines belong to which column
    (`right_lines` empty for single_column/ambiguous), the detected mode,
    and its confidence -- everything the reading-order sort and the trace
    enrichment (pipeline.py) need."""

    __slots__ = ("mode", "confidence", "left_lines", "right_lines", "reason")

    def __init__(self, mode, confidence, left_lines, right_lines, reason):
        self.mode = mode  # "single_column" | "two_column" | "ambiguous"
        self.confidence = confidence
        self.left_lines = left_lines
        self.right_lines = right_lines
        self.reason = reason


def _classify_page(spans: list[TextSpan], page_width_estimate: float) -> _PageLayout:
    all_lines = _group_into_lines(spans)

    if len(spans) < 2 * MIN_CORROBORATING_LINES or page_width_estimate <= 0:
        return _PageLayout("single_column", 0.95, all_lines, [], "too_few_spans_for_column_analysis")

    left_edges = sorted(set(round(s.bbox[0], 1) for s in spans))
    if len(left_edges) < 2:
        return _PageLayout("single_column", 0.95, all_lines, [], "single_left_edge_cluster")

    best_gap = 0.0
    split_bounds = None
    for a, b in zip(left_edges, left_edges[1:]):
        gap = b - a
        if gap > best_gap:
            best_gap = gap
            split_bounds = (a, b)

    threshold = page_width_estimate * COLUMN_GAP_RATIO
    if split_bounds is None or best_gap < threshold:
        return _PageLayout("single_column", 0.95, all_lines, [], "no_gap_cleared_threshold")

    split_point = (split_bounds[0] + split_bounds[1]) / 2
    left_spans = [s for s in spans if s.bbox[0] < split_point]
    right_spans = [s for s in spans if s.bbox[0] >= split_point]
    left_lines = _group_into_lines(left_spans)
    right_lines = _group_into_lines(right_spans)

    accepted, signals = _evaluate_corroboration(left_lines, right_lines)
    reason = "; ".join(f"{'+' if s.passed else '-'}{s.detail}" for s in signals)

    if not accepted:
        return _PageLayout("ambiguous", 0.35, all_lines, [], f"gap_found_but_not_corroborated: {reason}")

    corroboration_strength = min(len(left_lines), len(right_lines)) - MIN_CORROBORATING_LINES
    confidence = min(0.9, 0.6 + 0.05 * corroboration_strength)
    return _PageLayout("two_column", confidence, left_lines, right_lines, f"corroborated: {reason}")


def _ordered_spans_for_page(page_layout: _PageLayout) -> list[TextSpan]:
    if page_layout.mode == "two_column":
        left_sorted = sorted(page_layout.left_lines, key=lambda l: l.y0)
        right_sorted = sorted(page_layout.right_lines, key=lambda l: l.y0)
        ordered: list[TextSpan] = []
        for line in left_sorted:
            ordered.extend(replace(s, column_index=0) for s in sorted(line.spans, key=lambda s: s.bbox[0]))
        for line in right_sorted:
            ordered.extend(replace(s, column_index=1) for s in sorted(line.spans, key=lambda s: s.bbox[0]))
        return ordered

    # single_column or ambiguous: no split is trusted -- read top-to-bottom
    # in natural document order rather than forcing a risky reorder ("fail
    # visibly and gracefully", architecture doc Section 11).
    all_lines_sorted = sorted(page_layout.left_lines, key=lambda l: l.y0)
    ordered = []
    for line in all_lines_sorted:
        ordered.extend(replace(s, column_index=0) for s in sorted(line.spans, key=lambda s: s.bbox[0]))
    return ordered


def _aggregate_document_mode(page_layouts: list[_PageLayout]):
    if not page_layouts:
        return "single_column", 0.95

    two_column_pages = [p for p in page_layouts if p.mode == "two_column"]
    if two_column_pages:
        confidence = sum(p.confidence for p in two_column_pages) / len(two_column_pages)
        return "two_column", confidence

    ambiguous_pages = [p for p in page_layouts if p.mode == "ambiguous"]
    if ambiguous_pages:
        confidence = sum(p.confidence for p in ambiguous_pages) / len(ambiguous_pages)
        return "ambiguous", confidence

    confidence = sum(p.confidence for p in page_layouts) / len(page_layouts)
    return "single_column", confidence


class ColumnAwareLayoutReconstructor:
    """Concrete `interfaces.LayoutReconstructor` implementation."""

    def reconstruct(self, doc: DocumentModel, trace: PipelineTrace | None = None) -> DocumentModel:
        pages: dict[int, list[TextSpan]] = {}
        for span in doc.spans:
            pages.setdefault(span.page_num, []).append(span)

        page_layouts: list[_PageLayout] = []
        reordered_spans: list[TextSpan] = []
        for page_num in sorted(pages):
            page_spans = pages[page_num]
            layout = _classify_page(page_spans, _page_width_estimate(page_spans))
            page_layouts.append(layout)
            reordered_spans.extend(_ordered_spans_for_page(layout))

        layout_mode, layout_confidence = _aggregate_document_mode(page_layouts)

        return replace(
            doc,
            spans=reordered_spans,
            layout_mode=layout_mode,
            layout_confidence=layout_confidence,
        )
