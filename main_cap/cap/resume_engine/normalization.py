"""
Normalization — Stage 6. See
docs/architecture/ResumeIntelligenceEngine.md Section 4.6.

`DefaultNormalizer` is a structural placeholder satisfying
`interfaces.Normalizer`. Unicode/whitespace cleanup, date canonicalization,
and technology de-aliasing/dedup are Milestone 6 work — not implemented
here.
"""

from __future__ import annotations

from resume_engine.interfaces import ParserResult
from resume_engine.pipeline_trace import PipelineTrace


class DefaultNormalizer:
    """Concrete `interfaces.Normalizer` implementation."""

    def normalize(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> dict[str, ParserResult]:
        raise NotImplementedError(
            "Normalization (unicode/whitespace cleanup, date canonicalization, "
            "de-aliasing/dedup) is implemented in Milestone 6 "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 4.6)."
        )
