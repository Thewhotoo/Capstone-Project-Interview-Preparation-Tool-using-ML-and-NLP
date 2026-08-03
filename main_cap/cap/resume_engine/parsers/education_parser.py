"""
EducationParser — Stage 4 plugin for the Education section (degree, major,
institution, graduation_year). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Structural placeholder implementing `interfaces.EntityParser`. Degree
gazetteer matching, institution corroboration, and graduation-year
extraction are Milestone 5 work — this field has no downstream functional
consumer today (Section 1.2 of the architecture doc), so it is correctly a
lower-priority milestone.
"""

from __future__ import annotations

from resume_engine.interfaces import ParserResult


class EducationParser:
    entity_name = "education"
    required_sections: tuple[str, ...] = ("education",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        raise NotImplementedError(
            "EducationParser is implemented in Milestone 5 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 4.4)."
        )
