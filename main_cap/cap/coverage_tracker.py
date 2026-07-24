"""
Coverage Tracker — Phase 1 of ResumeDiscussion_v2
(docs/architecture/ResumeDiscussion_v2.md, Chapter 14).

Implemented as an independent, directly-testable component rather than
folded into TopicPool's selection logic, per the Phase 1 instruction to
"implement independent coverage tracking." TopicPool owns one
CoverageTracker instance and delegates every coverage question to it; this
module has no knowledge of scoring, selection, or Question Specifications at
all — it only ever answers two questions, exactly as Chapter 14 defines them:

    - which categories are PRESENT on this profile (a profile with no
      certifications simply never has that category — a fact about the
      candidate, not a gap in the system), and
    - which categories have been COVERED (touched at least once) so far in
      this session.

`all_covered()` is the completion gate the architecture requires
(`all_categories_covered()`, Chapter 14) before a session may end at its
soft target length (FR5).
"""

from __future__ import annotations

from question_specification import QuestionCategory


class CoverageTracker:
    def __init__(self, present_categories: set[QuestionCategory]):
        self._present: frozenset[QuestionCategory] = frozenset(present_categories)
        self._covered: set[QuestionCategory] = set()

    def present(self) -> frozenset[QuestionCategory]:
        """Categories that actually have at least one unit on this profile."""
        return self._present

    def covered(self) -> frozenset[QuestionCategory]:
        """Categories touched (status != unasked) at least once this session."""
        return frozenset(self._covered)

    def uncovered(self) -> frozenset[QuestionCategory]:
        """Present categories not yet touched this session."""
        return self._present - self._covered

    def mark_covered(self, category: QuestionCategory) -> None:
        """
        Record that `category` has been touched this session. Raises if
        `category` isn't actually present on this profile — marking a
        category covered that the profile never had units for would be a
        bug in the caller, not a legitimate state transition.
        """
        if category not in self._present:
            raise ValueError(
                f"{category.value!r} is not a category present on this profile "
                f"(present categories: {sorted(c.value for c in self._present)})"
            )
        self._covered.add(category)

    def all_covered(self) -> bool:
        """True once every present category has been touched at least once —
        the completion gate (Chapter 14, FR5)."""
        return self._present <= self._covered
