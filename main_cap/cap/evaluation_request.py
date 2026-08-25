"""
EvaluationRequest — Phase 3 (RFC: AI Evaluation Engine, Revision 2 — APPROVED
AND FROZEN; Expected Concepts revision — APPROVED). Implemented exactly as
specified; no architectural deviation.

The Evaluator's complete, self-contained input. Deliberately minimal per the
frozen RFC's Section 2: no `InterviewQuestion`, no live `ConversationMemory`
reference — only what evaluation genuinely needs: the immutable
`QuestionSpecification`, the literal question text and reasoning type
actually targeted, the raw candidate answer, a narrow, frozen conversation
snapshot, and (approved final revision) the deterministically-derived list
of concepts a strong answer to this turn should touch on.

This is the ONLY object type shared between the Conversation Engine side
and the Evaluation Engine side. Nothing in this module imports
`InterviewQuestion`, `ConversationMemory`, `Planner`, or `TopicPool` — the
orchestration layer (evaluation_engine.py) is the one place permitted to
know about both sides; see the RFC Section 9/10 for why.

SCHEMA VERSION BUMPED v1 -> v2 for the Expected Concepts revision (Chapter
8.5's versioning discipline: adding a field is routine evolution, not a
breaking change, as long as the version stamp changes alongside it).
`expected_concepts` defaults to an empty tuple, so every `v1`-shaped request
remains valid under this schema unchanged.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from question_families import ReasoningType
from question_specification import QuestionSpecification

EVALUATION_REQUEST_SCHEMA_VERSION = "v2"


class ConversationContextSnapshot(BaseModel):
    """
    A frozen, narrow COPY of exactly what the Evaluator is allowed to know
    about the conversation so far — never a live reference to
    ConversationMemory. This is the load-bearing decision for Goal 1
    (complete Conversation/Evaluation independence, RFC Section 2): the
    Evaluator can never come to depend on ConversationMemory's internal
    structure, because it never sees a ConversationMemory instance at all.
    """

    model_config = ConfigDict(frozen=True)

    turn_number: int
    is_followup: bool
    prior_answers_for_this_spec: tuple[str, ...] = ()
    followups_used_on_this_spec: int = 0
    projects_discussed_so_far: tuple[str, ...] = ()
    technologies_mentioned_so_far: tuple[str, ...] = ()
    reasoning_types_covered_so_far: tuple[ReasoningType, ...] = ()

    @model_validator(mode="after")
    def _bounds(self) -> "ConversationContextSnapshot":
        if self.turn_number < 1:
            raise ValueError("turn_number must be >= 1")
        if self.followups_used_on_this_spec < 0:
            raise ValueError("followups_used_on_this_spec must be >= 0")
        return self


class EvaluationRequest(BaseModel):
    """
    Immutable. Assembled once, by the orchestration layer, per candidate
    answer. Field-by-field rationale lives in the frozen RFC (Phase 3,
    Revision 2, Section 2) — not repeated here; this module implements it,
    it does not re-derive it.
    """

    model_config = ConfigDict(frozen=True)

    request_id: str
    schema_version: str = EVALUATION_REQUEST_SCHEMA_VERSION
    requested_at: str  # ISO8601

    specification: QuestionSpecification
    question_text: str
    reasoning_type: ReasoningType

    answer_text: str

    conversation_context: ConversationContextSnapshot
    evaluation_focus: Optional[str] = None

    # Expected Concepts (final ML RFC revision — APPROVED). Deterministically
    # derived — NEVER predicted, never invented (see the approved RFC's
    # rejection of model-derived expected concepts). Populated by the
    # orchestration layer (evaluation_engine.py) via a growable lookup table
    # (expected_concepts_registry.py); empty when no table entry matches
    # this turn's grounding — graceful degradation, never an error.
    expected_concepts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _non_empty_provenance(self) -> "EvaluationRequest":
        for field_name in ("request_id", "requested_at", "question_text"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        return self
