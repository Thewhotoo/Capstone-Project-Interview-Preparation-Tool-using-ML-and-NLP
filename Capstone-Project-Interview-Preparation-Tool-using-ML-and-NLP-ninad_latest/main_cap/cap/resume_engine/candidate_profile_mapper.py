"""
Candidate Profile Mapper — Milestone 7 (Cutover). See
docs/architecture/Milestone7_ValidationReport.md.

Converts the engine-internal `AnnotatedCandidateProfile` (confidence.py)
into the exact public `CandidateProfile` shape
`candidate_profile_generator.py` has always returned -- the one
remaining piece needed before the deterministic engine can be swapped in
for Gemini. Per Section 1.3 of the architecture doc: "nothing downstream
should be able to tell it apart from today's Gemini output."

Four fields have no producer anywhere upstream (`predicted_domain`,
`experience_level`, `interview_blueprint`, `resume_summary`) -- all four
are built HERE, deterministically, from evidence Milestones 1-6 already
extracted. No LLM call anywhere in this module. Every one of the four
reuses an existing signal rather than adding a new parsing pass:

  - predicted_domain: gazetteer-keyword scoring (domain_gazetteer.py)
    against the already-extracted skills/technologies/concepts/roles --
    the same "gazetteer decides a closed-set classification" pattern
    already used throughout Milestones 2-5.
  - experience_level: total years (regex over `experience[].duration`,
    the same technique `candidate_profile_generator._calculate_total_years`
    already uses) + seniority keywords already present in `role` text.
  - interview_blueprint.technical_topics: almost entirely direct reuse --
    `projects[].technologies`/`concepts` are already TechnicalTopic-shaped
    evidence; experience-originated topics reuse the SAME gazetteer-scan
    technique `ProjectParser` already established (a small, accepted,
    independent duplication, consistent with every other cross-parser
    boundary in this engine).
  - interview_blueprint.estimated_weaknesses: a DIRECT reuse of the
    Validation Layer's own `Observation`s (Milestone 6) -- zero new
    heuristic invented.
  - resume_summary: a grounded template (never freeform generation),
    same philosophy as `seed_synthesis.py`'s template bank -- every
    clause traces to already-extracted data; empty when there's no
    evidence to summarize (graceful degradation, not a fabricated
    sentence with blanks filled in).
"""

from __future__ import annotations

import re
from collections import Counter

from resume_engine.concept_gazetteer import CONCEPTS
from resume_engine.confidence import AnnotatedCandidateProfile
from resume_engine.domain_gazetteer import DOMAIN_KEYWORDS
from resume_engine.technology_gazetteer import TECHNOLOGIES

_DEFAULT_DOMAIN = "Software Engineering"
_MAX_TECHNICAL_TOPICS = 8
_MAX_STRENGTHS = 5
_MAX_WEAKNESSES = 5

_YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
_SENIOR_KEYWORDS = ("senior", "staff", "principal", "lead", "manager", "director", "vp", "cto", "head of")
_JUNIOR_KEYWORDS = ("intern", "junior", "entry", "trainee", "fresher")

_OBSERVATION_TO_WEAKNESS = {
    "missing_technologies": "Some projects list no technologies, making it hard to gauge technical depth.",
    "no_measurable_outcome": "Project descriptions rarely cite measurable outcomes or impact.",
    "empty_experience_summary": "One or more experience entries have no description of the work done.",
    "missing_degree": "Education history doesn't clearly state a recognizable degree.",
    "missing_dates": "Some experience entries have no verifiable dates.",
    "inconsistent_dates": "An experience entry's dates appear inconsistent (end before start).",
    "skill_not_demonstrated": "Some listed skills aren't demonstrated in any project or role.",
    "missing_linkedin": "No LinkedIn profile is listed for further verification.",
}


def _entity_text(entity: dict, fields: tuple[str, ...]) -> str:
    parts = []
    for field_name in fields:
        value = entity.get(field_name)
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def classify_domain(profile_text: str) -> str:
    """Deterministic gazetteer-keyword scoring against the closed
    `DOMAIN_KEYWORDS` label set. Defaults to `_DEFAULT_DOMAIN` (matching
    Gemini path's own `_fuzzy_match_domain` default) when nothing
    scores -- never guesses a domain with zero supporting evidence."""
    text_lower = profile_text.lower()
    if not text_lower.strip():
        return _DEFAULT_DOMAIN

    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits:
            scores[domain] = hits

    if not scores:
        return _DEFAULT_DOMAIN
    return max(scores.items(), key=lambda kv: (kv[1], kv[0]))[0]


