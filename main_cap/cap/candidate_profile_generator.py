"""
Gemini-powered Candidate Profile Generator.

Uses Pydantic models + google-genai native structured output to parse resumes
into a CandidateProfile in a single Gemini 2.5 Flash call.

Architecture:
    Resume (PDF) -> PyMuPDF extracts text -> Gemini 2.5 Flash
        -> Structured CandidateProfile (Pydantic) -> JSON -> Dashboard / Discussion / Interview

Every module after profile generation consumes the generated Candidate Profile
without re-parsing the resume.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime


from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Debug response dumps write real candidate PII (name/email/phone) to disk on
# every call and are off by default; opt in only for local debugging.
_DEBUG_SAVE_RESPONSES = os.environ.get(
    "CAP_DEBUG_SAVE_GEMINI_RESPONSES", ""
).strip().lower() in ("1", "true", "yes")

_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_S = 1.0

# ── Domain labels (matches resume_classifier/utils/config.py) ────────────────

DOMAIN_LABELS = [
    "Software Engineering",
    "Data Science",
    "Finance",
    "Healthcare",
    "Marketing",
    "Law",
    "Education",
    "Mechanical Engineering",
    "Cybersecurity",
    "Product Management",
]


# ═════════════════════════════════════════════════════════════════════════════
# Pydantic Schema
# ═════════════════════════════════════════════════════════════════════════════


class ContactDetails(BaseModel):
    """Contact information extracted from the resume."""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    location: str = ""


class EducationEntry(BaseModel):
    """A single education record."""
    degree: str = ""
    major: str = ""
    institution: str = ""
    graduation_year: str = ""


class ExperienceEntry(BaseModel):
    """A single work experience record."""
    company: str = ""
    role: str = ""
    duration: str = ""
    summary: str = ""


class ProjectEntry(BaseModel):
    """A single project record extracted from the resume."""
    title: str = ""
    summary: str = Field(
        default="",
        description="Concise 2-3 sentence summary of the project grounded in the resume.",
    )
    technologies: list[str] = Field(
        default_factory=list,
        description="Technologies, tools, and frameworks used in this project.",
    )
    concepts: list[str] = Field(
        default_factory=list,
        description=(
            "Technical concepts demonstrated by this project "
            "(e.g. 'Caching', 'Microservices', 'RAG')."
        ),
    )
    interview_seeds: list[str] = Field(
        default_factory=list,
        description=(
            "Discussion topics that an interviewer could use to probe the "
            "candidate's understanding of this project "
            "(e.g. 'Why LangGraph?', 'Redis caching strategy')."
        ),
    )


class TechnicalTopic(BaseModel):
    """
    A technical concept the candidate actually demonstrated somewhere on the
    resume — never a standalone CS subject. Resume Discussion only asks about
    a technology in the context of the specific project or job that used it,
    so every topic here must name where it came from. If Gemini can't name a
    real project or experience entry for a topic, it must be omitted rather
    than invented.
    """
    topic: str = Field(
        default="",
        description=(
            "The specific technical concept as demonstrated, not an abstract "
            "subject — e.g. 'SBERT semantic similarity in the Resume Discussion "
            "stage', not 'Machine Learning'; 'LangGraph orchestration', not "
            "'Workflow orchestration'."
        ),
    )
    originating_project: str = Field(
        default="",
        description=(
            "The exact title of a project in `projects` that demonstrated this "
            "topic. Empty string if this topic came from experience instead."
        ),
    )
    originating_experience: str = Field(
        default="",
        description=(
            "The exact role/company of an entry in `experience` that "
            "demonstrated this topic. Empty string if this topic came from a "
            "project instead. At most one of originating_project / "
            "originating_experience should be set, never both, never neither."
        ),
    )
    evidence: str = Field(
        default="",
        description="A short phrase from the resume text justifying this topic — the actual claim being probed.",
    )


class InterviewBlueprint(BaseModel):
    """
    Pre-interview analysis that will drive the adaptive interview engine.
    Gemini infers these from the resume content.
    """
    resume_verification_topics: list[str] = Field(
        default_factory=list,
        description="Topics to verify claims from the resume (e.g. 'Docker experience', 'IIT education')",
    )
    technical_topics: list[TechnicalTopic] = Field(
        default_factory=list,
        description=(
            "3-8 technical concepts actually demonstrated in a specific "
            "project or job on this resume — never generic computer-science "
            "subjects and never a technology floating free of the project/job "
            "that used it. Each entry must cite exactly one originating "
            "project or experience entry."
        ),
    )
    starting_difficulty: str = Field(
        default="intermediate",
        description="Suggested starting difficulty: easy, intermediate, or hard",
    )
    estimated_strengths: list[str] = Field(
        default_factory=list,
        description="Areas where the candidate likely excels based on resume evidence",
    )
    estimated_weaknesses: list[str] = Field(
        default_factory=list,
        description="Areas with thin evidence or potential gaps in the candidate's profile",
    )


class CandidateProfile(BaseModel):
    """
    Complete structured candidate profile returned by Gemini.

    This Pydantic model is passed directly as response_schema to the
    google-genai SDK so the API enforces the schema at generation time.
    """
    candidate_name: str = ""
    contact_details: ContactDetails = Field(default_factory=ContactDetails)
    skills: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    predicted_domain: str = "Software Engineering"
    experience_level: str = "Intermediate"
    confidence: float = 0.5
    interview_blueprint: InterviewBlueprint = Field(default_factory=InterviewBlueprint)
    resume_summary: str = ""


# ═════════════════════════════════════════════════════════════════════════════
# PDF Text Extraction (PyMuPDF)
# ═════════════════════════════════════════════════════════════════════════════


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract readable text from a PDF using PyMuPDF.

    Uses simple page.get_text() by default.  If the extracted text appears
    out-of-order (heuristic: short lines, high ratio of single-word lines),
    falls back to block-based extraction via get_text("blocks") to
    reconstruct a better reading order.

    Args:
        file_path: Absolute path to a PDF file.

    Returns:
        Extracted text as a single string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If text extraction fails entirely.
    """
    try:
        import pymupdf
    except ImportError:
        raise RuntimeError(
            "pymupdf is required for PDF extraction. "
            "Install it with: pip install pymupdf"
        )

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    doc = pymupdf.open(file_path)
    try:
        pages_text: list[str] = []
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Simple extraction first
            text = page.get_text("text")

            # If text looks garbled or too sparse, try block-based extraction
            if _needs_block_fallback(text):
                text = _extract_blocks_ordered(page)

            pages_text.append(text)
    finally:
        doc.close()

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        raise ValueError(
            f"Could not extract any text from {file_path}. "
            "The PDF may be image-based (scanned)."
        )

    return full_text


