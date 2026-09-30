"""Tests for the Milestone 7 feature flag / backend selector added to
candidate_profile_generator.py. Kept as its own file (not appended to
test_candidate_profile_generator.py) since it tests this surface, not the
legacy Gemini-path tests.

Post-production-cutover: "engine" (the deterministic Resume Intelligence
Engine) is the default backend; "gemini" is the legacy/dev-tooling-only
opt-in, not a normal-request fallback."""

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


def test_default_backend_is_engine():
    assert cpg.get_active_parser_backend() == "engine"


def test_backend_can_be_switched_to_gemini_via_env_var():
    os.environ["CAP_RESUME_PARSER"] = "gemini"
    assert cpg.get_active_parser_backend() == "gemini"


def test_unrecognized_backend_value_falls_back_to_engine():
    """Never silently fall through to the API-dependent path on a typo --
    the trusted default post-cutover is the engine."""
    os.environ["CAP_RESUME_PARSER"] = "not-a-real-backend"
    assert cpg.get_active_parser_backend() == "engine"


def test_backend_selection_is_case_insensitive():
    os.environ["CAP_RESUME_PARSER"] = "GEMINI"
    assert cpg.get_active_parser_backend() == "gemini"


def test_engine_supports_pdf_docx_and_txt():
    assert cpg.engine_supports_format(".pdf") is True
    assert cpg.engine_supports_format(".docx") is True
    assert cpg.engine_supports_format(".txt") is True
    assert cpg.engine_supports_format(".PDF") is True


def test_engine_does_not_support_doc():
    assert cpg.engine_supports_format(".doc") is False


def test_generate_via_engine_rejects_unsupported_format(tmp_path):
    fake_file = tmp_path / "resume.doc"
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


def test_generate_via_engine_does_not_require_gemini_api_key(monkeypatch, tmp_path):
    """The whole point of the production cutover: parsing a resume through
    the engine path must succeed with GEMINI_API_KEY completely unset --
    no lazy genai client should ever be constructed on this path."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    resume_path = os.path.join(
        os.path.dirname(__file__),
        "resume_engine", "tests", "golden_corpus", "full_entity_resume_pdf", "resume.pdf",
    )
    # Would raise RuntimeError("GEMINI_API_KEY environment variable is not
    # set...") if this path touched _get_genai_client anywhere.
    profile_dict = cpg.generate_candidate_profile_via_engine(resume_path)
    assert cpg.CandidateProfile(**profile_dict)


def test_generate_via_engine_produces_schema_compatible_profile_from_txt(tmp_path):
    """TXT support (added alongside the production cutover): a plain-text
    resume must round-trip through the engine and the public schema just
    like PDF/DOCX."""
    resume_text = (
        "Jordan Example\n"
        "jordan@example.com | 555-123-4567\n\n"
        "EXPERIENCE\n"
        "Software Engineer, Acme Corp\n"
        "Jan 2021 - Present\n"
        "Built REST APIs using Python and Redis, improving latency by 30%.\n\n"
        "PROJECTS\n"
        "Resume Parser\n"
        "Built a resume parsing pipeline using Python, spaCy, and FastAPI.\n\n"
        "SKILLS\n"
        "Python, Redis, FastAPI, spaCy\n"
    )
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(resume_text, encoding="utf-8")

    profile_dict = cpg.generate_candidate_profile_via_engine(str(resume_path))

    reconstructed = cpg.CandidateProfile(**profile_dict)
    assert reconstructed.experience or reconstructed.projects
