"""Tests for the Milestone 7 Shadow Mode comparison tooling
(resume_engine/devtools/shadow_mode.py). `compare_profiles` is a pure
function (no API calls) and is tested directly; `run_shadow_comparison`
is tested with Gemini's call mocked out (never call the real API from a
test) but the engine path running for real against a golden-corpus
fixture."""

from __future__ import annotations

from pathlib import Path

from resume_engine.devtools.shadow_mode import compare_profiles, run_shadow_comparison

GOLDEN_CORPUS_DIR = Path(__file__).parent / "golden_corpus"


def _base_profile(**overrides) -> dict:
    base = {
        "candidate_name": "Jordan Example",
        "contact_details": {"email": "jordan@test.invalid", "phone": "", "linkedin": "", "location": ""},
        "skills": ["Python", "Redis"],
        "education": [],
        "experience": [{"company": "Acme", "role": "Engineer", "duration": "2020 - 2022", "summary": "Did things."}],
        "projects": [
            {"title": "X", "summary": "Built with Redis.", "technologies": ["Redis"], "concepts": [], "interview_seeds": []}
        ],
        "certifications": ["PMP"],
        "predicted_domain": "Software Engineering",
        "experience_level": "Intermediate",
        "confidence": 0.8,
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": [],
            "starting_difficulty": "intermediate",
            "estimated_strengths": [],
            "estimated_weaknesses": [],
        },
        "resume_summary": "A summary.",
    }
    base.update(overrides)
    return base


def test_identical_profiles_produce_no_discrepancies():
    profile = _base_profile()
    discrepancies = compare_profiles(profile, dict(profile))
    assert discrepancies == []


def test_scalar_difference_is_categorized_as_different_value():
    gemini = _base_profile(predicted_domain="Data Science")
    engine = _base_profile(predicted_domain="Software Engineering")
    discrepancies = compare_profiles(gemini, engine)
    matches = [d for d in discrepancies if d.field == "predicted_domain"]
    assert len(matches) == 1
    assert matches[0].category == "different_value"
    assert matches[0].gemini_value == "Data Science"
    assert matches[0].engine_value == "Software Engineering"


def test_flat_string_list_diff_is_order_independent():
    gemini = _base_profile(skills=["Python", "Redis"])
    engine = _base_profile(skills=["Redis", "Python"])
    discrepancies = compare_profiles(gemini, engine)
    assert not any(d.field == "skills" for d in discrepancies)


def test_flat_string_list_reports_missing_in_engine():
    gemini = _base_profile(skills=["Python", "Redis", "Leadership"])
    engine = _base_profile(skills=["Python", "Redis"])
    discrepancies = compare_profiles(gemini, engine)
    matches = [d for d in discrepancies if d.field == "skills" and d.category == "missing_in_engine"]
    assert len(matches) == 1
    assert matches[0].gemini_value == ["leadership"]


def test_flat_string_list_reports_missing_in_gemini():
    gemini = _base_profile(skills=["Python"])
    engine = _base_profile(skills=["Python", "Redis"])
    discrepancies = compare_profiles(gemini, engine)
    matches = [d for d in discrepancies if d.field == "skills" and d.category == "missing_in_gemini"]
    assert len(matches) == 1
    assert matches[0].engine_value == ["redis"]


def test_entity_list_count_mismatch_reported():
    gemini = _base_profile(projects=[_base_profile()["projects"][0], {"title": "Y", "summary": "", "technologies": [], "concepts": [], "interview_seeds": []}])
    engine = _base_profile()
    discrepancies = compare_profiles(gemini, engine)
    assert any(d.field == "projects" and d.category == "count_mismatch" for d in discrepancies)


def test_entity_list_missing_entry_reported_by_key():
    gemini = _base_profile()
    engine = _base_profile(projects=[])
    discrepancies = compare_profiles(gemini, engine)
    assert any(
        d.category == "missing_in_engine" and d.field == "projects[title='x']" for d in discrepancies
    )


def test_entity_list_subfield_difference_reported():
    gemini = _base_profile()
    engine_project = dict(_base_profile()["projects"][0])
    engine_project["technologies"] = ["Kafka"]
    engine = _base_profile(projects=[engine_project])
    discrepancies = compare_profiles(gemini, engine)
    matches = [d for d in discrepancies if "technologies" in d.field]
    assert len(matches) == 1
    assert matches[0].category == "different_value"


def test_shadow_mode_never_labels_a_side_as_ground_truth():
    """Structural check: every Discrepancy category is one of the four
    neutral, descriptive labels -- never anything implying correctness
    (e.g. no 'gemini_wrong' or 'engine_correct' category exists)."""
    gemini = _base_profile(predicted_domain="Data Science", skills=["Python", "Extra"])
    engine = _base_profile()
    discrepancies = compare_profiles(gemini, engine)
    allowed = {"missing_in_engine", "missing_in_gemini", "different_value", "count_mismatch"}
    for d in discrepancies:
        assert d.category in allowed


def test_run_shadow_comparison_produces_a_result_with_category_counts(monkeypatch):
    """Mocks Gemini's call (never hit the real API from a test); the
    engine path runs for real against a golden-corpus fixture."""
    import candidate_profile_generator

    def _fake_generate(resume_text: str) -> dict:
        return _base_profile(candidate_name="Gemini Says Hi")

    monkeypatch.setattr(candidate_profile_generator, "generate_candidate_profile", _fake_generate)

    resume_path = GOLDEN_CORPUS_DIR / "full_entity_resume_pdf" / "resume.pdf"
    result = run_shadow_comparison(str(resume_path), resume_text="irrelevant, mocked")

    assert result.gemini_profile["candidate_name"] == "Gemini Says Hi"
    assert result.engine_profile["candidate_name"]  # real engine output
    assert result.discrepancies  # names differ at minimum
    counts = result.category_counts()
    assert isinstance(counts, dict)
    assert sum(counts.values()) == len(result.discrepancies)
