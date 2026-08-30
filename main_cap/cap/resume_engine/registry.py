"""
ParserRegistry — Stage 4's collaborator, mirroring this codebase's
existing evaluator_registry.py pattern, adapted for dependency injection
(design review, item 1): rather than a bare module-level singleton being
the ONLY way to use it, `ParserRegistry` is a class implementing
`interfaces.ParserRunner`, so `ResumePipeline` can be constructed with any
instance of it (including a test double with a handful of fake parsers
registered) rather than depending on a specific global.

A default module-level instance plus thin pass-through functions are still
provided for the common case — parsers registering themselves against the
shared default at import time — for ergonomic parity with
evaluator_registry.py's calling style.
"""

from __future__ import annotations

import time

from resume_engine.document_model import DocumentModel
from resume_engine.interfaces import EntityParser, ParserResult, check_parser_conformance
from resume_engine.pipeline_trace import PipelineTrace, StageTrace
from resume_engine.sections import Section


class UnknownParserError(KeyError):
    """Raised when an entity_name isn't registered."""


class ParserRegistry:
    """Concrete `interfaces.ParserRunner` implementation."""

    def __init__(self) -> None:
        self._parsers: dict[str, EntityParser] = {}

    def register_parser(
        self,
        parser: EntityParser,
        *,
        sample_sections: dict[str, Section] | None = None,
        sample_doc: DocumentModel | None = None,
    ) -> None:
        """Registers `parser` under its own declared `.entity_name`. If
        sample fixtures are provided, a one-time conformance check
        (interfaces.check_parser_conformance) runs first — a
        non-conformant parser must never reach the registry, mirroring
        evaluator_registry.register_evaluator."""
        if sample_sections is not None and sample_doc is not None:
            check_parser_conformance(parser, sample_sections, sample_doc)
        self._parsers[parser.entity_name] = parser

    def get_parser(self, entity_name: str) -> EntityParser:
        if entity_name not in self._parsers:
            raise UnknownParserError(entity_name)
        return self._parsers[entity_name]

    def registered_parser_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers.keys()))

    def run_all(
        self,
        sections: dict[str, Section],
        doc: DocumentModel,
        trace: PipelineTrace | None = None,
    ) -> dict[str, ParserResult]:
        """Stage 4: runs every registered parser and merges results keyed
        by entity_name. Records one StageTrace per parser when `trace` is
        active — this is what gives per-parser timing (architecture doc
        Section 6.3) for free — and stamps each parser's declared
        `.version` into `trace.parser_versions` (design-review item 4)."""
        results: dict[str, ParserResult] = {}
        for entity_name, parser in self._parsers.items():
            started_at = time.perf_counter()
            result = parser.parse(sections, doc, trace=trace)
            duration_ms = (time.perf_counter() - started_at) * 1000
            results[entity_name] = result
            if trace is not None:
                trace.parser_versions[entity_name] = parser.version
                trace.record(
                    StageTrace(
                        stage_name=f"parser:{entity_name}",
                        input_summary=parser.required_sections,
                        output_summary=f"{len(result.entities)} entities",
                        metadata={"parser_version": parser.version},
                        warnings=result.observations,
                        confidences=result.confidences,
                        started_at=started_at,
                        duration_ms=duration_ms,
                    )
                )
        return results


# Default shared instance — parsers register against this at import time
# for the common case; ResumePipeline can still be constructed with a
# different ParserRegistry instance (or any other ParserRunner) for tests.
default_registry = ParserRegistry()


def register_parser(parser: EntityParser, **kwargs) -> None:
    default_registry.register_parser(parser, **kwargs)


def get_parser(entity_name: str) -> EntityParser:
    return default_registry.get_parser(entity_name)


def registered_parser_names() -> tuple[str, ...]:
    return default_registry.registered_parser_names()
