"""
Tests for the expanded scaffold diversity ceiling (v4_5000_scaffold.py) and
the diversity monitor (v4_5000_diversity.py). Deterministic, no network.
"""

import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import v4_5000_scaffold as scaffold
from v4_5000_diversity import DiversityThresholds, analyze
from question_families import ReasoningType
from question_specification import QuestionCategory


class TestScaffoldQuestionFormDiversity(unittest.TestCase):
    def test_many_distinct_question_forms(self):
        self.assertGreaterEqual(len(scaffold.question_form_ids()), 20)

    def test_many_distinct_intents(self):
        # the requested reasoning/intent facets (tradeoff/debugging/failure_analysis/...)
        self.assertGreaterEqual(len(scaffold.intent_ids()), 12)

    def test_question_openings_are_varied_across_a_sample(self):
        openings = Counter()
        for i in range(200):
            q = scaffold.make_slot(i).question.lower().split()
            openings[" ".join(q[:3])] += 1
        # no single 3-word opener should dominate the sample
        top_share = openings.most_common(1)[0][1] / 200
        self.assertLess(top_share, 0.30, f"opening too dominant: {openings.most_common(3)}")

    def test_all_reasoning_types_and_valid_enums(self):
        rtypes = set()
        cats = set()
        for i in range(300):
            s = scaffold.make_slot(i)
            ReasoningType(s.reasoning_type)
            QuestionCategory(s.category)
            rtypes.add(s.reasoning_type)
            cats.add(s.category)
        # a broad spread of reasoning types actually appears
        self.assertGreaterEqual(len(rtypes), 7)
        # all three project-compatible categories appear
        self.assertEqual(cats, {"project_deep_dive", "project_overview", "skill_in_context"})


class TestScaffoldTechnologyDiversity(unittest.TestCase):
    def test_multiple_tech_families_represented_in_a_sample(self):
        techs = Counter()
        for i in range(300):
            for t in scaffold.make_slot(i).technologies:
                techs[t] += 1
        # broad spread: many distinct technologies, no single one dominating
        self.assertGreaterEqual(len(techs), 25)
        total = sum(techs.values())
        top_share = techs.most_common(1)[0][1] / total
        self.assertLess(top_share, 0.20, f"tech too dominant: {techs.most_common(5)}")

    def test_frontend_mobile_ml_all_reachable(self):
        # sanity: the widened families actually surface
        techs = set()
        for i in range(400):
            techs.update(scaffold.make_slot(i).technologies)
        self.assertTrue({"React", "Vue", "Angular", "TypeScript"} & techs, "no frontend tech surfaced")
        self.assertTrue({"Swift", "Kotlin", "Flutter", "SwiftUI"} & techs, "no mobile tech surfaced")
        self.assertTrue({"PyTorch", "TensorFlow", "scikit-learn"} & techs, "no ML tech surfaced")
        self.assertTrue({"Java", "C++", "Go", "Rust"} & techs, "no non-Python language surfaced")


class TestScaffoldCandidateVariation(unittest.TestCase):
    def test_candidate_variation_present_and_deterministic(self):
        a = scaffold.make_slot(7)
        b = scaffold.make_slot(7)
        self.assertEqual(a.candidate, b.candidate)
        for attr in ("complexity", "maturity", "ownership_level", "outcome", "setting", "breadth"):
            self.assertTrue(getattr(a.candidate, attr))

    def test_candidate_variation_spans_values(self):
        ownerships = {scaffold.make_slot(i).candidate.ownership_level for i in range(100)}
        self.assertGreaterEqual(len(ownerships), 3)

    def test_project_families_are_diverse(self):
        fams = {scaffold.make_slot(i).project_family for i in range(300)}
        self.assertGreaterEqual(len(fams), 12)


class TestScaffoldBackwardCompat(unittest.TestCase):
    def test_make_slot_deterministic(self):
        self.assertEqual(scaffold.make_slot(42), scaffold.make_slot(42))

    def test_group_space_large(self):
        self.assertGreater(scaffold.approximate_group_space(), 5000)

    def test_slots_span_many_groups(self):
        groups = {scaffold.make_slot(i).group_id for i in range(300)}
        self.assertGreater(len(groups), 150)


class TestDiversityMonitor(unittest.TestCase):
    def _rec(self, **over):
        base = dict(
            id="x", group_id="g", category="project_deep_dive", reasoning_type="explanation",
            grounding={"title": "P", "summary": "s", "technologies": ["PostgreSQL"], "concepts": []},
            question="How did you handle it?", answer="ans",
            dimensions={"technical_correctness": 3, "depth_specificity": 3, "relevance_completeness": 3, "grounding_ownership": 3},
            humanized=False,
        )
        base.update(over)
        return base

    def test_empty_is_safe(self):
        rep = analyze([])
        self.assertEqual(rep.authored_count, 0)
        self.assertEqual(rep.warnings, [])

    def test_dominant_technology_warns(self):
        recs = [self._rec(id=str(i)) for i in range(20)]  # all PostgreSQL
        rep = analyze(recs)
        self.assertTrue(any("technology 'PostgreSQL'" in w for w in rep.warnings))

    def test_dominant_question_opening_warns(self):
        recs = [self._rec(id=str(i), grounding={"title": "P", "summary": "", "technologies": [f"T{i}"], "concepts": []}) for i in range(20)]
        rep = analyze(recs)  # all "How did you handle..."
        self.assertTrue(any("question opening" in w for w in rep.warnings))

    def test_frequencies_counts_are_correct(self):
        recs = [
            self._rec(id="a", reasoning_type="explanation", grounding={"title": "P", "summary": "", "technologies": ["React"], "concepts": []}),
            self._rec(id="b", reasoning_type="debugging", grounding={"title": "P", "summary": "", "technologies": ["Vue"], "concepts": []}),
        ]
        rep = analyze(recs)
        self.assertEqual(rep.frequencies["reasoning_type"], {"explanation": 1, "debugging": 1})
        self.assertEqual(rep.frequencies["technology"], {"React": 1, "Vue": 1})

    def test_records_without_optional_fields_do_not_crash(self):
        # the first 102 authored records omit question_form/intent/etc.
        rep = analyze([self._rec(id="a")])
        self.assertEqual(rep.frequencies["question_form"], {})
        self.assertEqual(rep.frequencies["intent"], {})

    def test_humanized_share_warning_band(self):
        recs = [self._rec(id=str(i)) for i in range(10)]  # 0% humanized
        rep = analyze(recs)
        self.assertTrue(any("humanized share" in w for w in rep.warnings))


if __name__ == "__main__":
    unittest.main()
