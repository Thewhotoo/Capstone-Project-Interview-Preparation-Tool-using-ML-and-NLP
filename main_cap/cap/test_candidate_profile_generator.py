"""
Tests for the Candidate Profile Generator.

Tests:
- Pydantic model construction and validation
- PDF text extraction (PyMuPDF) with all sample resumes
- Native structured output integration with Gemini (mocked)
- profile_to_frontend_format with nested schema
- End-to-end: extract -> generate -> format

Run:
    python -m pytest main_cap/cap/test_candidate_profile_generator.py -v
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from candidate_profile_generator import (
    CandidateProfile,
    ContactDetails,
    EducationEntry,
    ExperienceEntry,
    ProjectEntry,
    InterviewBlueprint,
    extract_text_from_pdf,
    generate_candidate_profile,
    profile_to_frontend_format,
    _fuzzy_match_domain,
    _normalise_level,
    _clean_string_list,
    _calculate_total_years,
    _extract_json_object,
    _parse_response_text,
    DOMAIN_LABELS,
)

# ── Paths ──────────────────────────────────────────────────────────────────

SAMPLE_RESUMES_DIR = os.path.join(
    os.path.expanduser("~"), "Downloads", "sample_resumes"
)

LEGACY_RESUME_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "parser_tests", "resumes", "010.pdf"
)


# ═════════════════════════════════════════════════════════════════════════════
# Pydantic Model Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestCandidateProfileModel(unittest.TestCase):
    """Verify Pydantic models construct correctly with defaults and data."""

    def test_minimal_profile(self):
        p = CandidateProfile()
        self.assertEqual(p.candidate_name, "")
        self.assertEqual(p.predicted_domain, "Software Engineering")
        self.assertEqual(p.experience_level, "Intermediate")
        self.assertEqual(p.confidence, 0.5)
        self.assertEqual(p.skills, [])
        self.assertEqual(p.education, [])
        self.assertEqual(p.experience, [])
        self.assertEqual(p.projects, [])
        self.assertEqual(p.certifications, [])
        self.assertIsInstance(p.contact_details, ContactDetails)
        self.assertIsInstance(p.interview_blueprint, InterviewBlueprint)

    def test_full_profile(self):
        data = {
            "candidate_name": "Alice Smith",
            "contact_details": {
                "email": "alice@example.com",
                "phone": "+1-555-0100",
                "linkedin": "linkedin.com/in/alice",
                "location": "NYC",
            },
            "skills": ["Python", "Docker"],
            "education": [
                {"degree": "B.S.", "major": "CS", "institution": "MIT", "graduation_year": "2020"}
            ],
            "experience": [
                {"company": "Acme", "role": "SWE", "duration": "2020 - Present", "summary": "Backend"}
            ],
            "projects": [
                {"title": "ChatBot", "description": "NLP bot", "technologies": ["Python", "spaCy"]}
            ],
            "certifications": ["AWS SAA"],
            "predicted_domain": "Software Engineering",
            "experience_level": "Advanced",
            "confidence": 0.92,
            "interview_blueprint": {
                "resume_verification_topics": ["AWS certification"],
                "technical_topics": ["distributed systems", "system design"],
                "starting_difficulty": "hard",
                "estimated_strengths": ["cloud architecture"],
                "estimated_weaknesses": ["frontend frameworks"],
            },
            "resume_summary": "Senior SWE with cloud expertise.",
        }
        p = CandidateProfile.model_validate(data)
        self.assertEqual(p.candidate_name, "Alice Smith")
        self.assertEqual(p.contact_details.email, "alice@example.com")
        self.assertEqual(p.contact_details.linkedin, "linkedin.com/in/alice")
        self.assertEqual(len(p.skills), 2)
        self.assertEqual(p.education[0].institution, "MIT")
        self.assertEqual(p.experience[0].company, "Acme")
        self.assertEqual(p.projects[0].technologies, ["Python", "spaCy"])
        self.assertEqual(p.interview_blueprint.starting_difficulty, "hard")
        self.assertEqual(len(p.interview_blueprint.technical_topics), 2)
        self.assertAlmostEqual(p.confidence, 0.92)

    def test_model_dump_roundtrip(self):
        p = CandidateProfile(candidate_name="Bob", skills=["Go"])
        d = p.model_dump()
        p2 = CandidateProfile.model_validate(d)
        self.assertEqual(p2.candidate_name, "Bob")
        self.assertEqual(p2.skills, ["Go"])


class TestInterviewBlueprint(unittest.TestCase):
    def test_defaults(self):
        ib = InterviewBlueprint()
        self.assertEqual(ib.resume_verification_topics, [])
        self.assertEqual(ib.technical_topics, [])
        self.assertEqual(ib.starting_difficulty, "intermediate")
        self.assertEqual(ib.estimated_strengths, [])
        self.assertEqual(ib.estimated_weaknesses, [])


# ═════════════════════════════════════════════════════════════════════════════
# PDF Text Extraction Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractTextFromPdf(unittest.TestCase):
    """Test extract_text_from_pdf with every resume in Downloads/sample_resumes/."""

    @classmethod
    def setUpClass(cls):
        cls.resumes = []
        if os.path.isdir(SAMPLE_RESUMES_DIR):
            for fname in sorted(os.listdir(SAMPLE_RESUMES_DIR)):
                if fname.lower().endswith(".pdf"):
                    cls.resumes.append(os.path.join(SAMPLE_RESUMES_DIR, fname))
        # Also include legacy test resume
        if os.path.isfile(LEGACY_RESUME_PATH):
            cls.resumes.append(LEGACY_RESUME_PATH)

    def test_each_resume_extracts_text(self):
        """Every available resume must produce meaningful text."""
        self.assertGreater(len(self.resumes), 0, "No resume PDFs found for testing")
        for resume_path in self.resumes:
            with self.subTest(resume=os.path.basename(resume_path)):
                text = extract_text_from_pdf(resume_path)
                self.assertIsInstance(text, str)
                self.assertGreater(len(text), 50,
                    f"Text too short from {os.path.basename(resume_path)}")
                # Most resumes will contain at least some letters
                self.assertTrue(any(c.isalpha() for c in text),
                    f"No alphabetic content from {os.path.basename(resume_path)}")

    def test_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            extract_text_from_pdf("/nonexistent/path.pdf")


class TestBlockFallback(unittest.TestCase):
    """Test the _needs_block_fallback heuristic."""

    def test_short_text_triggers_fallback(self):
        from candidate_profile_generator import _needs_block_fallback
        self.assertTrue(_needs_block_fallback("short"))

    def test_empty_text_triggers_fallback(self):
        from candidate_profile_generator import _needs_block_fallback
        self.assertTrue(_needs_block_fallback(""))

    def test_normal_text_no_fallback(self):
        from candidate_profile_generator import _needs_block_fallback
        text = (
            "John Doe\n"
            "Software Engineer at Acme Corp\n"
            "Experience building distributed systems and microservices\n"
            "Skills: Python, Go, Kubernetes, Docker\n"
            "Education: B.S. Computer Science, MIT 2020\n"
            "This is a longer line that represents normal paragraph text"
        )
        self.assertFalse(_needs_block_fallback(text))


# ═════════════════════════════════════════════════════════════════════════════
# Post-processing Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFuzzyMatchDomain(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(_fuzzy_match_domain("Software Engineering"), "Software Engineering")

    def test_case_insensitive(self):
        self.assertEqual(_fuzzy_match_domain("software engineering"), "Software Engineering")

    def test_fuzzy_partial(self):
        self.assertEqual(_fuzzy_match_domain("data sci"), "Data Science")

    def test_unknown_defaults(self):
        self.assertEqual(_fuzzy_match_domain("Quantum Physics"), "Software Engineering")

    def test_empty(self):
        self.assertEqual(_fuzzy_match_domain(""), "Software Engineering")


class TestNormaliseLevel(unittest.TestCase):
    def test_valid_levels(self):
        self.assertEqual(_normalise_level("Beginner"), "Beginner")
        self.assertEqual(_normalise_level("Intermediate"), "Intermediate")
        self.assertEqual(_normalise_level("Advanced"), "Advanced")

    def test_fuzzy_senior(self):
        self.assertEqual(_normalise_level("senior"), "Advanced")

    def test_fuzzy_junior(self):
        self.assertEqual(_normalise_level("entry-level"), "Beginner")

    def test_unknown(self):
        self.assertEqual(_normalise_level("whatever"), "Intermediate")

    def test_empty(self):
        self.assertEqual(_normalise_level(""), "Intermediate")


class TestCleanStringList(unittest.TestCase):
    def test_filters_empty(self):
        self.assertEqual(_clean_string_list(["a", "", "b", None, "c"]), ["a", "b", "c"])

    def test_empty_list(self):
        self.assertEqual(_clean_string_list([]), [])


class TestCalculateTotalYears(unittest.TestCase):
    def test_with_dict_entries(self):
        exps = [
            {"duration": "2018 - 2020"},
            {"duration": "2020 - Present"},
        ]
        years = _calculate_total_years(exps)
        self.assertGreaterEqual(years, 6)  # 2018 to 2026

    def test_empty(self):
        self.assertEqual(_calculate_total_years([]), 0)

    def test_single_year(self):
        self.assertEqual(_calculate_total_years([{"duration": "2023"}]), 0)


# ═════════════════════════════════════════════════════════════════════════════
# JSON Extraction Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestExtractJsonObject(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(_extract_json_object('{"a": 1}'), '{"a": 1}')

    def test_with_surrounding_text(self):
        result = _extract_json_object('Here:\n{"a": 1}\nDone.')
        self.assertEqual(result, '{"a": 1}')

    def test_nested(self):
        raw = '{"a": {"b": [1, 2]}, "c": "x"}'
        self.assertEqual(_extract_json_object(raw), raw)

    def test_no_braces(self):
        self.assertIsNone(_extract_json_object("no json here"))

    def test_unclosed(self):
        self.assertIsNone(_extract_json_object('{"a": 1'))


class TestParseResponseText(unittest.TestCase):
    def test_valid_json(self):
        data = CandidateProfile(candidate_name="Test", skills=["X"])
        raw = data.model_dump_json()
        result = _parse_response_text(raw)
        self.assertEqual(result.candidate_name, "Test")

    def test_fenced_json(self):
        data = CandidateProfile(candidate_name="Fenced")
        raw = f"```json\n{data.model_dump_json()}\n```"
        result = _parse_response_text(raw)
        self.assertEqual(result.candidate_name, "Fenced")

    def test_garbage_raises(self):
        with self.assertRaises(RuntimeError):
            _parse_response_text("not json at all")


# ═════════════════════════════════════════════════════════════════════════════
# Frontend Format Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestProfileToFrontendFormat(unittest.TestCase):
    """Test profile_to_frontend_format with the new nested schema."""

    def _full_profile_dict(self) -> dict:
        return CandidateProfile(
            candidate_name="Shubham Mookim",
            contact_details=ContactDetails(
                email="shubhammookim@gmail.com",
                phone="+918296461220",
            ),
            predicted_domain="Software Engineering",
            experience_level="Intermediate",
            confidence=0.87,
            skills=["Python", "FastAPI", "Docker", "AWS"],
            education=[
                EducationEntry(degree="B.Tech", major="Computer Science", institution="IIT", graduation_year="2018")
            ],
            experience=[
                ExperienceEntry(company="Acme", role="SDE", duration="2018 - 2020", summary="Backend"),
                ExperienceEntry(company="Globex", role="Senior SDE", duration="2020 - Present", summary="Full stack"),
            ],
            projects=[
                ProjectEntry(
                    title="AI SOC Analyst",
                    summary="Built an AI-powered SOC analyst using LangGraph for agent coordination.",
                    technologies=["Python", "LangGraph", "RAG", "Docker"],
                    concepts=["RAG", "Agent Orchestration", "Vector Databases"],
                    interview_seeds=["Why LangGraph?", "RAG architecture", "Agent coordination"],
                ),
                ProjectEntry(
                    title="Real-time Dashboard",
                    summary="Real-time analytics dashboard with Redis caching.",
                    technologies=["FastAPI", "Redis", "WebSocket"],
                    concepts=["Caching", "WebSockets", "Microservices"],
                    interview_seeds=["Redis caching strategy", "WebSocket design"],
                ),
            ],
            certifications=["AWS SAA"],
            interview_blueprint=InterviewBlueprint(
                technical_topics=["system design", "APIs"],
            ),
            resume_summary="Experienced SWE.",
        ).model_dump()

    def test_basic_mapping(self):
        f = profile_to_frontend_format(self._full_profile_dict())
        self.assertEqual(f["status"], "success")
        self.assertEqual(f["name"], "Shubham Mookim")
        self.assertEqual(f["email"], "shubhammookim@gmail.com")
        self.assertEqual(f["phone"], "+918296461220")
        self.assertEqual(f["predicted_domain"], "Software Engineering")
        self.assertEqual(f["quiz_domain"], "Software Engineer")
        self.assertEqual(f["confidence"], 0.87)
        self.assertEqual(f["skills"], ["Python", "FastAPI", "Docker", "AWS"])

    def test_experience_years(self):
        f = profile_to_frontend_format(self._full_profile_dict())
        self.assertEqual(f["experience"]["years"], 8)  # 2026 - 2018
        self.assertEqual(f["experience"]["level"], "Mid")

    def test_projects_list(self):
        f = profile_to_frontend_format(self._full_profile_dict())
        self.assertEqual(len(f["projects"]), 2)
        self.assertEqual(f["projects"][0]["title"], "AI SOC Analyst")
        self.assertIn("LangGraph", f["projects"][0]["technologies"])
        self.assertIn("RAG", f["projects"][0]["concepts"])
        self.assertIn("Why LangGraph?", f["projects"][0]["interview_seeds"])
        self.assertGreater(len(f["projects"][0]["summary"]), 10)

    def test_focus_topics_from_blueprint(self):
        f = profile_to_frontend_format(self._full_profile_dict())
        self.assertIn("system design", f["focus_topics"])
        self.assertIn("APIs", f["focus_topics"])

    def test_quiz_domain_mapping(self):
        tests = {
            "Software Engineering": "Software Engineer",
            "Data Science": "Data Scientist",
            "Cybersecurity": "Network Engineer",
            "Finance": "Database Engineer",
            "Healthcare": "Software Engineer",
        }
        for domain, expected in tests.items():
            p = self._full_profile_dict()
            p["predicted_domain"] = domain
            f = profile_to_frontend_format(p)
            self.assertEqual(f["quiz_domain"], expected, msg=f"Domain {domain}")

    def test_empty_experience_estimates_from_level(self):
        p = self._full_profile_dict()
        p["experience"] = []
        for level, expected in [("Beginner", 1), ("Intermediate", 3), ("Advanced", 7)]:
            p["experience_level"] = level
            f = profile_to_frontend_format(p)
            self.assertEqual(f["experience"]["years"], expected, msg=f"Level {level}")

    def test_detail_fields(self):
        f = profile_to_frontend_format(self._full_profile_dict())
        self.assertEqual(len(f["experience_detail"]), 2)
        self.assertEqual(f["experience_detail"][0]["company"], "Acme")
        # projects is now a list of project dicts (replaces projects_detail)
        self.assertEqual(len(f["projects"]), 2)
        self.assertEqual(f["projects"][0]["title"], "AI SOC Analyst")

    def test_education_serialised(self):
        f = profile_to_frontend_format(self._full_profile_dict())
        self.assertEqual(len(f["education"]), 1)
        self.assertEqual(f["education"][0]["degree"], "B.Tech")

    def test_flat_dict_backward_compat(self):
        """profile_to_frontend_format must also work with the old flat dict format."""
        flat = {
            "candidate_name": "Old Format",
            "email": "old@example.com",
            "phone": "555-0000",
            "predicted_domain": "Data Science",
            "experience_level": "Advanced",
            "confidence": 0.7,
            "skills": ["R"],
            "experience": [],
            "projects": [],
            "certifications": [],
            "focus_topics": ["ML"],
            "resume_summary": "Old.",
        }
        f = profile_to_frontend_format(flat)
        self.assertEqual(f["name"], "Old Format")
        self.assertEqual(f["email"], "old@example.com")
        self.assertEqual(f["quiz_domain"], "Data Scientist")
        self.assertEqual(f["focus_topics"], ["ML"])


# ═════════════════════════════════════════════════════════════════════════════
# Integration Test with Real Resume + Mocked Gemini
# ═════════════════════════════════════════════════════════════════════════════


class TestEndToEndWithMockedGemini(unittest.TestCase):
    """
    Extract text from real PDF -> call generate_candidate_profile with mocked
    Gemini -> verify full pipeline produces valid CandidateProfile dict.
    """

    @classmethod
    def setUpClass(cls):
        cls.resume_files = []
        if os.path.isdir(SAMPLE_RESUMES_DIR):
            for fname in sorted(os.listdir(SAMPLE_RESUMES_DIR)):
                if fname.lower().endswith(".pdf"):
                    cls.resume_files.append(os.path.join(SAMPLE_RESUMES_DIR, fname))

    def _patch_genai(self):
        """Context manager that mocks google.genai so the SDK import succeeds."""
        mock_genai = MagicMock()
        mock_types = MagicMock()
        # Make GenerateContentConfig store its kwargs so response_schema is inspectable
        mock_types.GenerateContentConfig.side_effect = lambda **kw: type(
            "_Cfg", (), kw
        )()
        return patch.dict("sys.modules", {
            "google": mock_genai,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        })

    def test_generate_with_mocked_gemini(self):
        """Verify the pipeline works end-to-end with mocked Gemini responses."""
        if not self.resume_files:
            self.skipTest("No sample resumes found")

        mock_profile = CandidateProfile(
            candidate_name="Test Candidate",
            contact_details=ContactDetails(email="test@test.com", phone="555-0100"),
            skills=["Python", "Docker"],
            education=[EducationEntry(degree="B.S.", major="CS", institution="MIT", graduation_year="2020")],
            experience=[ExperienceEntry(company="Acme", role="SWE", duration="2020 - Present", summary="Backend")],
            projects=[
                ProjectEntry(
                    title="TestProject",
                    summary="A test project.",
                    technologies=["Python"],
                    concepts=["Testing"],
                    interview_seeds=["Why testing?"],
                ),
            ],
            certifications=[],
            predicted_domain="Software Engineering",
            experience_level="Intermediate",
            confidence=0.8,
            interview_blueprint=InterviewBlueprint(
                technical_topics=["distributed systems", "API design"],
                starting_difficulty="intermediate",
                estimated_strengths=["Python"],
                estimated_weaknesses=["frontend"],
            ),
            resume_summary="Test candidate.",
        )

        # Mock the genai client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed = mock_profile
        mock_client.models.generate_content.return_value = mock_response

        for resume_path in self.resume_files:
            with self.subTest(resume=os.path.basename(resume_path)):
                text = extract_text_from_pdf(resume_path)
                self.assertGreater(len(text), 50)

                with self._patch_genai(), \
                     patch("candidate_profile_generator._genai_client", mock_client), \
                     patch("candidate_profile_generator._get_genai_client", return_value=mock_client):
                    profile_dict = generate_candidate_profile(text)

                # Validate structure
                self.assertIsInstance(profile_dict, dict)
                self.assertEqual(profile_dict["candidate_name"], "Test Candidate")
                self.assertIn("contact_details", profile_dict)
                self.assertIn("interview_blueprint", profile_dict)
                self.assertEqual(profile_dict["predicted_domain"], "Software Engineering")
                self.assertEqual(profile_dict["experience_level"], "Intermediate")

                # Verify Gemini was called exactly once
                self.assertEqual(mock_client.models.generate_content.call_count, 1,
                    "Gemini should be called exactly once per resume")

                mock_client.models.generate_content.reset_mock()

                # Verify frontend format conversion works
                frontend = profile_to_frontend_format(profile_dict)
                self.assertEqual(frontend["status"], "success")
                self.assertEqual(frontend["name"], "Test Candidate")
                self.assertTrue(
                    "system design" in frontend["focus_topics"] or
                    "distributed systems" in frontend["focus_topics"]
                )
                # Verify projects have new fields
                self.assertEqual(len(frontend["projects"]), 1)
                self.assertIn("technologies", frontend["projects"][0])
                self.assertIn("concepts", frontend["projects"][0])
                self.assertIn("interview_seeds", frontend["projects"][0])

    def test_gemini_called_once_per_resume(self):
        """Explicitly verify single Gemini call count across all resumes."""
        if not self.resume_files:
            self.skipTest("No sample resumes found")

        mock_profile = CandidateProfile(
            candidate_name="Once",
            skills=["Python"],
            projects=[ProjectEntry(title="P", summary="s", technologies=["Python"], concepts=["c"], interview_seeds=["t"])],
            predicted_domain="Software Engineering",
            experience_level="Intermediate",
        )

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.parsed = mock_profile
        mock_client.models.generate_content.return_value = mock_response

        for resume_path in self.resume_files:
            text = extract_text_from_pdf(resume_path)
            with self._patch_genai(), \
                 patch("candidate_profile_generator._genai_client", mock_client), \
                 patch("candidate_profile_generator._get_genai_client", return_value=mock_client):
                generate_candidate_profile(text)

            # Verify exactly one Gemini call was made
            self.assertEqual(mock_client.models.generate_content.call_count, 1,
                f"Gemini should be called exactly once for {os.path.basename(resume_path)}")

            # Verify the call had model, contents, and config kwargs
            call_kwargs = mock_client.models.generate_content.call_args.kwargs
            self.assertIn("model", call_kwargs)
            self.assertEqual(call_kwargs["model"], "gemini-2.5-flash")
            self.assertIn("contents", call_kwargs)
            self.assertIn("config", call_kwargs)

            mock_client.models.generate_content.reset_mock()


# ═════════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestErrorHandling(unittest.TestCase):
    def test_empty_text_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            generate_candidate_profile("")
        self.assertIn("too short", str(ctx.exception))

    def test_whitespace_only_raises(self):
        with self.assertRaises(RuntimeError):
            generate_candidate_profile("   \n  \n  ")

    def test_no_api_key_raises(self):
        with patch("candidate_profile_generator._get_genai_client",
                    side_effect=RuntimeError(
                        "GEMINI_API_KEY environment variable is not set. "
                        "Please set it to your Google AI Studio API key."
                    )):
            with self.assertRaises(RuntimeError) as ctx:
                generate_candidate_profile("Some resume text " * 10)
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))


class TestZeroSkillsRetry(unittest.TestCase):
    """Verify that generate_candidate_profile retries when Gemini returns skills=0."""

    def _patch_genai(self):
        mock_genai = MagicMock()
        mock_types = MagicMock()
        return patch.dict("sys.modules", {
            "google": mock_genai,
            "google.genai": mock_genai,
            "google.genai.types": mock_types,
        })

    def test_retry_triggered_on_zero_skills(self):
        """First call returns 0 skills, retry returns skills — should succeed."""
        zero_skills_profile = CandidateProfile(
            candidate_name="NoSkills",
            skills=[],
            predicted_domain="Software Engineering",
            experience_level="Intermediate",
        )
        fixed_profile = CandidateProfile(
            candidate_name="NoSkills",
            skills=["Python", "Docker", "Kubernetes"],
            predicted_domain="Software Engineering",
            experience_level="Intermediate",
        )

        mock_client = MagicMock()
        resp1 = MagicMock()
        resp1.parsed = zero_skills_profile
        resp2 = MagicMock()
        resp2.parsed = fixed_profile
        mock_client.models.generate_content.side_effect = [resp1, resp2]

        with self._patch_genai(), \
             patch("candidate_profile_generator._get_genai_client", return_value=mock_client):
            result = generate_candidate_profile("Software engineer with Python experience " * 20)

        self.assertEqual(len(result["skills"]), 3)
        self.assertEqual(mock_client.models.generate_content.call_count, 2)

    def test_no_retry_when_skills_present(self):
        """First call returns skills — no retry should happen."""
        good_profile = CandidateProfile(
            candidate_name="HasSkills",
            skills=["Python"],
            predicted_domain="Software Engineering",
        )

        mock_client = MagicMock()
        resp = MagicMock()
        resp.parsed = good_profile
        mock_client.models.generate_content.return_value = resp

        with self._patch_genai(), \
             patch("candidate_profile_generator._get_genai_client", return_value=mock_client):
            result = generate_candidate_profile("Python developer with experience " * 20)

        self.assertEqual(len(result["skills"]), 1)
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    def test_retry_still_zero_keeps_profile(self):
        """Both calls return 0 skills — profile is kept as-is (non-technical resume)."""
        zero_skills = CandidateProfile(
            candidate_name="Artist",
            skills=[],
            predicted_domain="Marketing",
        )

        mock_client = MagicMock()
        resp = MagicMock()
        resp.parsed = zero_skills
        mock_client.models.generate_content.return_value = resp

        with self._patch_genai(), \
             patch("candidate_profile_generator._get_genai_client", return_value=mock_client):
            result = generate_candidate_profile("Creative director with 10 years experience " * 20)

        self.assertEqual(result["skills"], [])
        self.assertEqual(mock_client.models.generate_content.call_count, 2)


if __name__ == "__main__":
    unittest.main()
