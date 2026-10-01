from resume_engine.interfaces import check_parser_conformance
from resume_engine.parsers.education_parser import EducationParser


def _education_section(make_section, make_text_span):
    spans = [
        make_text_span(text="Education", bbox=(72.0, 72.0, 150.0, 90.0), font_size=13.0, is_bold=True),
        make_text_span(
            text="Bachelor of Science in Computer Science",
            bbox=(72.0, 100.0, 300.0, 110.0),
            is_bold=True,
        ),
        make_text_span(text="Stanford University — 2020", bbox=(72.0, 117.0, 300.0, 127.0)),
        make_text_span(
            text="Massachusetts Institute of Technology",
            bbox=(72.0, 144.0, 300.0, 154.0),
            is_bold=True,
        ),
        make_text_span(
            text="Master of Science in Electrical Engineering, 2022",
            bbox=(72.0, 161.0, 350.0, 171.0),
        ),
    ]
    return make_section(label="education", raw_header_text="Education", spans=spans, header_confidence=0.9)


def test_education_parser_extracts_degree_major_institution_year_degree_first_template(
    make_section, make_text_span, make_document_model
):
    section = _education_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = EducationParser().parse({"education": section}, doc)

    first = result.entities[0]
    assert first["degree"] == "Bachelor of Science"
    assert first["major"] == "Computer Science"
    assert first["institution"] == "Stanford University"
    assert first["graduation_year"] == "2020"


def test_education_parser_extracts_degree_major_institution_year_institution_first_template(
    make_section, make_text_span, make_document_model
):
    section = _education_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = EducationParser().parse({"education": section}, doc)

    second = result.entities[1]
    assert second["degree"] == "Master of Science"
    assert second["major"] == "Electrical Engineering"
    assert second["institution"] == "Massachusetts Institute of Technology"
    assert second["graduation_year"] == "2022"


def test_education_parser_gazetteer_matched_institution_scores_higher_than_unrecognized(
    make_section, make_text_span, make_document_model
):
    section = _education_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = EducationParser().parse({"education": section}, doc)

    for confidence in result.confidences:
        assert any("institution_gazetteer_matched" in r for r in confidence.reasons)


def test_education_parser_accepts_unrecognized_institution_at_lower_confidence(
    make_section, make_text_span, make_document_model
):
    header = make_text_span(text="Bachelor of Arts in History", bbox=(72.0, 72.0, 300.0, 82.0), is_bold=True)
    body = make_text_span(text="Springfield State University, 2019", bbox=(72.0, 90.0, 300.0, 100.0))
    section = make_section(label="education", raw_header_text="", spans=[header, body], header_confidence=0.9)
    doc = make_document_model(spans=[header, body], body_font_size=10.0)

    result = EducationParser().parse({"education": section}, doc)

    entity = result.entities[0]
    assert entity["institution"] == "Springfield State University"
    assert any(
        "institution_present_not_gazetteer_matched" in r for r in result.confidences[0].reasons
    )
    assert not any("institution_gazetteer_matched" in r for r in result.confidences[0].reasons)


def test_education_parser_flags_entry_with_no_recognizable_degree(
    make_section, make_text_span, make_document_model
):
    header = make_text_span(text="Continuing Education", bbox=(72.0, 72.0, 300.0, 82.0), is_bold=True)
    body = make_text_span(text="Some workshop, 2021", bbox=(72.0, 90.0, 300.0, 100.0))
    section = make_section(label="education", raw_header_text="", spans=[header, body], header_confidence=0.9)
    doc = make_document_model(spans=[header, body], body_font_size=10.0)

    result = EducationParser().parse({"education": section}, doc)

    assert result.entities[0]["degree"] == ""
    assert any(o.category == "missing_degree" for o in result.observations)


def test_education_parser_skips_an_entry_with_nothing_extractable(
    make_section, make_text_span, make_document_model
):
    """Direct regression for the real-resume audit: a clustered entry this
    parser can extract NOTHING from (no degree, major, institution, or
    graduation_year -- e.g. a pre-university schooling aside with
    percentage marks, not a degree) must be skipped entirely rather than
    emitted as an empty {"degree": "", ...} placeholder (which surfaced as
    raw, unrendered JSON in the frontend)."""
    real_header = make_text_span(text="Bachelor of Arts in History", bbox=(72.0, 72.0, 300.0, 82.0), is_bold=True)
    real_body = make_text_span(text="Springfield State University, 2019", bbox=(72.0, 90.0, 300.0, 100.0))
    empty_header = make_text_span(text="National Centre for Excellence", bbox=(72.0, 120.0, 300.0, 130.0), is_bold=True)
    empty_body = make_text_span(text="Class XII: 85.4%, Class X: 94.7%", bbox=(72.0, 137.0, 300.0, 147.0))
    spans = [real_header, real_body, empty_header, empty_body]
    section = make_section(label="education", raw_header_text="", spans=spans, header_confidence=0.9)
    doc = make_document_model(spans=spans, body_font_size=10.0)

    result = EducationParser().parse({"education": section}, doc)

    assert len(result.entities) == 1
    assert result.entities[0]["institution"] == "Springfield State University"
    assert len(result.confidences) == 1


def test_education_parser_returns_empty_result_when_section_missing(make_document_model):
    doc = make_document_model(spans=[])
    result = EducationParser().parse({}, doc)
    assert result.entities == []
    assert result.confidences == []


def test_education_parser_conforms_to_entity_parser_protocol(make_section, make_text_span, make_document_model):
    section = _education_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)
    check_parser_conformance(EducationParser(), {"education": section}, doc)