def infer_experience_level(experiences: list[dict]) -> str:
    """Total years (from already-extracted `duration` strings) +
    seniority keywords already present in `role` text -- both signals
    Milestones 3/5 already produced, no new extraction."""
    years: list[int] = []
    seniority_bump = 0
    for exp in experiences:
        duration = exp.get("duration", "") or ""
        found_years = [int(m) for m in _YEAR_PATTERN.findall(duration)]
        years.extend(found_years)

        role = (exp.get("role", "") or "").lower()
        if any(kw in role for kw in _SENIOR_KEYWORDS):
            seniority_bump += 1
        elif any(kw in role for kw in _JUNIOR_KEYWORDS):
            seniority_bump -= 1

    total_years = (max(years) - min(years)) if len(years) >= 2 else 0

    if total_years >= 6 or seniority_bump >= 1:
        return "Advanced"
    if seniority_bump <= -1:
        return "Beginner"
    # <=1 verifiable year of dated experience (including zero, whether from
    # no experience section at all or a single short/undated entry, e.g. a
    # summer internship spanning one calendar year) is entry-level by
    # definition -- there is no dated/keyword evidence to support anything
    # higher. Previously this fell through to "Intermediate" as a bare
    # default whenever there was zero quantitative AND zero keyword signal,
    # fabricating a mid-level read (e.g. "3 yrs - Mid") for a student with
    # only a few months of internship experience. Never guess up from an
    # absence of evidence -- the same rule `classify_domain`'s
    # `_DEFAULT_DOMAIN` fallback already follows.
    if total_years <= 1:
        return "Beginner"
    return "Intermediate"


def _gazetteer_matches(text: str, gazetteer: tuple[str, ...]) -> list[str]:
    text_lower = text.lower()
    matches = []
    for term in gazetteer:
        if re.search(r"\b" + re.escape(term.lower()) + r"\b", text_lower):
            matches.append(term)
    return matches


def build_technical_topics(projects: list[dict], experiences: list[dict]) -> list[dict]:
    """Reuses `projects[].technologies`/`concepts` directly (zero new
    extraction) as the primary source; only scans `experience[].summary`
    text with the same gazetteer-matching technique `ProjectParser`
    already established when the project-derived topics don't fill the
    cap. Every topic cites exactly one origin, per the schema's XOR
    requirement, and `evidence` is always a literal substring of the
    entry's own summary -- never invented."""
    topics: list[dict] = []
    seen_topics: set[str] = set()

    for project in projects:
        title = project.get("title", "")
        if not title:
            continue
        summary = project.get("summary", "") or ""
        for topic_name in list(project.get("technologies") or []) + list(project.get("concepts") or []):
            key = topic_name.lower()
            if not topic_name or key in seen_topics:
                continue
            if len(topics) >= _MAX_TECHNICAL_TOPICS:
                return topics
            seen_topics.add(key)
            topics.append(
                {
                    "topic": topic_name,
                    "originating_project": title,
                    "originating_experience": "",
                    "evidence": summary[:160] if summary else f"listed under project {title!r}",
                }
            )

    if len(topics) >= _MAX_TECHNICAL_TOPICS:
        return topics

    for experience in experiences:
        role = experience.get("role", "")
        company = experience.get("company", "")
        label = f"{role} at {company}".strip() if company else role
        if not label:
            continue
        summary = experience.get("summary", "") or ""
        if not summary:
            continue
        for topic_name in _gazetteer_matches(summary, TECHNOLOGIES) + _gazetteer_matches(summary, CONCEPTS):
            key = topic_name.lower()
            if key in seen_topics:
                continue
            if len(topics) >= _MAX_TECHNICAL_TOPICS:
                return topics
            seen_topics.add(key)
            topics.append(
                {
                    "topic": topic_name,
                    "originating_project": "",
                    "originating_experience": label,
                    "evidence": summary[:160],
                }
            )

    return topics


def estimate_strengths(projects: list[dict], skills: list[str]) -> list[str]:
    """Top technologies by frequency across projects + explicit skills --
    a direct frequency count over already-extracted data, no new
    heuristic signal."""
    counter: Counter[str] = Counter()
    for project in projects:
        for tech in project.get("technologies") or []:
            counter[tech] += 1
    for skill in skills:
        counter[skill] += 1

    strengths = []
    for tech, _count in counter.most_common(_MAX_STRENGTHS):
        strengths.append(f"Demonstrated proficiency in {tech}")
    return strengths


def estimate_weaknesses(observations: list) -> list[str]:
    """Direct reuse of the Validation Layer's already-computed
    Observations (Milestone 6) -- zero new heuristic invented here."""
    weaknesses: list[str] = []
    seen_categories: set[str] = set()
    for observation in observations:
        category = getattr(observation, "category", None)
        if category in _OBSERVATION_TO_WEAKNESS and category not in seen_categories:
            seen_categories.add(category)
            weaknesses.append(_OBSERVATION_TO_WEAKNESS[category])
            if len(weaknesses) >= _MAX_WEAKNESSES:
                break
    return weaknesses


