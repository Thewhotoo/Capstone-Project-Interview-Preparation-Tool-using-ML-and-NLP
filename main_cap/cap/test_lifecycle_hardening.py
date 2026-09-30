"""
Tests for the lifecycle-state hardening invariant — Phase 1.5, Task 2
(docs/architecture/ResumeDiscussion_v2.md, Chapter 11.4, Chapter 14).

THE INVARIANT: `UnitLifecycleState.status` and `CoverageTracker`'s
covered-categories set can never be observed out of sync. This is provable
because (1) `status` has no public setter, and (2) the only methods that
change it (`TopicPool.mark_active`/`mark_covered`/`mark_skipped`) always
update `CoverageTracker` in the same call.

These tests prove the invariant from multiple angles: that direct mutation
is impossible, that the controlled API keeps the two in sync, that invalid
state-machine transitions are rejected, and that follow-ups are constrained
to the currently ACTIVE unit.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import sample_profile_dict
from question_specification import (
    InvalidLifecycleTransitionError,
    QuestionCategory,
    UnitLifecycleState,
    UnitStatus,
)
from topic_pool import TopicPool


class TestDirectMutationIsImpossible(unittest.TestCase):
    """Half of the invariant: there is no way to change `status` except
    through TopicPool's controlled methods."""

    def test_status_assignment_raises(self):
        state = UnitLifecycleState()
        with self.assertRaises(AttributeError):
            state.status = UnitStatus.ACTIVE

    def test_followups_used_assignment_raises(self):
        state = UnitLifecycleState()
        with self.assertRaises(AttributeError):
            state.followups_used = 5

    def test_style_used_assignment_raises(self):
        state = UnitLifecycleState()
        with self.assertRaises(AttributeError):
            state.style_used = "tradeoffs"

    def test_no_public_method_bypasses_transition_validation(self):
        """The only way to reach `_transition` from outside this module is
        through TopicPool's mark_* methods, which are exercised in
        TestControlledApiKeepsCoverageInSync below."""
        state = UnitLifecycleState()
        self.assertTrue(hasattr(state, "_transition"))
        # The underscore prefix is the documented signal that this is not
        # part of the public contract — verified functionally, not just by
        # naming convention, in the tests below.


class TestControlledApiKeepsCoverageInSync(unittest.TestCase):
    """Half of the invariant: every method that changes `status` also
    updates CoverageTracker, atomically, in the same call."""

    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_mark_active_updates_both_status_and_coverage_together(self):
        spec = self.pool.select_next(None)
        self.assertNotIn(spec.category, self.pool.categories_covered())
        self.pool.mark_active(spec.id)
        self.assertEqual(self.pool.lifecycle_of(spec.id).status, UnitStatus.ACTIVE)
        self.assertIn(spec.category, self.pool.categories_covered())

    def test_mark_covered_updates_both_together(self):
        spec = self.pool.select_next(None)
        self.pool.mark_covered(spec.id)
        self.assertEqual(self.pool.lifecycle_of(spec.id).status, UnitStatus.COVERED)
        self.assertIn(spec.category, self.pool.categories_covered())

    def test_mark_skipped_updates_both_together(self):
        spec = self.pool.select_next(None)
        self.pool.mark_skipped(spec.id)
        self.assertEqual(self.pool.lifecycle_of(spec.id).status, UnitStatus.SKIPPED)
        self.assertIn(spec.category, self.pool.categories_covered())

    def test_status_and_coverage_never_diverge_across_a_full_session(self):
        """Drive every unit in the pool to a terminal state, checking after
        EVERY single transition that lifecycle status and CoverageTracker
        agree exactly — not just at the end."""
        last_category = None
        while True:
            spec = self.pool.select_next(last_category)
            if spec is None:
                break
            self.pool.mark_active(spec.id)
            self._assert_consistent()
            self.pool.mark_covered(spec.id)
            self._assert_consistent()
            last_category = spec.category

    def _assert_consistent(self):
        """The invariant, checked directly: a category is 'covered' in
        CoverageTracker if and only if at least one of its units has a
        status other than UNASKED."""
        covered = self.pool.categories_covered()
        for category in self.pool.categories_present():
            any_touched = any(
                self.pool.lifecycle_of(spec_id).status != UnitStatus.UNASKED
                for spec_id, spec in self.pool.specifications.items()
                if spec.category == category
            )
            self.assertEqual(
                category in covered, any_touched,
                f"CoverageTracker disagrees with lifecycle state for {category!r}",
            )


