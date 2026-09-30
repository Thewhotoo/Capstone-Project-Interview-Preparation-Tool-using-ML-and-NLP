"""
Question-bank Technical Interview (tech_interview/ and /api/tech-interview/*):
selection, the follow-up policy, the live session, the grader on anchor
answers, and the routes end to end.

The grader tests load the real MiniLM and NLI models (cached locally);
set CAP_SKIP_MODEL_TESTS=1 to skip them. Every other test uses a fake grader.
"""

import os
import random
import unittest
from collections import Counter
from unittest import mock

from _app_test_setup import signed_up_client
from database import db
from models import SESSION_COMPLETED, SESSION_TERMINATED, InterviewSession
from tech_interview import session as session_module
from tech_interview.bank import KeyPoint, Question, load_bank
from tech_interview.followup import GOOD_SCORE, MAX_FOLLOWUPS, decide
from tech_interview.grader import Clarity, Grade, analyse_clarity, strip_fillers
from tech_interview.selector import difficulty_plan, select_questions
from tech_interview.session import RECOVERED_CREDIT, TechInterview

POINTS = ("P1 point", "P2 point", "P3 point")


def make_question(qid="q1", subject="os", topic="Topic", difficulty="medium", followups=True):
    return Question(
        id=qid, subject=subject, topic_id=f"{subject}:{topic}", topic=topic, difficulty=difficulty,
        text=f"Question {qid}?", reference_answer="Reference.",
        key_points=tuple(KeyPoint(p, f"Follow-up on {p}?" if followups else "", f"Expected {p}.")
                         for p in POINTS),
        confidence=0.9,
    )


def make_grade(covered=(), partial=(), clarity=None):
    missing = [p for p in POINTS if p not in covered and p not in partial]
    kp = (len(covered) + 0.5 * len(partial)) / len(POINTS)
    return Grade(round(0.85 * kp + 0.15 * 0.5, 3), kp, 0.5, list(covered), list(partial), missing,
                 clarity=clarity or Clarity(words=30))


class TestSelector(unittest.TestCase):
    def setUp(self):
        self.bank = load_bank()
        if not self.bank:
            self.skipTest("question bank not available")

    def test_difficulty_plan(self):
        self.assertEqual(Counter(difficulty_plan(8)), {"easy": 2, "medium": 5, "hard": 1})
        self.assertEqual(Counter(difficulty_plan(10)), {"easy": 2, "medium": 6, "hard": 2})

    def test_distinct_topics_spread_subjects_and_difficulty_order(self):
        order = {"easy": 0, "medium": 1, "hard": 2}
        for seed in range(20):
            qs = select_questions(self.bank, 10, rng=random.Random(seed))
            self.assertEqual(len(qs), 10)
            self.assertEqual(len({q.topic_id for q in qs}), 10)
            self.assertEqual(len({q.subject for q in qs}), 5)
            self.assertLessEqual(max(Counter(q.subject for q in qs).values()), 3)
            self.assertEqual([q.difficulty for q in qs], sorted((q.difficulty for q in qs), key=order.get))

    def test_seen_questions_are_avoided(self):
        first = select_questions(self.bank, 10, rng=random.Random(1))
        second = select_questions(self.bank, 10, seen_ids={q.id for q in first}, rng=random.Random(1))
        self.assertFalse({q.id for q in first} & {q.id for q in second})


class TestFollowupPolicy(unittest.TestCase):
    def decide(self, grade, used=0, clarified=False, asked=(), q=None):
        return decide(q or make_question(), grade, followups_used=used, clarified=clarified,
                      asked_points=set(asked))

    def test_good_answer_moves_on(self):
        self.assertEqual(self.decide(make_grade(covered=POINTS)).kind, "next")

    def test_dont_know_moves_on(self):
        self.assertEqual(self.decide(make_grade(clarity=Clarity(words=3, dont_know=True))).reason, "dont_know")

    def test_unclear_answer_gets_one_clarification(self):
        unclear = Clarity(words=30, vague=True)
        self.assertEqual(self.decide(make_grade(clarity=unclear)).kind, "clarify")
        self.assertEqual(self.decide(make_grade(clarity=unclear), used=1, clarified=True).kind, "probe")

    def test_probes_missing_before_partial_and_never_twice(self):
        g = make_grade(partial=["P1 point"])
        d = self.decide(g)
        self.assertEqual((d.kind, d.key_point.point), ("probe", "P2 point"))
        d = self.decide(g, used=1, asked=["P2 point"])
        self.assertEqual(d.key_point.point, "P3 point")

    def test_limit_and_no_prepared_followup(self):
        self.assertEqual(self.decide(make_grade(), used=MAX_FOLLOWUPS).reason, "followup_limit")
        self.assertEqual(self.decide(make_grade(), q=make_question(followups=False)).reason, "nothing_to_probe")


