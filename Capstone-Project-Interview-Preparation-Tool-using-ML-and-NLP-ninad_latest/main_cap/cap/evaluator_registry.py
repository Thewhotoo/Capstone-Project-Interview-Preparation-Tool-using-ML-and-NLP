"""
Evaluator Registry — Phase 3 (RFC Section 7 / architecture Chapter 19.8 —
APPROVED AND FROZEN). Implemented exactly as specified.

Resolves "the active evaluator" by name. The Conversation Engine's
orchestration layer depends on THIS registry, never on a concrete evaluator
class directly — this is the dependency-injection seam that lets
`HeuristicEvaluator` be swapped for `GeminiEvaluator`/`HybridEvaluator`/a
future fine-tuned model without any caller changing.

Risk mitigation from the RFC (Section 10, "model-replacement-mid-session
risk"): the active evaluator must be resolved ONCE per session, at session
start, and pinned for that session's full duration — never re-resolved per
turn. This module only exposes "resolve now"; callers (evaluation_engine.py
/ conversation_engine.py) are responsible for holding onto what they get
back rather than calling `get_active_evaluator()` again mid-session.
"""

from __future__ import annotations

from typing import Optional

from evaluation_request import EvaluationRequest
from evaluator import Evaluator, check_conformance


class UnknownEvaluatorError(KeyError):
    """Raised when a name isn't registered, or no active evaluator has
    been set yet."""


_registry: dict[str, Evaluator] = {}
_active_name: Optional[str] = None


def register_evaluator(
    evaluator: Evaluator,
    *,
    sample_request: Optional[EvaluationRequest] = None,
    make_active: bool = False,
) -> None:
    """
    Register `evaluator` under its own declared `.name`. If `sample_request`
    is provided, a one-time conformance check (evaluator.check_conformance)
    runs before registration — a non-conformant evaluator must never reach
    the registry, mirroring the traceability gates elsewhere in this
    architecture that reject invalid units before they can ever be selected.
    """
    if sample_request is not None:
        check_conformance(evaluator, sample_request)
    _registry[evaluator.name] = evaluator
    if make_active:
        set_active_evaluator(evaluator.name)


def set_active_evaluator(name: str) -> None:
    global _active_name
    if name not in _registry:
        raise UnknownEvaluatorError(name)
    _active_name = name


def get_evaluator(name: str) -> Evaluator:
    if name not in _registry:
        raise UnknownEvaluatorError(name)
    return _registry[name]


def get_active_evaluator() -> Evaluator:
    """Resolve the currently-active evaluator. Callers MUST call this only
    once per session (at session start) and hold onto the returned
    reference for that session's lifetime — see this module's docstring."""
    if _active_name is None:
        raise UnknownEvaluatorError("no active evaluator has been set")
    return _registry[_active_name]


def registered_evaluator_names() -> tuple[str, ...]:
    return tuple(sorted(_registry.keys()))


def active_evaluator_name() -> Optional[str]:
    return _active_name
