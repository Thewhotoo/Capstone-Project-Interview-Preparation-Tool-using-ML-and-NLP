"""
Regression tests for the fixes made while integrating the Phase 1 engine
(resumeParser_integration.md §2, 2026-09-30). Each case is the minimal shape of
a problem seen on a real or golden-corpus resume; none uses resume-specific
text in the engine itself.
"""

from resume_engine.parsers._entry_clustering import _title_separator, cluster_entries
from resume_engine.parsers.certification_parser import _is_not_a_certification_name
from resume_engine.parsers.contact_parser import _extract_phone, _infer_candidate_name
from resume_engine.text_normalization import is_page_marker, reads_as_sentence, strip_date_ranges


def _lines(make_text_span, rows, font=10.0, pitch=14.0):
    """rows: list of (text, bold, font_size or None). One span per line, evenly spaced."""
    spans = []
    for i, (text, bold, size) in enumerate(rows):
        y = 100.0 + i * pitch
        spans.append(make_text_span(text=text, bbox=(72.0, y, 400.0, y + 10.0), font_size=size or font, is_bold=bold))
    return spans


def _headers(entries):
    return [e.header_text for e in entries]


# ── entry clustering ───────────────────────────────────────────────────────

def test_date_range_dash_is_not_a_title_separator(make_text_span):
    # "Role March, 2022 - March, 2025" then "Company - address": one job, not two.
    assert _title_separator("Software Developer March, 2022 - March, 2025") == ""
    assert _title_separator("Gravity Tech - 123 Anywhere St., Any City") == "-"
    spans = _lines(make_text_span, [
        ("Software Developer March, 2022 - March, 2025", True, 12.0),
        ("Gravity Tech - 123 Anywhere St., Any City", False, 10.0),
        ("Developed and maintained digital applications based on user requirements", False, 11.0),
    ])
    assert _headers(cluster_entries(spans, 11.0)) == ["Software Developer March, 2022 - March, 2025"]


def test_sentence_like_bullet_lines_do_not_start_entries(make_text_span):
    spans = _lines(make_text_span, [
        ("Software Engineer, at Fauget Company", True, 10.0),
        ("Built the logic for a streamlined platform of ad serving", False, 10.0),
        ("Conducted a test for software bugs and speed", False, 10.0),       # past-tense lead, wraps
        ("in its operation, fixing the bugs and recording", False, 10.0),
        ("Performed system analysis, debugging, and performance optimization", False, 10.0),
        ("Software Engineer, at Paucek Company", True, 10.0),
    ])
    assert _headers(cluster_entries(spans, 10.0)) == [
        "Software Engineer, at Fauget Company", "Software Engineer, at Paucek Company"]


def test_wrapped_continuation_is_not_a_project(make_text_span):
    spans = _lines(make_text_span, [
        ("FairEdge Data Agent - Enterprise NL-to-SQL Pipeline 2025", True, 10.0),
        ("Built a multi-agent system that lets non-technical teams query large datasets using no", False, 10.0),
        ("SQL knowledge required; deployed to a live enterprise HR analytics client", False, 10.0),
    ])
    assert len(cluster_entries(spans, 10.0)) == 1


def test_short_title_case_project_titles_still_split(make_text_span):
    # The Phase 1 behaviour the sentence rule must not undo: dateless, boldless
    # titles separated by a blank line (the engine's boundary signal for them).
    rows = ["Task Tracker", "A web app to track tasks with reminders", "Chat App", "Real time chat using websockets"]
    ys = [100.0, 114.0, 142.0, 156.0]   # blank line above "Chat App"
    spans = [make_text_span(text=t, bbox=(72.0, y, 400.0, y + 10.0), font_size=10.0) for t, y in zip(rows, ys)]
    assert _headers(cluster_entries(spans, 10.0)) == ["Task Tracker", "Chat App"]


def test_page_marker_is_not_an_entry(make_text_span):
    assert is_page_marker("Page 1") and is_page_marker("Page 2 of 3") and is_page_marker("1/2")
    assert not is_page_marker("Page Builder Plugin")
    spans = _lines(make_text_span, [
        ("Acme Corp, Senior Engineer, 2021-Present", False, 9.0),
        ("Owned the payments retry pipeline handling millions of transactions.", False, 9.0),
        ("Page 1", False, 8.0),
    ])
    assert _headers(cluster_entries(spans, 9.0)) == ["Acme Corp, Senior Engineer, 2021-Present"]


