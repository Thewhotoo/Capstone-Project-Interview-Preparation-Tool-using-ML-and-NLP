"""Phase 1 (parser generalization) — unit tests for the shared, structural
text-normalization utilities. All cases are generic patterns, never keyed to
a specific resume."""

from __future__ import annotations

from resume_engine.text_normalization import (
    clean_text,
    contains_year,
    is_bare_date_line,
    is_open_list_end,
    looks_like_title,
    normalize_heading,
    normalize_title,
    repair_glyph_split,
    split_title_and_tech_tail,
    starts_with_action_verb,
    starts_with_bullet,
    starts_with_non_title_label,
    strip_leading_bullet,
    strip_leading_enumeration,
)


class TestGlyphSplitRepair:
    def test_two_word_all_caps_heading(self):
        assert repair_glyph_split("T ECHNICAL   S KILLS") == "TECHNICAL SKILLS"

    def test_single_word_heading(self):
        assert repair_glyph_split("E DUCATION") == "EDUCATION"

    def test_trailing_single_letter_run_is_glued(self):
        assert repair_glyph_split("A BOUT M E") == "ABOUT ME"

    def test_already_clean_heading_is_unchanged(self):
        assert repair_glyph_split("TECHNICAL SKILLS") == "TECHNICAL SKILLS"
        assert repair_glyph_split("Experience") == "Experience"

    def test_does_not_merge_ordinary_mixed_case_prose(self):
        # A single capital before a lowercase word is normal prose, never a
        # drop-cap artifact -- must be left alone.
        assert repair_glyph_split("A motivated learner") == "A motivated learner"
        assert repair_glyph_split("I used Redis") == "I used Redis"

    def test_normalize_heading_repairs_and_cleans(self):
        assert normalize_heading("P ROFILE   S UMMARY") == "PROFILE SUMMARY"


class TestBulletsAndEnumeration:
    def test_strip_leading_enumeration(self):
        assert strip_leading_enumeration("1. Chronos") == "Chronos"
        assert strip_leading_enumeration("2) Foo Bar") == "Foo Bar"
        assert strip_leading_enumeration("Chronos") == "Chronos"

    def test_strip_leading_bullet(self):
        assert strip_leading_bullet("• RAG Agent") == "RAG Agent"
        assert strip_leading_bullet("– Developed a thing") == "Developed a thing"
        assert strip_leading_bullet("- item") == "item"

    def test_starts_with_bullet(self):
        assert starts_with_bullet("• x")
        assert starts_with_bullet("–   y")
        assert not starts_with_bullet("Chronos")
        assert not starts_with_bullet("end-to-end pipeline")  # mid-word hyphen, not a bullet


class TestBodyLineSignals:
    def test_action_verb_detection(self):
        assert starts_with_action_verb("Developed an agentic RAG assistant")
        assert starts_with_action_verb("• Owned the module end to end")
        assert not starts_with_action_verb("RAG Research Assistant Agent")

    def test_non_title_label_detection(self):
        assert starts_with_non_title_label("Tools & technologies used: Python")
        assert starts_with_non_title_label("GitHub: my-repo")
        assert not starts_with_non_title_label("Chronos Distributed System")

    def test_open_list_end(self):
        assert is_open_list_end("HTML, CSS, JavaScript, React,")
        assert is_open_list_end("Foo |")
        assert not is_open_list_end("React and Node")


class TestTitleHelpers:
    def test_looks_like_title(self):
        assert looks_like_title("Chronos – Distributed Task System")
        assert not looks_like_title("developing a small tool")  # opens lowercase
        assert not looks_like_title(
            "Built and maintained a full-stack production service with clean modular code and tests."
        )  # a sentence

    def test_split_title_and_tech_tail(self):
        head, techs = split_title_and_tech_tail("Foo Platform | React, Node.js, Redis")
        assert head == "Foo Platform"
        assert techs == ["React", "Node.js", "Redis"]

    def test_split_title_and_tech_tail_no_pipe(self):
        head, techs = split_title_and_tech_tail("Foo Platform")
        assert head == "Foo Platform"
        assert techs == []

    def test_tech_tail_strips_icon_glyphs(self):
        _, techs = split_title_and_tech_tail("Foo | React, JWT \x8c \x87")
        assert techs == ["React", "JWT"]

    def test_normalize_title_strips_number_bullet_and_year(self):
        title, techs = normalize_title("1. Chronos � Distributed System | FastAPI, Redis")
        assert title == "Chronos - Distributed System"
        assert techs == ["FastAPI", "Redis"]

    def test_normalize_title_drops_trailing_year(self):
        title, _ = normalize_title("RAG Research Assistant Agent 2026")
        assert title == "RAG Research Assistant Agent"


class TestMisc:
    def test_contains_year(self):
        assert contains_year("Started 2023")
        assert not contains_year("no dates here")

    def test_is_bare_date_line(self):
        assert is_bare_date_line("2026")
        assert is_bare_date_line("2023 - Present")
        assert is_bare_date_line("2023 – 2027")
        assert not is_bare_date_line("Developed in 2023 a system")

    def test_clean_text_repairs_replacement_char(self):
        assert clean_text("Chronos � Distributed") == "Chronos - Distributed"
