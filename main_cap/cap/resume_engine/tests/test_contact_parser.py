from resume_engine.interfaces import check_parser_conformance
from resume_engine.parsers.contact_parser import ContactParser


def _contact_section(make_section, make_text_span, lines):
    spans = [make_text_span(text=text, bbox=(72.0, 72.0 + i * 16, 300.0, 82.0 + i * 16), font_size=size)
             for i, (text, size) in enumerate(lines)]
    return make_section(label="contact", raw_header_text="", spans=spans)


def test_contact_parser_extracts_all_fields(make_section, make_text_span, make_document_model):
    section = _contact_section(
        make_section,
        make_text_span,
        [
            ("Jordan Example", 18.0),
            ("jordan.example@test.invalid", 10.0),
            ("(555) 010-1234", 10.0),
            ("San Francisco", 10.0),
        ],
    )
    doc = make_document_model(spans=section.spans, hyperlinks=[])

    result = ContactParser().parse({"contact": section}, doc)

    assert len(result.entities) == 1
    entity = result.entities[0]
    assert entity["candidate_name"] == "Jordan Example"
    assert entity["email"] == "jordan.example@test.invalid"
    assert entity["phone"] == "(555) 010-1234"
    assert entity["location"] == "San Francisco"
    assert len(result.confidences) == 1
    assert result.confidences[0].reasons


def test_contact_parser_finds_linkedin_from_hyperlink_not_visible_text(
    make_section, make_text_span, make_document_model
):
    """Direct regression for the architecture doc's named gap: a
    "LinkedIn" label hyperlinked to a URL with no visible URL text."""
    span = make_text_span(text="LinkedIn", bbox=(72.0, 72.0, 150.0, 82.0))
    section = make_section(label="contact", raw_header_text="", spans=[span])
    doc = make_document_model(
        spans=[span], hyperlinks=[("https://linkedin.com/in/jordan", (72.0, 72.0, 150.0, 82.0), 0)]
    )

    result = ContactParser().parse({"contact": section}, doc)

    assert result.entities[0]["linkedin"] == "https://linkedin.com/in/jordan"


def test_contact_parser_returns_empty_result_when_contact_section_missing(make_document_model):
    doc = make_document_model(spans=[])
    result = ContactParser().parse({}, doc)
    assert result.entities == []
    assert result.confidences == []


def test_contact_parser_handles_sparse_contact_section_gracefully(
    make_section, make_text_span, make_document_model
):
    """Only an email, nothing else -- must not crash, confidence reflects
    the gaps honestly rather than guessing."""
    span = make_text_span(text="jordan.example@test.invalid", bbox=(72.0, 72.0, 220.0, 82.0))
    section = make_section(label="contact", raw_header_text="", spans=[span])
    doc = make_document_model(spans=[span])

    result = ContactParser().parse({"contact": section}, doc)

    entity = result.entities[0]
    assert entity["email"] == "jordan.example@test.invalid"
    assert entity["phone"] == ""
    assert entity["linkedin"] == ""
    assert result.confidences[0].score < 0.5


def test_contact_parser_conforms_to_entity_parser_protocol(make_section, make_text_span, make_document_model):
    span = make_text_span(text="jordan.example@test.invalid", bbox=(72.0, 72.0, 220.0, 82.0))
    section = make_section(label="contact", raw_header_text="", spans=[span])
    doc = make_document_model(spans=[span])
    check_parser_conformance(ContactParser(), {"contact": section}, doc)