class TestTechInterviewSession(unittest.TestCase):
    def interview(self, grades, covers=None, n=2):
        grades, covers = list(grades), list(covers or [])
        return TechInterview([make_question(f"q{i}", topic=f"T{i}") for i in range(n)],
                             grade_fn=lambda q, a: grades.pop(0),
                             cover_fn=lambda kp, a: (covers.pop(0), {"entailment": 0.9, "similarity": 0.8}))

    def test_good_answer_goes_straight_to_the_next_question(self):
        iv = self.interview([make_grade(covered=POINTS)])
        self.assertEqual(iv.prompt()["kind"], "question")
        result = iv.submit("a good answer")
        self.assertEqual(result["record"]["closed_because"], "good_answer")
        self.assertEqual(result["prompt"]["number"], 2)

    def test_followups_recover_points_at_reduced_credit(self):
        iv = self.interview([make_grade(covered=["P1 point"])], covers=["covered", "missing"])
        first = iv.submit("partial answer")
        self.assertIsNone(first["record"])
        self.assertEqual(first["prompt"]["kind"], "followup")
        self.assertEqual(first["prompt"]["text"], "Follow-up on P2 point?")
        self.assertEqual(iv.submit("recovers P2")["prompt"]["text"], "Follow-up on P3 point?")
        record = iv.submit("still no idea")["record"]
        self.assertEqual(record["closed_because"], "followup_limit")
        self.assertEqual(record["covered"], ["P1 point", "P2 point"])
        self.assertEqual(record["missing"], ["P3 point"])
        self.assertEqual(len(record["exchanges"]), MAX_FOLLOWUPS)
        expected = round(0.85 * (1 + RECOVERED_CREDIT) / 3 + 0.15 * 0.5, 3)
        self.assertEqual(record["score"], expected)
        self.assertLess(record["score"], make_grade(covered=["P1 point", "P2 point"]).score)

    def test_clarification_regrades_the_combined_answer(self):
        iv = self.interview([make_grade(clarity=Clarity(words=30, vague=True)), make_grade(covered=POINTS)])
        self.assertEqual(iv.submit("um vague stuff")["prompt"]["kind"], "clarify")
        record = iv.submit("clear explanation")["record"]
        self.assertGreaterEqual(record["score"], GOOD_SCORE)
        self.assertEqual(record["exchanges"][0]["kind"], "clarify")

    def test_finishes_and_summarises(self):
        iv = self.interview([make_grade(covered=POINTS), make_grade(clarity=Clarity(words=3, dont_know=True))])
        iv.submit("good")
        result = iv.submit("I don't know")
        self.assertTrue(result["finished"])
        self.assertIsNone(result["prompt"])
        summary = iv.summary()
        self.assertEqual(summary["questions_answered"], 2)
        self.assertEqual(summary["weak_topics"], ["T1"])
        with self.assertRaises(RuntimeError):
            iv.submit("more")


class TestClarity(unittest.TestCase):
    def test_fillers_detected_and_stripped(self):
        answer = "um so uh when the quantum is uh small there are like more context switches"
        self.assertTrue(analyse_clarity(answer).unclear)
        self.assertNotIn("uh", strip_fillers(answer).split())

    def test_dont_know(self):
        self.assertTrue(analyse_clarity("Sorry, I don't know this one.").dont_know)


class TestCuratedBank(unittest.TestCase):
    """CAP_CURATED_ONLY (default on): new interviews use only the hand-reviewed best questions."""

    def setUp(self):
        self.all_active = load_bank(curated=False)
        if not any(q.curated for q in self.all_active):
            self.skipTest("bank has no curated questions")

    def test_default_serves_only_curated(self):
        with mock.patch.dict(os.environ, {"CAP_CURATED_ONLY": "1"}):
            served = load_bank()
        self.assertTrue(served)
        self.assertTrue(all(q.curated for q in served))
        self.assertLess(len(served), len(self.all_active))
        self.assertNotIn("dsa.binary_tree_properties.hard2", {q.id for q in served})   # false premise

    def test_switch_off_serves_every_active_question(self):
        with mock.patch.dict(os.environ, {"CAP_CURATED_ONLY": "0"}):
            self.assertEqual(len(load_bank()), len(self.all_active))

    def test_curated_set_fills_a_full_interview_every_time(self):
        served = load_bank(curated=True)
        for seed in range(200):
            picked = select_questions(served, 8, rng=random.Random(seed))
            self.assertEqual(len(picked), 8)
            self.assertEqual(len({q.topic_id for q in picked}), 8)

    def test_often_asked_topics_come_up_more(self):
        import dataclasses
        bank = [dataclasses.replace(make_question(f"q{i}", topic=f"T{i}"), interview_priority=3 if i < 5 else 1)
                for i in range(10)]
        counts = Counter()
        for seed in range(300):
            for q in select_questions(bank, 3, rng=random.Random(seed)):
                counts[q.interview_priority] += 1
        self.assertGreater(counts[3], 3 * counts[1])

    def test_lookup_by_id_still_sees_uncurated_questions(self):
        from tech_interview.bank import question_by_id
        uncurated = next(q for q in self.all_active if not q.curated)
        self.assertIsNotNone(question_by_id(uncurated.id))


