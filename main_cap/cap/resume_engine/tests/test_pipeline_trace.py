import json

import pytest

from resume_engine import __version__
from resume_engine.confidence import Confidence
from resume_engine.pipeline_trace import PipelineTrace, StageTrace


def test_total_duration_ms_sums_stages():
    trace = PipelineTrace(document_id="doc-1")
    trace.record(StageTrace(stage_name="a", duration_ms=10.0))
    trace.record(StageTrace(stage_name="b", duration_ms=15.5))
    assert trace.total_duration_ms == 25.5


def test_total_duration_ms_is_zero_for_empty_trace():
    trace = PipelineTrace(document_id="doc-1")
    assert trace.total_duration_ms == 0.0


def test_engine_version_defaults_to_package_version():
    trace = PipelineTrace(document_id="doc-1")
    assert trace.engine_version == __version__


def test_parser_versions_defaults_to_empty_dict():
    trace = PipelineTrace(document_id="doc-1")
    assert trace.parser_versions == {}


def test_to_json_round_trips_document_id_and_stages():
    trace = PipelineTrace(document_id="doc-1")
    trace.record(StageTrace(stage_name="extraction", duration_ms=5.0))
    parsed = json.loads(trace.to_json())
    assert parsed["document_id"] == "doc-1"
    assert parsed["engine_version"] == __version__
    assert parsed["stages"][0]["stage_name"] == "extraction"
    assert parsed["total_duration_ms"] == 5.0


def test_to_console_renders_confidence_reasons_as_checklist():
    trace = PipelineTrace(document_id="doc-1")
    confidence = Confidence(score=0.91, reasons=["+strong_title_match", "-missing_measurable_outcome"])
    trace.record(StageTrace(stage_name="project_parser", duration_ms=9.0, confidences=[confidence]))
    output = trace.to_console()
    assert "✓ strong_title_match" in output
    assert "⚠ missing_measurable_outcome" in output
    assert "0.91" in output


def test_to_html_not_implemented_until_milestone_6():
    trace = PipelineTrace(document_id="doc-1")
    with pytest.raises(NotImplementedError):
        trace.to_html()
