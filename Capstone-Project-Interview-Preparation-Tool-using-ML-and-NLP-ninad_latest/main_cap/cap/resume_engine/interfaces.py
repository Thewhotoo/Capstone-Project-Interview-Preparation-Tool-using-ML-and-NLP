"""
Interfaces — every contract the Resume Intelligence Engine's pipeline
depends on. See docs/architecture/ResumeIntelligenceEngine.md Section 5
(plugin parser architecture) and the design-review decision to make
`ResumePipeline` depend on interfaces rather than concrete implementations
for every stage, not only the entity parsers.

Structural typing (`Protocol`, `runtime_checkable`) throughout, mirroring
this codebase's existing `evaluator.py` precedent: any object exposing the
right shape satisfies the contract, with no shared base class required.
Concrete implementations live in the sibling stage modules (extractor.py,
layout.py, sections.py, registry.py, cross_reference.py, normalization.py,
validation.py, confidence.py, parsers/*.py) and are wired together only in
factory.py — this module defines contracts, never implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from resume_engine.confidence import AnnotatedCandidateProfile, Confidence
from resume_engine.document_model import DocumentModel
from resume_engine.pipeline_trace import PipelineTrace
from resume_engine.sections import Section
from resume_engine.validation import Observation

# ── Stage interfaces ─────────────────────────────────────────────────────


@runtime_checkable
class DocumentExtractor(Protocol):
    def extract(
        self, file_path: str, source_format: str, trace: PipelineTrace | None = None
    ) -> DocumentModel: ...


@runtime_checkable
class LayoutReconstructor(Protocol):
    def reconstruct(self, doc: DocumentModel, trace: PipelineTrace | None = None) -> DocumentModel: ...


@runtime_checkable
class SectionDetector(Protocol):
    def detect(self, doc: DocumentModel, trace: PipelineTrace | None = None) -> list[Section]: ...


@dataclass
class ParserResult:
    """One EntityParser's output: the entities it found, one Confidence
    per entity (same order), and any Observations raised during parsing
    itself (e.g. "inconsistent dates")."""

    entities: list[Any] = field(default_factory=list)
    confidences: list[Confidence] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)


class ParserConformanceError(ValueError):
    """Raised when a parser implementation fails to satisfy the
    EntityParser contract. A non-conformant parser must never be
    registered — mirrors evaluator.py's EvaluatorConformanceError."""


@runtime_checkable
class EntityParser(Protocol):
    """Structural interface every entity parser (contact, experience,
    project, education, skills, certification) implements. See
    docs/architecture/ResumeIntelligenceEngine.md Section 5."""

    entity_name: str  # "contact" | "experience" | "projects" | "education" |
    # "skills" | "certifications"
    required_sections: tuple[str, ...]
    version: str  # declared parser revision, mirrors Evaluator.version — recorded
    # into PipelineTrace.parser_versions on every run (registry.py)

    def parse(
        self,
        sections: dict[str, Section],
        doc: DocumentModel,
        trace: PipelineTrace | None = None,
    ) -> ParserResult: ...


@runtime_checkable
class ParserRunner(Protocol):
    """What `ResumePipeline` depends on for Stage 4 — satisfied by
    `registry.ParserRegistry`. Kept as its own interface (rather than the
    pipeline depending on `ParserRegistry` directly) so the pipeline can be
    tested with a fake runner that has no real parsers registered at all."""

    def run_all(
        self,
        sections: dict[str, Section],
        doc: DocumentModel,
        trace: PipelineTrace | None = None,
    ) -> dict[str, ParserResult]: ...


@runtime_checkable
class CrossReferenceEngine(Protocol):
    def cross_reference(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> dict[str, ParserResult]: ...


@runtime_checkable
class Normalizer(Protocol):
    def normalize(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> dict[str, ParserResult]: ...


@runtime_checkable
class ValidationEngine(Protocol):
    def validate(
        self, parser_results: dict[str, ParserResult], trace: PipelineTrace | None = None
    ) -> list[Observation]: ...


@runtime_checkable
class ConfidenceEngine(Protocol):
    def score(
        self,
        parser_results: dict[str, ParserResult],
        observations: list[Observation],
        trace: PipelineTrace | None = None,
    ) -> AnnotatedCandidateProfile: ...


# ── Conformance checking ─────────────────────────────────────────────────


def check_parser_conformance(
    parser: EntityParser,
    sample_sections: dict[str, Section],
    sample_doc: DocumentModel,
) -> None:
    """Runs ONE parse() call against sample fixtures and verifies the
    result satisfies the EntityParser contract. Mirrors evaluator.py's
    check_conformance: intended to run once, at registration time
    (registry.ParserRegistry.register_parser), never per live parse call."""

    for attr in ("entity_name", "required_sections", "version"):
        if not hasattr(parser, attr):
            raise ParserConformanceError(f"Parser is missing required attribute {attr!r}")
    if not parser.entity_name.strip():
        raise ParserConformanceError("EntityParser.entity_name must not be empty")
    if not parser.required_sections:
        raise ParserConformanceError("EntityParser.required_sections must not be empty")
    if not parser.version.strip():
        raise ParserConformanceError("EntityParser.version must not be empty")

    result = parser.parse(sample_sections, sample_doc)

    if not isinstance(result, ParserResult):
        raise ParserConformanceError("parse() must return a ParserResult")
    if len(result.entities) != len(result.confidences):
        raise ParserConformanceError(
            f"parse() returned {len(result.entities)} entities but "
            f"{len(result.confidences)} confidences — must be 1:1"
        )
    for confidence in result.confidences:
        if not confidence.reasons:
            raise ParserConformanceError(
                "Every Confidence must carry non-empty .reasons — confidence must "
                "always be explainable "
                "(see docs/architecture/ResumeIntelligenceEngine.md Section 7)"
            )
