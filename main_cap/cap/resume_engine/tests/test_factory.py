import pytest

from resume_engine.factory import default_parser_registry, default_pipeline
from resume_engine.interfaces import ParserConformanceError
from resume_engine.registry import ParserRegistry


def test_default_parser_registry_registers_all_six_parsers():
    registry = default_parser_registry()
    assert registry.registered_parser_names() == (
        "certifications",
        "contact",
        "education",
        "experience",
        "projects",
        "skills",
    )


def test_default_parser_registry_runs_conformance_checking_for_real_m3_parsers():
    """A non-conformant real parser must be rejected at registration --
    direct regression for the factory.py conformance-checking gap the
    Milestone 3 plan flagged and fixed."""

    class BrokenContactParser:
        entity_name = "contact"
        required_sections = ("contact",)
        version = "0.1.0"

        def parse(self, sections, doc, trace=None):
            return "not a ParserResult"

    registry = ParserRegistry()
    with pytest.raises(ParserConformanceError):
        registry.register_parser(BrokenContactParser(), sample_sections={}, sample_doc=_empty_doc())


def test_default_pipeline_constructs_without_error():
    pipeline = default_pipeline()
    assert pipeline.parser_runner.registered_parser_names() == (
        "certifications",
        "contact",
        "education",
        "experience",
        "projects",
        "skills",
    )


def _empty_doc():
    from resume_engine.document_model import DocumentModel

    return DocumentModel(spans=[], body_font_size=10.0)
