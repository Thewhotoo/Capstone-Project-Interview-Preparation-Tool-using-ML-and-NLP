"""Smoke tests for Milestone 3's new gazetteers -- non-empty, no
duplicates, and (loosely) that the well-known entries a test resume would
use are actually present."""

from resume_engine.concept_gazetteer import CONCEPTS
from resume_engine.job_title_gazetteer import JOB_TITLES
from resume_engine.technology_gazetteer import TECHNOLOGIES


def test_technology_gazetteer_is_non_empty_and_has_no_duplicates():
    assert len(TECHNOLOGIES) > 20
    assert len(TECHNOLOGIES) == len(set(TECHNOLOGIES))
    assert "Python" in TECHNOLOGIES
    assert "React" in TECHNOLOGIES


def test_job_title_gazetteer_is_non_empty_and_has_no_duplicates():
    assert len(JOB_TITLES) > 10
    assert len(JOB_TITLES) == len(set(JOB_TITLES))
    assert "Software Engineer" in JOB_TITLES


def test_concept_gazetteer_is_non_empty_and_has_no_duplicates():
    assert len(CONCEPTS) > 10
    assert len(CONCEPTS) == len(set(CONCEPTS))
    assert "Microservices" in CONCEPTS
