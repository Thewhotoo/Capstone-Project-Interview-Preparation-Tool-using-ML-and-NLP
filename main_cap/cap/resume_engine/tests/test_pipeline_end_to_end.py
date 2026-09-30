"""End-to-end pipeline regression test — Milestone 6 makes this possible
for the first time (all 8 stages now have real implementations). See
docs/architecture/Milestone6_ValidationReport.md."""

from __future__ import annotations

from pathlib import Path

from resume_engine.factory import default_pipeline
from resume_engine.pipeline_trace import PipelineTrace

GOLDEN_CORPUS_DIR = Path(__file__).parent / "golden_corpus"


def test_default_pipeline_runs_all_eight_stages_without_error():
    pipeline = default_pipeline()
    resume_path = GOLDEN_CORPUS_DIR / "full_entity_resume_pdf" / "resume.pdf"

    profile = pipeline.run(str(resume_path), "pdf")

    assert profile.overall_confidence.score > 0.0
    assert profile.overall_confidence.reasons
    assert isinstance(profile.observations, list)
    assert "projects" in profile.parser_results
    assert len(profile.parser_results["projects"].entities) == 2


def test_default_pipeline_run_with_trace_records_every_stage():
    pipeline = default_pipeline()
    resume_path = GOLDEN_CORPUS_DIR / "full_entity_resume_pdf" / "resume.pdf"
    trace = PipelineTrace(document_id="full_entity_resume_pdf")

    pipeline.run(str(resume_path), "pdf", trace=trace)

    stage_names = [s.stage_name for s in trace.stages]
    for expected in (
        "document_extraction",
        "layout_reconstruction",
        "section_detection",
        "entity_parsing",
        "cross_reference",
        "normalization",
        "validation",
        "confidence_scoring",
    ):
        assert expected in stage_names


def test_pipeline_output_has_no_none_values_anywhere_in_entities():
    """Section 1.3's hard convention, checked end-to-end for the first
    time: empty string / empty list as the missing-value sentinel, never
    None, across every stage's mutation of the entities."""
    pipeline = default_pipeline()
    resume_path = GOLDEN_CORPUS_DIR / "full_entity_resume_pdf" / "resume.pdf"

    profile = pipeline.run(str(resume_path), "pdf")

    for result in profile.parser_results.values():
        for entity in result.entities:
            if isinstance(entity, dict):
                for value in entity.values():
                    assert value is not None
