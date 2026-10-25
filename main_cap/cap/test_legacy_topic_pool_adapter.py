"""
Tests for legacy_topic_pool_adapter.py — Phase 1.5, Task 1 (migration).

Verifies the compatibility wrapper in isolation (test_e2e.py and
_verify_traceability.py already exercise it through discussion_engine.py's
real phrasing functions and turn loop; these tests focus on the adapter's
own dict-view contract).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _planning_test_fixtures import sample_profile_dict
from legacy_topic_pool_adapter import TopicPool, _UnitView


class TestUnitsProperty(unittest.TestCase):
    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_units_returns_a_dict_of_all_specs(self):
        self.assertEqual(len(self.pool.units), len(self.pool._pool.specifications))

    def test_units_values_are_dict_like(self):
        for unit in self.pool.units.values():
            self.assertEqual(unit["status"], "unasked")
            self.assertIn("category", unit)
            self.assertIn("grounding", unit)

    def test_units_keys_match_pool_specification_ids(self):
        self.assertEqual(set(self.pool.units.keys()), set(self.pool._pool.specifications.keys()))


class TestDictShapeCompatibility(unittest.TestCase):
    """Every key the legacy unit dict had must still be readable the same way."""

    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())
        self.unit = self.pool.select_next(None)

    def test_all_legacy_keys_present(self):
        for key in (
            "id", "category", "text_seed", "grounding", "status", "followups_used",
            "priority_boost", "source_type", "source_id", "source_field", "reason",
            "style_used",
        ):
            self.assertIn(key, self.unit)

    def test_category_and_source_type_are_plain_strings(self):
        self.assertIsInstance(self.unit["category"], str)
        self.assertIsInstance(self.unit["source_type"], str)

    def test_grounding_has_exactly_one_key_matching_source_type(self):
        grounding = self.unit["grounding"]
        self.assertEqual(len(grounding), 1)
        self.assertIn(self.unit["source_type"], grounding)

    def test_dict_get_with_default_works(self):
        self.assertEqual(self.unit.get("nonexistent_key", "fallback"), "fallback")


class TestLiveMutationRoutesThroughHardenedApi(unittest.TestCase):
    """The critical compatibility requirement: `unit["status"] = "covered"`
    (as existing tests/legacy code do) must be a REAL state change, not a
    dead-end write to a throwaway snapshot — otherwise select_next() would
    keep re-offering the same unit forever."""

    def setUp(self):
        self.pool = TopicPool(sample_profile_dict())

    def test_status_assignment_persists_across_select_next_calls(self):
        unit = self.pool.select_next(None)
        first_id = unit["id"]
        unit["status"] = "covered"
        # A second select_next must NOT return the same unit again — this
        # only holds if the assignment above actually reached the pool.
        next_unit = self.pool.select_next(unit["category"])
        self.assertNotEqual(next_unit["id"], first_id)

    def test_status_assignment_active_then_covered(self):
        unit = self.pool.select_next(None)
        unit["status"] = "active"
        self.assertEqual(self.pool.get(unit["id"])["status"], "active")
        unit["status"] = "covered"
        self.assertEqual(self.pool.get(unit["id"])["status"], "covered")

    def test_followups_used_increment_persists(self):
        unit = self.pool.select_next(None)
        unit["status"] = "active"
        unit["followups_used"] += 1
        refetched = self.pool.get(unit["id"])
        self.assertEqual(refetched["followups_used"], 1)

    def test_style_used_assignment_persists(self):
        unit = self.pool.select_next(None)
        unit["style_used"] = "tradeoffs"
        refetched = self.pool.get(unit["id"])
        self.assertEqual(refetched["style_used"], "tradeoffs")

    def test_invalid_status_value_rejected(self):
        unit = self.pool.select_next(None)
        with self.assertRaises(ValueError):
            unit["status"] = "not_a_real_status"

    def test_invalid_followups_jump_rejected(self):
        unit = self.pool.select_next(None)
        unit["status"] = "active"
        with self.assertRaises(ValueError):
            unit["followups_used"] = 99

    def test_provenance_keys_are_read_only(self):
        unit = self.pool.select_next(None)
        for key in ("id", "category", "text_seed", "grounding", "priority_boost",
                    "source_type", "source_id", "source_field", "reason"):
            with self.assertRaises(KeyError):
                unit[key] = "attempted mutation"

    def test_deletion_is_never_allowed(self):
        unit = self.pool.select_next(None)
        with self.assertRaises(TypeError):
            del unit["status"]


class TestRejectedPassthrough(unittest.TestCase):
    def test_rejected_is_list_of_plain_dicts_with_expected_keys(self):
        pool = TopicPool(sample_profile_dict())
        self.assertEqual(len(pool.rejected), 1)
        rejected = pool.rejected[0]
        self.assertIsInstance(rejected, dict)
        for key in ("topic", "originating_project", "originating_experience", "reason"):
            self.assertIn(key, rejected)


class TestCoveragePassthrough(unittest.TestCase):
    def test_categories_present_are_plain_strings(self):
        pool = TopicPool(sample_profile_dict())
        for cat in pool.categories_present():
            self.assertIsInstance(cat, str)

    def test_all_categories_covered_false_initially(self):
        pool = TopicPool(sample_profile_dict())
        self.assertFalse(pool.all_categories_covered())

    def test_remaining_decreases_after_status_change(self):
        pool = TopicPool(sample_profile_dict())
        total = pool.remaining()
        unit = pool.select_next(None)
        unit["status"] = "covered"
        self.assertEqual(pool.remaining(), total - 1)


class TestNoPlanningLogicDuplicated(unittest.TestCase):
    """Task 5: the adapter must not reimplement priority/matching/selection
    logic — it must delegate. Verified by checking the adapter shares the
    exact same underlying TopicPool/CoverageTracker instances, not parallel
    copies of their data."""

    def test_adapter_delegates_to_a_real_new_topic_pool_instance(self):
        from topic_pool import TopicPool as PlanningTopicPool

        pool = TopicPool(sample_profile_dict())
        self.assertIsInstance(pool._pool, PlanningTopicPool)

    def test_selection_order_matches_the_underlying_pool_exactly(self):
        from topic_pool import TopicPool as PlanningTopicPool

        profile = sample_profile_dict()
        adapter = TopicPool(profile)
        raw = PlanningTopicPool(profile)

        last_category_adapter = None
        last_category_raw = None
        adapter_order = []
        raw_order = []
        while True:
            u = adapter.select_next(last_category_adapter)
            r = raw.select_next(last_category_raw)
            if u is None:
                self.assertIsNone(r)
                break
            adapter_order.append(u["id"])
            raw_order.append(r.id)
            u["status"] = "covered"
            raw.mark_covered(r.id)
            last_category_adapter = u["category"]
            last_category_raw = r.category
        self.assertEqual(adapter_order, raw_order)


if __name__ == "__main__":
    unittest.main()
