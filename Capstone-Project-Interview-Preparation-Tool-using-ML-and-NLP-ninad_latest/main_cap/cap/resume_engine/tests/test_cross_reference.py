"""Tests for the Cross-Reference stage's Milestone 4 responsibility:
wiring `seed_synthesis.py` into the pipeline. See
docs/architecture/Milestone4_Design.md Section 6."""

from __future__ import annotations

from resume_engine.cross_reference import DefaultCrossReferenceEngine
from resume_engine.interfaces import ParserResult
from resume_engine.confidence import Confidence
from resume_engine.pipeline_trace import PipelineTrace


def _project_result(*projects: dict) -> ParserResult:
    return ParserResult(
        entities=list(projects),
        confidences=[Confidence(score=0.8, reasons=["+ok"]) for _ in projects],
        observations=[],
    )


def test_cross_reference_populates_interview_seeds_on_each_project():
    parser_results = {
        "projects": _project_result(
            {"title": "X", "summary": "", "technologies": ["Redis"], "concepts": [], "interview_seeds": []}
        )
    }
    result = DefaultCrossReferenceEngine().cross_reference(parser_results)
    assert result["projects"].entities[0]["interview_seeds"] == [
        "Why did you use Redis in this project?"
    ]


def test_cross_reference_no_op_when_no_projects_key():
    parser_results = {"experience": _project_result()}
    result = DefaultCrossReferenceEngine().cross_reference(parser_results)
    assert result is parser_results


def test_cross_reference_no_op_when_projects_empty():
    parser_results = {"projects": _project_result()}
    result = DefaultCrossReferenceEngine().cross_reference(parser_results)
    assert result["projects"].entities == []


def test_cross_reference_does_not_touch_trace_when_none():
    parser_results = {
        "projects": _project_result({"title": "X", "summary": "", "technologies": ["Go"], "concepts": []})
    }
    # No trace passed -- must not raise, must not require a trace object.
    DefaultCrossReferenceEngine().cross_reference(parser_results, trace=None)


def test_cross_reference_records_stage_trace_with_evidence_accounting_when_tracing():
    parser_results = {
        "projects": _project_result(
            {
                "title": "X",
                "summary": "",
                "technologies": ["Python", "Redis", "Docker"],
                "concepts": ["Caching"],
            }
        )
    }
    trace = PipelineTrace(document_id="doc-1")
    DefaultCrossReferenceEngine().cross_reference(parser_results, trace=trace)

    stages_by_name = {s.stage_name: s for s in trace.stages}
    assert "cross_reference:seed_synthesis" in stages_by_name
    assert "cross_reference:demonstrated_skills" in stages_by_name
    stage = stages_by_name["cross_reference:seed_synthesis"]
    assert "evidence_accounting" in stage.metadata
    accounting_records = stage.metadata["evidence_accounting"]
    assert len(accounting_records) == 1
    assert accounting_records[0]["project_title"] == "X"
    assert accounting_records[0]["discovered"]  # non-empty
    assert stage.confidences  # per-seed confidences retained on the trace


def test_evidence_accounting_never_reaches_the_public_project_dict():
    """Hard boundary from Design doc Section 8.6: Evidence Accounting must
    never leak into CandidateProfile-shaped data -- only into
    PipelineTrace.metadata."""
    project = {"title": "X", "summary": "", "technologies": ["Go"], "concepts": []}
    parser_results = {"projects": _project_result(project)}
    trace = PipelineTrace(document_id="doc-1")
    DefaultCrossReferenceEngine().cross_reference(parser_results, trace=trace)

    assert set(project.keys()) == {"title", "summary", "technologies", "concepts", "interview_seeds"}


def test_no_stage_trace_recorded_when_trace_is_none():
    parser_results = {
        "projects": _project_result({"title": "X", "summary": "", "technologies": ["Go"], "concepts": []})
    }
    # trace stays None throughout -- nothing to assert on since there's no
    # trace object, but this documents the zero-cost-when-disabled
    # contract explicitly rather than leaving it implicit.
    result = DefaultCrossReferenceEngine().cross_reference(parser_results, trace=None)
    assert result["projects"].entities[0]["interview_seeds"] == ["Why did you use Go in this project?"]


# ── Demonstrated-skills tagging (Milestone 5) ────────────────────────────


def _skills_result(*skills: str) -> ParserResult:
    return ParserResult(
        entities=list(skills),
        confidences=[Confidence(score=0.7, reasons=["+listed_in_explicit_skills_section:x"]) for _ in skills],
        observations=[],
    )


def test_skill_demonstrated_in_a_project_gets_a_confidence_boost_and_reason():
    parser_results = {
        "skills": _skills_result("Redis"),
        "projects": _project_result(
            {"title": "Cache Layer", "summary": "Built with Redis.", "technologies": ["Redis"], "concepts": []}
        ),
    }
    DefaultCrossReferenceEngine().cross_reference(parser_results)

    confidence = parser_results["skills"].confidences[0]
    assert confidence.score > 0.7
    assert any("demonstrated_in_project:Cache Layer" in r for r in confidence.reasons)


def test_skill_demonstrated_in_experience_gets_tagged():
    parser_results = {
        "skills": _skills_result("Kubernetes"),
        "experience": _project_result(
            {"role": "SRE", "company": "Acme", "duration": "", "summary": "Ran workloads on Kubernetes."}
        ),
    }
    DefaultCrossReferenceEngine().cross_reference(parser_results)

    confidence = parser_results["skills"].confidences[0]
    assert any("demonstrated_in_experience:Acme" in r for r in confidence.reasons)


def test_skill_not_demonstrated_anywhere_gets_an_observation_and_no_boost():
    parser_results = {
        "skills": _skills_result("Leadership"),
        "projects": _project_result(
            {"title": "X", "summary": "Built with Redis.", "technologies": ["Redis"], "concepts": []}
        ),
    }
    DefaultCrossReferenceEngine().cross_reference(parser_results)

    confidence = parser_results["skills"].confidences[0]
    assert confidence.score == 0.7
    assert "-not_demonstrated_elsewhere" in confidence.reasons
    assert any(o.category == "skill_not_demonstrated" for o in parser_results["skills"].observations)


def test_demonstrated_skills_tagging_never_touches_public_skill_strings():
    parser_results = {
        "skills": _skills_result("Redis", "Leadership"),
        "projects": _project_result(
            {"title": "X", "summary": "Built with Redis.", "technologies": ["Redis"], "concepts": []}
        ),
    }
    DefaultCrossReferenceEngine().cross_reference(parser_results)
    assert parser_results["skills"].entities == ["Redis", "Leadership"]


def test_demonstrated_skills_no_op_when_no_skills_key():
    parser_results = {"experience": _project_result()}
    result = DefaultCrossReferenceEngine().cross_reference(parser_results)
    assert "skills" not in result


def test_demonstrated_skills_stage_trace_recorded_even_without_projects():
    parser_results = {"skills": _skills_result("Leadership")}
    trace = PipelineTrace(document_id="doc-1")
    DefaultCrossReferenceEngine().cross_reference(parser_results, trace=trace)
    stages_by_name = {s.stage_name: s for s in trace.stages}
    assert "cross_reference:demonstrated_skills" in stages_by_name
    assert stages_by_name["cross_reference:demonstrated_skills"].metadata == {
        "skills_checked": 1,
        "demonstrated": 0,
    }