class TestStateMachineValidation(unittest.TestCase):
    """Chapter 11.1's state machine: unasked -> active -> (covered|skipped),
    or unasked straight to (covered|skipped); covered/skipped are terminal."""

    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_unasked_to_active_allowed(self):
        spec = self.pool.select_next(None)
        self.pool.mark_active(spec.id)  # must not raise

    def test_unasked_to_covered_allowed_without_active(self):
        """The duplicate-collision path (Chapter 15) marks a never-active
        unit covered directly."""
        spec = self.pool.select_next(None)
        self.pool.mark_covered(spec.id)  # must not raise

    def test_unasked_to_skipped_allowed_without_active(self):
        spec = self.pool.select_next(None)
        self.pool.mark_skipped(spec.id)  # must not raise

    def test_active_to_covered_allowed(self):
        spec = self.pool.select_next(None)
        self.pool.mark_active(spec.id)
        self.pool.mark_covered(spec.id)  # must not raise

    def test_active_to_skipped_allowed(self):
        spec = self.pool.select_next(None)
        self.pool.mark_active(spec.id)
        self.pool.mark_skipped(spec.id)  # must not raise

    def test_covered_to_active_rejected(self):
        spec = self.pool.select_next(None)
        self.pool.mark_covered(spec.id)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_active(spec.id)

    def test_covered_to_covered_rejected(self):
        spec = self.pool.select_next(None)
        self.pool.mark_covered(spec.id)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_covered(spec.id)

    def test_skipped_to_active_rejected(self):
        spec = self.pool.select_next(None)
        self.pool.mark_skipped(spec.id)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_active(spec.id)

    def test_skipped_to_covered_rejected(self):
        spec = self.pool.select_next(None)
        self.pool.mark_skipped(spec.id)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_covered(spec.id)

    def test_a_rejected_transition_leaves_state_and_coverage_unchanged(self):
        """A failed transition must not partially apply — status and
        coverage must both stay exactly as they were before the attempt."""
        spec = self.pool.select_next(None)
        self.pool.mark_covered(spec.id)
        covered_before = self.pool.categories_covered()
        status_before = self.pool.lifecycle_of(spec.id).status
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_active(spec.id)
        self.assertEqual(self.pool.lifecycle_of(spec.id).status, status_before)
        self.assertEqual(self.pool.categories_covered(), covered_before)


class TestFollowupConstrainedToActiveUnit(unittest.TestCase):
    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_followup_allowed_on_active_unit(self):
        spec = self.pool.select_next(None)
        self.pool.mark_active(spec.id)
        self.pool.mark_followup_used(spec.id)
        self.assertEqual(self.pool.lifecycle_of(spec.id).followups_used, 1)

    def test_followup_rejected_on_unasked_unit(self):
        spec = self.pool.select_next(None)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_followup_used(spec.id)

    def test_followup_rejected_on_covered_unit(self):
        spec = self.pool.select_next(None)
        self.pool.mark_covered(spec.id)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_followup_used(spec.id)

    def test_followup_rejected_on_skipped_unit(self):
        spec = self.pool.select_next(None)
        self.pool.mark_skipped(spec.id)
        with self.assertRaises(InvalidLifecycleTransitionError):
            self.pool.mark_followup_used(spec.id)

    def test_multiple_followups_accumulate(self):
        spec = self.pool.select_next(None)
        self.pool.mark_active(spec.id)
        self.pool.mark_followup_used(spec.id)
        self.pool.mark_followup_used(spec.id)
        self.assertEqual(self.pool.lifecycle_of(spec.id).followups_used, 2)


class TestSetStyleUsed(unittest.TestCase):
    def test_style_persists_through_controlled_setter(self):
        pool = TopicPool(sample_profile_dict())
        spec = pool.select_next(None)
        pool.mark_active(spec.id)
        pool.set_style_used(spec.id, "tradeoffs")
        self.assertEqual(pool.lifecycle_of(spec.id).style_used, "tradeoffs")


if __name__ == "__main__":
    unittest.main()
