"""Phase 1 (parser generalization) — integration tests for the root-cause
fixes, exercised through the real section detector / parsers. Every case is a
GENERAL structural pattern (glyph-split heading, bulleted sub-point, wrapped
tech list, credential-ID line, ...), never a check tied to a specific resume.
"""

from __future__ import annotations

from resume_engine.document_model import DocumentModel, TextSpan
from resume_engine.parsers._entry_clustering import cluster_entries
from resume_engine.parsers.certification_parser import CertificationParser, _is_credential_noise
from resume_engine.parsers.contact_parser import ContactParser
from resume_engine.parsers.education_parser import EducationParser, _find_graduation_year, _is_secondary_entry
from resume_engine.parsers.project_parser import ProjectParser
from resume_engine.parsers.skills_parser import SkillsParser, _split_tokens
from resume_engine.pipeline import _absorb_repeated_unknown_entries, _group_sections_by_label
from resume_engine.sections import HeuristicSectionDetector, Section


def _span(text, y, *, bold=False, font=10.0):
    return TextSpan(text=text, bbox=(0.0, y, 300.0, y + 10.0), font_size=font, is_bold=bold, page_num=0)


def _line_spans(lines):
    """One span per logical line, stacked vertically so each is its own
    visual line. `lines` is a list of (text, bold, font)."""
    return [_span(text, i * 20.0, bold=bold, font=font) for i, (text, bold, font) in enumerate(lines)]


def _doc(spans, body_font_size=10.0):
    return DocumentModel(spans=spans, body_font_size=body_font_size)


def _detect_grouped(doc):
    return _group_sections_by_label(_absorb_repeated_unknown_entries(HeuristicSectionDetector().detect(doc)))


# ── Entry clustering: bullets / bold-in-bullet / wrapped tech ─────────────────

class TestEntryClustering:
    def test_bulleted_action_subpoints_do_not_start_entries(self):
        spans = _line_spans([
            ("Foo Platform | React, Node.js, Express", True, 11.0),
            ("• Developed a responsive web platform for events.", True, 10.0),
            ("• Implemented authentication and REST APIs.", True, 10.0),
        ])
        entries = cluster_entries(spans, body_font_size=10.0)
        assert len(entries) == 1
        assert entries[0].header_text.startswith("Foo Platform")

    def test_wrapped_technology_list_is_not_a_new_entry(self):
        # A title line ending mid-list (trailing comma) whose tech list wraps
        # onto a bold second line must not become a second project.
        spans = _line_spans([
            ("CharityConnect – Donation Platform | HTML, CSS, React,", True, 11.0),
            ("MySQL", True, 11.0),
            ("• Built a responsive platform.", True, 10.0),
        ])
        entries = cluster_entries(spans, body_font_size=10.0)
        assert len(entries) == 1

    def test_bulleted_titles_with_years_are_distinct_entries(self):
        # Some resumes mark each entry with a bullet + a year. These ARE
        # separate entries (distinguished from sub-points by not being
        # action-verb sentences and by carrying a year).
        spans = _line_spans([
            ("• RAG Research Assistant Agent 2026", True, 11.0),
            ("Developed an agentic assistant using LangGraph.", False, 9.0),
            ("• Interview Prep Tool 2025", True, 11.0),
            ("Proposes an AI-based interview system.", False, 9.0),
        ])
        entries = cluster_entries(spans, body_font_size=10.0)
        assert len(entries) == 2

    def test_consecutive_bold_header_lines_are_one_entry(self):
        # An institution line + a degree line, both bold and adjacent, are a
        # single multi-line entry header, not two entries.
        spans = _line_spans([
            ("PES University 2023 - 2027", True, 12.0),
            ("B.Tech in Computer Science", True, 12.0),
            ("GPA: 7.9", False, 9.0),
        ])
        entries = cluster_entries(spans, body_font_size=10.0)
        assert len(entries) == 1


# ── Section detection: glyph-split heading + no silent content loss ───────────

class TestSectionDetection:
    def test_glyph_split_heading_is_recognized(self):
        doc = _doc(_line_spans([
            ("T ECHNICAL   S KILLS", True, 12.0),
            ("Python, Java, React", False, 10.0),
        ]))
        labels = {s.label for s in HeuristicSectionDetector().detect(doc)}
        assert "skills" in labels

    def test_entry_content_after_header_is_not_dropped(self):
        # A bold institution/degree line right under EDUCATION must stay part
        # of the education section, not become an "unknown" section that is
        # silently discarded.
        doc = _doc(_line_spans([
            ("EDUCATION", True, 12.0),
            ("PES University 2023 - 2027", True, 12.0),
            ("B.Tech in Computer Science and Engineering", True, 12.0),
        ]))
        sections = _detect_grouped(doc)
        result = EducationParser().parse(sections, doc)
        assert len(result.entities) == 1
        assert "PES University" in result.entities[0]["institution"]
        assert result.entities[0]["degree"]

    def test_trailing_period_line_is_not_a_section_header(self):
        doc = _doc(_line_spans([
            ("PROJECTS", True, 12.0),
            ("Foo Tool | Python", True, 10.0),
            ("improve the preparation experience.", True, 10.0),  # wrapped sentence fragment
        ]))
        labels = [s.label for s in HeuristicSectionDetector().detect(doc)]
        assert "experience" not in labels


# ── Project parser: numbering stripped, tech tail parsed ──────────────────────

