"""
InterviewQuestion — Phase 2 of ResumeDiscussion_v2 (Chapter 12).

The final, immutable record of a question actually presented to the
candidate. This is deliberately NOT a raw string: a raw string would throw
away exactly the provenance/family/reasoning-type information the rest of
this system (and Phase 3's evaluator/explainability/dashboard) needs.

`specification` is embedded, not referenced by id, so an `InterviewQuestion`
is a fully self-contained, replayable record — Chapter 11.4's immutability
guarantee for `QuestionSpecification` extends transitively to every
`InterviewQuestion` built from one.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from question_families import ReasoningType
from question_specification import QuestionSpecification


class InterviewQuestion(BaseModel):
    """
    Immutable. Produced only by `question_realizer.QuestionRealizer` — no
    other component constructs one, and nothing may modify one after
    creation (Chapter 11.4's immutability principle, extended to the
    Realizer's own output).
    """

    model_config = ConfigDict(frozen=True)

    question_text: str
    """The full text shown to the candidate, including any transition
    phrase (Chapter 8, Transitions)."""

    transition_text: str
    """The transition phrase alone, e.g. "Now let's move on to another
    project. " — empty string for the very first question of a session."""

    specification: QuestionSpecification
    """The immutable Question Specification this question was realized
    from — the permanent provenance record (Chapter 11.4)."""

    family: str
    """Which registered question family (question_families.py) was used —
    the phrasing angle, e.g. "architecture", "debugging"."""

    reasoning_type: ReasoningType
    """The cognitive task this question represents (Chapter 16) — derived
    from `family`, never independently chosen."""

    project_reference: Optional[str]
    """The project title this question is about, if it is project-grounded
    (via `specification.grounding.project`) — None for experience/
    certification-grounded questions."""

    is_followup: bool
    """True if this question is a follow-up on the same specification's
    unit rather than a fresh turn (Chapter 17)."""

    turn_number: int
    """1-indexed position of this question within its session."""

    metadata: tuple[tuple[str, str], ...] = ()
    """An immutable key-value bag reserved for a later evaluation phase
    (e.g. expected concept/technology hints) — a tuple of pairs rather than
    a dict so it cannot be mutated in place despite the model being frozen
    (the same reasoning `Grounding`'s tuple fields use, Chapter 11.4)."""

    def metadata_dict(self) -> dict:
        """Convenience read view — never mutate the result and expect it to
        affect this object; it is a fresh copy every call."""
        return dict(self.metadata)