def _needs_block_fallback(text: str) -> bool:
    """
    Heuristic: detect if simple extraction produced garbled/out-of-order text.

    Returns True when the text has many short fragments (likely from
    multi-column layouts) rather than flowing paragraphs.
    """
    if not text or len(text) < 100:
        return True

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return True

    short_lines = sum(1 for ln in lines if len(ln) < 15)
    single_word_lines = sum(1 for ln in lines if " " not in ln and len(ln) > 1)

    # If >60% of lines are very short, block-based extraction may yield
    # better reading order.
    ratio_short = short_lines / len(lines)
    ratio_single_word = single_word_lines / len(lines)

    return ratio_short > 0.60 and ratio_single_word > 0.30


def _extract_blocks_ordered(page) -> str:
    """
    Extract text from a PyMuPDF page using blocks, sorted by position
    to approximate natural reading order (top-to-bottom, left-to-right).
    """
    blocks = page.get_text("blocks")
    # Each block: (x0, y0, x1, y1, text, block_no, block_type)
    # block_type 0 = text, 1 = image
    text_blocks = [b for b in blocks if b[6] == 0]

    # Sort by vertical position first, then horizontal
    text_blocks.sort(key=lambda b: (round(b[1] / 10) * 10, b[0]))

    lines = []
    for block in text_blocks:
        block_text = block[4].strip()
        if block_text:
            lines.append(block_text)

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# Gemini Client (lazy singleton)
# ═════════════════════════════════════════════════════════════════════════════

_genai_client = None


def _get_genai_client():
    """Return a cached google-genai Client, creating it on first call."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Please set it to your Google AI Studio API key."
        )

    from google import genai
    _genai_client = genai.Client(api_key=api_key)
    return _genai_client


# ═════════════════════════════════════════════════════════════════════════════
# Profile Generation
# ═════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """\
You are an expert resume parser. Given the full text extracted from a resume,
produce a structured CandidateProfile.

Fill every field accurately based on what the resume contains.
- If information is absent, leave the field as an empty string, empty list, or
  default value as appropriate.
- predicted_domain must be exactly one of: {domains}
- experience_level must be one of: Beginner, Intermediate, Advanced
- confidence is a float from 0.0 to 1.0 reflecting how certain you are about
  the predicted_domain prediction.
- interview_blueprint.technical_topics: 3-8 technical concepts the candidate
  ACTUALLY DEMONSTRATED in one specific project or job on this resume. This
  is not a list of subjects to quiz the candidate on — it is a list of claims
  worth discussing further, each traceable to exactly one place on the resume.
    * Every entry's `originating_project` must exactly match a title in
      `projects`, OR `originating_experience` must exactly match a role/company
      in `experience` — never both, never neither.
    * `evidence` must be a specific phrase from the resume, not a paraphrase
      of the topic name.
    * WRONG: topic="Machine Learning" (an abstract subject, no resume claim).
    * WRONG: topic="Docker", originating_project="", originating_experience=""
      (a real technology, but no cited origin — omit it instead).
    * RIGHT: topic="SBERT-based semantic similarity for answer scoring",
      originating_project="Adaptive Interview Platform",
      evidence="uses SBERT to score candidate answers during discussion".
  If you cannot name a real project or experience entry for a topic, leave it
  out entirely rather than inventing one — an empty list is correct if nothing
  qualifies.
- interview_blueprint.estimated_strengths should cite resume evidence.
- interview_blueprint.estimated_weaknesses should note gaps or thin evidence.
- skills should be deduplicated and sorted by relevance to the candidate's
  primary domain.