class TestProjectParser:
    def test_leading_numbering_is_stripped_and_tech_tail_parsed(self):
        section = Section(
            label="projects",
            raw_header_text="Projects",
            spans=_line_spans([
                ("Projects", True, 12.0),
                ("1. Chronos – Task System | FastAPI, Redis", True, 11.0),
                ("Built a distributed task system.", False, 9.0),
            ]),
            header_confidence=0.9,
        )
        result = ProjectParser().parse({"projects": section}, _doc(section.spans))
        assert len(result.entities) == 1
        assert result.entities[0]["title"] == "Chronos – Task System"
        assert "FastAPI" in result.entities[0]["technologies"]
        assert "Redis" in result.entities[0]["technologies"]


# ── Name extraction ──────────────────────────────────────────────────────────

class TestNameExtraction:
    def test_name_recovered_when_sharing_line_with_phone(self):
        section = Section(
            label="contact",
            raw_header_text="",
            spans=_line_spans([
                ("Jane Q Doe +1 555 123 4567", False, 18.0),
                ("jane.doe@example.com", False, 10.0),
            ]),
            header_confidence=1.0,
        )
        result = ContactParser().parse({"contact": section}, _doc(section.spans))
        assert result.entities[0]["candidate_name"] == "Jane Q Doe"

    def test_headline_banner_is_not_chosen_as_name(self):
        section = Section(
            label="contact",
            raw_header_text="",
            spans=_line_spans([
                ("AI Engineer GitHub Profile", False, 18.0),
                ("Priya Sharma", False, 14.0),
                ("priya@example.com", False, 10.0),
            ]),
            header_confidence=1.0,
        )
        result = ContactParser().parse({"contact": section}, _doc(section.spans))
        assert result.entities[0]["candidate_name"] == "Priya Sharma"


# ── Education: graduation year + secondary suppression ───────────────────────

class TestEducationDates:
    def test_explicit_range_uses_end_year(self):
        assert _find_graduation_year("2023 – 2027", "Bachelor of Technology") == "2027"

    def test_ongoing_degree_uses_start_plus_duration(self):
        assert _find_graduation_year("2023 - Present", "B.Tech") == "2027"
        assert _find_graduation_year("2023 - Present", "Master of Science") == "2025"

    def test_lone_expected_year_is_used_as_is(self):
        assert _find_graduation_year("Expected 2027", "B.Tech") == "2027"

    def test_single_year_unchanged(self):
        assert _find_graduation_year("2021", "") == "2021"

    def test_secondary_entry_detection(self):
        assert _is_secondary_entry("", "Ryan International School 2021 ICSE Grade 10")
        assert _is_secondary_entry("", "Some PU College 2nd PUC")
        assert not _is_secondary_entry("B.Tech", "PES University 2023 - 2027")

    def test_school_entries_suppressed_when_a_degree_exists(self):
        section = Section(
            label="education",
            raw_header_text="Education",
            spans=_line_spans([
                ("Education", True, 12.0),
                ("PES University 2023 - 2027", True, 11.0),
                ("B.Tech in Computer Science", True, 11.0),
                ("GPA 7.9", False, 9.0),
                ("Ryan International School 2021", True, 11.0),
                ("ICSE Grade 10", False, 9.0),
            ]),
            header_confidence=0.9,
        )
        result = EducationParser().parse({"education": section}, _doc(section.spans))
        assert len(result.entities) == 1
        assert "PES University" in result.entities[0]["institution"]


# ── Skills: prose exclusion ──────────────────────────────────────────────────

class TestSkillsProse:
    def test_non_skill_category_prose_is_excluded(self):
        text = "\n".join([
            "Languages: Python, Java, React",
            "Areas of Interest: applications of AI in aerospace and beyond",
            "further research into how it helps",
        ])
        tokens = [t.lower() for t in _split_tokens(text)]
        assert "python" in tokens
        assert "java" in tokens
        assert not any("aerospace" in t or "research" in t for t in tokens)

    def test_soft_skills_category_with_extra_spaces_is_excluded(self):
        text = "Languages: Python\nSoft   Skills:   Communication, Teamwork"
        tokens = [t.lower() for t in _split_tokens(text)]
        assert "python" in tokens
        assert "communication" not in tokens

    def test_long_prose_token_is_dropped(self):
        text = "Skills: Python, this is a long prose phrase that is not a skill at all"
        tokens = _split_tokens(text)
        assert "Python" in tokens
        assert all(len(t.split()) <= 6 for t in tokens)


# ── Certifications: ID lines excluded ────────────────────────────────────────

class TestCertificationNoise:
    def test_credential_id_lines_detected_as_noise(self):
        assert _is_credential_noise("Credential ID: UC-e382fa97-137e")
        assert _is_credential_noise("Services Credential ID: 15032016-202307-")
        assert _is_credential_noise("064")
        assert not _is_credential_noise("Full-Stack Web Development Bootcamp – Online")

    def test_certification_parser_drops_id_lines(self):
        section = Section(
            label="certifications",
            raw_header_text="Certifications",
            spans=_line_spans([
                ("Certifications", True, 12.0),
                ("Programming in C – Surekha IT", False, 10.0),
                ("Credential ID: 15032016-202307-", False, 10.0),
                ("064", False, 10.0),
            ]),
            header_confidence=0.9,
        )
        result = CertificationParser().parse({"certifications": section}, _doc(section.spans))
        assert any("Programming in C" in c for c in result.entities)
        assert not any("Credential" in c or c == "064" for c in result.entities)
