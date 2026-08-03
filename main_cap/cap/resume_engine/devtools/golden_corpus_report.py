"""
Milestone 1 + 2 + 3 validation-pass report generator -- NOT a pytest test.

Runs the real PdfDocxExtractor + ColumnAwareLayoutReconstructor +
HeuristicSectionDetector + (post pipeline.py's section-merge/absorption
logic) ContactParser/ExperienceParser/ProjectParser across every fixture in
resume_engine/tests/golden_corpus/ and prints a structured summary of
extraction quality, hyperlink capture, layout mode/confidence, reading-order
sanity, section labels/confidence, and entity-parsing counts, flagging every
failure or low-confidence result explicitly rather than silently
passing/failing a binary assertion.

This is dev tooling for a point-in-time validation pass (see
docs/architecture/Milestone1_ValidationReport.md /
Milestone2_ValidationReport.md for the write-ups this script's output fed),
not a permanent regression gate -- the permanent gate is
resume_engine/tests/test_golden_corpus_extraction.py.

Usage (from main_cap/cap/):
    python -m resume_engine.devtools.golden_corpus_report
"""

from __future__ import annotations

import json
from pathlib import Path

from resume_engine.extractor import ExtractionFailure, PdfDocxExtractor
from resume_engine.layout import ColumnAwareLayoutReconstructor
from resume_engine.parsers.contact_parser import ContactParser
from resume_engine.parsers.experience_parser import ExperienceParser
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.pipeline import _absorb_repeated_unknown_entries, _group_sections_by_label
from resume_engine.sections import HeuristicSectionDetector

GOLDEN_CORPUS_DIR = Path(__file__).parent.parent / "tests" / "golden_corpus"

# Inclusive: 0.6 is the algorithm's own minimum "just barely corroborated"
# two_column confidence (layout.py's confidence formula floors there), so a
# fixture landing exactly on it is a borderline call worth surfacing, not
# a clean pass.
LOW_CONFIDENCE_THRESHOLD = 0.6


def _discover_fixtures() -> list[Path]:
    return sorted(p.parent for p in GOLDEN_CORPUS_DIR.glob("*/metadata.json"))


def _resume_file(fixture_dir: Path, document_type: str) -> Path:
    extension = "pdf" if document_type == "pdf" else "docx"
    return fixture_dir / f"resume.{extension}"


def _is_reading_order_monotonic(doc) -> bool:
    """Cheap, format-agnostic reading-order sanity check: within each
    column of each page, y0 should be non-decreasing. This catches a
    scrambled reorder even without a hand-verified expected order."""
    seen: dict[tuple[int, int], float] = {}
    for span in doc.spans:
        key = (span.page_num, span.column_index)
        prev_y = seen.get(key)
        if prev_y is not None and span.bbox[1] < prev_y - 0.5:
            return False
        seen[key] = span.bbox[1]
    return True


def _max_same_y_column_split(doc) -> int:
    """Counts, per page, how many distinct y0 values (rounded to a whole
    point) have spans assigned to MORE THAN ONE column_index -- i.e. one
    printed line whose spans got pulled apart into different columns. This
    is what monotonicity checking above can't see: each column stays
    internally sorted even when a same-line span (a right-aligned date, an
    icon) has been wrongly split away from the rest of its line. Returns
    the count of such split lines across the whole document."""
    by_page_y: dict[tuple[int, int], set[int]] = {}
    for span in doc.spans:
        key = (span.page_num, round(span.bbox[1]))
        by_page_y.setdefault(key, set()).add(span.column_index)
    return sum(1 for columns in by_page_y.values() if len(columns) > 1)