PROJECTS — every project MUST include:
  - title: the project name exactly as described in the resume.
  - summary: a 2-3 sentence summary grounded strictly in the resume text.
    Do NOT invent details not present in the resume.
  - technologies: tools, frameworks, languages, and platforms used.
  - concepts: technical concepts demonstrated (e.g. "Caching",
    "Microservices", "RAG", "Authentication", "System Architecture").
  - interview_seeds: natural discussion topics an interviewer could raise
    about this project. These are NOT questions — they are topic seeds
    like "Why LangGraph?", "Redis caching strategy", "Authentication flow",
    "API design", "System architecture", "Database schema",
    "Deployment strategy", "Error handling", "Scalability".

Everything must be grounded in the resume. Never hallucinate information.
""".format(domains=", ".join(DOMAIN_LABELS))

_RETRY_PROMPT = """\
The previous extraction returned zero skills, which is almost certainly wrong.
Re-analyze the resume text below and extract ALL technical and professional skills.
Look for:
  - Programming languages, frameworks, libraries, and tools
  - Certifications and domain knowledge
  - Soft skills mentioned explicitly
  - Technologies mentioned in experience, projects, or education sections

If the resume mentions ANY technology, tool, language, or methodology, it MUST
appear in the skills list.  A resume with zero skills is an extraction failure.

--- RESUME TEXT ---

