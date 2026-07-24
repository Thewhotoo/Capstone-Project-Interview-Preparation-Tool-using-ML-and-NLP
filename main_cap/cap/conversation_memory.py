"""
ConversationMemory — Phase 2 of ResumeDiscussion_v2 (Chapter 13, narrowed).

This is a deliberately fresh, evaluation-free memory model — it does NOT
reuse `discussion_engine.DiscussionMemory`, which mixes in evaluation-
derived state (concepts_mastered, concepts_needing_clarification,
current_difficulty) that belongs to a later phase. ConversationMemory
tracks only what Phase 2 (the Question Realizer, Discussion Policy) needs
to phrase a natural, non-repetitive, well-sequenced conversation:

    - which projects/skills/technologies have come up
    - which reasoning types (Chapter 16) have been covered
    - recent phrasing styles / question families / transitions (repetition
      prevention, Chapter 12.4 / Phase 2 Task 9)
    - a full conversation timeline
    - previous answers — METADATA ONLY (e.g. word count), never content or
      a score. Storing an evaluation here would violate the explicit Phase
      2 boundary: "ConversationMemory must not store evaluation."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from interview_question import InterviewQuestion
from question_families import ReasoningType

# How many recent entries repetition-prevention checks look back across —
# small and fixed, matching the legacy Realizer's "avoid the immediately
# preceding style" scope (Chapter 12.2) plus a little extra headroom for
# the family/transition checks Phase 2 adds.
_RECENCY_WINDOW = 3


@dataclass(frozen=True)
class AnswerMetadata:
    """Previous-answer bookkeeping — deliberately NOT the answer text and
    NOT a score. Only shape/length facts a Realizer could plausibly use for
    phrasing (e.g. "the candidate has been giving short answers"), never
    anything evaluation implies about correctness."""

    word_count: int
    sentence_count: int


@dataclass(frozen=True)
class ConversationTurnRecord:
    """One entry in the conversation timeline (Chapter 13)."""

    turn_number: int
    spec_id: str
    source_id: str
    category: str
    family: str
    reasoning_type: ReasoningType
    is_followup: bool
    project_reference: Optional[str]
    answer: Optional[AnswerMetadata] = None


class ConversationMemory:
    """Mutable, session-scoped conversation state. Every mutation happens
    through an explicit method — there is no implicit background tracking —
    so what triggers a memory update is always traceable to one call site."""

    def __init__(self) -> None:
        self.projects_discussed: set[str] = set()
        self.skills_discussed: set[str] = set()
        self.technologies_mentioned: set[str] = set()
        self.reasoning_types_covered: set[ReasoningType] = set()
        self.recent_phrasing_styles: list[tuple[str, int]] = []  # (family, variant_index)
        self.recent_question_families: list[str] = []
        self.recent_transitions: list[str] = []
        self.timeline: list[ConversationTurnRecord] = []
        self._source_touch_counts: dict[str, int] = {}
        # Keyed by (source_id, category) rather than source_id alone: a
        # project's overview/deep-dive/skill_in_context specs all share the
        # SAME source_id (the project title), but each category has its own
        # narrative arc (discussion_policy._ARC) with its own, independent
        # progression — a project touched 8 times by deep-dive questions
        # must not make its FIRST skill_in_context question think it's the
        # 9th step of the (much shorter) skill_in_context arc.
        self._source_category_touch_counts: dict[tuple[str, str], int] = {}

    # ── Recording a turn ──────────────────────────────────────────────────

    def record_turn(
        self,
        question: InterviewQuestion,
        variant_index: int,
        answer_text: Optional[str] = None,
    ) -> None:
        """
        Record that `question` was asked (and, once answered, the shape of
        the candidate's answer — metadata only, never the text itself
        beyond what's needed to compute word/sentence counts, and never a
        score). This is the ONLY place conversation state changes; the
        Question Realizer itself is a pure function and never calls this.
        """
        spec = question.specification

        if spec.grounding.project is not None:
            self.projects_discussed.add(spec.grounding.project.title)
            self.technologies_mentioned.update(spec.grounding.project.technologies)
            self.skills_discussed.update(spec.grounding.project.technologies)

        self.reasoning_types_covered.add(question.reasoning_type)
        self.recent_question_families.append(question.family)
        self.recent_phrasing_styles.append((question.family, variant_index))
        if question.transition_text:
            self.recent_transitions.append(question.transition_text)
        self._source_touch_counts[spec.source_id] = self._source_touch_counts.get(spec.source_id, 0) + 1
        category_key = (spec.source_id, spec.category.value)
        self._source_category_touch_counts[category_key] = self._source_category_touch_counts.get(category_key, 0) + 1

        answer_meta = None
        if answer_text is not None:
            answer_meta = AnswerMetadata(
                word_count=len(answer_text.split()),
                sentence_count=max(1, answer_text.count(".") + answer_text.count("!") + answer_text.count("?")),
            )

        self.timeline.append(ConversationTurnRecord(
            turn_number=question.turn_number,
            spec_id=spec.id,
            source_id=spec.source_id,
            category=spec.category.value,
            family=question.family,
            reasoning_type=question.reasoning_type,
            is_followup=question.is_followup,
            project_reference=question.project_reference,
            answer=answer_meta,
        ))

    # ── Queries used by the Discussion Policy / Question Realizer ────────

    def times_source_touched(self, source_id: str) -> int:
        """How many turns (any category) have already been recorded for
        this exact project/experience/certification identity — used only
        to detect "is this the very first time this topic has come up at
        all" (Discussion Policy's overview-opening special case)."""
        return self._source_touch_counts.get(source_id, 0)

    def times_source_category_touched(self, source_id: str, category: str) -> int:
        """How many turns of THIS SPECIFIC category have already been
        recorded for this source_id — the Discussion Policy's input for
        progressing through that category's own narrative arc, independent
        of how many turns of OTHER categories already happened for the
        same project."""
        return self._source_category_touch_counts.get((source_id, category), 0)

    def family_already_used_for_source(self, source_id: str, family: str) -> bool:
        """Has `family` already been used for this exact source_id, in ANY
        category? Used to stop a project's second category (e.g.
        project_overview, whose own arc starts at "overview") from
        re-opening with an overview-flavored question when a project_deep_dive
        spec already covered that framing for the same project earlier."""
        return any(t.source_id == source_id and t.family == family for t in self.timeline)

    def last_source_id(self) -> Optional[str]:
        return self.timeline[-1].source_id if self.timeline else None

    def last_family(self) -> Optional[str]:
        return self.recent_question_families[-1] if self.recent_question_families else None

    def is_family_recently_used(self, family: str, window: int = _RECENCY_WINDOW) -> bool:
        return family in self.recent_question_families[-window:]

    def is_transition_recently_used(self, text: str, window: int = _RECENCY_WINDOW) -> bool:
        return text in self.recent_transitions[-window:]

    def last_phrasing_style(self) -> Optional[tuple[str, int]]:
        return self.recent_phrasing_styles[-1] if self.recent_phrasing_styles else None

    def turn_count(self) -> int:
        return len(self.timeline)
