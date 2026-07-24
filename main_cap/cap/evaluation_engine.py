"""
Evaluation Engine orchestration — Phase 3 (RFC Section 9 — APPROVED AND
FROZEN; Expected Concepts revision — APPROVED). Implemented exactly as
specified.

This is the ONE module in the whole system permitted to know about both
the Conversation Engine's types (`InterviewQuestion`, `ConversationMemory`,
`Planner`) and the Evaluation Engine's types (`EvaluationRequest`,
`Evaluator`, `EvaluationResult`) — exactly the "seam" the frozen RFC
describes in Section 1 and Section 9. Neither `conversation_memory.py`,
`question_realizer.py`, `discussion_policy.py`, `planner.py`, nor
`topic_pool.py` import anything from this module or from any Evaluation
Engine module — that is the "Conversation Engine must remain completely
unaware of evaluation" boundary, verified by test_evaluation_engine.py's
import-graph assertion.

Also home to the Evaluation Ledger: a session-scoped, append-only store of
`EvaluationResult`s. Deliberately NOT a field on `ConversationMemory` —
Phase 2 approved ConversationMemory specifically as evaluation-free, and
this module preserves that boundary rather than quietly eroding it.

Expected Concepts revision (approved): this module is also where
`expected_concepts` gets populated — via `expected_concepts_registry`'s
deterministic lookup table, consulted against the specification's grounding
fields. This keeps the lookup entirely inside the Evaluation Engine's own
boundary; `QuestionSpecification`/`Planner`/`TopicPool` are untouched.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from conversation_memory import ConversationMemory
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import EvaluationResult
from evaluator import Evaluator
from expected_concepts_registry import expected_concepts_for
from interview_question import InterviewQuestion
from planner import Planner


def build_request(
    interview_question: InterviewQuestion,
    answer_text: str,
    memory: ConversationMemory,
    planner: Planner,
    answer_history: dict[str, tuple[str, ...]],
    evaluation_focus: Optional[str] = None,
) -> EvaluationRequest:
    """
    Assemble the ONE immutable object the Evaluator ever sees. Reads
    `InterviewQuestion`/`ConversationMemory`/`Planner` (Conversation Engine
    types) and produces an `EvaluationRequest` (Evaluation Engine type) —
    this function's entire existence IS the boundary between the two.

    `answer_history` is orchestration-layer session state (owned by the
    caller, e.g. conversation_engine.py's session dict) mapping spec_id ->
    the tuple of raw answer texts already given for that spec THIS session
    — NOT stored in ConversationMemory (Phase 2's approved boundary
    excludes even metadata-derived raw text; this RFC field needs the
    actual text, so it lives here instead, one layer up).
    """
    spec = interview_question.specification
    lifecycle = planner.pool.lifecycle_of(spec.id)
    followups_used = lifecycle.followups_used if lifecycle is not None else 0

    context = ConversationContextSnapshot(
        turn_number=interview_question.turn_number,
        is_followup=interview_question.is_followup,
        prior_answers_for_this_spec=answer_history.get(spec.id, ()),
        followups_used_on_this_spec=followups_used,
        projects_discussed_so_far=tuple(sorted(memory.projects_discussed)),
        technologies_mentioned_so_far=tuple(sorted(memory.technologies_mentioned)),
        reasoning_types_covered_so_far=tuple(memory.reasoning_types_covered),
    )

    return EvaluationRequest(
        request_id=f"evalreq_{_uuid.uuid4().hex[:12]}",
        requested_at=datetime.now(timezone.utc).isoformat(),
        specification=spec,
        question_text=interview_question.question_text,
        reasoning_type=interview_question.reasoning_type,
        answer_text=answer_text,
        conversation_context=context,
        evaluation_focus=evaluation_focus,
        expected_concepts=_lookup_expected_concepts(spec),
    )


def _lookup_expected_concepts(spec) -> tuple[str, ...]:
    """
    Deterministic lookup only — never predicted, never invented (approved
    RFC's explicit rejection of model-derived expected concepts). Tries
    every grounding-derived candidate name against
    `expected_concepts_registry`; an unrecognized name simply contributes
    nothing (graceful degradation, logged for offline curation).
    """
    grounding = spec.grounding
    if grounding.project is not None:
        candidates = (*grounding.project.technologies, *grounding.project.concepts, grounding.project.title)
    elif grounding.certification is not None:
        candidates = (grounding.certification.name,)
    else:
        candidates = ()
    return expected_concepts_for(candidates)


def evaluate(evaluator: Evaluator, request: EvaluationRequest) -> EvaluationResult:
    """Thin, explicit call-through — exists so every evaluation call in the
    system goes through one named function, not a scattered
    `evaluator.evaluate(...)` call at every call site."""
    return evaluator.evaluate(request)


class EvaluationLedger:
    """
    Session-scoped, append-only accumulator of `EvaluationResult`s — the
    "Evaluation Ledger" named in the frozen RFC (Section 1). Lives at the
    orchestration/session layer, never inside `ConversationMemory`.
    """

    def __init__(self) -> None:
        self._results: list[EvaluationResult] = []

    def append(self, result: EvaluationResult) -> None:
        self._results.append(result)

    def all(self) -> tuple[EvaluationResult, ...]:
        return tuple(self._results)

    def for_specification(self, specification_id: str) -> tuple[EvaluationResult, ...]:
        return tuple(r for r in self._results if r.specification_id == specification_id)

    def __len__(self) -> int:
        return len(self._results)
