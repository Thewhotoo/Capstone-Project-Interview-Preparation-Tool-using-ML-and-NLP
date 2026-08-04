"""Tests for the Milestone 7 feature flag / backend selector added to
candidate_profile_generator.py -- Phase 2 of the cutover. Kept as its own
file (not appended to test_candidate_profile_generator.py) since it tests
new Milestone 7 surface, not the existing Gemini-path tests."""

import os

import pytest

import candidate_profile_generator as cpg


@pytest.fixture(autouse=True)
def _clean_env():
    original = os.environ.pop("CAP_RESUME_PARSER", None)
    yield
    if original is not None:
        os.environ["CAP_RESUME_PARSER"] = original
    else:
        os.environ.pop("CAP_RESUME_PARSER", None)


def test_default_backend_is_gemini():
    assert cpg.get_active_parser_backend() == "gemini"


def test_backend_can_be_switched_to_engine_via_env_var():
    os.environ["CAP_RESUME_PARSER"] = "engine"
    assert cpg.get_active_parser_backend() == "engine"


def test_unrecognized_backend_value_falls_back_to_gemini():
    os.environ["CAP_RESUME_PARSER"] = "not-a-real-backend"
    assert cpg.get_active_parser_backend() == "gemini"


def test_backend_selection_is_case_insensitive():
    os.environ["CAP_RESUME_PARSER"] = "ENGINE"
    assert cpg.get_active_parser_backend() == "engine"


def test_engine_supports_pdf_and_docx():
    assert cpg.engine_supports_format(".pdf") is True
    assert cpg.engine_supports_format(".docx") is True
    assert cpg.engine_supports_format(".PDF") is True


def test_engine_does_not_support_doc_or_txt():
    assert cpg.engine_supports_format(".doc") is False
    assert cpg.engine_supports_format(".txt") is False


def test_generate_via_engine_rejects_unsupported_format(tmp_path):
    fake_file = tmp_path / "resume.txt"
    fake_file.write_text("hello")
    with pytest.raises(RuntimeError, match="does not support"):
        cpg.generate_candidate_profile_via_engine(str(fake_file))


def test_generate_via_engine_produces_schema_compatible_profile():
    resume_path = os.path.join(
        os.path.dirname(__file__),
        "resume_engine", "tests", "golden_corpus", "full_entity_resume_pdf", "resume.pdf",
    )
    profile_dict = cpg.generate_candidate_profile_via_engine(resume_path)

    # Round-trips through the exact public schema, same guarantee the
    # Gemini path provides.
    reconstructed = cpg.CandidateProfile(**profile_dict)
    assert reconstructed.projects
    assert reconstructed.experience
