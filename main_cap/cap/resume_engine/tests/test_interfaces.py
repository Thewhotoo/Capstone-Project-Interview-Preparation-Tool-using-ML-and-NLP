import pytest

from resume_engine.confidence import Confidence
from resume_engine.interfaces import (
    ParserConformanceError,
    ParserResult,
    check_parser_conformance,
)


class ConformingParser:
    entity_name = "fake"
    required_sections = ("fake_section",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None):
        return ParserResult(
            entities=["entity"],
            confidences=[Confidence(score=0.9, reasons=["+matched"])],
            observations=[],
        )


class MismatchedLengthParser(ConformingParser):
    def parse(self, sections, doc, trace=None):
        return ParserResult(entities=["a", "b"], confidences=[Confidence(score=0.9, reasons=["+x"])])


class EmptyReasonsParser(ConformingParser):
    def parse(self, sections, doc, trace=None):
        return ParserResult(entities=["a"], confidences=[Confidence(score=0.9, reasons=[])])


class EmptyEntityNameParser(ConformingParser):
    entity_name = ""


class EmptyRequiredSectionsParser(ConformingParser):
    required_sections = ()


class NonParserResultReturningParser(ConformingParser):
    def parse(self, sections, doc, trace=None):
        return {"entities": ["a"]}


class MissingAttrParser:
    def parse(self, sections, doc, trace=None):
        return ParserResult()


def test_conforming_parser_passes():
    check_parser_conformance(ConformingParser(), {}, None)


def test_mismatched_entity_confidence_length_rejected():
    with pytest.raises(ParserConformanceError):
        check_parser_conformance(MismatchedLengthParser(), {}, None)


def test_empty_confidence_reasons_rejected():
    with pytest.raises(ParserConformanceError):
        check_parser_conformance(EmptyReasonsParser(), {}, None)


def test_empty_entity_name_rejected():
    with pytest.raises(ParserConformanceError):
        check_parser_conformance(EmptyEntityNameParser(), {}, None)


def test_empty_required_sections_rejected():
    with pytest.raises(ParserConformanceError):
        check_parser_conformance(EmptyRequiredSectionsParser(), {}, None)


def test_non_parser_result_return_rejected():
    with pytest.raises(ParserConformanceError):
        check_parser_conformance(NonParserResultReturningParser(), {}, None)


def test_missing_required_attribute_rejected():
    with pytest.raises(ParserConformanceError):
        check_parser_conformance(MissingAttrParser(), {}, None)