def build_resume_summary(
    candidate_name: str, predicted_domain: str, experience_level: str, total_years: int, top_skills: list[str]
) -> str:
    """A grounded template, never freeform generation -- every clause
    traces to already-extracted data. Empty when there's no real
    evidence to summarize (graceful degradation, matching the same
    permanent rule `seed_synthesis.py` established for interview_seeds:
    no fabricated content when evidence is thin)."""
    if not candidate_name and not top_skills:
        return ""

    who = candidate_name or "This candidate"
    # "beginner professional" reads as a contradiction (flagged during the
    # production-walkthrough audit) -- use the same Junior/Mid/Senior
    # wording the rest of the app already shows for this level (frontend
    # experience.level display, candidate_profile_generator._LEVEL_TO_DISPLAY)
    # instead of the raw internal Beginner/Intermediate/Advanced enum value.
    level_word = {"Beginner": "junior", "Intermediate": "mid-level", "Advanced": "senior"}.get(
        experience_level, experience_level.lower()
    )
    parts = [f"{who} is a {level_word} {predicted_domain.lower()} professional"]
    if total_years > 0:
        parts.append(f" with {total_years} years of experience")
    if top_skills:
        parts.append(f", skilled in {', '.join(top_skills[:5])}")
    return "".join(parts) + "."


def _calculate_total_years(experiences: list[dict]) -> int:
    years: list[int] = []
    for exp in experiences:
        duration = exp.get("duration", "") or ""
        years.extend(int(m) for m in _YEAR_PATTERN.findall(duration))
    if len(years) >= 2:
        return max(years) - min(years)
    return 0


def map_to_candidate_profile(annotated: AnnotatedCandidateProfile) -> dict:
    """The Milestone 7 entry point: builds a plain dict shaped EXACTLY
    like `candidate_profile_generator.CandidateProfile.model_dump()` --
    validated by actually constructing that Pydantic model (catching any
    shape mistake here, at translation time, rather than downstream) and
    dumping it back to a dict, matching `generate_candidate_profile`'s
    own return convention exactly."""
    import candidate_profile_generator as gemini_schema

    parser_results = annotated.parser_results

    contact_entities = parser_results.get("contact")
    contact = (contact_entities.entities[0] if contact_entities and contact_entities.entities else {})

    experiences = parser_results.get("experience").entities if "experience" in parser_results else []
    projects = parser_results.get("projects").entities if "projects" in parser_results else []
    education = parser_results.get("education").entities if "education" in parser_results else []
    skills = parser_results.get("skills").entities if "skills" in parser_results else []
    certifications = parser_results.get("certifications").entities if "certifications" in parser_results else []

    profile_text = " ".join(
        [
            " ".join(skills),
            " ".join(_entity_text(p, ("title", "summary", "technologies", "concepts")) for p in projects),
            " ".join(_entity_text(e, ("role", "company", "summary")) for e in experiences),
        ]
    )
    predicted_domain = classify_domain(profile_text)
    experience_level = infer_experience_level(experiences)
    total_years = _calculate_total_years(experiences)

    technical_topics = build_technical_topics(projects, experiences)
    estimated_strengths = estimate_strengths(projects, skills)
    estimated_weaknesses = estimate_weaknesses(annotated.observations)
    starting_difficulty = {"Beginner": "easy", "Intermediate": "intermediate", "Advanced": "hard"}[
        experience_level
    ]

    resume_summary = build_resume_summary(
        contact.get("candidate_name", ""), predicted_domain, experience_level, total_years, skills
    )

    profile = gemini_schema.CandidateProfile(
        candidate_name=contact.get("candidate_name", ""),
        contact_details=gemini_schema.ContactDetails(
            email=contact.get("email", ""),
            phone=contact.get("phone", ""),
            linkedin=contact.get("linkedin", ""),
            location=contact.get("location", ""),
        ),
        skills=list(skills),
        education=[
            gemini_schema.EducationEntry(
                degree=e.get("degree", ""),
                major=e.get("major", ""),
                institution=e.get("institution", ""),
                graduation_year=e.get("graduation_year", ""),
            )
            for e in education
        ],
        experience=[
            gemini_schema.ExperienceEntry(
                company=e.get("company", ""),
                role=e.get("role", ""),
                duration=e.get("duration", ""),
                summary=e.get("summary", ""),
            )
            for e in experiences
        ],
        projects=[
            gemini_schema.ProjectEntry(
                title=p.get("title", ""),
                summary=p.get("summary", ""),
                technologies=list(p.get("technologies") or []),
                concepts=list(p.get("concepts") or []),
                interview_seeds=list(p.get("interview_seeds") or []),
            )
            for p in projects
        ],
        certifications=list(certifications),
        predicted_domain=predicted_domain,
        experience_level=experience_level,
        confidence=annotated.overall_confidence.score,
        interview_blueprint=gemini_schema.InterviewBlueprint(
            resume_verification_topics=[],
            technical_topics=[gemini_schema.TechnicalTopic(**t) for t in technical_topics],
            starting_difficulty=starting_difficulty,
            estimated_strengths=estimated_strengths,
            estimated_weaknesses=estimated_weaknesses,
        ),
        resume_summary=resume_summary,
    )

    return profile.model_dump()
