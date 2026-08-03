import pytest

from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.pipeline_trace import PipelineTrace
from resume_engine.registry import ParserRegistry, UnknownParserError


class FakeParser:
    def __init__(self, entity_name, version="0.1.0"):
        self.entity_name = entity_name
        self.required_sections = (entity_name,)
        self.version = version

    def parse(self, sections, doc, trace=None):
        return ParserResult(entities=["x"], confidences=[Confidence(score=1.0, reasons=["+ok"])])


def test_register_and_get_parser():
    registry = ParserRegistry()
    registry.register_parser(FakeParser("experience"))
    assert registry.get_parser("experience").entity_name == "experience"


def test_registered_parser_names_is_sorted():
    registry = ParserRegistry()
    registry.register_parser(FakeParser("skills"))
    registry.register_parser(FakeParser("contact"))
    assert registry.registered_parser_names() == ("contact", "skills")


def test_unknown_parser_raises():
    registry = ParserRegistry()
    with pytest.raises(UnknownParserError):
        registry.get_parser("nope")


def test_run_all_merges_results_from_every_registered_parser():
    registry = ParserRegistry()
    registry.register_parser(FakeParser("experience"))
    registry.register_parser(FakeParser("projects"))

    results = registry.run_all(sections={}, doc=None, trace=None)

    assert set(results.keys()) == {"experience", "projects"}
    assert all(isinstance(r, ParserResult) for r in results.values())


def test_run_all_records_a_stage_trace_and_version_per_parser():
    registry = ParserRegistry()
    registry.register_parser(FakeParser("experience", version="0.2.0"))
    registry.register_parser(FakeParser("projects", version="0.3.0"))
    trace = PipelineTrace(document_id="doc-1")

    registry.run_all(sections={}, doc=None, trace=trace)

    assert trace.parser_versions == {"experience": "0.2.0", "projects": "0.3.0"}
    stage_names = {s.stage_name for s in trace.stages}
    assert stage_names == {"parser:experience", "parser:projects"}


def test_register_with_sample_fixtures_runs_conformance_check():
    registry = ParserRegistry()
    registry.register_parser(FakeParser("experience"), sample_sections={}, sample_doc=None)
    assert registry.get_parser("experience") is not None
