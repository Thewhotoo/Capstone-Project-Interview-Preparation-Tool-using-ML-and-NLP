"""
Validation Layer — Stage 7. See
docs/architecture/ResumeIntelligenceEngine.md Section 8 for the full rule
catalogue (Completeness, Consistency, Cross-reference, Structural) and the
explicit non-goal (validation observes, it never gates profile generation).

Only `Observation` (the data model) and a stub engine live here in
Milestone 0; the actual rule functions are Milestone 6 work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class Observation:
    """One validation finding — never a parsing failure, always a quality
    observation about the resume's content (per the architecture doc's
    explicit framing: "these are observations, not parsing failures")."""

    severity: Literal["info", "notice", "warning"]
    category: str  # stable slug, e.g. "missing_technologies", "unverified_skill"
    message: str  # human-readable, e.g. "Project 'X' has no technologies listed."
    entity_ref: str  # e.g. "projects[2]"


class DefaultValidationEngine:
    """Concrete `interfaces.ValidationEngine` implementation. The rule
    catalogue (Section 8 of the architecture doc) is Milestone 6 work —
    not implemented yet."""

    def validate(self, parser_results, trace=None) -> list[Observation]:
        raise NotImplementedError(
            "Validation rules are implemented in Milestone 6 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 8)."
        )
