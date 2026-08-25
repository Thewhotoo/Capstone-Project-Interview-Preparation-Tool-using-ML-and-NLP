"""
Validation Layer — Stage 7. See
docs/architecture/ResumeIntelligenceEngine.md Section 8 for the full rule
catalogue (Completeness, Consistency, Cross-reference, Structural) and the
explicit non-goal (validation observes, it never gates profile generation).

`DefaultValidationEngine.validate()` does two things:

1. Collects every `Observation` already embedded by an earlier stage --
   parsers raise their own (`missing_technologies`, `missing_degree`,
   `empty_section`, `missing_dates`, ...), Cross-Reference raises
   `skill_not_demonstrated`, Normalization raises
   `duplicate_technologies_merged`/`duplicate_entries_merged`. This stage
   is the single place they all surface together in the final
   `AnnotatedCandidateProfile.observations`, per Section 8's own framing
   of validation as one unified layer.
2. Runs the small set of NEW rules from Section 8's catalogue not already
   covered by an earlier stage: missing LinkedIn, no measurable outcome
   in a project, and an experience entry whose end date precedes its
   start date.

Known, accepted scope gap (documented, not hidden): Section 8's
"unknown/ambiguous section header" structural rule needs the raw
`list[Section]` (with `header_match_reason`), which `ValidationEngine`'s
frozen interface signature (`validate(parser_results, trace)`,
`interfaces.py`) never receives -- only Section Detection's OWN merged
`sections_by_label` dict reaches downstream stages, and that information
is lost by the time this stage runs. Not implementable without an
interface change, which is out of scope for a validation-rule milestone;
noted here rather than silently claiming full Section 8 coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from resume_engine.dates import parse_date_range

_METRIC_PATTERN = re.compile(r"\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?x\b", re.IGNORECASE)


@dataclass
class Observation:
    """One validation finding — never a parsing failure, always a quality
    observation about the resume's content (per the architecture doc's
    explicit framing: "these are observations, not parsing failures")."""

    severity: Literal["info", "notice", "warning"]
    category: str  # stable slug, e.g. "missing_technologies", "unverified_skill"
    message: str  # human-readable, e.g. "Project 'X' has no technologies listed."
    entity_ref: str  # e.g. "projects[2]"


def _collect_embedded_observations(parser_results) -> list[Observation]:
    collected: list[Observation] = []
    for entity_name in sorted(parser_results.keys()):
        collected.extend(parser_results[entity_name].observations)
    return collected


def _rule_missing_linkedin(parser_results) -> list[Observation]:
    contact_result = parser_results.get("contact")
    if not contact_result or not contact_result.entities:
        return []
    contact = contact_result.entities[0]
    if not contact.get("linkedin"):
        return [
            Observation(
                severity="notice",
                category="missing_linkedin",
                message="No LinkedIn profile found in contact details.",
                entity_ref="contact",
            )
        ]
    return []


def _rule_no_measurable_outcome(parser_results) -> list[Observation]:
    project_result = parser_results.get("projects")
    if not project_result:
        return []
    observations = []
    for index, project in enumerate(project_result.entities):
        summary = project.get("summary", "") or ""
        if summary and not _METRIC_PATTERN.search(summary):
            observations.append(
                Observation(
                    severity="info",
                    category="no_measurable_outcome",
                    message=f"Project '{project.get('title', '')}' has no measurable outcome "
                    "(no percentage/multiplier found in its summary).",
                    entity_ref=f"projects[{index}]",
                )
            )
    return observations


def _rule_empty_experience_summary(parser_results) -> list[Observation]:
    experience_result = parser_results.get("experience")
    if not experience_result:
        return []
    observations = []
    for index, experience in enumerate(experience_result.entities):
        if not experience.get("summary"):
            observations.append(
                Observation(
                    severity="info",
                    category="empty_experience_summary",
                    message=f"Experience entry '{experience.get('role', '')}' has an empty summary.",
                    entity_ref=f"experience[{index}]",
                )
            )
    return observations


def _rule_inconsistent_dates(parser_results) -> list[Observation]:
    experience_result = parser_results.get("experience")
    if not experience_result:
        return []
    observations = []
    for index, experience in enumerate(experience_result.entities):
        date_range = parse_date_range(experience.get("duration", "") or "")
        if date_range is None or date_range.start is None or date_range.end is None:
            continue
        if date_range.end < date_range.start:
            observations.append(
                Observation(
                    severity="warning",
                    category="inconsistent_dates",
                    message=f"Experience entry '{experience.get('role', '')}' has an end date "
                    "before its start date.",
                    entity_ref=f"experience[{index}]",
                )
            )
    return observations


_NEW_RULES = (
    _rule_missing_linkedin,
    _rule_no_measurable_outcome,
    _rule_empty_experience_summary,
    _rule_inconsistent_dates,
)


class DefaultValidationEngine:
    """Concrete `interfaces.ValidationEngine` implementation."""

    def validate(self, parser_results, trace=None) -> list[Observation]:
        observations = _collect_embedded_observations(parser_results)
        for rule in _NEW_RULES:
            observations.extend(rule(parser_results))
        return observations