def test_glyph_only_line_does_not_split_an_education_entry(make_text_span):
    spans = _lines(make_text_span, [
        ("PES University", True, 10.0),
        ("•", False, 5.0),
        ("B.Tech — Electronics & Communications Engineering", False, 8.0),
    ])
    assert _headers(cluster_entries(spans, 8.0)) == ["PES University"]


def test_reads_as_sentence_leaves_titles_alone():
    assert not reads_as_sentence("Hotel Booking Website")
    assert not reads_as_sentence("Introduction to Data Engineering on Google Cloud")
    assert reads_as_sentence("Performed system analysis, debugging, and performance optimization")
    assert "2022" not in strip_date_ranges("Developer March, 2022 - March, 2025")


# ── certifications ─────────────────────────────────────────────────────────

def test_certification_lines_that_are_not_names_are_skipped():
    for junk, nxt in [("01 Jun 2052- present", ""), ("Giggling Platypus Co.", ""),
                      ("Designed and implemented a new", "microservice architecture"),
                      ("microservice architecture using Borcelle to", "")]:
        assert _is_not_a_certification_name(junk, nxt), junk
    for name in ["Cloud Certified", "AWS Certified Cloud Practitioner",
                 "Introduction to Data Engineering on Google Cloud", "Oracle Certified Java Programmer"]:
        assert not _is_not_a_certification_name(name), name


# ── contact ────────────────────────────────────────────────────────────────

def test_resume_suffix_does_not_hide_the_name():
    assert _infer_candidate_name([("Jordan Example - Resume", 16.0), ("jordan@example.com", 9.0)]) == "Jordan Example"
    assert _infer_candidate_name([("Resume - Asha Rao", 16.0)]) == "Asha Rao"


def test_letter_spaced_name_falls_back_to_printed_letters():
    assert _infer_candidate_name([("J U L I A N A S I L V A", 24.0), ("SYSTEM ENGINEER", 12.0)]) == "J U L I A N A S I L V A"


def test_phone_does_not_swallow_the_next_fields_number():
    assert _extract_phone("hello@x.com 123-456-7890 123 Anywhere St., Any City") == "123-456-7890"
    assert _extract_phone("+91 90000 12345") == "+91 90000 12345"


# ── experience header dates ────────────────────────────────────────────────

def test_printed_date_range_is_removed_before_role_company_split(make_text_span, make_document_model):
    from resume_engine.parsers.experience_parser import ExperienceParser
    from resume_engine.sections import Section
    spans = _lines(make_text_span, [
        ("Experience", True, 14.0),
        ("Software Developer March, 2022 - March, 2025", True, 12.0),
        ("Developed and maintained digital applications based on user requirements", False, 11.0),
    ])
    section = Section(label="experience", spans=spans, header_confidence=1.0, raw_header_text="Experience")
    entity = ExperienceParser().parse({"experience": section}, make_document_model(spans=spans)).entities[0]
    assert "2022" not in entity["role"] and "2025" not in entity["role"]
    assert "2025" not in entity.get("company", "")


def test_month_comma_year_dates_are_recognized():
    from datetime import date
    from resume_engine.dates import parse_date_range
    r = parse_date_range("Software Developer March, 2022 - March, 2025")
    assert r is not None and r.start == date(2022, 3, 1) and r.end == date(2025, 3, 1)
    assert parse_date_range("Engineer 2021") is None


def test_bracketed_tech_group_in_title_tail_is_not_split_mid_bracket():
    from resume_engine.text_normalization import normalize_title
    title, techs = normalize_title(
        "AI Resume-Grounded Interview Platform | Python, Flask, Hugging Face Transformers (DeBERTa-v3, Qwen2.5),")
    assert title == "AI Resume-Grounded Interview Platform"
    assert techs == ["Python", "Flask", "Hugging Face Transformers", "DeBERTa-v3", "Qwen2.5"]
