"""
Cross-Reference Pass — Stage 5. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.5 and
docs/architecture/Milestone4_Design.md (approved design for the
interview_seeds responsibility this stage carries).

`DefaultCrossReferenceEngine` has two responsibilities, per Section 4.5:

1. Interview-seed synthesis (`seed_synthesis.py`, Milestone 4) over every
   parsed `projects` entity, written back onto each project dict's
   existing `interview_seeds` field.
2. Demonstrated-skill tagging (Milestone 5): for each entry in `skills`,
   checks whether that skill is also evidenced in `projects`/`experience`
   text. Per Section 4.5's "annotate, don't add" rule and the public
   `CandidateProfile.skills` shape being a flat `list[str]` (no per-skill
   dict to attach a field to without a schema change), this annotation
   lives entirely in the ENGINE-INTERNAL `Confidence.reasons` for that
   skill (boosted score + a "+demonstrated_in_..." reason) and, when a
   skill is NOT demonstrated, an `Observation` on the skills
   `ParserResult` -- exactly the "skills listed but never demonstrated"
   validation signal Section 8 describes. Neither touches the public
   schema.
"""

from __future__ import annotations

import re
from dataclasses import asdict

from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.pipeline_trace import PipelineTrace, StageTrace
from resume_engine.seed_synthesis import synthesize_seeds
from resume_engine.validation import Observation

_DEMONSTRATED_SCORE_BOOST = 0.1


def _entity_search_text(entity: dict, fields: tuple[str, ...]) -> str:
    parts = []
    for field_name in fields:
        value = entity.get(field_name)
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _tag_demonstrated_skills(parser_results: dict[str, ParserResult]) -> dict:
    """Mutates the `skills` ParserResult's confidences/observations in
    place (engine-internal data, never the public schema). Returns a
    small summary dict for StageTrace metadata."""
    skills_result = parser_results.get("skills")
    if skills_result is None or not skills_result.entities:
        return {"skills_checked": 0, "demonstrated": 0}

    project_result = parser_results.get("projects")
    experience_result = parser_results.get("experience")

    haystacks: list[tuple[str, str, str]] = []  # (kind, name, lowercased text)
    for project in (project_result.entities if project_result else []):
        text = _entity_search_text(project, ("title", "summary", "technologies", "concepts"))
        haystacks.append(("project", project.get("title", "") or "unnamed project", text))
    for experience in (experience_result.entities if experience_result else []):
        text = _entity_search_text(experience, ("role", "company", "summary"))
        name = experience.get("company", "") or experience.get("role", "") or "unnamed experience"
        haystacks.append(("experience", name, text))

    demonstrated_count = 0
    new_confidences: list[Confidence] = []
    for skill, confidence in zip(skills_result.entities, skills_result.confidences):
        pattern = re.compile(r"\b" + re.escape(skill.lower()) + r"\b")
        match = next((h for h in haystacks if pattern.search(h[2])), None)

        reasons = list(confidence.reasons)
        score = confidence.score
        if match is not None:
            kind, name, _ = match
            reasons.append(f"+demonstrated_in_{kind}:{name}")
            score = min(1.0, score + _DEMONSTRATED_SCORE_BOOST)
            demonstrated_count += 1
        else:
            reasons.append("-not_demonstrated_elsewhere")
            skills_result.observations.append(
                Observation(
                    severity="notice",
                    category="skill_not_demonstrated",
                    message=f"Skill '{skill}' is listed but not demonstrated in any project or experience entry.",
                    entity_ref=f"skills[{skill!r}]",
                )
            )
        new_confidences.append(Confidence(score=round(score, 4), reasons=reasons))

    skills_result.confidences = new_confidences
    return {"skills_checked": len(skills_result.entities), "demonstrated": demonstrated_count}


class DefaultCrossReferenceEngine:
    """Concrete `interfaces.CrossReferenceEngine` implementation."""

    def cross_reference(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> dict[str, ParserResult]:
        demonstrated_summary = _tag_demonstrated_skills(parser_results)

        project_result = parser_results.get("projects")
        if project_result is None or not project_result.entities:
            if trace is not None:
                trace.record(
                    StageTrace(
                        stage_name="cross_reference:demonstrated_skills",
                        metadata=demonstrated_summary,
                    )
                )
            return parser_results

        want_accounting = trace is not None
        accountings = []
        stage_confidences = []
        total_seeds = 0

        for project in project_result.entities:
            synthesis = synthesize_seeds(project, want_accounting=want_accounting)
            project["interview_seeds"] = synthesis.seeds
            total_seeds += len(synthesis.seeds)
            stage_confidences.extend(synthesis.seed_confidences)
            if synthesis.accounting is not None:
                accountings.append(synthesis.accounting)

        if trace is not None:
            trace.record(
                StageTrace(
                    stage_name="cross_reference:seed_synthesis",
                    input_summary=f"{len(project_result.entities)} projects",
                    output_summary=f"{total_seeds} interview_seeds generated",
                    metadata={"evidence_accounting": [asdict(a) for a in accountings]},
                    confidences=stage_confidences,
                )
            )
            trace.record(
                StageTrace(
                    stage_name="cross_reference:demonstrated_skills",
                    metadata=demonstrated_summary,
                )
            )

        return parser_results
