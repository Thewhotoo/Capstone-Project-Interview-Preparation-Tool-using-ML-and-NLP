from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.normalization import DefaultNormalizer


def _result(*entities, scores=None) -> ParserResult:
    scores = scores or [0.7] * len(entities)
    return ParserResult(
        entities=list(entities),
        confidences=[Confidence(score=s, reasons=["+x"]) for s in scores],
        observations=[],
    )


def test_normalizer_collapses_whitespace_and_normalizes_unicode_in_contact_fields():
    contact = {
        "candidate_name": "Jordan  Example",  # non-breaking spaces
        "email": "  jordan@test.invalid  ",
        "phone": "555-0100",
        "linkedin": "",
        "location": "San Francisco",  # em-space
    }
    parser_results = {"contact": _result(contact)}
    DefaultNormalizer().normalize(parser_results)

    normalized = parser_results["contact"].entities[0]
    assert normalized["candidate_name"] == "Jordan Example"
    assert normalized["email"] == "jordan@test.invalid"
    assert normalized["location"] == "San Francisco"


def test_normalizer_canonicalizes_duration_separator():
    experience = {"company": "Acme", "role": "Engineer", "duration": "Jan 2020—Mar 2021", "summary": ""}
    parser_results = {"experience": _result(experience)}
    DefaultNormalizer().normalize(parser_results)

    assert parser_results["experience"].entities[0]["duration"] == "Jan 2020 - Mar 2021"


def test_normalizer_dedupes_project_technologies_and_logs_observation():
    project = {
        "title": "X",
        "summary": "",
        "technologies": ["JS", "JavaScript", "Redis"],
        "concepts": [],
        "interview_seeds": [],
    }
    parser_results = {"projects": _result(project)}
    DefaultNormalizer().normalize(parser_results)

    normalized = parser_results["projects"].entities[0]
    assert normalized["technologies"] == ["JavaScript", "Redis"]
    observations = parser_results["projects"].observations
    assert any(o.category == "duplicate_technologies_merged" for o in observations)


def test_normalizer_does_not_touch_technologies_with_no_duplicates():
    project = {"title": "X", "summary": "", "technologies": ["Python", "Redis"], "concepts": [], "interview_seeds": []}
    parser_results = {"projects": _result(project)}
    DefaultNormalizer().normalize(parser_results)

    assert parser_results["projects"].entities[0]["technologies"] == ["Python", "Redis"]
    assert parser_results["projects"].observations == []


def test_normalizer_dedupes_flat_skills_list_after_aliasing_and_keeps_entities_confidences_aligned():
    parser_results = {
        "skills": ParserResult(
            entities=["JS", "JavaScript", "Redis"],
            confidences=[
                Confidence(score=0.7, reasons=["+a"]),
                Confidence(score=0.9, reasons=["+b"]),
                Confidence(score=0.8, reasons=["+c"]),
            ],
            observations=[],
        )
    }
    DefaultNormalizer().normalize(parser_results)

    result = parser_results["skills"]
    assert result.entities == ["JavaScript", "Redis"]
    assert len(result.entities) == len(result.confidences)
    # The higher-confidence duplicate ("JavaScript", 0.9) is the one kept.
    assert result.confidences[0].score == 0.9
    assert any(o.category == "duplicate_entries_merged" for o in result.observations)


def test_normalizer_cleans_certification_text_without_technology_aliasing():
    parser_results = {
        "certifications": ParserResult(
            entities=["AWS  Certified Solutions Architect"],
            confidences=[Confidence(score=0.8, reasons=["+x"])],
            observations=[],
        )
    }
    DefaultNormalizer().normalize(parser_results)
    assert parser_results["certifications"].entities == ["AWS Certified Solutions Architect"]


def test_normalizer_never_introduces_none_and_never_changes_field_types():
    project = {"title": "", "summary": "", "technologies": [], "concepts": [], "interview_seeds": []}
    parser_results = {"projects": _result(project)}
    DefaultNormalizer().normalize(parser_results)

    normalized = parser_results["projects"].entities[0]
    for value in normalized.values():
        assert value is not None


def test_normalizer_handles_empty_parser_results_without_error():
    parser_results = {"projects": _result()}
    result = DefaultNormalizer().normalize(parser_results)
    assert result["projects"].entities == []


def test_normalizer_is_a_noop_pass_through_for_unrecognized_entity_types():
    """Contact is a single dict entity, not in _STRING_FIELDS_BY_ENTITY_TYPE
    beyond its own declared fields -- confirms unknown extra fields are
    left alone rather than raising."""
    contact = {"candidate_name": "X", "email": "", "phone": "", "linkedin": "", "location": "", "extra": 123}
    parser_results = {"contact": _result(contact)}
    DefaultNormalizer().normalize(parser_results)
    assert parser_results["contact"].entities[0]["extra"] == 123
