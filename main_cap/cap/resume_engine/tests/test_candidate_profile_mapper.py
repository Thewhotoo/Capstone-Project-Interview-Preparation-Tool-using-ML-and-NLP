from resume_engine.candidate_profile_mapper import (
    build_resume_summary,
    build_technical_topics,
    classify_domain,
    estimate_strengths,
    estimate_weaknesses,
    infer_experience_level,
    map_to_candidate_profile,
)
from resume_engine.confidence import AnnotatedCandidateProfile, Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.validation import Observation


def _result(*entities) -> ParserResult:
    return ParserResult(
        entities=list(entities),
        confidences=[Confidence(score=0.8, reasons=["+x"]) for _ in entities],
        observations=[],
    )


# ── classify_domain ────────────────────────────────────────────────────


def test_classify_domain_matches_software_engineering_keywords():
    assert classify_domain("Python React Docker Kubernetes REST API") == "Software Engineering"


def test_classify_domain_matches_data_science_keywords():
    assert classify_domain("pandas numpy scikit-learn machine learning tensorflow") == "Data Science"


def test_classify_domain_defaults_when_no_keywords_match():
    assert classify_domain("") == "Software Engineering"
    assert classify_domain("xyzzy plugh qwerty") == "Software Engineering"


# ── infer_experience_level ────────────────────────────────────────────


def test_infer_experience_level_advanced_from_years():
    experiences = [{"role": "Engineer", "duration": "2015 - 2022"}]
    assert infer_experience_level(experiences) == "Advanced"


def test_infer_experience_level_advanced_from_seniority_keyword():
    experiences = [{"role": "Staff Engineer", "duration": ""}]
    assert infer_experience_level(experiences) == "Advanced"


def test_infer_experience_level_beginner_from_junior_keyword():
    experiences = [{"role": "Software Engineering Intern", "duration": "2023 - 2023"}]
    assert infer_experience_level(experiences) == "Beginner"


def test_infer_experience_level_beginner_with_no_experience_at_all():
    """Regression: zero experience entries (a student/fresher resume with
    no Experience section) previously fell through to a bare "Intermediate"
    default -- fabricating a mid-level read from zero evidence. Never guess
    up from an absence of evidence."""
    assert infer_experience_level([]) == "Beginner"


def test_infer_experience_level_beginner_from_single_short_undated_internship():
    """Direct regression for the real-resume audit finding: a single
    internship-style entry spanning one calendar year (start and end dates
    both in the same year, so the year-span heuristic computes 0 total
    years) with no seniority keyword in the role text previously defaulted
    to "Intermediate" (observed in production as "3 yrs - Mid" surfacing in
    the generated interview summary) despite there being zero dated or
    keyword evidence of more than entry-level experience."""
    experiences = [
        {"company": "PES University EC Campus", "role": "CAVE Labs", "duration": "Jun 2025 - Aug 2025"}
    ]
    assert infer_experience_level(experiences) == "Beginner"


def test_infer_experience_level_preserves_genuine_multi_year_professional():
    """A genuine multi-year candidate (dated experience spanning several
    years, no explicit seniority keyword) must stay "Intermediate", not be
    downgraded by the same fix that stops zero-evidence cases from
    defaulting there."""
    experiences = [{"role": "Software Engineer", "company": "Acme", "duration": "2021 - 2024"}]
    assert infer_experience_level(experiences) == "Intermediate"


# ── build_technical_topics ─────────────────────────────────────────────


def test_technical_topics_reuse_project_technologies_and_concepts_directly():
    projects = [
        {"title": "X", "summary": "Built with Redis.", "technologies": ["Redis"], "concepts": ["Caching"]}
    ]
    topics = build_technical_topics(projects, [])
    topic_names = {t["topic"] for t in topics}
    assert topic_names == {"Redis", "Caching"}
    for t in topics:
        assert t["originating_project"] == "X"
        assert t["originating_experience"] == ""


def test_technical_topics_never_cite_both_project_and_experience():
    projects = [{"title": "X", "summary": "", "technologies": ["Redis"], "concepts": []}]
    experiences = [{"role": "Engineer", "company": "Acme", "summary": "Used Kafka daily."}]
    topics = build_technical_topics(projects, experiences)
    for t in topics:
        assert bool(t["originating_project"]) != bool(t["originating_experience"])


def test_technical_topics_from_experience_only_when_no_projects():
    experiences = [{"role": "SRE", "company": "Acme", "summary": "Ran Kubernetes clusters."}]
    topics = build_technical_topics([], experiences)
    assert any(t["topic"] == "Kubernetes" for t in topics)
    assert all(t["originating_experience"] == "SRE at Acme" for t in topics)


def test_technical_topics_capped_at_max():
    projects = [
        {
            "title": "X",
            "summary": "",
            "technologies": ["Python", "Redis", "Docker", "Kafka", "AWS", "Postgres", "React", "GraphQL", "Kubernetes"],
            "concepts": [],
        }
    ]
    topics = build_technical_topics(projects, [])
    assert len(topics) <= 8


def test_technical_topics_dedupes_by_name():
    projects = [
        {"title": "X", "summary": "", "technologies": ["Redis"], "concepts": []},
        {"title": "Y", "summary": "", "technologies": ["Redis"], "concepts": []},
    ]
    topics = build_technical_topics(projects, [])
    assert len(topics) == 1


# ── estimate_strengths / estimate_weaknesses ────────────────────────────


