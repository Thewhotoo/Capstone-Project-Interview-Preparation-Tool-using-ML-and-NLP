"""
interview_feedback.build_feedback (adapted from a teammate's module) and its
hook in conversation_engine.end_conversation.
"""

import unittest

import conversation_engine
from candidate_profile_generator import CandidateProfile, ProjectEntry
from interview_feedback import DEPTH, GROUNDING, RELEVANCE, SCOPE_NOTE, TECH_MISMATCH, build_feedback
from tech_consistency_flag import NOT_INDEPENDENTLY_VERIFIED, POSSIBLE_MISMATCH


def _ev(overall, depth=None, completeness=None, ownership=None, grounding=None):
    dims = []
    for name, v in (("technical_depth", depth), ("completeness", completeness),
                    ("ownership", ownership), ("resume_grounding", grounding), ("communication", 0.7)):
        if v is not None:
            dims.append({"name": name, "raw_score": v, "confidence": 0.8, "contributes_to_overall": True})
    return {"overall_score": overall, "dimensions": dims}


class TestBuildFeedback(unittest.TestCase):
    def test_reads_our_dimension_names_and_never_zero_fills(self):
        # completeness is reported for only one answer: its mean must be that one value, not diluted by zeros
        fb = build_feedback([_ev(0.8, depth=0.9, ownership=0.8, grounding=0.6),
                             _ev(0.7, depth=0.7, completeness=0.9, ownership=0.6)])
        means = fb["stats"]["dimension_means"]
        self.assertAlmostEqual(means[DEPTH], 0.8, places=3)
        self.assertAlmostEqual(means[RELEVANCE], 0.9, places=3)
        self.assertAlmostEqual(means[GROUNDING], (0.7 + 0.6) / 2, places=3)
        self.assertEqual(fb["headline"], "Strong session — specific, grounded answers.")
        self.assertEqual(fb["scope_note"], SCOPE_NOTE)

    def test_mostly_non_answers(self):
        fb = build_feedback([_ev(0.1, depth=0.1), _ev(0.05, depth=0.1), _ev(0.1), _ev(0.7, depth=0.7)])
        self.assertEqual(fb["headline"], "Most questions weren't really answered.")
        self.assertEqual(fb["stats"]["non_substantive"], 3)

    def test_mixed_session_names_the_weakest_area(self):
        fb = build_feedback([_ev(0.7, depth=0.2, completeness=0.8, ownership=0.7),
                             _ev(0.45, depth=0.3, completeness=0.7, ownership=0.6),
                             _ev(0.5, depth=0.25, completeness=0.75, ownership=0.65)])
        self.assertEqual(fb["headline"], "A mixed session with clear room to go deeper.")
        self.assertIn("go a level deeper", fb["summary"])
        self.assertEqual([f["dimension"] for f in fb["focus_areas"]], [DEPTH])

    def test_non_answers_never_earn_strengths(self):
        # gated junk keeps high dimension scores; they must not turn into praise
        fb = build_feedback([_ev(0.1, depth=0.9, ownership=0.9, grounding=0.9) for _ in range(5)])
        self.assertEqual(fb["headline"], "Most questions weren't really answered.")
        self.assertEqual(fb["strengths"], [])
        self.assertEqual(fb["stats"]["dimension_means"], {})

    def test_empty_session(self):
        self.assertEqual(build_feedback([])["stats"]["questions"], 0)


class TestTechConsistencyInFeedback(unittest.TestCase):
    """build_feedback never calls the NLI model itself -- it only reads the
    already-computed per-turn flags, so these are plain unit tests."""

    def _timeline(self, *project_refs):
        return [{"turn_number": i + 1, "project_reference": ref} for i, ref in enumerate(project_refs)]

    def test_no_flags_means_no_extra_focus_area(self):
        fb = build_feedback(
            [_ev(0.8, depth=0.9, ownership=0.8, grounding=0.6)],
            self._timeline("Project A"),
            [NOT_INDEPENDENTLY_VERIFIED],
        )
        self.assertFalse(any(f["dimension"] == TECH_MISMATCH for f in fb["focus_areas"]))
        self.assertFalse(fb["stats"]["tech_mismatch_flagged"])

    def test_mismatch_adds_a_named_focus_area_first(self):
        fb = build_feedback(
            [_ev(0.8, depth=0.9, ownership=0.8, grounding=0.6), _ev(0.2, depth=0.1)],
            self._timeline("Project A", "Project A"),
            [POSSIBLE_MISMATCH, POSSIBLE_MISMATCH],
        )
        self.assertEqual(fb["focus_areas"][0]["dimension"], TECH_MISMATCH)
        self.assertIn("Project A", fb["focus_areas"][0]["tip"])
        self.assertTrue(fb["stats"]["tech_mismatch_flagged"])

    def test_mismatch_names_multiple_distinct_projects(self):
        fb = build_feedback(
            [_ev(0.8, depth=0.9), _ev(0.7, depth=0.8)],
            self._timeline("Project A", "Project B"),
            [POSSIBLE_MISMATCH, POSSIBLE_MISMATCH],
        )
        tip = fb["focus_areas"][0]["tip"]
        self.assertIn("Project A", tip)
        self.assertIn("Project B", tip)

    def test_missing_flags_list_does_not_break_feedback(self):
        fb = build_feedback([_ev(0.8, depth=0.9, ownership=0.8, grounding=0.6)])
        self.assertFalse(any(f["dimension"] == TECH_MISMATCH for f in fb["focus_areas"]))


class TestEndConversationCarriesFeedback(unittest.TestCase):
    def setUp(self):
        # don't depend on whatever evaluator an earlier test left active
        import evaluator_registry
        from heuristic_evaluator import HeuristicEvaluator
        evaluator_registry._registry.clear()
        evaluator_registry._active_name = None
        evaluator_registry.register_evaluator(HeuristicEvaluator(), make_active=True)

    def test_summary_has_feedback(self):
        profile = CandidateProfile(
            candidate_name="Test", skills=["Python", "Flask"],
            projects=[ProjectEntry(title="Interview Coach", summary="A Flask app.", technologies=["Python", "Flask"])],
        ).model_dump()
        payload, _ = conversation_engine.start_conversation(profile)
        cid = payload["conversation_id"]
        conversation_engine.advance_conversation(
            cid, "I built the answer storage myself in SQLite so a restart lost nothing, and added an index on "
                 "the session id when the history page got slow.")
        summary, status = conversation_engine.end_conversation(cid)
        self.assertEqual(status, 200)
        self.assertIn("headline", summary["feedback"])
        self.assertEqual(summary["feedback"]["stats"]["questions"], 1)
        self.assertTrue(summary["feedback"]["stats"]["dimension_means"])   # our dimensions were found


if __name__ == "__main__":
    unittest.main()


class TestScopeNoteAfterFactCheck(unittest.TestCase):
    def test_scope_note_mentions_the_ai_fact_check_only_when_it_ran(self):
        from interview_feedback import SCOPE_NOTE_FACT_CHECKED
        plain = {"overall_score": 0.7, "grade": "good", "dimensions": [], "reasoning": "Technical correctness: not independently verified"}
        checked = dict(plain, reasoning="Technical correctness: checked by an automated AI fact-checker (qwen3:4b) running locally")
        self.assertEqual(build_feedback([plain])["scope_note"], SCOPE_NOTE)
        self.assertEqual(build_feedback([plain, checked])["scope_note"], SCOPE_NOTE_FACT_CHECKED)
