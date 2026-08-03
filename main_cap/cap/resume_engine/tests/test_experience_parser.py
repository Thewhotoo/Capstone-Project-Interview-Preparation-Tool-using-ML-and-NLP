from resume_engine.interfaces import check_parser_conformance
from resume_engine.parsers.experience_parser import ExperienceParser


def _experience_section(make_section, make_text_span):
    spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 90.0), font_size=13.0, is_bold=True),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 100.0, 250.0, 110.0), is_bold=True),
        make_text_span(text="2021 - Present", bbox=(450.0, 100.0, 520.0, 110.0)),
        make_text_span(text="Led migration of the billing platform.", bbox=(72.0, 117.0, 280.0, 127.0)),
        make_text_span(text="Senior Engineer, Beta Inc", bbox=(72.0, 134.0, 250.0, 144.0), is_bold=True),
        make_text_span(text="Jan 2018 - Mar 2021", bbox=(450.0, 134.0, 520.0, 144.0)),
        make_text_span(text="Built the analytics dashboard.", bbox=(72.0, 151.0, 260.0, 161.0)),
    ]
    return make_section(
        label="experience", raw_header_text="Experience", spans=spans, header_confidence=0.9
    )


def test_experience_parser_extracts_role_company_date_summary(make_section, make_text_span, make_document_model):
    section = _experience_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    assert len(result.entities) == 2
    first, second = result.entities
    assert first == {
        "company": "Acme Corp",
        "role": "Senior Engineer",
        "duration": "2021 - Present",
        "summary": "Led migration of the billing platform.",
    }
    assert second["company"] == "Beta Inc"
    assert second["role"] == "Senior Engineer"
    assert second["duration"] == "Jan 2018 - Mar 2021"


def test_experience_parser_does_not_treat_section_header_as_an_entry(
    make_section, make_text_span, make_document_model
):
    """Regression: Section.spans starts with the header line itself
    ("Experience") -- must not become its own bogus entry."""
    section = _experience_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    roles = [e["role"] for e in result.entities]
    assert "Experience" not in roles


def test_experience_parser_disambiguates_role_first_order(make_section, make_text_span, make_document_model):
    span = make_text_span(text="Senior Engineer, Acme Corp", bbox=(72.0, 72.0, 250.0, 82.0), is_bold=True)
    section = make_section(label="experience", raw_header_text="", spans=[span], header_confidence=0.9)
    doc = make_document_model(spans=[span], body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    assert result.entities[0]["role"] == "Senior Engineer"
    assert result.entities[0]["company"] == "Acme Corp"


def test_experience_parser_flags_entry_with_no_parseable_dates(make_section, make_text_span, make_document_model):
    span = make_text_span(text="Senior Engineer, Acme Corp", bbox=(72.0, 72.0, 250.0, 82.0), is_bold=True)
    body = make_text_span(text="No dates on this one.", bbox=(72.0, 90.0, 260.0, 100.0))
    section = make_section(label="experience", raw_header_text="", spans=[span, body], header_confidence=0.9)
    doc = make_document_model(spans=[span, body], body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    assert "-no_parseable_dates" in result.confidences[0].reasons
    assert len(result.observations) == 1
    assert result.observations[0].category == "missing_dates"


def test_experience_parser_returns_empty_result_when_section_missing(make_document_model):
    doc = make_document_model(spans=[])
    result = ExperienceParser().parse({}, doc)
    assert result.entities == []
    assert result.confidences == []


def test_experience_parser_conforms_to_entity_parser_protocol(make_section, make_text_span, make_document_model):
    section = _experience_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)
    check_parser_conformance(ExperienceParser(), {"experience": section}, doc)
