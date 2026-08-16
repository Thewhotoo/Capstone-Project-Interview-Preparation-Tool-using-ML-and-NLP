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


# ─── Institution-marker fallback (Phase 2: CAVE Labs / PES University) ───

def _single_header_entry(make_section, make_text_span, header_text, duration="Jun 2025 - Aug 2025"):
    """One experience entry: a bold header span plus a date span plus one
    body/summary line -- mirrors the real resume's shape closely enough to
    exercise date-stripping + role/company splitting together."""
    spans = [
        make_text_span(text=header_text, bbox=(72.0, 72.0, 250.0, 82.0), is_bold=True),
        make_text_span(text=duration, bbox=(450.0, 72.0, 520.0, 82.0)),
        make_text_span(text="Did some real work here.", bbox=(72.0, 90.0, 260.0, 100.0)),
    ]
    section = make_section(label="experience", raw_header_text="", spans=spans, header_confidence=0.9)
    return section, spans


def test_cave_labs_header_leaves_role_empty_and_preserves_full_header_as_company(
    make_section, make_text_span, make_document_model,
):
    """Direct reproduction of the audited bug: neither "CAVE Labs" nor
    "PES University EC Campus" is a job title -- role must stay empty, and
    company must be the ORIGINAL header text verbatim, not a fabricated
    "CAVE Labs" job title."""
    header = "CAVE Labs – PES University EC Campus"
    section, spans = _single_header_entry(make_section, make_text_span, header)
    doc = make_document_model(spans=spans, body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    assert result.entities[0]["role"] == ""
    assert result.entities[0]["company"] == header
    assert "+role_left_empty_institutional_pattern" in result.confidences[0].reasons


def test_institutional_pattern_with_comma_delimiter(make_section, make_text_span, make_document_model):
    header = "CAVE Labs, PES University EC Campus"
    section, spans = _single_header_entry(make_section, make_text_span, header)
    doc = make_document_model(spans=spans, body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    assert result.entities[0]["role"] == ""
    assert result.entities[0]["company"] == header


def test_institutional_pattern_with_hyphen_delimiter(make_section, make_text_span, make_document_model):
    header = "CAVE Labs - PES University EC Campus"
    section, spans = _single_header_entry(make_section, make_text_span, header)
    doc = make_document_model(spans=spans, body_font_size=10.0)

    result = ExperienceParser().parse({"experience": section}, doc)

    assert result.entities[0]["role"] == ""
    assert result.entities[0]["company"] == header


def test_institutional_pattern_generalizes_to_other_institution_markers(
    make_section, make_text_span, make_document_model,
):
    """Not specific to "CAVE Labs"/"PES University" -- any similarly-shaped
    "org, host institution" header with a generic institution-type noun
    must be handled the same way."""
    for header in (
        "Research Lab – Springfield College",
        "AI Group, Northwood Institute of Technology",
        "Robotics Club - Riverdale Polytechnic",
        "Media Lab – Eastgate Campus",
    ):
        section, spans = _single_header_entry(make_section, make_text_span, header)
        doc = make_document_model(spans=spans, body_font_size=10.0)
        result = ExperienceParser().parse({"experience": section}, doc)
        assert result.entities[0]["role"] == "", header
        assert result.entities[0]["company"] == header, header


def test_negative_control_software_engineer_google_unaffected(make_section, make_text_span, make_document_model):
    section, spans = _single_header_entry(make_section, make_text_span, "Software Engineer - Google")
    doc = make_document_model(spans=spans, body_font_size=10.0)
    result = ExperienceParser().parse({"experience": section}, doc)
    assert result.entities[0]["role"] == "Software Engineer"
    assert result.entities[0]["company"] == "Google"


def test_negative_control_intern_microsoft_unaffected(make_section, make_text_span, make_document_model):
    section, spans = _single_header_entry(make_section, make_text_span, "Intern - Microsoft")
    doc = make_document_model(spans=spans, body_font_size=10.0)
    result = ExperienceParser().parse({"experience": section}, doc)
    assert result.entities[0]["role"] == "Intern"
    assert result.entities[0]["company"] == "Microsoft"


def test_negative_control_research_intern_university_x_unaffected(
    make_section, make_text_span, make_document_model,
):
    """A REAL title ("Research Intern", gazetteer-listed) paired with a
    university -- must NOT be swept into the institution-fallback just
    because "University" appears; the gazetteer-confident path always
    wins first."""
    section, spans = _single_header_entry(make_section, make_text_span, "Research Intern - University X")
    doc = make_document_model(spans=spans, body_font_size=10.0)
    result = ExperienceParser().parse({"experience": section}, doc)
    assert result.entities[0]["role"] == "Research Intern"
    assert result.entities[0]["company"] == "University X"


def test_unlisted_title_paired_with_university_does_not_invent_a_role(
    make_section, make_text_span, make_document_model,
):
    """"Teaching Assistant" is not in the job-title gazetteer, so this
    entry is NOT confidently disambiguated. The institution-marker
    fallback must leave role empty rather than guessing "Teaching
    Assistant" is the role purely by position -- an honest "we don't know"
    is preferred over an unconfirmed guess, even though this specific
    guess happens to look plausible."""
    header = "Teaching Assistant – Stanford University"
    section, spans = _single_header_entry(make_section, make_text_span, header)
    doc = make_document_model(spans=spans, body_font_size=10.0)
    result = ExperienceParser().parse({"experience": section}, doc)
    assert result.entities[0]["role"] == ""
    assert result.entities[0]["company"] == header


def test_existing_role_company_examples_still_split_correctly(
    make_section, make_text_span, make_document_model,
):
    """Regression guard: normal, non-institutional headers are completely
    unaffected by the new fallback branch."""
    for header, expected_role, expected_company in (
        ("Acme Corp, Senior Engineer", "Senior Engineer", "Acme Corp"),
        ("Senior Engineer, Beta Inc", "Senior Engineer", "Beta Inc"),
    ):
        section, spans = _single_header_entry(make_section, make_text_span, header)
        doc = make_document_model(spans=spans, body_font_size=10.0)
        result = ExperienceParser().parse({"experience": section}, doc)
        assert result.entities[0]["role"] == expected_role, header
        assert result.entities[0]["company"] == expected_company, header
