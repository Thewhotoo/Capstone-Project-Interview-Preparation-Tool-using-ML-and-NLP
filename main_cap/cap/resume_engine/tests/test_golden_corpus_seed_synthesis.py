"""Golden Corpus regression + acceptance-criteria checks for Milestone 4
(Interview Seed Synthesis). See docs/architecture/Milestone4_Design.md
Section 8 (Evaluation Strategy) and
resume_engine/tests/golden_corpus/seed_synthesis_fixtures/projects.json.

Two fixture sources, per the design's evaluation strategy:
  1. Real-document fixtures (`full_entity_resume_pdf`) run through the
     actual, frozen M1-3 pipeline stages plus the new Cross-Reference
     stage -- the true end-to-end regression gate.
  2. Hand-authored project-evidence fixtures spanning the zero/sparse/
     moderate/rich evidence profiles from Section 8.4, run directly
     against `synthesize_seeds` -- these are what make Section 8's
     acceptance criteria (hallucination-freedom, dedup, explainable
     unused evidence) checkable across a deliberately broader spread of
     evidence shapes than any single resume PDF would exercise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resume_engine.cross_reference import DefaultCrossReferenceEngine
from resume_engine.extractor import PdfDocxExtractor
from resume_engine.interfaces import ParserResult
from resume_engine.layout import ColumnAwareLayoutReconstructor
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.pipeline import _absorb_repeated_unknown_entries, _group_sections_by_label
from resume_engine.sections import HeuristicSectionDetector
from resume_engine.seed_synthesis import synthesize_seeds

GOLDEN_CORPUS_DIR = Path(__file__).parent / "golden_corpus"
FIXTURES_PATH = Path(__file__).parent / "golden_corpus" / "seed_synthesis_fixtures" / "projects.json"

_VALID_UNUSED_REASON_PREFIXES = (
    "below_cap:",
    "duplicate_of:",
    "precondition_not_met:",
    "lower_priority_unselected",
)


def _load_fixtures() -> list[dict]:
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


FIXTURES = _load_fixtures()


# ── Real-document golden gate: full_entity_resume_pdf through the actual
#    frozen pipeline stages + the new Cross-Reference stage ─────────────


def test_full_entity_resume_pdf_interview_seeds_match_golden_snapshot():
    fixture_dir = GOLDEN_CORPUS_DIR / "full_entity_resume_pdf"
    expected = json.loads((fixture_dir / "expected_interview_seeds.json").read_text(encoding="utf-8"))

    doc = PdfDocxExtractor().extract(str(fixture_dir / "resume.pdf"), "pdf")
    doc = ColumnAwareLayoutReconstructor().reconstruct(doc)
    raw_sections = _absorb_repeated_unknown_entries(HeuristicSectionDetector().detect(doc))
    sections = _group_sections_by_label(raw_sections)

    project_result = ProjectParser().parse(sections, doc)
    parser_results = {"projects": project_result}
    DefaultCrossReferenceEngine().cross_reference(parser_results)

    actual = {e["title"]: e["interview_seeds"] for e in parser_results["projects"].entities}
    assert actual == expected


# ── Hand-authored evidence-profile fixtures ──────────────────────────────


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fx: fx["id"])
def test_fixture_seeds_match_golden_snapshot(fixture: dict):
    result = synthesize_seeds(fixture["project"], want_accounting=True)
    assert result.seeds == fixture["expected_seeds"], fixture["notes"]


@pytest.mark.parametrize(
    "fixture", [fx for fx in FIXTURES if fx["evidence_profile"] == "zero"], ids=lambda fx: fx["id"]
)
def test_zero_evidence_fixtures_produce_no_seeds(fixture: dict):
    """Objective acceptance criterion (Section 8.7 #4): every zero-evidence
    fixture produces exactly [], with no exceptions."""
    result = synthesize_seeds(fixture["project"])
    assert result.seeds == []


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fx: fx["id"])
def test_no_hallucinated_evidence(fixture: dict):
    """Objective acceptance criterion (Section 8.6 #1): consumed ⊆
    discovered for every project, every fixture."""
    result = synthesize_seeds(fixture["project"], want_accounting=True)
    discovered_keys = {(item.kind, item.value) for item in result.accounting.discovered}
    for seed_text, evidence in result.accounting.consumed.items():
        for item in evidence:
            assert (item.kind, item.value) in discovered_keys, (
                f"seed {seed_text!r} cites unlisted evidence {item!r}"
            )


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fx: fx["id"])
def test_no_duplicate_evidence_consumption(fixture: dict):
    """Objective acceptance criterion (Section 8.6 #2): no single
    EvidenceItem appears in more than one seed's consumed entry."""
    result = synthesize_seeds(fixture["project"], want_accounting=True)
    seen: set[tuple[str, str]] = set()
    for evidence in result.accounting.consumed.values():
        for item in evidence:
            key = (item.kind, item.value)
            assert key not in seen, f"{key} consumed by more than one seed"
            seen.add(key)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fx: fx["id"])
def test_every_unused_evidence_item_is_explainable(fixture: dict):
    """Objective acceptance criterion (Section 8.6 #4): 100% of unused
    items carry one of the four closed-vocabulary reason codes."""
    result = synthesize_seeds(fixture["project"], want_accounting=True)
    for unused_item in result.accounting.unused:
        assert unused_item.reason.startswith(_VALID_UNUSED_REASON_PREFIXES), (
            f"unexplained unused evidence: {unused_item!r}"
        )


def test_false_tradeoff_fixtures_never_produce_a_tradeoff_seed():
    """Objective acceptance criterion (Section 8.7 #5): the tradeoff-probe
    family never fires without a literal comparison-pattern match AND two
    nearby technologies -- both deliberately-adversarial fixtures must
    produce zero seeds containing the tradeoff phrasing."""
    for fixture in FIXTURES:
        if not fixture["id"].startswith("false_tradeoff"):
            continue
        result = synthesize_seeds(fixture["project"])
        assert not any("over the alternative" in seed for seed in result.seeds), fixture["id"]


def test_rich_fixtures_fully_utilize_metrics_and_comparisons():
    """Objective acceptance criterion (Section 8.6 #3): metrics and
    comparison phrases reach 100% utilization when their preconditions
    are met -- checked across every 'rich' fixture with such evidence."""
    for fixture in FIXTURES:
        if fixture["evidence_profile"] != "rich":
            continue
        result = synthesize_seeds(fixture["project"], want_accounting=True)
        for unused_item in result.accounting.unused:
            assert unused_item.item.kind not in ("metric",), (
                f"{fixture['id']}: metric left unused unexpectedly: {unused_item!r}"
            )


def test_evidence_profiles_cover_the_expected_spread():
    """Sanity check on fixture-set composition against Section 8.7 #2's
    minimums: 2+ zero, 2+ sparse, 3+ moderate, 3+ rich."""
    counts: dict[str, int] = {}
    for fixture in FIXTURES:
        counts[fixture["evidence_profile"]] = counts.get(fixture["evidence_profile"], 0) + 1
    assert counts.get("zero", 0) >= 2
    assert counts.get("sparse", 0) >= 2
    assert counts.get("moderate", 0) >= 3
    assert counts.get("rich", 0) >= 3
