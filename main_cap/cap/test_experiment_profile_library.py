"""
Tests for experiment_profile_library.py -- the 36-profile curated library.
Exercises the real, unmodified Planner/TopicPool to confirm every profile
is well-formed and traceable, no network/LLM calls involved.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from experiment_profile_library import all_experiment_profiles
from planner import ConversationState, Planner
from question_specification import UnitStatus


def _plan_all(profile: dict):
    planner = Planner(profile)
    state = ConversationState()
    specs = []
    while True:
        spec = planner.plan_next(state)
        if spec is None:
            break
        planner.advance(spec.id, UnitStatus.COVERED)
        state = ConversationState(last_category=spec.category)
        specs.append(spec)
    return specs, planner.rejected


class TestExperimentProfileLibrary(unittest.TestCase):
    def test_produces_thirty_six_profiles(self):
        self.assertEqual(len(all_experiment_profiles()), 36)

    def test_every_profile_has_a_unique_candidate_name(self):
        profiles = all_experiment_profiles()
        names = [p["candidate_name"] for p in profiles]
        self.assertEqual(len(names), len(set(names)))

    def test_covers_twelve_domains_three_each(self):
        profiles = all_experiment_profiles()
        domains = [p["predicted_domain"] for p in profiles]
        counts = {d: domains.count(d) for d in set(domains)}
        self.assertEqual(len(counts), 12)
        self.assertTrue(all(c == 3 for c in counts.values()))

    def test_every_profile_plans_with_zero_rejections(self):
        for profile in all_experiment_profiles():
            specs, rejected = _plan_all(profile)
            self.assertEqual(rejected, [], f"{profile['candidate_name']} had rejected topics: {rejected}")
            self.assertGreater(len(specs), 0, f"{profile['candidate_name']} produced zero units")

    def test_total_unique_specifications_within_target_range(self):
        total = sum(len(_plan_all(p)[0]) for p in all_experiment_profiles())
        # Approved validation target: roughly 350-450 unique specifications.
        self.assertGreaterEqual(total, 350)
        self.assertLessEqual(total, 450)

    def test_average_units_per_profile_near_ten(self):
        profiles = all_experiment_profiles()
        total = sum(len(_plan_all(p)[0]) for p in profiles)
        average = total / len(profiles)
        self.assertGreaterEqual(average, 8.0)
        self.assertLessEqual(average, 12.0)


if __name__ == "__main__":
    unittest.main()
