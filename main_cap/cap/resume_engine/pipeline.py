"""
ResumePipeline — Milestone 0 foundation (see
docs/architecture/ResumeIntelligenceEngine.md Section 2.1 for the
eight-stage pipeline this class orchestrates).

Built around dependency injection (design-review item 1): every
collaborator is declared as a Protocol (resume_engine.interfaces) and
supplied by the caller, never imported or constructed here. This is what
makes the pipeline testable with fakes/mocks and swappable per-stage
without touching this file. The concrete implementations that satisfy
these interfaces live in the sibling stage modules and are wired together
only in factory.py (the composition root) — this module must never import
any of them directly.

No stage has real logic yet (Milestone 0). Calling `.run()` will raise
NotImplementedError at whichever stage's concrete implementation hasn't
landed yet — expected until Milestones 1-6 land.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from resume_engine.confidence import AnnotatedCandidateProfile, Confidence
from resume_engine.interfaces import (
    ConfidenceEngine,
    CrossReferenceEngine,
    DocumentExtractor,
    LayoutReconstructor,
    Normalizer,
    ParserRunner,
    SectionDetector,
    ValidationEngine,
)
from resume_engine.pipeline_trace import PipelineTrace, StageTrace
from resume_engine.sections import Section

EnrichFn = Callable[[Any], "tuple[dict[str, Any], list[Confidence]]"]

# Sections whose entity parser clusters multiple bold-titled entries out of
# one section (`_entry_clustering.cluster_entries`) AND where a dropped
# entry is a real, silent data-loss bug -- exactly the two
# `_absorb_repeated_unknown_entries`'s single-isolated-unknown absorption
# rule was built for. "education" also uses `cluster_entries` but is
# deliberately excluded: its own entries (e.g. a bold institution-name
# line) routinely trigger the same bold-body signal for reasons unrelated
# to a second real degree, and an unrecognized trailing entry there yields
# nothing `EducationParser` can extract -- see that function's docstring.
_MULTI_ENTRY_ABSORPTION_LABELS = frozenset({"projects", "experience"})


def _document_extraction_enrich(doc) -> "tuple[dict[str, Any], list[Confidence]]":
    """Builds document_extraction's StageTrace metadata/confidence from the
    DocumentModel it returned. See
    docs/architecture/ResumeIntelligenceEngine.md Section 4.1 and Section 6."""
    quality = doc.extraction_quality
    metadata = {
        "span_count": quality.span_count,
        "page_count": doc.page_count,
        "chars_extracted": quality.chars_extracted,
        "hyperlink_count": len(doc.hyperlinks),
        "notes": list(quality.notes),
    }
    reasons: list[str] = [f"+sufficient_text_extracted ({quality.chars_extracted} chars)"]
    score = 1.0
    if doc.hyperlinks:
        reasons.append(f"+hyperlinks_found:{len(doc.hyperlinks)}")
    for note in quality.notes:
        reasons.append(f"-{note}")
        score = min(score, 0.7)
    return metadata, [Confidence(score=score, reasons=reasons)]


def _layout_reconstruction_enrich(doc) -> "tuple[dict[str, Any], list[Confidence]]":
    """Builds layout_reconstruction's StageTrace metadata/confidence from
    the DocumentModel it returned. See
    docs/architecture/ResumeIntelligenceEngine.md Section 4.2 and Section 6."""
    metadata = {
        "layout_mode": doc.layout_mode,
        "layout_confidence": doc.layout_confidence,
    }
    mode = doc.layout_mode or "single_column"
    if mode == "single_column":
        reasons = ["+single_column_default"]
    elif mode == "two_column":
        reasons = [f"+two_column_corroborated (confidence {doc.layout_confidence:.2f})"]
    else:
        reasons = ["-ambiguous_layout_across_pages"]
    return metadata, [Confidence(score=doc.layout_confidence, reasons=reasons)]


def _section_detection_enrich(sections: list[Section]) -> "tuple[dict[str, Any], list[Confidence]]":
    """Builds section_detection's StageTrace metadata/confidence from the
    list[Section] it returned -- run on the RAW list (before
    `_group_sections_by_label`'s merge), so a label detected more than once
    (e.g. cross-page continuation, Section 4.3) still shows up as one entry
    per raw header hit here, matching what SectionDetector.detect() itself
    reported. See docs/architecture/ResumeIntelligenceEngine.md Section 4.3
    and Section 6."""
    metadata = {
        "section_count": len(sections),
        "labels_found": [s.label for s in sections],
        "unknown_count": sum(1 for s in sections if s.label == "unknown"),
    }
    confidences = [
        Confidence(
            score=s.header_confidence,
            reasons=[f"{'-' if s.label == 'unknown' else '+'}{s.label}:{s.header_match_reason}"],
        )
        for s in sections
    ]
    return metadata, confidences


def _absorb_repeated_unknown_entries(sections: list[Section]) -> list[Section]:
    """Milestone 2/pipeline interaction fix, found during Milestone 3
    validation: `HeuristicSectionDetector` has no concept of "entry" -- a
    bold/larger line INSIDE a section (a job's "Company, Role" line, a
    project's title line) is structurally indistinguishable to it from a
    genuine new section boundary, and most such lines don't confidently
    match any canonical label, landing in `"unknown"`. Two signatures look
    identical at the classification level:
      - a genuine standalone ambiguous section (e.g. "Languages",
        `ambiguous_header_pdf`) -- a single, isolated "unknown" hit;
      - an unrecognized entry sub-header -- part of a REPEATING pattern:
        2+ consecutive "unknown" hits immediately following the same real
        section, one per entry.

    There is no reliable geometric signal to distinguish these from a
    single data point (confirmed: neither indentation nor confidence tier
    differs between the two cases), so this uses repetition instead: 2+
    consecutive `"unknown"` Sections immediately following a real
    (non-"unknown") section, with no other real section in between, are
    absorbed into that section rather than left as separate `"unknown"`
    entries. A single, isolated `"unknown"` is untouched -- `sections.py`
    itself (Milestone 2, frozen) is not modified; this is purely a
    consumption-side grouping decision, the same kind of fix already
    applied for the list/dict interface bridge below.

    Single-entry residual limitation narrowed (real-resume-audit fix): a
    single isolated "unknown" immediately after a real section IS now
    absorbed when that real section already contains its own bold body
    line -- i.e. the section has already established "bold line = a new
    entry" as ITS OWN convention (exactly how Projects/Experience entries
    are typically styled), so another same-style bold line right after it
    reads as one more entry of that convention, not a random new topic.
    `ambiguous_header_pdf`'s "Languages" case still correctly stays
    unabsorbed under this rule: that fixture's "Experience" entry line
    ("Acme Corp, Senior Engineer, 2021-Present") is NOT bold, so no such
    convention is established there, and "Languages" (bold) doesn't match
    it. Found via a real second-project-silently-dropped bug: a project
    title short enough to pass `sections.py`'s header word-count filter
    (<=6 words) but long enough to differ from the section's other entries
    was fragmenting into a standalone, never-consumed "unknown" Section --
    exactly this single-entry gap, now closed for the case where a
    same-convention signal genuinely exists. Still no signal exists to
    resolve the genuinely ambiguous case (a single unknown after a section
    with NO established bold-entry convention of its own) -- that stays
    unabsorbed, unchanged.

    This single-entry absorption is deliberately SCOPED to
    `_MULTI_ENTRY_ABSORPTION_LABELS` ("projects", "experience") only --
    the two sections `cluster_entries` (`_entry_clustering.py`) is actually
    designed around, and the two the architecture doc's own motivating
    examples name ("a job's Company,Role line, a project's title line").
    Found via a second real bug: "education" also uses `cluster_entries`
    (a person occasionally has 2+ degrees) and its own entries are
    routinely bold (e.g. a bold institution-name line), so
    `_has_bold_body_line` was true there too -- absorbing an unrelated
    single trailing "unknown" (a pre-university schooling aside, styled
    with its own bold line but containing no recognizable degree/
    institution/major/year) as a phantom second Education entry that
    `EducationParser` had no way to extract anything from, surfacing as an
    empty entity (`candidate_profile_mapper` then serialized it into the
    frontend as raw, unrendered JSON -- see `EducationParser`'s own
    empty-entry guard, which is the second, independent layer of defense
    for this same failure mode). Certifications also never hits this path
    -- it doesn't use `cluster_entries` at all (single-line entries, no
    multi-entry clustering to protect). Not scoped by a resume-specific
    check (no text/keyword matching on "National Centre for Excellence" or
    any other literal) -- scoped by section LABEL, the same generic,
    label-based distinction every other rule in this function already uses.

    A run never includes an unknown section whose header line was
    font-elevated (`Section.header_font_elevated`, sections.py) -- that's
    the same visual weight every confidently-labeled section header in the
    document carries, so it's a genuine (if gazetteer-unrecognized) section
    boundary, not a same-size bold sub-entry label. Found during resume-
    intelligence-quality validation: a real "Honors & Awards" section (no
    gazetteer alias yet) landing right after a run of same-size bold skills
    category labels ("Frontend:", "Backend:", ...) was being swept into the
    Skills section along with them, contaminating it with unrelated prose.
    A font-elevated unknown section is therefore treated like a real
    section for run purposes: it ends any run in progress and is never
    itself absorbed."""
    result: list[Section] = []
    i = 0
    while i < len(sections):
        section = sections[i]
        if (
            section.label != "unknown"
            or section.header_font_elevated
            or not result
            or result[-1].label == "unknown"
        ):
            result.append(section)
            i += 1
            continue

        run_start = i
        while i < len(sections) and sections[i].label == "unknown" and not sections[i].header_font_elevated:
            i += 1
        run = sections[run_start:i]

        single_entry_absorbable = (
            len(run) == 1
            and result[-1].label in _MULTI_ENTRY_ABSORPTION_LABELS
            and _has_bold_body_line(result[-1])
        )
        if len(run) >= 2 or single_entry_absorbable:
            for unknown_section in run:
                result[-1].spans.extend(unknown_section.spans)
        else:
            result.extend(run)

    return result


def _has_bold_body_line(section: Section) -> bool:
    """True if `section` already has at least one bold line in its own
    body, excluding the header line itself -- the signal
    `_absorb_repeated_unknown_entries` uses to tell "this section already
    styles its own entries in bold, so a same-style single unknown right
    after it is another entry" apart from "no such convention exists here,
    so an isolated unknown is a genuinely separate topic" (see that
    function's docstring). Local, self-contained line-grouping -- the same
    accepted duplication `sections.py`/`_entry_clustering.py` each already
    have their own copy of, not a shared import across those layer
    boundaries. Defensively returns False (the pre-existing, safe default)
    for spans that don't carry real layout attributes -- e.g. the plain
    string/object stand-ins some unit tests build directly."""
    groups: list[list] = []
    for span in section.spans:
        try:
            if groups:
                last = groups[-1][-1]
                same_block = span.page_num == last.page_num and span.column_index == last.column_index
                if same_block and abs(span.bbox[1] - last.bbox[1]) <= 3.0:
                    groups[-1].append(span)
                    continue
            groups.append([span])
        except AttributeError:
            return False

    for line_spans in groups[1:]:  # [0] is the section's own header line
        try:
            line_text = " ".join(s.text for s in line_spans).strip()
            if line_text and line_text != section.raw_header_text and any(s.is_bold for s in line_spans):
                return True
        except AttributeError:
            return False
    return False


def _group_sections_by_label(sections: list[Section]) -> dict[str, Section]:
    """Bridges `SectionDetector.detect()`'s declared `list[Section]` return
    type to `ParserRunner.run_all()`'s declared `dict[str, Section]`
    parameter type -- both interfaces are individually correct (the
    detector's list preserves every raw header hit for explainability; the
    parser runner wants one bucket per canonical label), so this small
    grouping step is the pipeline's job to bridge them, not a reason to
    change either interface. Concatenating spans for a label detected more
    than once is also the entire mechanism for cross-page/column
    continuation (Section 4.3, Section 5 of the milestone plan): a header
    re-appearing (or, per sections.py's own walk, content simply
    continuing under one open section across a page break) naturally
    produces one dict entry either way. The first-detected Section's
    `header_confidence`/`header_match_reason`/`raw_header_text` win when a
    label repeats -- consistent with the cascade's own "first confident
    match wins" philosophy (architecture doc Section 4.3)."""
    grouped: dict[str, Section] = {}
    for section in sections:
        if section.label in grouped:
            grouped[section.label].spans.extend(section.spans)
        else:
            grouped[section.label] = section
    return grouped