@unittest.skipIf(os.environ.get("CAP_SKIP_MODEL_TESTS"), "model tests disabled")
class TestGraderAnchors(unittest.TestCase):
    """Grader calibration anchors (PROJECT_DOCUMENTATION.md §4.25); loads the real models."""

    @classmethod
    def setUpClass(cls):
        from tech_interview.grader import grade_answer
        bank = load_bank()
        try:
            cls.q = next(q for q in bank if q.subject == "os" and q.topic == "Context switching")
        except StopIteration:
            raise unittest.SkipTest("anchor question not in the active bank")
        cls.grade = staticmethod(lambda a: grade_answer(cls.q, a))

    def test_ordering(self):
        good = self.grade(
            "When the time quantum is small, the CPU switches between processes very often, so the number "
            "of context switches goes up. Each switch saves and restores process state, which is overhead. "
            "In modern systems the switch time is only a small fraction of the quantum, but if the switch "
            "requires swapping a process in or out of memory it becomes costly.").score
        # short and hesitant: DeBERTa gives it little credit, but it is flagged unclear,
        # so the candidate is asked to clarify and gets follow-ups
        hesitant = self.grade("um so uh when the quantum is uh small there are like more context switches "
                              "you know and uh that is overhead")
        echo = self.grade("Context switching is about switching context, it is when the context of the "
                          "system switches.").score
        dont_know = self.grade("I don't know.").score
        self.assertGreaterEqual(good, GOOD_SCORE)
        self.assertLess(hesitant.score, GOOD_SCORE)
        self.assertTrue(hesitant.clarity.unclear)
        self.assertLessEqual(echo, 0.15)
        self.assertLessEqual(dont_know, 0.1)


def _fake_grade(question, answer, *args, **kwargs):
    if "don't know" in answer:
        return make_grade(clarity=Clarity(words=4, dont_know=True))
    return Grade(0.9, 1.0, 0.5, [k.point for k in question.key_points], [], [], clarity=Clarity(words=30))


@mock.patch.object(session_module, "grade_answer", _fake_grade)
class TestTechInterviewRoutes(unittest.TestCase):
    def setUp(self):
        if not load_bank():
            self.skipTest("question bank not available")
        self.client, _ = signed_up_client()

    def start(self, mode="round2"):
        response = self.client.post("/api/tech-interview/start", json={"mode": mode})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_full_round2_interview_is_recorded(self):
        body = self.start()
        sid = body["session"]["id"]
        self.assertEqual(body["prompt"]["total"], 8)
        asked = []
        prompt = body["prompt"]
        while prompt:
            asked.append(prompt["question_id"])
            answer = "I don't know" if len(asked) == 3 else "a full answer"
            reply = self.client.post(f"/api/tech-interview/{sid}/answer", json={"answer": answer}).get_json()
            prompt = reply["prompt"]
        self.assertTrue(reply["finished"])
        self.assertEqual(len(set(asked)), 8)

        report = self.client.post(f"/api/tech-interview/{sid}/end", json={}).get_json()
        self.assertEqual(report["session"]["status"], SESSION_COMPLETED)
        self.assertEqual(len(report["questions"]), 8)
        self.assertEqual(report["summary"]["weak_topics"], [report["questions"][2]["topic"]])

        detail = self.client.get(f"/api/sessions/{sid}").get_json()["session"]
        self.assertEqual(len(detail["turns"]), 8)
        self.assertEqual(self.client.post(f"/api/tech-interview/{sid}/answer", json={"answer": "x"}).status_code, 404)

        # the next interview does not repeat these questions
        nxt = self.start("standalone")
        self.assertEqual(nxt["prompt"]["total"], 10)
        self.assertNotIn(nxt["prompt"]["question_id"], asked)

    def test_integrity_violation_terminates(self):
        sid = self.start()["session"]["id"]
        self.client.post(f"/api/tech-interview/{sid}/answer", json={"answer": "a full answer"})
        report = self.client.post(f"/api/tech-interview/{sid}/end", json={
            "integrity": {"terminated": True, "type": "tab_switch", "label": "Left the tab"}}).get_json()
        self.assertEqual(report["session"]["status"], SESSION_TERMINATED)
        self.assertEqual(len(report["questions"]), 1)

    def test_validation_and_ownership(self):
        self.assertEqual(self.client.post("/api/tech-interview/start", json={"mode": "x"}).status_code, 400)
        sid = self.start()["session"]["id"]
        self.assertEqual(self.client.post(f"/api/tech-interview/{sid}/answer", json={"answer": 5}).status_code, 400)
        other, _ = signed_up_client()
        self.assertEqual(other.post(f"/api/tech-interview/{sid}/answer", json={"answer": "x"}).status_code, 404)
        self.assertEqual(other.post(f"/api/tech-interview/{sid}/end", json={}).status_code, 404)

    def test_starting_again_abandons_the_live_interview(self):
        sid = self.start()["session"]["id"]
        self.start()
        self.assertEqual(self.client.post(f"/api/tech-interview/{sid}/answer", json={"answer": "x"}).status_code, 404)
        with self.client.application.app_context():
            self.assertEqual(db.session.get(InterviewSession, sid).status, "abandoned")


if __name__ == "__main__":
    unittest.main()
