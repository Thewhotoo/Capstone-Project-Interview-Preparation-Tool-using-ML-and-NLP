"""Tests for the Milestone 7 batch Shadow Mode tooling
(resume_engine/devtools/shadow_mode_batch.py). Gemini's call is mocked
(never hit the real API in a test); the engine path and file I/O run for
real."""

from __future__ import annotations

import json

from resume_engine.devtools.shadow_mode import (
    Discrepancy,
    EngineComparisonError,
    GeminiComparisonError,
    ShadowComparisonResult,
)
from resume_engine.devtools.shadow_mode_batch import (
    ExtractionComparisonError,
    _error_stage,
    aggregate_category_counts,
    run_batch_shadow_comparison,
    write_report,
)


def _fake_result(*categories: str) -> ShadowComparisonResult:
    return ShadowComparisonResult(
        gemini_profile={},
        engine_profile={},
        discrepancies=[Discrepancy(field=f"f{i}", category=c, gemini_value=1, engine_value=2) for i, c in enumerate(categories)],
    )


def test_aggregate_category_counts_sums_across_resumes():
    results = {
        "a.pdf": _fake_result("different_value", "different_value"),
        "b.pdf": _fake_result("missing_in_engine"),
    }
    totals = aggregate_category_counts(results)
    assert totals == {"different_value": 2, "missing_in_engine": 1}


def test_aggregate_category_counts_skips_error_entries():
    results = {"a.pdf": _fake_result("different_value"), "b.pdf": ValueError("corrupt file")}
    totals = aggregate_category_counts(results)
    assert totals == {"different_value": 1}


def test_write_report_produces_valid_json_with_summary_and_per_resume_entries(tmp_path):
    results = {
        "a.pdf": _fake_result("different_value"),
        "b.pdf": ValueError("corrupt file"),
    }
    report_path = tmp_path / "report.json"
    write_report(results, str(report_path))

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["summary"] == {"different_value": 1}
    assert "category_counts" in report["resumes"]["a.pdf"]
    assert report["resumes"]["b.pdf"]["error"] == "corrupt file"


def test_run_batch_shadow_comparison_over_golden_corpus_directory(monkeypatch, tmp_path):
    """Copies one real golden-corpus PDF into an isolated directory
    (batch runner scans a directory non-recursively) and runs the batch
    over it, with Gemini mocked."""
    import shutil
    from pathlib import Path

    import candidate_profile_generator

    source = Path(__file__).parent / "golden_corpus" / "full_entity_resume_pdf" / "resume.pdf"
    shutil.copy(source, tmp_path / "resume.pdf")

    def _fake_generate(resume_text: str) -> dict:
        return {
            "candidate_name": "Gemini Says Hi", "contact_details": {"email": "", "phone": "", "linkedin": "", "location": ""},
            "skills": [], "education": [], "experience": [], "projects": [], "certifications": [],
            "predicted_domain": "Software Engineering", "experience_level": "Intermediate", "confidence": 0.5,
            "interview_blueprint": {
                "resume_verification_topics": [], "technical_topics": [], "starting_difficulty": "intermediate",
                "estimated_strengths": [], "estimated_weaknesses": [],
            },
            "resume_summary": "",
        }

    monkeypatch.setattr(candidate_profile_generator, "generate_candidate_profile", _fake_generate)

    results = run_batch_shadow_comparison(str(tmp_path))

    assert "resume.pdf" in results
    assert isinstance(results["resume.pdf"], ShadowComparisonResult)
    assert results["resume.pdf"].engine_profile["candidate_name"]  # real engine ran


def test_run_batch_shadow_comparison_records_errors_without_aborting(monkeypatch, tmp_path):
    (tmp_path / "not_a_real_pdf.pdf").write_bytes(b"not a real pdf")

    results = run_batch_shadow_comparison(str(tmp_path))

    assert isinstance(results["not_a_real_pdf.pdf"], Exception)


def test_run_batch_shadow_comparison_skips_unsupported_file_types(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    results = run_batch_shadow_comparison(str(tmp_path))
    assert results == {}


def test_error_stage_classifies_tagged_exceptions():
    assert _error_stage(GeminiComparisonError("x")) == "gemini_error"
    assert _error_stage(EngineComparisonError("x")) == "engine_error"
    assert _error_stage(ExtractionComparisonError("x")) == "extraction_error"
    assert _error_stage(ValueError("x")) == "unknown_error"


def test_run_batch_shadow_comparison_tags_extraction_failures(tmp_path):
    """A file that fails extraction (corrupt/garbage bytes) must be
    stored as an ExtractionComparisonError, not a bare exception, so the
    report can classify it separately from Gemini/engine failures."""
    (tmp_path / "not_a_real_pdf.pdf").write_bytes(b"not a real pdf")

    results = run_batch_shadow_comparison(str(tmp_path))

    assert isinstance(results["not_a_real_pdf.pdf"], ExtractionComparisonError)


def test_write_report_meta_and_stage_grouping(tmp_path):
    results = {
        "a.pdf": _fake_result("different_value"),
        "b.pdf": GeminiComparisonError("rate limit"),
        "c.pdf": EngineComparisonError("boom"),
        "d.pdf": ExtractionComparisonError("corrupt"),
    }
    report_path = tmp_path / "report.json"
    write_report(results, str(report_path))

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["meta"] == {
        "total_resumes": 4,
        "completed": 1,
        "errored": 3,
        "errors_by_stage_count": {"gemini_error": 1, "engine_error": 1, "extraction_error": 1},
    }
    assert report["errors_by_stage"] == {
        "gemini_error": ["b.pdf"], "engine_error": ["c.pdf"], "extraction_error": ["d.pdf"],
    }
    assert report["resumes"]["b.pdf"] == {"error": "rate limit", "stage": "gemini_error"}
    assert report["resumes"]["c.pdf"] == {"error": "boom", "stage": "engine_error"}


def test_write_report_flags_critical_failure_candidates(tmp_path):
    healthy = ShadowComparisonResult(
        gemini_profile={}, engine_profile={}, discrepancies=[],
        topic_pool_check={"ok": True, "specifications_count": 3, "rejected_count": 0},
    )
    unhealthy = ShadowComparisonResult(
        gemini_profile={}, engine_profile={}, discrepancies=[],
        topic_pool_check={"ok": False, "specifications_count": 0, "rejected_count": 0},
    )
    results = {"good.pdf": healthy, "bad.pdf": unhealthy}
    report_path = tmp_path / "report.json"
    write_report(results, str(report_path))

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["critical_failure_candidates"] == ["bad.pdf"]
