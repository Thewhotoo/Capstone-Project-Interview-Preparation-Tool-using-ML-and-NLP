"""
interview_feedback.build_feedback (adapted from a teammate's module) and its
hook in conversation_engine.end_conversation.
"""

import unittest

import conversation_engine
from candidate_profile_generator import CandidateProfile, ProjectEntry
from interview_feedback import DEPTH, GROUNDING, RELEVANCE, SCOPE_NOTE, build_feedback


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
