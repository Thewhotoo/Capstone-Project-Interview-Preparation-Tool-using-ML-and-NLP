"""
Cross-Reference Pass — Stage 5. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.5.

`DefaultCrossReferenceEngine` is a structural placeholder satisfying
`interfaces.CrossReferenceEngine`. Demonstrated-skill tagging and
interview_seed synthesis (per the Milestone 4 design pass) are Milestone 5
work — not implemented here.
"""

from __future__ import annotations

from resume_engine.interfaces import ParserResult
from resume_engine.pipeline_trace import PipelineTrace


class DefaultCrossReferenceEngine:
    """Concrete `interfaces.CrossReferenceEngine` implementation."""

    def cross_reference(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> dict[str, ParserResult]:
        raise NotImplementedError(
            "Cross-reference pass (demonstrated-skills tagging, interview_seed "
            "synthesis) is implemented in Milestone 5 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 4.5)."
        )
