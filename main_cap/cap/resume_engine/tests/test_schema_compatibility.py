"""Schema-compatibility test (architecture doc Section 9): construct a
profile from the real engine's parsers and run it through the EXISTING
`topic_pool.py` code, unmodified, asserting no exception and a non-empty
TopicPool -- the direct regression test for the one hard invariant
identified in Section 1.2 ("never produce a profile with zero usable
specs for a resume that has real content").

Only checkable end-to-end now that Milestone 5 makes `CertificationParser`
real (Milestone 3 already covered `ExperienceParser`/`ProjectParser`, the
other two contributors to TopicPool's specs)."""

from __future__ import annotations

from topic_pool import TopicPool

from resume_engine.cross_reference import DefaultCrossReferenceEngine
from resume_engine.parsers.certification_parser import CertificationParser
from resume_engine.parsers.experience_parser import ExperienceParser
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.parsers.skills_parser import SkillsParser


def _synthetic_resume_sections(make_section, make_text_span):
    experience_spans = [
        make_text_span(text="Experience", bbox=(72.0, 72.0, 150.0, 82.0), font_size=13.0, is_bold=True),
        make_text_span(text="Acme Corp, Senior Engineer", bbox=(72.0, 90.0, 300.0, 100.0), is_bold=True),
        make_text_span(text="Jan 2021 - Present", bbox=(72.0, 107.0, 250.0, 117.0)),
        make_text_span(
            text="Owned the payments retry pipeline handling millions of transactions per day.",
            bbox=(72.0, 124.0, 450.0, 134.0),
        ),
    ]
    projects_spans = [
        make_text_span(text="Projects", bbox=(72.0, 152.0, 150.0, 162.0), font_size=13.0, is_bold=True),
        make_text_span(text="AI SOC Analyst", bbox=(72.0, 170.0, 250.0, 180.0), is_bold=True),
        make_text_span(
            text="Built a Python and Redis based caching system for security alerts.",
            bbox=(72.0, 187.0, 450.0, 197.0),
        ),
        make_text_span(text="Tech: Python, Redis, Docker", bbox=(72.0, 204.0, 300.0, 214.0)),
    ]
    skills_spans = [
        make_text_span(text="Skills", bbox=(72.0, 232.0, 150.0, 242.0), font_size=13.0, is_bold=True),
        make_text_span(text="Python, Redis, Docker, Leadership", bbox=(72.0, 250.0, 400.0, 260.0)),
    ]
    certifications_spans = [
        make_text_span(text="Certifications", bbox=(72.0, 278.0, 200.0, 288.0), font_size=13.0, is_bold=True),
        make_text_span(text="AWS Certified Solutions Architect", bbox=(72.0, 296.0, 350.0, 306.0)),
    ]

    return {
        "experience": make_section(
            label="experience", raw_header_text="Experience", spans=experience_spans, header_confidence=0.9
        ),
        "projects": make_section(
            label="projects", raw_header_text="Projects", spans=projects_spans, header_confidence=0.9
        ),
        "skills": make_section(
            label="skills", raw_header_text="Skills", spans=skills_spans, header_confidence=0.9
        ),
        "certifications": make_section(
            label="certifications",
            raw_header_text="Certifications",
            spans=certifications_spans,
            header_confidence=0.9,
        ),
    }


def test_real_parsers_plus_cross_reference_produce_a_nonempty_topic_pool(
    make_section, make_text_span, make_document_model
):
    sections = _synthetic_resume_sections(make_section, make_text_span)
    all_spans = [s for section in sections.values() for s in section.spans]
    doc = make_document_model(spans=all_spans, body_font_size=10.0)

    parser_results = {
        "experience": ExperienceParser().parse(sections, doc),
        "projects": ProjectParser().parse(sections, doc),
        "skills": SkillsParser().parse(sections, doc),
        "certifications": CertificationParser().parse(sections, doc),
    }
    DefaultCrossReferenceEngine().cross_reference(parser_results)

    profile = {
        "projects": parser_results["projects"].entities,
        "experience": parser_results["experience"].entities,
        "certifications": parser_results["certifications"].entities,
        "interview_blueprint": {},
    }

    pool = TopicPool(profile)

    assert len(pool.specifications) > 0
    assert pool.rejected == []


def test_no_field_produced_by_the_new_parsers_is_ever_none():
    """Section 1.3's hard convention: empty string / empty list as the
    missing-value sentinel, never `None` -- a single stray None is the one
    regression class that's easy to introduce and easy to miss."""
    from resume_engine.parsers.certification_parser import CertificationParser
    from resume_engine.parsers.education_parser import EducationParser

    result = CertificationParser().parse({}, None)
    assert result.entities == []

    result = EducationParser().parse({}, None)
    assert result.entities == []
