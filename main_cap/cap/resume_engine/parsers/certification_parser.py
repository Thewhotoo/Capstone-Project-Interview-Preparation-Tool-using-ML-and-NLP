"""
CertificationParser — Stage 4 plugin for the Certifications section. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Structural placeholder implementing `interfaces.EntityParser`. Gazetteer
normalization plus the stray-mention sweep of Skills/Summary sections are
Milestone 5 work.
"""

from __future__ import annotations

from resume_engine.interfaces import ParserResult


class CertificationParser:
    entity_name = "certifications"
    required_sections: tuple[str, ...] = ("certifications",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        raise NotImplementedError(
            "CertificationParser is implemented in Milestone 5 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 4.4)."
        )