def test_estimate_strengths_counts_frequency_across_projects_and_skills():
    projects = [{"technologies": ["Redis", "Python"]}, {"technologies": ["Redis"]}]
    strengths = estimate_strengths(projects, ["Redis"])
    assert strengths[0] == "Demonstrated proficiency in Redis"


def test_estimate_weaknesses_reuses_validation_observations():
    observations = [
        Observation(severity="info", category="no_measurable_outcome", message="m", entity_ref="projects[0]"),
        Observation(severity="notice", category="missing_linkedin", message="m", entity_ref="contact"),
        Observation(severity="info", category="unrelated_category", message="m", entity_ref="x"),
    ]
    weaknesses = estimate_weaknesses(observations)
    assert len(weaknesses) == 2
    assert all(isinstance(w, str) and w for w in weaknesses)


def test_estimate_weaknesses_dedupes_by_category():
    observations = [
        Observation(severity="info", category="no_measurable_outcome", message="a", entity_ref="projects[0]"),
        Observation(severity="info", category="no_measurable_outcome", message="b", entity_ref="projects[1]"),
    ]
    assert len(estimate_weaknesses(observations)) == 1


# ── build_resume_summary ────────────────────────────────────────────────


def test_resume_summary_is_empty_when_no_evidence():
    assert build_resume_summary("", "Software Engineering", "Intermediate", 0, []) == ""


def test_resume_summary_grounded_in_extracted_data():
    summary = build_resume_summary("Jordan", "Data Science", "Advanced", 6, ["Python", "Pandas"])
    assert "Jordan" in summary
    assert "6 years" in summary
    assert "Python" in summary


def test_resume_summary_never_says_beginner_professional():
    """Regression for the production-walkthrough audit: "beginner
    professional" reads as a contradiction. The summary should use the
    same Junior/Mid/Senior wording the rest of the app already shows for
    this level."""
    summary = build_resume_summary("Jordan", "Software Engineering", "Beginner", 0, ["Python"])
    assert "beginner" not in summary.lower()
    assert "junior" in summary.lower()


# ── map_to_candidate_profile (full integration) ─────────────────────────


def _full_annotated_profile() -> AnnotatedCandidateProfile:
    parser_results = {
        "contact": _result(
            {"candidate_name": "Jordan Example", "email": "jordan@test.invalid", "phone": "", "linkedin": "", "location": "SF"}
        ),
        "experience": _result(
            {"company": "Acme", "role": "Senior Engineer", "duration": "2018 - 2024", "summary": "Led backend systems using Kafka."}
        ),
        "projects": _result(
            {
                "title": "AI SOC Analyst",
                "summary": "Built a Python and Redis based caching system.",
                "technologies": ["Python", "Redis"],
                "concepts": ["Caching"],
                "interview_seeds": ["Why did you use Redis in this project?"],
            }
        ),
        "education": _result({"degree": "BS", "major": "CS", "institution": "State University", "graduation_year": "2018"}),
        "skills": _result("Python", "Redis"),
        "certifications": _result("AWS Certified Solutions Architect"),
    }
    observations = [
        Observation(severity="info", category="no_measurable_outcome", message="m", entity_ref="projects[0]")
    ]
    return AnnotatedCandidateProfile(
        parser_results=parser_results,
        observations=observations,
        overall_confidence=Confidence(score=0.83, reasons=["+contact:1 entities, avg confidence 0.80"]),
    )


def test_map_to_candidate_profile_produces_a_pydantic_validated_dict():
    import candidate_profile_generator as gemini_schema

    profile_dict = map_to_candidate_profile(_full_annotated_profile())

    # Round-trips cleanly through the exact public schema -- the whole
    # point of this mapper.
    reconstructed = gemini_schema.CandidateProfile(**profile_dict)
    assert reconstructed.candidate_name == "Jordan Example"
    assert reconstructed.confidence == 0.83
    assert reconstructed.projects[0].title == "AI SOC Analyst"
    assert reconstructed.projects[0].interview_seeds == ["Why did you use Redis in this project?"]
    assert reconstructed.education[0].institution == "State University"
    assert reconstructed.certifications == ["AWS Certified Solutions Architect"]


def test_map_to_candidate_profile_all_expected_top_level_keys_present():
    profile_dict = map_to_candidate_profile(_full_annotated_profile())
    expected_keys = {
        "candidate_name", "contact_details", "skills", "education", "experience",
        "projects", "certifications", "predicted_domain", "experience_level",
        "confidence", "interview_blueprint", "resume_summary",
    }
    assert expected_keys.issubset(profile_dict.keys())


def test_map_to_candidate_profile_works_with_empty_annotated_profile():
    empty = AnnotatedCandidateProfile(
        parser_results={}, observations=[], overall_confidence=Confidence(score=0.0, reasons=["-empty"])
    )
    profile_dict = map_to_candidate_profile(empty)
    assert profile_dict["candidate_name"] == ""
    assert profile_dict["projects"] == []
    assert profile_dict["resume_summary"] == ""


def test_map_to_candidate_profile_runs_through_topic_pool_and_profile_to_frontend_format():
    """The actual downstream-compatibility check: existing, unmodified
    consumer code must accept this mapper's output without exception."""
    from topic_pool import TopicPool
    from candidate_profile_generator import profile_to_frontend_format

    profile_dict = map_to_candidate_profile(_full_annotated_profile())

    frontend = profile_to_frontend_format(profile_dict)
    assert frontend["status"] == "success"
    assert frontend["name"] == "Jordan Example"

    pool = TopicPool(profile_dict)
    assert len(pool.specifications) > 0
    assert pool.rejected == []
