"""Golden-corpus regression tests for Milestone 1 (Document Extraction +
Layout Reconstruction) and Milestone 2 (Section Detection). See
resume_engine/tests/golden_corpus/README.md for the fixture format and
docs/architecture/ResumeIntelligenceEngine.md Section 9 for the testing
strategy this corpus implements.

Every fixture directory under golden_corpus/ with a `metadata.json` is
picked up automatically -- adding a new fixture directory in a later
milestone requires no change to this file."""

import json
from pathlib import Path

import pytest

from resume_engine.extractor import ExtractionFailure, PdfDocxExtractor
from resume_engine.layout import ColumnAwareLayoutReconstructor
from resume_engine.pipeline import _absorb_repeated_unknown_entries, _group_sections_by_label
from resume_engine.parsers.contact_parser import ContactParser
from resume_engine.parsers.experience_parser import ExperienceParser
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.sections import HeuristicSectionDetector

GOLDEN_CORPUS_DIR = Path(__file__).parent / "golden_corpus"


def _discover_fixtures() -> list[Path]:
    return sorted(p.parent for p in GOLDEN_CORPUS_DIR.glob("*/metadata.json"))


FIXTURE_DIRS = _discover_fixtures()


def _resume_file(fixture_dir: Path, document_type: str) -> Path:
    extension = "pdf" if document_type == "pdf" else "docx"
    return fixture_dir / f"resume.{extension}"


def _check_layout(fixture_dir: Path, doc) -> None:
    expected = json.loads((fixture_dir / "expected_layout.json").read_text())

    assert doc.layout_mode == expected["layout_mode"]
    assert doc.layout_confidence >= expected["layout_confidence_min"]
    assert doc.extraction_quality.span_count >= expected["span_count_min"]
    assert len(doc.hyperlinks) == expected["hyperlink_count"]

    if "extraction_notes_contains" in expected:
        assert expected["extraction_notes_contains"] in doc.extraction_quality.notes

    if "expected_span_order_contains" in expected:
        texts = [s.text for s in doc.spans]
        expected_subsequence = expected["expected_span_order_contains"]
        indices = [texts.index(t) for t in expected_subsequence]
        assert indices == sorted(indices), (
            f"expected {expected_subsequence!r} to appear in this order in {texts!r}"
        )


def _check_sections(fixture_dir: Path, doc) -> None:
    expected = json.loads((fixture_dir / "expected_sections.json").read_text())
    sections = HeuristicSectionDetector().detect(doc)
    by_label = {s.label: s for s in sections}

    assert [s.label for s in sections] == expected["expected_labels_in_order"]

    for label, min_conf in expected.get("min_confidence_by_label", {}).items():
        assert by_label[label].header_confidence >= min_conf, (
            f"{label}: expected confidence >= {min_conf}, got {by_label[label].header_confidence}"
        )
    for label, max_conf in expected.get("max_confidence_by_label", {}).items():
        assert by_label[label].header_confidence <= max_conf, (
            f"{label}: expected confidence <= {max_conf}, got {by_label[label].header_confidence}"
        )
    for label, substring in expected.get("reason_must_contain", {}).items():
        assert substring in by_label[label].header_match_reason
    for label in expected.get("labels_must_be_absent", []):
        assert label not in by_label


def _check_entities(fixture_dir: Path, doc) -> None:
    expected = json.loads((fixture_dir / "expected_entities.json").read_text())

    raw_sections = _absorb_repeated_unknown_entries(HeuristicSectionDetector().detect(doc))
    sections = _group_sections_by_label(raw_sections)

    if "contact" in expected:
        result = ContactParser().parse(sections, doc)
        assert len(result.entities) == expected["contact"]["entity_count"]
        if result.entities:
            for field, value in expected["contact"].get("expected_fields", {}).items():
                assert result.entities[0][field] == value

    if "experience" in expected:
        result = ExperienceParser().parse(sections, doc)
        assert len(result.entities) == expected["experience"]["entity_count"]
        if "expected_roles" in expected["experience"]:
            assert [e["role"] for e in result.entities] == expected["experience"]["expected_roles"]
        if "expected_companies" in expected["experience"]:
            assert [e["company"] for e in result.entities] == expected["experience"]["expected_companies"]

    if "projects" in expected:
        result = ProjectParser().parse(sections, doc)
        assert len(result.entities) == expected["projects"]["entity_count"]
        if "expected_titles" in expected["projects"]:
            assert [e["title"] for e in result.entities] == expected["projects"]["expected_titles"]
        for title, techs in expected["projects"].get("technologies_contains", {}).items():
            entity = next(e for e in result.entities if e["title"] == title)
            for tech in techs:
                assert tech in entity["technologies"]


@pytest.mark.parametrize("fixture_dir", FIXTURE_DIRS, ids=lambda p: p.name)
def test_golden_corpus_fixture(fixture_dir: Path):
    metadata = json.loads((fixture_dir / "metadata.json").read_text())
    resume_path = _resume_file(fixture_dir, metadata["document_type"])
    extractor = PdfDocxExtractor()

    if metadata.get("expects_extraction_failure"):
        with pytest.raises(ExtractionFailure):
            extractor.extract(str(resume_path), metadata["document_type"])
        return

    has_layout_expectation = (fixture_dir / "expected_layout.json").exists()
    has_sections_expectation = (fixture_dir / "expected_sections.json").exists()
    has_entities_expectation = (fixture_dir / "expected_entities.json").exists()

    doc = extractor.extract(str(resume_path), metadata["document_type"])
    doc = ColumnAwareLayoutReconstructor().reconstruct(doc)

    if not has_layout_expectation and not has_sections_expectation and not has_entities_expectation:
        # Validation-pass fixtures (diverse real-world template styles,
        # some deliberately probing known limitations -- see
        # docs/architecture/Milestone1_ValidationReport.md) intentionally
        # have no hand-verified expectations yet: their purpose is
        # exploratory reporting (resume_engine/devtools/golden_corpus_report.py),
        # not a hard regression gate. Smoke-only here: must not crash.
        return

    if has_layout_expectation:
        _check_layout(fixture_dir, doc)
    if has_sections_expectation:
        _check_sections(fixture_dir, doc)
    if has_entities_expectation:
        _check_entities(fixture_dir, doc)


def test_golden_corpus_has_at_least_the_milestone_1_minimum_fixtures():
    fixture_ids = {p.name for p in FIXTURE_DIRS}
    required = {
        "single_column_pdf",
        "two_column_sidebar_pdf",
        "docx_plain_paragraphs",
        "docx_table_sidebar",
        "hyperlinked_contact_icons_pdf",
        "nested_bullets_pdf",
        "ragged_single_column_pdf",
        "scanned_image_only_pdf",
        "corrupt_pdf",
        "corrupt_or_password_docx",
    }
    assert required.issubset(fixture_ids)


def test_golden_corpus_has_at_least_the_milestone_2_minimum_fixtures():
    fixture_ids = {p.name for p in FIXTURE_DIRS}
    required = {
        "every_section_pdf",
        "missing_sections_pdf",
        "nonstandard_headers_pdf",
        "ambiguous_header_pdf",
        "docx_heading_styles",
        "repeated_running_header_pdf",
        "creative_header_sbert_pdf",
    }
    assert required.issubset(fixture_ids)


def test_golden_corpus_has_at_least_the_milestone_3_minimum_fixtures():
    fixture_ids = {p.name for p in FIXTURE_DIRS}
    required = {"full_entity_resume_pdf", "single_entry_sections_pdf"}
    assert required.issubset(fixture_ids)
