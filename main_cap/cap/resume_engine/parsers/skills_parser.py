"""
SkillsParser — Stage 4 plugin for the Skills section. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Structural placeholder implementing `interfaces.EntityParser`. Gazetteer
normalization against the shared technology/tool gazetteer (also used by
ProjectParser) is Milestone 5 work. Cross-section "demonstrated in a
project" tagging is NOT this parser's job — that's the Cross-Reference
Pass (cross_reference.py, Milestone 5).
"""

from __future__ import annotations

from resume_engine.interfaces import ParserResult


class SkillsParser:
    entity_name = "skills"
    required_sections: tuple[str, ...] = ("skills",)
    version = "0.1.0"

    def parse(self, sections, doc, trace=None) -> ParserResult:
        raise NotImplementedError(
            "SkillsParser is implemented in Milestone 5 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 4.4)."
        )
