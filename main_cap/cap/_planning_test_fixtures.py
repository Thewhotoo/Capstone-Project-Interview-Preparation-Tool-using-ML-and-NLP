"""
Shared fixture builders for Phase 1 (Planning) tests.

Not a test module itself (no `test_` prefix) — imported by
test_question_specification.py, test_traceability.py, test_coverage_tracker.py,
test_topic_pool.py, and test_planner.py so every test suite exercises the
same representative Candidate Profile shape rather than five slightly
different hand-rolled dicts.
"""

from __future__ import annotations

import copy


def sample_profile_dict() -> dict:
    """
    A representative Candidate Profile (as the plain-dict shape produced by
    `CandidateProfile.model_dump()` in candidate_profile_generator.py) with:

    - 2 projects, one of which has interview_seeds (-> project_deep_dive
      units) and one of which does not (-> project_overview unit only)
    - 1 experience entry
    - 1 certification
    - 3 technical_topics: one tracing to a real project, one tracing to a
      real experience entry, and one citing a project that does NOT exist
      on this profile (must be rejected — Chapter 10.3/11.3)
    - estimated_weaknesses touching "Resume Discussion Platform" so its
      priority_boost path is exercised
    """
    return {
        "candidate_name": "Test Candidate",
        "contact_details": {"email": "test@example.com"},
        "skills": ["Python", "Docker", "Redis"],
        "education": [],
        "experience": [
            {
                "company": "Acme Corp",
                "role": "Software Engineering Intern",
                "duration": "Summer 2024",
                "summary": "Built internal tooling for the data platform team.",
            }
        ],
        "projects": [
            {
                "title": "Resume Discussion Platform",
                "summary": "An adaptive interview platform grounded in a candidate's resume.",
                "technologies": ["Python", "Flask", "SBERT"],
                "concepts": ["Semantic similarity", "Traceability"],
                "interview_seeds": [
                    "Why SBERT for answer scoring?",
                    "Redis caching strategy",
                ],
            },
            {
                "title": "Static Portfolio Site",
                "summary": "A simple static site built with a template engine.",
                "technologies": ["HTML", "CSS"],
                "concepts": ["Static site generation"],
                "interview_seeds": [],
            },
        ],
        "certifications": ["AWS Certified Cloud Practitioner"],
        "predicted_domain": "Software Engineering",
        "experience_level": "Intermediate",
        "confidence": 0.8,
        "resume_summary": "A software engineering candidate.",
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": [
                {
                    "topic": "SBERT semantic similarity for answer scoring",
                    "originating_project": "Resume Discussion Platform",
                    "originating_experience": "",
                    "evidence": "uses SBERT to score candidate answers during discussion",
                },
                {
                    "topic": "Internal data tooling",
                    "originating_project": "",
                    "originating_experience": "Software Engineering Intern",
                    "evidence": "built internal tooling for the data platform team",
                },
                {
                    "topic": "GraphQL federation",
                    "originating_project": "Order Management System",  # does NOT exist
                    "originating_experience": "",
                    "evidence": "irrelevant — this project does not exist on this profile",
                },
            ],
            "starting_difficulty": "intermediate",
            "estimated_strengths": ["Strong grasp of semantic search"],
            "estimated_weaknesses": ["Resume Discussion Platform"],
        },
    }


def sample_profile_dict_copy() -> dict:
    """A deep copy of `sample_profile_dict()` — use when a test needs to
    assert two independently-built pools/planners produce identical output
    from what is genuinely separate profile data, not the same shared dict
    reference."""
    return copy.deepcopy(sample_profile_dict())


def minimal_profile_dict() -> dict:
    """The smallest profile that still has at least one discussable unit —
    a single project with no interview_seeds, no experience, no
    certifications, no technical_topics."""
    return {
        "candidate_name": "Minimal Candidate",
        "projects": [
            {
                "title": "Solo Project",
                "summary": "A small personal project.",
                "technologies": ["Python"],
                "concepts": [],
                "interview_seeds": [],
            }
        ],
        "experience": [],
        "certifications": [],
        "interview_blueprint": {
            "technical_topics": [],
            "estimated_weaknesses": [],
        },
    }


def empty_profile_dict() -> dict:
    """A profile with nothing discussable at all — TopicPool must build zero
    units and never error."""
    return {
        "candidate_name": "Empty Candidate",
        "projects": [],
        "experience": [],
        "certifications": [],
        "interview_blueprint": {"technical_topics": [], "estimated_weaknesses": []},
    }
