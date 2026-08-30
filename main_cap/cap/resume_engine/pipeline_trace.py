"""
PipelineTrace — first-class observability for the Resume Intelligence
Engine. See docs/architecture/ResumeIntelligenceEngine.md Section 6 for
the full design ("one object, multiple renderers").

Every pipeline stage accepts an optional `trace: PipelineTrace | None`
parameter (default None). When None, nothing here is touched — zero
behavioral or performance cost in production. When a caller supplies a
real PipelineTrace, each stage appends one StageTrace before returning.

Unlike the parsing/extraction stages, this module is real, working
infrastructure as of Milestone 0 (Section 6.6 of the architecture doc: the
trace hook must exist before the stages that use it are written, not be
retrofitted later). `to_html()` is the one deferred renderer (Milestone 6,
once there's a substantial pipeline worth visualizing).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from resume_engine import __version__ as _ENGINE_VERSION
from resume_engine.confidence import Confidence
from resume_engine.validation import Observation


@dataclass
class StageTrace:
    """Everything observable about one pipeline stage's execution: what it
    received, what it produced, why (metadata + confidences + warnings),
    and how long it took."""

    stage_name: str
    input_summary: Any = None
    output_summary: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[Observation] = field(default_factory=list)
    confidences: list[Confidence] = field(default_factory=list)
    started_at: float = 0.0
    duration_ms: float = 0.0


@dataclass
class PipelineTrace:
    """The full record of one pipeline run.

    `engine_version` and `parser_versions` (design-review item 4) make it
    possible to tell, from a trace alone, exactly which engine/parser
    revision produced it — the mechanism for comparing parser revisions
    against each other during long-term development, without touching the
    public `CandidateProfile` schema at all (versioning is an internal
    observability concern, not a product output)."""

    document_id: str
    engine_version: str = _ENGINE_VERSION
    parser_versions: dict[str, str] = field(default_factory=dict)
    stages: list[StageTrace] = field(default_factory=list)

    @property
    def total_duration_ms(self) -> float:
        return sum(stage.duration_ms for stage in self.stages)

    def record(self, stage_trace: StageTrace) -> None:
        self.stages.append(stage_trace)

    def to_json(self) -> str:
        return json.dumps(
            {
                "document_id": self.document_id,
                "engine_version": self.engine_version,
                "parser_versions": self.parser_versions,
                "total_duration_ms": self.total_duration_ms,
                "stages": [asdict(stage) for stage in self.stages],
            },
            indent=2,
            default=str,
        )

    def to_console(self) -> str:
        lines = [
            f"PipelineTrace for {self.document_id} "
            f"(engine {self.engine_version}, {self.total_duration_ms:.1f}ms total)"
        ]
        for stage in self.stages:
            lines.append(f"  {stage.stage_name}: {stage.duration_ms:.1f}ms")
            for confidence in stage.confidences:
                lines.append(f"    Confidence: {confidence.score:.2f}")
                for reason in confidence.reasons:
                    if reason.startswith("+"):
                        lines.append(f"      ✓ {reason[1:]}")
                    elif reason.startswith("-"):
                        lines.append(f"      ⚠ {reason[1:]}")
                    else:
                        lines.append(f"      - {reason}")
            for warning in stage.warnings:
                lines.append(f"    [{warning.severity}] {warning.message}")
        return "\n".join(lines)

    def to_html(self) -> str:
        raise NotImplementedError(
            "HTML trace rendering lands in Milestone 6, once there is a "
            "substantial enough pipeline to be worth visualizing "
            "(see docs/architecture/ResumeIntelligenceEngine.md Section 6.6)."
        )
