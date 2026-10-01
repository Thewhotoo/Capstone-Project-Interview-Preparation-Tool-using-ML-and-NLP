"""
Evaluator Interface — Phase 3 (RFC Section 7 — APPROVED AND FROZEN).
Implemented exactly as specified; preserved verbatim, no redesign.

ONE method: `evaluate(request) -> result`. Stateless — no implementation
may hold session-specific mutable state between calls; everything a call
needs must arrive in that call's `EvaluationRequest`. This is what lets
`HeuristicEvaluator` / `GeminiEvaluator` / `HybridEvaluator` /
`FutureFineTunedEvaluator` all plug in identically, and it is why the
Conversation Engine never needs to change when the evaluator does — it
only ever depends on this interface, resolved once per session via the
Evaluator Registry (dependency injection).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from evaluation_request import EvaluationRequest
from evaluation_result import EvaluationResult
from question_families import ReasoningType


class EvaluatorConformanceError(ValueError):
    """Raised when an evaluator implementation fails to satisfy the
    Evaluator Responsibility Contract (RFC Section 7). A non-conformant
    implementation must never be registered (evaluator_registry.py) —
    mirrors the architecture's existing traceability gates: reject an
    invalid unit before it can ever be selected/used."""


@runtime_checkable
class Evaluator(Protocol):
    """
    Structural interface (a `Protocol`, not required to be subclassed) —
    any object exposing this shape satisfies the contract. This is a
    deliberate choice: it lets `HeuristicEvaluator`, a future
    `GeminiEvaluator`, etc. be entirely independent implementations that
    never need to share a common base class, only a common shape.
    """

    name: str
    version: str
    declared_dimensions: tuple[str, ...]
    declared_reasoning_types: tuple[ReasoningType, ...]
    requires_network: bool

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        ...


def check_conformance(evaluator: Evaluator, sample_request: EvaluationRequest) -> None:
    """
    Runs ONE evaluation call against `sample_request` and verifies the
    result satisfies the Evaluator Responsibility Contract. Raises
    `EvaluatorConformanceError` with a specific reason on the first
    violation found. Intended to run ONCE, at registration time
    (`evaluator_registry.register_evaluator`) — never per live evaluation
    call, which would defeat the point of a stateless, cheap interface.
    """
    for attr in ("name", "version", "declared_dimensions", "declared_reasoning_types", "requires_network"):
        if not hasattr(evaluator, attr):
            raise EvaluatorConformanceError(f"Evaluator is missing required attribute {attr!r}")
    if not evaluator.name.strip():
        raise EvaluatorConformanceError("Evaluator.name must not be empty")
    if not evaluator.version.strip():
        raise EvaluatorConformanceError("Evaluator.version must not be empty")
    if not evaluator.declared_dimensions:
        raise EvaluatorConformanceError("declared_dimensions must not be empty")
    if not evaluator.declared_reasoning_types:
        raise EvaluatorConformanceError("declared_reasoning_types must not be empty")

    result = evaluator.evaluate(sample_request)

    if result.request_id != sample_request.request_id:
        raise EvaluatorConformanceError(
            "EvaluationResult.request_id must match the request it answered"
        )
    if not result.dimensions:
        raise EvaluatorConformanceError("EvaluationResult must contain at least one DimensionScore")

    declared = set(evaluator.declared_dimensions)
    produced = {d.name for d in result.dimensions}
    if not produced.issubset(declared):
        raise EvaluatorConformanceError(
            f"Evaluator produced dimensions {sorted(produced - declared)} it never declared "
            f"(declared: {sorted(declared)})"
        )
    if sample_request.reasoning_type not in evaluator.declared_reasoning_types:
        raise EvaluatorConformanceError(
            f"Evaluator does not declare support for reasoning_type "
            f"{sample_request.reasoning_type!r} used in the sample request"
        )

    # Goal 4 (no opaque scores) — belt-and-suspenders on top of
    # EvaluationResult's own constructor-time validation: a conformance
    # check exists precisely to catch a violation BEFORE registration, not
    # rely on every future caller re-discovering it independently.
    if not result.reasoning.strip():
        raise EvaluatorConformanceError("reasoning must not be empty (Goal 4: no opaque scores)")
    if not result.confidence_rationale.strip():
        raise EvaluatorConformanceError("confidence_rationale must not be empty (Goal 4)")
    if not result.evaluator_name.strip() or not result.evaluator_version.strip():
        raise EvaluatorConformanceError("evaluator_name/evaluator_version must be populated")
    if result.evaluator_name != evaluator.name:
        raise EvaluatorConformanceError(
            f"EvaluationResult.evaluator_name ({result.evaluator_name!r}) does not match "
            f"Evaluator.name ({evaluator.name!r})"
        )
