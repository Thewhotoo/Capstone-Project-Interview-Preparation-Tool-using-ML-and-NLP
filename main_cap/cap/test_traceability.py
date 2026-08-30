"""
Tests for traceability.py — Phase 1 of ResumeDiscussion_v2 (Chapters 8.4,
10.3, 11).

Covers the "substance gate": does a cited project/experience/certification
origin actually exist on THIS profile.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import sample_profile_dict
from traceability import (
    TraceabilityCheckResult,
    find_certification_by_name,
    find_experience_by_label,
    find_project_by_title,
    validate_certification_exists,
    validate_experience_exists,
    validate_project_exists,
    validate_technical_topic_origin,
)


class TestFindProjectByTitle(unittest.TestCase):
    def setUp(self):
        self.projects = sample_profile_dict()["projects"]

    def test_exact_match(self):
        found = find_project_by_title("Resume Discussion Platform", self.projects)
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "Resume Discussion Platform")

    def test_case_insensitive_match(self):
        found = find_project_by_title("resume discussion platform", self.projects)
        self.assertIsNotNone(found)

    def test_no_match(self):
        found = find_project_by_title("Order Management System", self.projects)
        self.assertIsNone(found)

    def test_empty_title_no_match(self):
        self.assertIsNone(find_project_by_title("", self.projects))

    def test_accepts_pydantic_model_entries(self):
        class FakeProject:
            def __init__(self, title):
                self.title = title

        found = find_project_by_title("X", [FakeProject("X"), FakeProject("Y")])
        self.assertIsNotNone(found)


class TestFindExperienceByLabel(unittest.TestCase):
    def setUp(self):
        self.experiences = sample_profile_dict()["experience"]

    def test_match_by_role_only(self):
        found = find_experience_by_label("Software Engineering Intern", self.experiences)
        self.assertIsNotNone(found)

    def test_match_by_role_at_company(self):
        found = find_experience_by_label(
            "Software Engineering Intern at Acme Corp", self.experiences
        )
        self.assertIsNotNone(found)

    def test_no_match(self):
        found = find_experience_by_label("Marketing Lead", self.experiences)
        self.assertIsNone(found)


class TestFindCertificationByName(unittest.TestCase):
    def setUp(self):
        self.certs = sample_profile_dict()["certifications"]

    def test_match(self):
        self.assertIsNotNone(find_certification_by_name("AWS Certified Cloud Practitioner", self.certs))

    def test_no_match(self):
        self.assertIsNone(find_certification_by_name("Azure Fundamentals", self.certs))


class TestValidateExists(unittest.TestCase):
    def setUp(self):
        profile = sample_profile_dict()
        self.projects = profile["projects"]
        self.experiences = profile["experience"]
        self.certs = profile["certifications"]

    def test_validate_project_exists_true(self):
        result = validate_project_exists("Resume Discussion Platform", self.projects)
        self.assertIsInstance(result, TraceabilityCheckResult)
        self.assertTrue(result.ok)
        self.assertTrue(result.reason)

    def test_validate_project_exists_false(self):
        result = validate_project_exists("Nonexistent Project", self.projects)
        self.assertFalse(result.ok)
        self.assertIn("no project titled", result.reason)

    def test_validate_experience_exists_true(self):
        result = validate_experience_exists("Software Engineering Intern", self.experiences)
        self.assertTrue(result.ok)

    def test_validate_experience_exists_false(self):
        result = validate_experience_exists("Nonexistent Role", self.experiences)
        self.assertFalse(result.ok)

    def test_validate_certification_exists_true(self):
        result = validate_certification_exists("AWS Certified Cloud Practitioner", self.certs)
        self.assertTrue(result.ok)

    def test_validate_certification_exists_false(self):
        result = validate_certification_exists("Nonexistent Cert", self.certs)
        self.assertFalse(result.ok)


class TestValidateTechnicalTopicOrigin(unittest.TestCase):
    def setUp(self):
        profile = sample_profile_dict()
        self.projects = profile["projects"]
        self.experiences = profile["experience"]

    def test_valid_project_origin(self):
        result = validate_technical_topic_origin(
            "Resume Discussion Platform", "", self.projects, self.experiences
        )
        self.assertTrue(result.ok)

    def test_valid_experience_origin(self):
        result = validate_technical_topic_origin(
            "", "Software Engineering Intern", self.projects, self.experiences
        )
        self.assertTrue(result.ok)

    def test_nonexistent_project_origin_rejected(self):
        result = validate_technical_topic_origin(
            "Order Management System", "", self.projects, self.experiences
        )
        self.assertFalse(result.ok)

    def test_nonexistent_experience_origin_rejected(self):
        result = validate_technical_topic_origin(
            "", "Marketing Lead", self.projects, self.experiences
        )
        self.assertFalse(result.ok)

    def test_both_set_is_malformed_and_rejected(self):
        result = validate_technical_topic_origin(
            "Resume Discussion Platform",
            "Software Engineering Intern",
            self.projects,
            self.experiences,
        )
        self.assertFalse(result.ok)
        self.assertIn("malformed", result.reason)

    def test_neither_set_is_malformed_and_rejected(self):
        result = validate_technical_topic_origin("", "", self.projects, self.experiences)
        self.assertFalse(result.ok)
        self.assertIn("malformed", result.reason)


if __name__ == "__main__":
    unittest.main()
