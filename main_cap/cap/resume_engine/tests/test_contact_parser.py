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


def _word_level_row(make_text_span, y: float, words: list[tuple[str, float]]) -> list:
    """Builds one visual line out of several separate WORD-level spans
    (plus a whitespace-only span between each pair), matching how
    `PdfDocxExtractor` actually emits spans -- one per word, not one per
    line -- which is the shape that exposed the Phase 1 real-world
    fragmentation bugs below."""
    spans = []
    x = 72.0
    for i, (word, size) in enumerate(words):
        if i > 0:
            spans.append(make_text_span(text=" ", bbox=(x, y, x + 4.0, y + 10.0), font_size=size))
            x += 4.0
        spans.append(make_text_span(text=word, bbox=(x, y, x + len(word) * 6.0 + 2.0, y + 10.0), font_size=size))
        x += len(word) * 6.0 + 2.0
    return spans


def test_contact_parser_keeps_phone_country_code_across_word_level_spans(
    make_section, make_text_span, make_document_model
):
    """Regression test -- Phase 1 real-world evaluation: a phone number
    split across separate word-level spans ("+91" / " " / "9972425152")
    joined with an extra space per whitespace-only span must not lose its
    country code to the phone regex's single-character separator
    tolerance."""
    spans = _word_level_row(make_text_span, y=90.0, words=[("+91", 10.0), ("9972425152", 10.0)])
    section = make_section(label="contact", raw_header_text="", spans=spans)
    doc = make_document_model(spans=spans)

    result = ContactParser().parse({"contact": section}, doc)

    assert result.entities[0]["phone"] == "+91 9972425152"


def test_contact_parser_reconstructs_a_multi_word_location_from_word_level_spans(
    make_section, make_text_span, make_document_model
):
    """Regression test -- Phase 1 real-world evaluation: a multi-word
    location split across word-level spans must be matched as one
    reconstructed line, not as individual words (which almost never score
    above the gazetteer match threshold on their own)."""
    spans = _word_level_row(
        make_text_span,
        y=72.0,
        words=[("Bengaluru,", 10.0), ("Karnataka", 10.0), ("560017,", 10.0), ("India", 10.0)],
    )
    section = make_section(label="contact", raw_header_text="", spans=spans)
    doc = make_document_model(spans=spans)

    result = ContactParser().parse({"contact": section}, doc)

    assert result.entities[0]["location"] == "Bengaluru, Karnataka 560017, India"


def test_contact_parser_extracts_location_from_a_pipe_delimited_horizontal_line(
    make_section, make_text_span, make_document_model
):
    """Regression test -- Phase 1 real-world evaluation: some resumes
    print phone/location/email/handles all on one "|"-delimited line. The
    whole-line email/phone skip must not discard the location segment
    printed alongside them on the same line."""
    span = make_text_span(
        text="+91 9122604819 | Kolkata, India | jordan.example@test.invalid",
        bbox=(72.0, 90.0, 400.0, 100.0),
        font_size=10.0,
    )
    section = make_section(label="contact", raw_header_text="", spans=[span])
    doc = make_document_model(spans=[span])

    result = ContactParser().parse({"contact": section}, doc)

    assert result.entities[0]["location"] == "Kolkata, India"


def test_contact_parser_does_not_match_a_gazetteer_word_inside_a_section_heading(
    make_section, make_text_span, make_document_model
):
    """Regression test -- Phase 1 real-world evaluation: a gazetteer word
    (e.g. "Massachusetts") appearing inside unrelated section-heading text
    ("Education Massachusetts Institute of Technology") must not be
    fabricated as the candidate's location."""
    span = make_text_span(
        text="Education Massachusetts Institute of Technology (MIT)",
        bbox=(72.0, 106.0, 400.0, 116.0),
        font_size=10.0,
    )
    section = make_section(label="contact", raw_header_text="", spans=[span])
    doc = make_document_model(spans=[span])

    result = ContactParser().parse({"contact": section}, doc)

    assert result.entities[0]["location"] == ""


def test_contact_parser_joins_a_name_stacked_across_two_equal_font_lines(
    make_section, make_text_span, make_document_model
):
    """Regression test -- Phase 1 real-world evaluation: some templates
    print first/last name as two separate stacked lines at identical font
    size ("ANGEL" / "MATAPANG") rather than one line; picking only the
    first such line truncated the name."""
    first_line = [make_text_span(text="ANGEL", bbox=(72.0, 72.0, 150.0, 100.0), font_size=36.0)]
    second_line = [make_text_span(text="MATAPANG", bbox=(72.0, 104.0, 220.0, 132.0), font_size=36.0)]
    email_line = [
        make_text_span(text="jordan.example@test.invalid", bbox=(72.0, 140.0, 260.0, 150.0), font_size=10.0)
    ]
    spans = first_line + second_line + email_line
    section = make_section(label="contact", raw_header_text="", spans=spans)
    doc = make_document_model(spans=spans)

    result = ContactParser().parse({"contact": section}, doc)

    assert result.entities[0]["candidate_name"] == "ANGEL MATAPANG"
