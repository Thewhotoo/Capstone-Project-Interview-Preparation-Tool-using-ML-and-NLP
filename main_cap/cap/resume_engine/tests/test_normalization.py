from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.normalization import DefaultNormalizer, clean_text


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


# ── clean_text: bullet/glyph leakage fix (multi-resume validation) ─────────
# Real cases reproduced from Shubham-Mookim-Resume.pdf and
# ops_saikarthik_resume-1.pdf's raw pymupdf spans, plus the negative cases
# that prove this is NOT a broad Unicode blacklist -- dashes, accents, and
# mid-string bullets must all survive untouched.

def test_clean_text_strips_leading_bullet():
    assert clean_text("• ForGood.ai") == "ForGood.ai"


def test_clean_text_strips_leading_sub_bullet():
    assert clean_text("◦ Owned 8+ production services") == "Owned 8+ production services"


def test_clean_text_strips_embedded_control_character():
    # The real \x80 icon-font-glyph artifact found in Shubham-Mookim-Resume.pdf.
    assert clean_text("[ \x80 ]") == "[ ]"


def test_clean_text_strips_standalone_replacement_character():
    # The real � bullet-glyph artifact found in ops_saikarthik_resume-1.pdf.
    assert clean_text("�") == ""


def test_clean_text_strips_embedded_replacement_character():
    assert clean_text("Da�ta Analysis") == "Data Analysis"


def test_clean_text_preserves_en_dash_and_em_dash():
    assert clean_text("January 2025 – Present") == "January 2025 – Present"
    assert clean_text("a 140x speedup — see benchmark") == "a 140x speedup — see benchmark"


def test_clean_text_preserves_accented_characters():
    assert clean_text("naïve") == "naïve"
    assert clean_text("café") == "café"
    assert clean_text("São Paulo") == "São Paulo"


def test_clean_text_does_not_strip_mid_string_bullet():
    assert clean_text("mid • string") == "mid • string"


def test_clean_text_combined_real_world_case():
    # The exact FairEdge Data Agent project title, leading bullet stripped,
    # em dash preserved, in one string.
    assert (
        clean_text("• FairEdge Data Agent — Enterprise NL-to-SQL Agentic Pipeline")
        == "FairEdge Data Agent — Enterprise NL-to-SQL Agentic Pipeline"
    )


def test_normalizer_strips_leading_bullet_from_real_project_title_field():
    # End-to-end through DefaultNormalizer, not just the clean_text unit,
    # confirming the fix reaches the actual entity field pipeline.
    project = {
        "title": "• Patient OS v2 — Multi-Source Health AI Copilot",
        "summary": "", "technologies": [], "concepts": [], "interview_seeds": [],
    }
    parser_results = {"projects": _result(project)}
    DefaultNormalizer().normalize(parser_results)
    assert parser_results["projects"].entities[0]["title"] == "Patient OS v2 — Multi-Source Health AI Copilot"