def run_report() -> list[dict]:
    extractor = PdfDocxExtractor()
    layout = ColumnAwareLayoutReconstructor()
    section_detector = HeuristicSectionDetector()
    rows: list[dict] = []

    for fixture_dir in _discover_fixtures():
        metadata = json.loads((fixture_dir / "metadata.json").read_text())
        fixture_id = metadata["fixture_id"]
        resume_path = _resume_file(fixture_dir, metadata["document_type"])

        row = {
            "fixture_id": fixture_id,
            "template_style": metadata.get("template_style", "-"),
            "document_type": metadata["document_type"],
        }

        if metadata.get("expects_extraction_failure"):
            try:
                extractor.extract(str(resume_path), metadata["document_type"])
                row["result"] = "UNEXPECTED_SUCCESS"
                row["flag"] = "FAILURE: expected ExtractionFailure but extraction succeeded"
            except ExtractionFailure as exc:
                row["result"] = "EXTRACTION_FAILURE (expected)"
                row["flag"] = None
                row["failure_message"] = str(exc)
            rows.append(row)
            continue

        try:
            doc = extractor.extract(str(resume_path), metadata["document_type"])
        except ExtractionFailure as exc:
            row["result"] = "UNEXPECTED_EXTRACTION_FAILURE"
            row["flag"] = f"FAILURE: unexpected ExtractionFailure: {exc}"
            rows.append(row)
            continue

        doc = layout.reconstruct(doc)

        row["chars_extracted"] = doc.extraction_quality.chars_extracted
        row["span_count"] = doc.extraction_quality.span_count
        row["hyperlink_count"] = len(doc.hyperlinks)
        row["page_count"] = doc.page_count
        row["layout_mode"] = doc.layout_mode
        row["layout_confidence"] = round(doc.layout_confidence, 2)
        row["extraction_notes"] = doc.extraction_quality.notes
        row["reading_order_monotonic"] = _is_reading_order_monotonic(doc)
        # Reported, not auto-flagged: this metric can't by itself distinguish
        # a genuine defect (a right-aligned date pulled off its own line into
        # a phantom column) from completely normal two-column content (a
        # sidebar row and a main-column row that happen to render at the
        # same height, which is routine and correct). Whether a given
        # fixture's count is a problem is a per-fixture judgment call, made
        # in docs/architecture/Milestone1_ValidationReport.md by comparing
        # against that fixture's documented expected classification -- not
        # something this script can decide on its own.
        row["same_line_column_splits"] = _max_same_y_column_split(doc)

        sections = section_detector.detect(doc)
        row["section_labels"] = ",".join(s.label for s in sections)
        row["section_count"] = len(sections)
        row["unknown_section_count"] = sum(1 for s in sections if s.label == "unknown")
        row["min_section_confidence"] = round(min((s.header_confidence for s in sections), default=0.0), 2)

        # Post pipeline.py's absorption/merge logic -- what the M3 parsers
        # actually see, not the raw per-header hits above.
        merged = _group_sections_by_label(_absorb_repeated_unknown_entries(sections))
        row["contact_count"] = len(ContactParser().parse(merged, doc).entities)
        row["experience_count"] = len(ExperienceParser().parse(merged, doc).entities)
        row["projects_count"] = len(ProjectParser().parse(merged, doc).entities)

        flags = []
        if doc.layout_confidence <= LOW_CONFIDENCE_THRESHOLD and doc.layout_mode != "single_column":
            flags.append(f"LOW_CONFIDENCE layout ({doc.layout_confidence:.2f}, mode={doc.layout_mode})")
        if doc.layout_mode == "ambiguous":
            flags.append("AMBIGUOUS layout classification")
        if not row["reading_order_monotonic"]:
            flags.append("READING_ORDER not monotonic within a column")
        if doc.extraction_quality.chars_extracted < 150:
            flags.append(f"SPARSE extraction ({doc.extraction_quality.chars_extracted} chars)")
        if row["section_count"] == 0:
            flags.append("NO_SECTIONS detected at all")
        if row["unknown_section_count"] > 1:
            flags.append(f"MULTIPLE unknown sections ({row['unknown_section_count']})")
        if "experience" in merged and row["experience_count"] == 0:
            flags.append("EXPERIENCE section detected but zero entries parsed")
        if "projects" in merged and row["projects_count"] == 0:
            flags.append("PROJECTS section detected but zero entries parsed")

        row["result"] = "OK" if not flags else "FLAGGED"
        row["flag"] = "; ".join(flags) if flags else None
        rows.append(row)

    return rows


def print_report(rows: list[dict]) -> None:
    header = (
        f"{'fixture_id':<32} {'style':<16} {'type':<5} {'chars':>6} {'spans':>6} "
        f"{'links':>5} {'pages':>5} {'layout_mode':<14} {'conf':>5} {'same_y':>7}  result"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        if row["result"].startswith(("EXTRACTION_FAILURE", "UNEXPECTED")):
            print(
                f"{row['fixture_id']:<32} {row['template_style']:<16} {row['document_type']:<5} "
                f"{'--':>6} {'--':>6} {'--':>5} {'--':>5} {'--':<14} {'--':>5} {'--':>7}  {row['result']}"
            )
        else:
            print(
                f"{row['fixture_id']:<32} {row['template_style']:<16} {row['document_type']:<5} "
                f"{row['chars_extracted']:>6} {row['span_count']:>6} {row['hyperlink_count']:>5} "
                f"{row['page_count']:>5} {row['layout_mode']:<14} {row['layout_confidence']:>5} "
                f"{row['same_line_column_splits']:>7}  {row['result']}"
            )

    print()
    section_header = (
        f"{'fixture_id':<32} {'sections':>8} {'unknown':>7} {'min_conf':>8}  labels"
    )
    print("Section Detection:")
    print(section_header)
    print("-" * len(section_header))
    for row in rows:
        if row["result"].startswith(("EXTRACTION_FAILURE", "UNEXPECTED")):
            continue
        print(
            f"{row['fixture_id']:<32} {row['section_count']:>8} {row['unknown_section_count']:>7} "
            f"{row['min_section_confidence']:>8}  {row['section_labels']}"
        )

    print()
    entity_header = f"{'fixture_id':<32} {'contact':>7} {'experience':>10} {'projects':>8}"
    print("Entity Parsing (Milestone 3):")
    print(entity_header)
    print("-" * len(entity_header))
    for row in rows:
        if row["result"].startswith(("EXTRACTION_FAILURE", "UNEXPECTED")):
            continue
        print(
            f"{row['fixture_id']:<32} {row['contact_count']:>7} {row['experience_count']:>10} "
            f"{row['projects_count']:>8}"
        )

    print()
    print("Flagged fixtures:")
    flagged = [r for r in rows if r.get("flag")]
    if not flagged:
        print("  (none)")
    for row in flagged:
        print(f"  - {row['fixture_id']}: {row['flag']}")

    print()
    print(f"Total fixtures: {len(rows)}, flagged: {len(flagged)}")


if __name__ == "__main__":
    print_report(run_report())
