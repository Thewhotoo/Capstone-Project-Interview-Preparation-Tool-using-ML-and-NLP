from resume_engine.interfaces import check_parser_conformance
from resume_engine.parsers.project_parser import ProjectParser


def _projects_section(make_section, make_text_span):
    spans = [
        make_text_span(text="Projects", bbox=(72.0, 72.0, 150.0, 90.0), font_size=13.0, is_bold=True),
        make_text_span(text="AI SOC Analyst", bbox=(72.0, 100.0, 200.0, 110.0), is_bold=True),
        make_text_span(
            text="Built a Python and Redis based caching system for security alerts using microservices.",
            bbox=(72.0, 117.0, 400.0, 127.0),
        ),
        make_text_span(text="Tech: Python, Redis, Docker", bbox=(72.0, 134.0, 300.0, 144.0)),
        make_text_span(text="Task Tracker", bbox=(72.0, 151.0, 200.0, 161.0), is_bold=True),
        make_text_span(
            text="A React and Node.js app for tracking personal tasks with authentication.",
            bbox=(72.0, 168.0, 400.0, 178.0),
        ),
    ]
    return make_section(label="projects", raw_header_text="Projects", spans=spans, header_confidence=0.9)


def test_project_parser_extracts_title_summary_technologies(make_section, make_text_span, make_document_model):
    section = _projects_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ProjectParser().parse({"projects": section}, doc)

    assert len(result.entities) == 2
    first, second = result.entities
    assert first["title"] == "AI SOC Analyst"
    assert "Python" in first["technologies"]
    assert "Redis" in first["technologies"]
    assert "Docker" in first["technologies"]
    assert first["interview_seeds"] == []
    assert second["title"] == "Task Tracker"
    assert "React" in second["technologies"]
    assert "Node.js" in second["technologies"]


def test_project_parser_does_not_treat_section_header_as_an_entry(
    make_section, make_text_span, make_document_model
):
    section = _projects_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ProjectParser().parse({"projects": section}, doc)

    titles = [e["title"] for e in result.entities]
    assert "Projects" not in titles


def test_project_parser_summary_excludes_the_tech_labeled_line(make_section, make_text_span, make_document_model):
    section = _projects_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ProjectParser().parse({"projects": section}, doc)

    assert "Tech:" not in result.entities[0]["summary"]
    assert "caching system" in result.entities[0]["summary"]


def test_project_parser_interview_seeds_always_empty_in_milestone_3(
    make_section, make_text_span, make_document_model
):
    section = _projects_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ProjectParser().parse({"projects": section}, doc)

    assert all(e["interview_seeds"] == [] for e in result.entities)
    for confidence in result.confidences:
        assert any("interview_seeds_not_implemented" in r for r in confidence.reasons)
        # Confidence ceiling documented in the milestone plan: the
        # architecture doc's fourth term (seed precondition satisfied,
        # +0.2) is omitted entirely in M3, not faked.
        assert confidence.score <= 0.8


def test_project_parser_flags_project_with_no_technologies(make_section, make_text_span, make_document_model):
    header = make_text_span(text="Personal Blog", bbox=(72.0, 72.0, 200.0, 82.0), is_bold=True)
    body = make_text_span(text="A simple blog about my hobbies.", bbox=(72.0, 90.0, 300.0, 100.0))
    section = make_section(label="projects", raw_header_text="", spans=[header, body], header_confidence=0.9)
    doc = make_document_model(spans=[header, body], body_font_size=10.0)

    result = ProjectParser().parse({"projects": section}, doc)

    assert result.entities[0]["technologies"] == []
    assert any(o.category == "missing_technologies" for o in result.observations)


def test_project_parser_returns_empty_result_when_section_missing(make_document_model):
    doc = make_document_model(spans=[])
    result = ProjectParser().parse({}, doc)
    assert result.entities == []
    assert result.confidences == []


def test_project_parser_conforms_to_entity_parser_protocol(make_section, make_text_span, make_document_model):
    section = _projects_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)
    check_parser_conformance(ProjectParser(), {"projects": section}, doc)


def test_project_parser_title_is_consistent_for_traceability_join_key(
    make_section, make_text_span, make_document_model
):
    """traceability.find_project_by_title does an exact, case-insensitive
    strip().lower() match against title -- must not carry incidental
    leading/trailing whitespace."""
    section = _projects_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = ProjectParser().parse({"projects": section}, doc)

    for entity in result.entities:
        assert entity["title"] == entity["title"].strip()