@dataclass
class ResumePipeline:
    """Orchestrates the eight-stage Resume Intelligence Engine pipeline.
    Every collaborator is an interface (resume_engine.interfaces); this
    class never constructs or imports a concrete implementation itself."""

    extractor: DocumentExtractor
    layout_reconstructor: LayoutReconstructor
    section_detector: SectionDetector
    parser_runner: ParserRunner
    cross_reference_engine: CrossReferenceEngine
    normalizer: Normalizer
    validation_engine: ValidationEngine
    confidence_engine: ConfidenceEngine

    def run(
        self,
        file_path: str,
        source_format: str,
        trace: PipelineTrace | None = None,
    ) -> AnnotatedCandidateProfile:
        """Runs all eight stages in order and returns the final annotated
        profile. Threads `trace` through every stage so a caller can
        inspect every intermediate representation (architecture doc
        Section 6) without affecting behavior when `trace` is None (the
        production default)."""
        doc = self._timed(
            "document_extraction",
            trace,
            self.extractor.extract,
            file_path,
            source_format,
            trace=trace,
            enrich=_document_extraction_enrich,
        )
        doc = self._timed(
            "layout_reconstruction",
            trace,
            self.layout_reconstructor.reconstruct,
            doc,
            trace=trace,
            enrich=_layout_reconstruction_enrich,
        )
        sections = self._timed(
            "section_detection",
            trace,
            self.section_detector.detect,
            doc,
            trace=trace,
            enrich=_section_detection_enrich,
        )
        sections = _absorb_repeated_unknown_entries(sections)
        sections_by_label = _group_sections_by_label(sections)
        parser_results = self._timed(
            "entity_parsing", trace, self.parser_runner.run_all, sections_by_label, doc, trace=trace
        )
        parser_results = self._timed(
            "cross_reference", trace, self.cross_reference_engine.cross_reference, parser_results, trace=trace
        )
        parser_results = self._timed(
            "normalization", trace, self.normalizer.normalize, parser_results, trace=trace
        )
        observations = self._timed(
            "validation", trace, self.validation_engine.validate, parser_results, trace=trace
        )
        annotated_profile = self._timed(
            "confidence_scoring",
            trace,
            self.confidence_engine.score,
            parser_results,
            observations,
            trace=trace,
        )
        return annotated_profile

    @staticmethod
    def _timed(
        stage_name: str,
        pipeline_trace: PipelineTrace | None,
        fn,
        *args,
        enrich: EnrichFn | None = None,
        **kwargs,
    ):
        """Calls `fn`, and when `pipeline_trace` is active, records a
        StageTrace with the wall-clock duration — this is what gives every
        stage's timing (architecture doc Section 6.3) without each stage
        having to implement its own timing code. Named `pipeline_trace`
        rather than `trace` specifically so it never collides with the
        `trace=` keyword argument being forwarded to `fn` via `**kwargs`.

        `enrich`, when given, is called with the stage's return value to
        produce `(metadata, confidences)` for the StageTrace — this is what
        lets document_extraction/layout_reconstruction (Milestone 1) report
        real signals instead of a bare timing line, without requiring every
        stage's Protocol signature (interfaces.py) to change. `enrich`
        itself is never forwarded to `fn`."""
        if pipeline_trace is None:
            return fn(*args, **kwargs)
        started_at = time.perf_counter()
        result = fn(*args, **kwargs)
        duration_ms = (time.perf_counter() - started_at) * 1000
        metadata: dict[str, Any] = {}
        confidences: list[Confidence] = []
        if enrich is not None:
            metadata, confidences = enrich(result)
        pipeline_trace.record(
            StageTrace(
                stage_name=stage_name,
                metadata=metadata,
                confidences=confidences,
                started_at=started_at,
                duration_ms=duration_ms,
            )
        )
        return result
