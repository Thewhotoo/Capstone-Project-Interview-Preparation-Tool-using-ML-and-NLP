from resume_engine.interfaces import check_parser_conformance
from resume_engine.parsers.skills_parser import SkillsParser


def _skills_section(make_section, make_text_span, text="Python, Redis, Docker, Leadership"):
    spans = [
        make_text_span(text="Skills", bbox=(72.0, 72.0, 150.0, 90.0), font_size=13.0, is_bold=True),
        make_text_span(text=text, bbox=(72.0, 100.0, 400.0, 110.0)),
    ]
    return make_section(label="skills", raw_header_text="Skills", spans=spans, header_confidence=0.9)


def test_skills_parser_splits_on_commas_and_returns_one_entity_per_skill(
    make_section, make_text_span, make_document_model
):
    section = _skills_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = SkillsParser().parse({"skills": section}, doc)

    assert result.entities == ["Python", "Redis", "Docker", "Leadership"]
    assert len(result.confidences) == len(result.entities)


def test_skills_parser_normalizes_gazetteer_hit_casing(make_section, make_text_span, make_document_model):
    section = _skills_section(make_section, make_text_span, text="javascript, python")
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = SkillsParser().parse({"skills": section}, doc)

    assert "JavaScript" in result.entities
    assert "Python" in result.entities


def test_skills_parser_dedupes_case_insensitively(make_section, make_text_span, make_document_model):
    section = _skills_section(make_section, make_text_span, text="Python, python, PYTHON")
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = SkillsParser().parse({"skills": section}, doc)

    assert result.entities == ["Python"]


def test_skills_parser_gazetteer_match_scores_higher_than_non_gazetteer_skill(
    make_section, make_text_span, make_document_model
):
    section = _skills_section(make_section, make_text_span, text="Python, Leadership")
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = SkillsParser().parse({"skills": section}, doc)

    by_skill = dict(zip(result.entities, result.confidences))
    assert by_skill["Python"].score > by_skill["Leadership"].score


def test_skills_parser_splits_on_pipes_and_bullets(make_section, make_text_span, make_document_model):
    section = _skills_section(make_section, make_text_span, text="Python | Redis • Docker")
    doc = make_document_model(spans=section.spans, body_font_size=10.0)

    result = SkillsParser().parse({"skills": section}, doc)

    assert set(result.entities) == {"Python", "Redis", "Docker"}


def test_skills_parser_returns_empty_result_when_section_missing(make_document_model):
    doc = make_document_model(spans=[])
    result = SkillsParser().parse({}, doc)
    assert result.entities == []
    assert result.confidences == []


def test_skills_parser_conforms_to_entity_parser_protocol(make_section, make_text_span, make_document_model):
    section = _skills_section(make_section, make_text_span)
    doc = make_document_model(spans=section.spans, body_font_size=10.0)
    check_parser_conformance(SkillsParser(), {"skills": section}, doc)