{resume_text}
"""

_MAX_CHARS = 30_000


# ═════════════════════════════════════════════════════════════════════════════
# Milestone 7 — Resume Intelligence Engine backend selector
# ═════════════════════════════════════════════════════════════════════════════
# Feature flag: which parser backend produces the CandidateProfile.
# "engine" (default, as of the production cutover -- the deterministic
# Resume Intelligence Engine, Milestones 1-7) or "gemini" (legacy path,
# kept only for Shadow Mode's own use -- see shadow_mode.py -- and as a
# manual escape hatch; not used by any normal request). Read at call
# time, not import time, so it can be overridden per-process (env var) or
# per-test without reloading this module.
_ENGINE_SUPPORTED_FORMATS = {".pdf": "pdf", ".docx": "docx", ".txt": "txt"}


def get_active_parser_backend() -> str:
    """Returns "engine" or "gemini". Defaults to "engine" post-cutover.
    Falls back to "gemini" only when explicitly requested (e.g. by
    Shadow Mode, or a manual override) -- any other/unrecognized value
    also defaults to "engine", never silently falling through to the
    Gemini/API-dependent path on a typo."""
    raw = os.environ.get("CAP_RESUME_PARSER", "engine").strip().lower()
    return "gemini" if raw == "gemini" else "engine"


def engine_supports_format(file_extension: str) -> bool:
    """The Resume Intelligence Engine's Document Extraction stage
    (`resume_engine.extractor.PdfDocxExtractor`) handles PDF/DOCX/TXT.
    .doc (legacy binary Word format) has no engine-side extractor and no
    observed demand in this project -- callers must reject it (or fall
    back to Gemini, for Shadow Mode's own dev use only) rather than
    silently mishandling it."""
    return file_extension.lower() in _ENGINE_SUPPORTED_FORMATS


def generate_candidate_profile_via_engine(file_path: str) -> dict:
    """The Resume Intelligence Engine path: runs the real 8-stage
    pipeline (`resume_engine.factory.default_pipeline`) and maps its
    output to the exact same public `CandidateProfile` shape
    `generate_candidate_profile` (the Gemini path) returns --
    `resume_engine.candidate_profile_mapper.map_to_candidate_profile` is
    what guarantees that shape match. Imports are local/lazy so a
    process running only the Gemini path never pays the engine's
    (heavier: SBERT/KeyBERT model loading) import cost.

    Raises: the same exception types the engine itself raises
    (`resume_engine.extractor.ExtractionFailure` for corrupt/scanned
    files) -- callers should catch and handle exactly as they already do
    for the Gemini path's `RuntimeError`.
    """
    import os as _os

    from resume_engine.candidate_profile_mapper import map_to_candidate_profile
    from resume_engine.factory import default_pipeline

    extension = _os.path.splitext(file_path)[1].lower()
    source_format = _ENGINE_SUPPORTED_FORMATS.get(extension)
    if source_format is None:
        raise RuntimeError(
            f"Resume Intelligence Engine does not support {extension!r} files "
            "(only .pdf/.docx/.txt) -- caller must reject the upload (or, for "
            "Shadow Mode's own dev use only, fall back to the Gemini path)."
        )

    annotated_profile = default_pipeline().run(file_path, source_format)
    return map_to_candidate_profile(annotated_profile)


def generate_candidate_profile(resume_text: str) -> dict:
    """
    Call Gemini 2.5 Flash once with native structured output to produce a
    CandidateProfile matching the Pydantic schema.

    Args:
        resume_text: Full text extracted from a resume.

    Returns:
        dict representation of the validated CandidateProfile.

    Raises:
        RuntimeError: On API errors, rate limits, or schema validation failures.
    """
    if not resume_text or len(resume_text.strip()) < 50:
        raise RuntimeError(
            "Resume text is too short or empty. "
            "Cannot generate a meaningful candidate profile."
        )

    truncated = resume_text[:_MAX_CHARS]
    if len(resume_text) > _MAX_CHARS:
        logger.warning(
            "Resume text truncated from %d to %d chars for Gemini",
            len(resume_text), _MAX_CHARS,
        )

    client = _get_genai_client()
    from google.genai import types

    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"--- RESUME TEXT ---\n\n{truncated}"
    )

    # ── First Gemini call with native structured output ───────────────
    logger.info("Calling Gemini 2.5 Flash (structured output)")
    response = _generate_with_retry(
        client,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=CandidateProfile,
        ),
    )
    _check_truncation(response, label="primary")

    # ══════════════════════════════════════════════════════════════════
    # DEBUG: Save raw response + metadata for diagnostics (opt-in only —
    # writes candidate PII to disk, see CAP_DEBUG_SAVE_GEMINI_RESPONSES)
    # ══════════════════════════════════════════════════════════════════
    if _DEBUG_SAVE_RESPONSES:
        try:
            _debug_save_response(response, prompt)
        except Exception as _dbg_err:
            logger.warning("Debug save failed (non-fatal): %s", _dbg_err)

    # ── Parse into Pydantic model ─────────────────────────────────────
    if response.parsed is not None:
        profile_model = response.parsed
    else:
        # Fallback: SDK didn't auto-parse (shouldn't happen with schema set)
        raw_text = (response.text or "").strip()
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response.")
        profile_model = _parse_response_text(raw_text)

    # ── Post-process / validate ───────────────────────────────────────
    profile_model = _post_process(profile_model)

    # ── Retry if skills=0 (extraction failure) ────────────────────────
    if not profile_model.skills:
        logger.warning(
            "Gemini returned 0 skills for domain '%s' — retrying with "
            "explicit extraction prompt",
            profile_model.predicted_domain,
        )
        retry_prompt = _RETRY_PROMPT.format(resume_text=truncated)
        retry_response = _generate_with_retry(
            client,
            contents=retry_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=CandidateProfile,
            ),
        )
        _check_truncation(retry_response, label="retry")

        # DEBUG: Save retry response too (opt-in only, see above)
        if _DEBUG_SAVE_RESPONSES:
            try:
                _debug_save_response(retry_response, retry_prompt, label="retry")
            except Exception as _dbg_err:
                logger.warning("Debug save (retry) failed (non-fatal): %s", _dbg_err)

        if retry_response.parsed is not None:
            profile_model = _post_process(retry_response.parsed)
        else:
            raw_text = (retry_response.text or "").strip()
            if raw_text:
                profile_model = _post_process(_parse_response_text(raw_text))

        if not profile_model.skills:
            logger.warning(
                "Retry still returned 0 skills for domain '%s'. "
                "Keeping the profile as-is (may be a non-technical resume).",
                profile_model.predicted_domain,
            )

    profile_dict = profile_model.model_dump()

    logger.info(
        "Candidate profile generated: name=%s domain=%s level=%s skills=%d",
        profile_dict.get("candidate_name"),
        profile_dict.get("predicted_domain"),
        profile_dict.get("experience_level"),
        len(profile_dict.get("skills", [])),
    )
    return profile_dict


def _parse_response_text(raw_text: str) -> CandidateProfile:
    """
    Last-resort fallback: parse raw JSON text into a CandidateProfile.
    Used only when the SDK doesn't return .parsed.

    DEBUG INSTRUMENTATION: logs every failure with full exception details.
    """
    import json as _json

    errors_log = []  # Collect all errors for final diagnostic

    # Try direct parse
    try:
        data = _json.loads(raw_text)
        try:
            return CandidateProfile.model_validate(data)
        except Exception as ve:
            err_msg = f"json.loads() succeeded but model_validate() FAILED:\n{ve}"
            logger.error("DEBUG _parse_response_text [attempt 1 - direct]: %s", err_msg)
            errors_log.append({"attempt": "direct_model_validate", "error": str(ve), "errors": _extract_validation_errors(ve)})
    except _json.JSONDecodeError as je:
        err_msg = f"json.loads() FAILED: {je}"
        logger.error("DEBUG _parse_response_text [attempt 1 - direct]: %s", err_msg)
        errors_log.append({"attempt": "direct_json_loads", "error": str(je)})
    except Exception as e:
        err_msg = f"Unexpected error: {type(e).__name__}: {e}"
        logger.error("DEBUG _parse_response_text [attempt 1 - direct]: %s", err_msg)
        errors_log.append({"attempt": "direct_unexpected", "error": err_msg})

    # Try stripping markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw_text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        data = _json.loads(cleaned)
        try:
            return CandidateProfile.model_validate(data)
        except Exception as ve:
            err_msg = f"json.loads() succeeded but model_validate() FAILED:\n{ve}"
            logger.error("DEBUG _parse_response_text [attempt 2 - fence_stripped]: %s", err_msg)
            errors_log.append({"attempt": "fence_stripped_model_validate", "error": str(ve), "errors": _extract_validation_errors(ve)})
    except _json.JSONDecodeError as je:
        err_msg = f"json.loads() FAILED on fence-stripped text: {je}"
        logger.error("DEBUG _parse_response_text [attempt 2 - fence_stripped]: %s", err_msg)
        errors_log.append({"attempt": "fence_stripped_json_loads", "error": str(je)})
    except Exception as e:
        err_msg = f"Unexpected error: {type(e).__name__}: {e}"
        logger.error("DEBUG _parse_response_text [attempt 2 - fence_stripped]: %s", err_msg)
        errors_log.append({"attempt": "fence_stripped_unexpected", "error": err_msg})

    # Try brace-matching extraction
    extracted = _extract_json_object(raw_text)
    if extracted:
        try:
            data = _json.loads(extracted)
            try:
                return CandidateProfile.model_validate(data)
            except Exception as ve:
                err_msg = f"json.loads() succeeded but model_validate() FAILED on extracted JSON:\n{ve}"
                logger.error("DEBUG _parse_response_text [attempt 3 - brace_extracted]: %s", err_msg)
                errors_log.append({"attempt": "brace_extracted_model_validate", "error": str(ve), "errors": _extract_validation_errors(ve), "extracted_preview": extracted[:200]})
        except _json.JSONDecodeError as je:
            err_msg = f"json.loads() FAILED on brace-extracted JSON: {je}"
            logger.error("DEBUG _parse_response_text [attempt 3 - brace_extracted]: %s", err_msg)
            errors_log.append({"attempt": "brace_extracted_json_loads", "error": str(je), "extracted_preview": extracted[:200]})
        except Exception as e:
            err_msg = f"Unexpected error: {type(e).__name__}: {e}"
            logger.error("DEBUG _parse_response_text [attempt 3 - brace_extracted]: %s", err_msg)
            errors_log.append({"attempt": "brace_extracted_unexpected", "error": err_msg})
    else:
        logger.error("DEBUG _parse_response_text: _extract_json_object returned None — no { } found in response")
        errors_log.append({"attempt": "brace_extraction", "error": "No JSON object found in response (no opening brace)"})

    # All attempts failed — dump full diagnostic
    logger.error(
        "DEBUG _parse_response_text: ALL 3 ATTEMPTS FAILED.\n"
        "Response text length: %d chars\n"
        "Response text preview (first 500 chars): %s\n"
        "Response text last 200 chars: %s\n"
        "Errors collected: %s",
        len(raw_text),
        raw_text[:500],
        raw_text[-200:] if len(raw_text) > 200 else raw_text,
        _json.dumps(errors_log, indent=2, default=str),
    )

    # An "Unterminated string" error almost always means the response was
    # cut off mid-JSON by max_output_tokens rather than genuinely malformed —
    # _check_truncation() (called unconditionally, unlike the debug dump
    # below) already logged whether that's what happened.
    debug_hint = (
        "See debug_candidate_profile.json for the raw response."
        if _DEBUG_SAVE_RESPONSES else
        "Set CAP_DEBUG_SAVE_GEMINI_RESPONSES=1 and retry to capture the raw "
        "response for diagnosis."
    )
    raise RuntimeError(
        "Failed to parse Gemini response into a CandidateProfile. "
        "The AI returned malformed data — this usually means the response "
        f"was truncated before completing. {debug_hint} "
        f"Errors: {[e['error'][:100] for e in errors_log]}"
    )


def _extract_validation_errors(exc: Exception) -> list[dict]:
    """
    DEBUG: Extract structured error details from a Pydantic ValidationError.
    Returns a list of {loc, msg, type} dicts for each validation error.
    """
    errors = []
    try:
        from pydantic import ValidationError
        if isinstance(exc, ValidationError):
            for err in exc.errors():
                errors.append({
                    "loc": [str(x) for x in err.get("loc", [])],
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                    "input_preview": str(err.get("input", ""))[:200],
                })
            # Log full validation errors as JSON
            logger.error(
                "DEBUG Pydantic ValidationError details:\n%s",
                exc.json() if hasattr(exc, "json") else str(exc),
            )
        else:
            errors.append({"error": str(exc)})
    except Exception as e:
        errors.append({"extraction_error": str(e), "original_error": str(exc)})
    return errors


def _extract_json_object(raw: str) -> str | None:
    """Find the outermost { ... } using brace-depth matching."""
    start = raw.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(raw)):
        ch = raw[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]

    return None


def _is_retryable_gemini_error(exc: Exception) -> bool:
    """Rate limits, timeouts, and 5xx are worth retrying; auth/permission
    errors are not — retrying an invalid API key never helps."""
    error_str = str(exc).lower()
    if any(kw in error_str for kw in ("api_key", "authentication", "permission", "401", "403")):
        return False
    return any(
        kw in error_str
        for kw in ("rate", "limit", "timeout", "deadline", "500", "502", "503", "unavailable")
    )


def _generate_with_retry(client, contents: str, config):
    """
    Call Gemini with a short retry/backoff for transient failures. This is
    the system's only remaining LLM call site after the Resume Discussion
    redesign, so a single dropped request now costs more than it used to.
    """
    last_exc: Exception | None = None
    for attempt in range(_RETRY_MAX_ATTEMPTS):
        try:
            return client.models.generate_content(
                model="gemini-2.5-flash", contents=contents, config=config,
            )
        except Exception as e:
            last_exc = e
            if attempt < _RETRY_MAX_ATTEMPTS - 1 and _is_retryable_gemini_error(e):
                delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "Gemini call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, _RETRY_MAX_ATTEMPTS, delay, e,
                )
                time.sleep(delay)
                continue
            break
    _raise_gemini_error(last_exc)


def _check_truncation(response, label: str = "primary") -> bool:
    """
    Log a warning if Gemini's response was cut off before completing (hit
    max_output_tokens rather than finishing normally) — the classic cause of
    a JSON parse failure that looks like "Unterminated string starting at
    line N". This check is deliberately PII-free (only finish_reason/token
    counts, never resume content) so it always runs, unlike the full
    _debug_save_response dump below which is gated behind
    CAP_DEBUG_SAVE_GEMINI_RESPONSES.
    """
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return False
        finish_reason = str(getattr(candidates[0], "finish_reason", "")).lower()
        is_truncated = bool(finish_reason) and "stop" not in finish_reason
        if is_truncated:
            usage = getattr(response, "usage_metadata", None)
            logger.warning(
                "Gemini response (%s) was truncated — finish_reason=%s, "
                "candidates_token_count=%s. max_output_tokens may still be too "
                "low for this resume; consider raising it further.",
                label, finish_reason,
                getattr(usage, "candidates_token_count", "unknown") if usage else "unknown",
            )
        return is_truncated
    except Exception:
        return False


def _raise_gemini_error(exc: Exception):
    """Translate Gemini API exceptions into clear RuntimeError messages."""
    error_str = str(exc).lower()
    if "rate" in error_str and "limit" in error_str:
        raise RuntimeError(
            "Gemini API rate limit exceeded. Please wait and try again."
        ) from exc
    if "timeout" in error_str or "deadline" in error_str:
        raise RuntimeError(
            "Gemini API request timed out. Please try again."
        ) from exc
    if any(kw in error_str for kw in ("api_key", "authentication", "permission", "401", "403")):
        raise RuntimeError(
            "Invalid Gemini API key. Check GEMINI_API_KEY."
        ) from exc
    if "500" in error_str or "502" in error_str or "503" in error_str:
        raise RuntimeError(
            f"Gemini API server error: {exc}"
        ) from exc
    raise RuntimeError(f"Gemini API error: {exc}") from exc


def _debug_save_response(response, prompt: str, label: str = "primary"):
    """
    DEBUG INSTRUMENTATION — save raw Gemini response + metadata to disk.

    Writes to:
        debug_candidate_profile.json   (primary call)
        debug_candidate_profile_retry.json  (retry call)

    Collects:
        - response.text (raw text as-is)
        - response.parsed (whether SDK parsed it)
        - response metadata (finish_reason, token counts)
        - prompt length
        - truncation detection
    """
    import json as _json
    import os as _os
    from datetime import datetime as _dt

    debug_dir = _os.path.dirname(_os.path.abspath(__file__))
    filename = f"debug_candidate_profile{'_' + label if label != 'primary' else ''}.json"
    filepath = _os.path.join(debug_dir, filename)

    raw_text = ""
    parsed_obj = None
    metadata = {}

    # Extract raw text
    try:
        raw_text = response.text or ""
    except Exception as e:
        raw_text = f"[ERROR extracting response.text: {e}]"

    # Extract parsed object
    try:
        parsed = response.parsed
        if parsed is not None:
            if hasattr(parsed, "model_dump"):
                parsed_obj = parsed.model_dump()
            elif isinstance(parsed, dict):
                parsed_obj = parsed
            else:
                parsed_obj = str(parsed)
    except Exception as e:
        parsed_obj = f"[ERROR extracting response.parsed: {e}]"

    # Extract metadata from response
    try:
        # finish_reason
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "finish_reason"):
                metadata["finish_reason"] = str(candidate.finish_reason)
            if hasattr(candidate, "finish_message"):
                metadata["finish_message"] = candidate.finish_message
            # Token counts from usage_metadata
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                metadata["prompt_token_count"] = getattr(um, "prompt_token_count", None)
                metadata["candidates_token_count"] = getattr(um, "candidates_token_count", None)
                metadata["total_token_count"] = getattr(um, "total_token_count", None)
        # Also check top-level usage_metadata
        if not metadata.get("total_token_count") and hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            metadata["prompt_token_count"] = getattr(um, "prompt_token_count", None)
            metadata["candidates_token_count"] = getattr(um, "candidates_token_count", None)
            metadata["total_token_count"] = getattr(um, "total_token_count", None)
    except Exception as e:
        metadata["extraction_error"] = str(e)

    # Truncation detection
    is_truncated = False
    try:
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "finish_reason"):
                fr = str(candidate.finish_reason).lower()
                is_truncated = "stop" not in fr  # FINISH_REASON_STOP = complete; others = truncated
                metadata["is_truncated"] = is_truncated
                metadata["finish_reason_raw"] = fr
    except Exception:
        pass

    # Build debug payload
    debug_data = {
        "_timestamp": _dt.now().isoformat(),
        "_label": label,
        "_debug_note": "DEBUG INSTRUMENTATION — do not modify. Collecting evidence for root cause analysis.",
        "prompt_length_chars": len(prompt),
        "response_text_length": len(raw_text),
        "response_parsed_is_none": parsed_obj is None if parsed_obj != f"[ERROR extracting response.parsed: None]" else True,
        "is_truncated": is_truncated,
        "metadata": metadata,
        "response_text_preview": raw_text[:500] if raw_text else "(empty)",
        "response_text_full": raw_text,
        "response_parsed": parsed_obj,
    }

    # Write to file
    with open(filepath, "w", encoding="utf-8") as f:
        _json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(
        "DEBUG: Raw Gemini response saved to %s "
        "(text_len=%d, parsed=%s, truncated=%s, tokens=%s)",
        filepath,
        len(raw_text),
        parsed_obj is not None,
        is_truncated,
        metadata.get("total_token_count"),
    )

    # Also log critical diagnostics
    if is_truncated:
        logger.warning(
            "DEBUG: RESPONSE TRUNCATED — finish_reason=%s. "
            "max_output_tokens (4096) may be too low for this resume.",
            metadata.get("finish_reason_raw"),
        )

    if parsed_obj is None and raw_text:
        logger.warning(
            "DEBUG: response.parsed is None but response.text exists (len=%d). "
            "SDK failed to auto-parse despite response_schema being set. "
            "Will fall through to _parse_response_text().",
            len(raw_text),
        )

    if not raw_text and parsed_obj is None:
        logger.error(
            "DEBUG: BOTH response.text AND response.parsed are empty/None. "
            "This indicates a complete API failure."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Post-processing
# ═════════════════════════════════════════════════════════════════════════════


def _post_process(profile: CandidateProfile) -> CandidateProfile:
    """Validate and normalise the Gemini-returned profile."""
    # Normalise domain
    profile.predicted_domain = _fuzzy_match_domain(profile.predicted_domain)

    # Normalise experience level
    profile.experience_level = _normalise_level(profile.experience_level)

    # Clamp confidence
    if not (0.0 <= profile.confidence <= 1.0):
        profile.confidence = 0.5
    else:
        profile.confidence = round(profile.confidence, 4)

    # Clean skills
    profile.skills = _clean_string_list(profile.skills)

    # Clean certifications
    profile.certifications = _clean_string_list(profile.certifications)

    # Normalise interview_blueprint. technical_topics must cite exactly one
    # origin (project XOR experience) with a non-empty topic — anything else
    # is a malformed/hallucinated entry and is dropped here rather than
    # passed downstream. (Whether the cited origin actually exists in
    # `projects`/`experience` is checked later, in the Resume Discussion
    # engine, which has the full profile to cross-reference against.)
    ib = profile.interview_blueprint
    ib.technical_topics = [
        t for t in ib.technical_topics
        if t.topic.strip()
        and (bool(t.originating_project.strip()) != bool(t.originating_experience.strip()))
    ]
    ib.estimated_strengths = _clean_string_list(ib.estimated_strengths)
    ib.estimated_weaknesses = _clean_string_list(ib.estimated_weaknesses)
    if ib.starting_difficulty not in ("easy", "intermediate", "hard"):
        ib.starting_difficulty = "intermediate"

    return profile


def _fuzzy_match_domain(raw: str) -> str:
    """Match raw domain string to one of DOMAIN_LABELS."""
    if not raw:
        return "Software Engineering"

    if raw in DOMAIN_LABELS:
        return raw

    raw_lower = raw.lower()
    for d in DOMAIN_LABELS:
        if d.lower() == raw_lower:
            return d
        if d.lower() in raw_lower or raw_lower in d.lower():
            return d

    return "Software Engineering"


def _normalise_level(raw: str) -> str:
    """Map free-text experience level to Beginner / Intermediate / Advanced."""
    if not raw:
        return "Intermediate"

    valid = {"Beginner", "Intermediate", "Advanced"}
    if raw in valid:
        return raw

    low = raw.lower()
    if any(kw in low for kw in ("begin", "junior", "entry", "fresher")):
        return "Beginner"
    if any(kw in low for kw in ("inter", "mid")):
        return "Intermediate"
    if any(kw in low for kw in ("adv", "senior", "expert", "lead")):
        return "Advanced"
    return "Intermediate"


def _clean_string_list(items: list) -> list[str]:
    """Filter out empty / non-string items."""
    return [str(item).strip() for item in items if item and str(item).strip()]


# ═════════════════════════════════════════════════════════════════════════════
# Frontend Format Conversion
# ═════════════════════════════════════════════════════════════════════════════

_DOMAIN_TO_DISCUSSION = {
    "Software Engineering": "Software Engineer",
    "Data Science": "Data Scientist",
    "Cybersecurity": "Network Engineer",
    "Finance": "Database Engineer",
}

_LEVEL_TO_DISPLAY = {
    "Beginner": "Junior",
    "Intermediate": "Mid",
    "Advanced": "Senior",
}


def profile_to_frontend_format(profile: dict) -> dict:
    """
    Convert a CandidateProfile dict (from generate_candidate_profile) into
    the flat format expected by the existing frontend / dashboard.

    The frontend expects:
        status, name, email, phone, predicted_domain, discussion_domain,
        confidence, skills, experience{years,level}, education,
        projects, certifications, focus_topics, resume_summary,
        experience_detail
    """
    predicted_domain = profile.get("predicted_domain", "Software Engineering")
    discussion_domain = _DOMAIN_TO_DISCUSSION.get(predicted_domain, "Software Engineer")

    # Extract contact details (handle both flat and nested formats)
    contact = profile.get("contact_details", {})
    if isinstance(contact, dict):
        email = contact.get("email", "") or profile.get("email", "")
        phone = contact.get("phone", "") or profile.get("phone", "")
    else:
        email = profile.get("email", "")
        phone = profile.get("phone", "")

    total_years = _calculate_total_years(profile.get("experience", []))
    display_level = _LEVEL_TO_DISPLAY.get(
        profile.get("experience_level", "Intermediate"), "Unknown"
    )

    # `total_years` is left at 0 (never synthesized from `experience_level`
    # alone) when the resume has no dated evidence to compute a real
    # span from -- e.g. a single internship entry within one calendar
    # year, or no Experience section at all. Found during the production
    # walkthrough audit: this used to backfill a fabricated year count
    # (Beginner->1, Intermediate->3, Advanced->7) purely from the level
    # label, with zero supporting dated evidence -- the literal source of
    # the "3 yrs - Mid" text a prior audit flagged as unsupported. The
    # frontend's own `expText` fallback (falsy `years` -> show the level
    # alone, e.g. "Junior") already handles years==0 correctly; this
    # backend fallback was defeating it.

    # Extract interview_blueprint topics as focus_topics for backward compat.
    # technical_topics is now a list of {topic, originating_project,
    # originating_experience, evidence} objects, not plain strings — this
    # flat display field only ever wants the topic name.
    ib = profile.get("interview_blueprint", {})
    if isinstance(ib, dict):
        focus_topics = [
            t.get("topic", "") if isinstance(t, dict) else str(t)
            for t in ib.get("technical_topics", [])
        ]
        focus_topics = [t for t in focus_topics if t]
    else:
        focus_topics = []

    # Fallback: if flat dict has focus_topics, use it (backward compat)
    if not focus_topics:
        focus_topics = profile.get("focus_topics", [])

    return {
        "status": "success",
        "name": profile.get("candidate_name", ""),
        "email": email,
        "phone": phone,
        "predicted_domain": predicted_domain,
        "discussion_domain": discussion_domain,
        "confidence": profile.get("confidence", 0.0),
        "skills": profile.get("skills", []),
        "experience": {
            "years": total_years,
            "level": display_level,
        },
        "education": [_education_to_dict(e) for e in profile.get("education", [])],
        "projects": [_project_to_dict(p) for p in profile.get("projects", [])],
        # Extra fields
        "certifications": profile.get("certifications", []),
        "focus_topics": focus_topics,
        "resume_summary": profile.get("resume_summary", ""),
        "experience_detail": [_experience_to_dict(e) for e in profile.get("experience", [])],
    }


def _entry_to_dict(entry, str_fields: tuple = (), list_fields: tuple = ()) -> dict:
    """
    Coerce a profile sub-entry (either a plain dict or a Pydantic model
    instance — both show up here depending on the parse path) into a plain
    dict with the given scalar (str_fields) and list-of-str (list_fields)
    keys. Shared by _education_to_dict/_experience_to_dict/_project_to_dict,
    which previously each reimplemented this same dict-vs-model branch.
    """
    if isinstance(entry, dict):
        result = {f: str(entry.get(f, "")) for f in str_fields}
        result.update({f: [str(v) for v in entry.get(f, []) if v] for f in list_fields})
        return result
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    return {}


def _education_to_dict(entry) -> dict:
    return _entry_to_dict(entry, str_fields=("degree", "major", "institution", "graduation_year"))


def _experience_to_dict(entry) -> dict:
    return _entry_to_dict(entry, str_fields=("company", "role", "duration", "summary"))


def _project_to_dict(entry) -> dict:
    return _entry_to_dict(
        entry,
        str_fields=("title", "summary"),
        list_fields=("technologies", "concepts", "interview_seeds"),
    )


def _calculate_total_years(experiences: list) -> int:
    """Calculate total professional experience in years from experience entries."""
    all_years: list[int] = []
    current_year = datetime.now().year

    for exp in experiences:
        duration = ""
        if isinstance(exp, dict):
            duration = exp.get("duration", "")
        elif hasattr(exp, "duration"):
            duration = exp.duration
        if not duration:
            continue

        years_found = [int(y) for y in re.findall(r"([12]\d{3})", duration)]
        if re.search(r"present|current", duration, re.IGNORECASE):
            years_found.append(current_year)
        all_years.extend(years_found)

    if len(all_years) >= 2:
        return max(all_years) - min(all_years)
    return 0
