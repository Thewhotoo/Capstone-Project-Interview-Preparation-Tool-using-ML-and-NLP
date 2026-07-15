"""
Gemini-powered Candidate Profile Generator.

Uses Pydantic models + google-genai native structured output to parse resumes
into a CandidateProfile in a single Gemini 2.5 Flash call.

Architecture:
    Resume (PDF) -> PyMuPDF extracts text -> Gemini 2.5 Flash
        -> Structured CandidateProfile (Pydantic) -> JSON -> Dashboard / Quiz / Interview

Every module after profile generation consumes the generated Candidate Profile
without re-parsing the resume.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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


class InterviewBlueprint(BaseModel):
    """
    Pre-interview analysis that will drive the adaptive interview engine.
    Gemini infers these from the resume content.
    """
    resume_verification_topics: list[str] = Field(
        default_factory=list,
        description="Topics to verify claims from the resume (e.g. 'Docker experience', 'IIT education')",
    )
    technical_topics: list[str] = Field(
        default_factory=list,
        description="Key technical areas to assess based on the candidate's profile",
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
- interview_blueprint.technical_topics should list 3-8 key technical areas
  to probe during an interview.
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
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
                response_schema=CandidateProfile,
            ),
        )
    except Exception as e:
        _raise_gemini_error(e)

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
        try:
            retry_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=retry_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                    response_schema=CandidateProfile,
                ),
            )
        except Exception as e:
            _raise_gemini_error(e)

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
    """
    import json as _json

    # Try direct parse
    try:
        data = _json.loads(raw_text)
        return CandidateProfile.model_validate(data)
    except Exception:
        pass

    # Try stripping markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw_text.strip())
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    try:
        data = _json.loads(cleaned)
        return CandidateProfile.model_validate(data)
    except Exception:
        pass

    # Try brace-matching extraction
    extracted = _extract_json_object(raw_text)
    if extracted:
        try:
            data = _json.loads(extracted)
            return CandidateProfile.model_validate(data)
        except Exception:
            pass

    raise RuntimeError(
        "Failed to parse Gemini response into a CandidateProfile. "
        "The AI returned malformed data."
    )


def _extract_json_object(raw: str) -> Optional[str]:
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

    # Normalise interview_blueprint
    ib = profile.interview_blueprint
    ib.technical_topics = _clean_string_list(ib.technical_topics)
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

_DOMAIN_TO_QUIZ = {
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
        status, name, email, phone, predicted_domain, quiz_domain,
        confidence, skills, experience{years,level}, education,
        projects_count, certifications, focus_topics, resume_summary,
        experience_detail, projects_detail
    """
    predicted_domain = profile.get("predicted_domain", "Software Engineering")
    quiz_domain = _DOMAIN_TO_QUIZ.get(predicted_domain, "Software Engineer")

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

    if total_years == 0:
        lvl = profile.get("experience_level", "Intermediate")
        total_years = {"Beginner": 1, "Intermediate": 3, "Advanced": 7}.get(lvl, 1)

    # Extract interview_blueprint topics as focus_topics for backward compat
    ib = profile.get("interview_blueprint", {})
    if isinstance(ib, dict):
        focus_topics = ib.get("technical_topics", [])
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
        "quiz_domain": quiz_domain,
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


def _education_to_dict(entry) -> dict:
    if isinstance(entry, dict):
        return {
            "degree": str(entry.get("degree", "")),
            "major": str(entry.get("major", "")),
            "institution": str(entry.get("institution", "")),
            "graduation_year": str(entry.get("graduation_year", "")),
        }
    # Pydantic model instance
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    return {}


def _experience_to_dict(entry) -> dict:
    if isinstance(entry, dict):
        return {
            "company": str(entry.get("company", "")),
            "role": str(entry.get("role", "")),
            "duration": str(entry.get("duration", "")),
            "summary": str(entry.get("summary", "")),
        }
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    return {}


def _project_to_dict(entry) -> dict:
    if isinstance(entry, dict):
        return {
            "title": str(entry.get("title", "")),
            "summary": str(entry.get("summary", entry.get("description", ""))),
            "technologies": [str(t) for t in entry.get("technologies", []) if t],
            "concepts": [str(c) for c in entry.get("concepts", []) if c],
            "interview_seeds": [str(s) for s in entry.get("interview_seeds", []) if s],
        }
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    return {}


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
