"""Tests for the answer-engagement attenuator (answer_engagement.py).

Unit-level: the multiplier is ~1.0 for real answers and near 0 only for a reply
that restates the question (echo/parrot). End-to-end: echoing the question back
through the real Round 1 path (conversation_engine -> evaluation_engine.evaluate)
is pulled down, while a genuine answer is not."""

import unittest

import conversation_engine
from answer_engagement import engagement_multiplier
from candidate_profile_generator import CandidateProfile, ProjectEntry


class TestEngagementMultiplier(unittest.TestCase):
    def test_echo_is_attenuated(self):
        q = "Why did you choose Postgres for the analytics service in this project?"
        v = engagement_multiplier(q, q)  # verbatim restatement
        self.assertLess(v.multiplier, 0.5)
        self.assertEqual(v.reason, "echo")

    def test_real_answers_are_not_attenuated(self):
        q = "Why did you choose Postgres for the analytics service in this project?"
        for ans in [
            "I picked Postgres because the data was relational and we needed joins across users and orders.",
            "We used it and it worked fine for what we needed.",                     # vague but real
            "It's a widely used database that is reliable and has strong tooling.",   # generic but real
            "Honestly I just went with what the team already knew.",
            "I set up the schema and wrote the migrations, then added an index when the dashboard slowed down.",
        ]:
            v = engagement_multiplier(q, ans)
            self.assertGreaterEqual(v.multiplier, 0.999, (ans, v))

    def test_short_declarative_sharing_question_words_is_not_echo(self):
        # Shares wording with the question but adds content -> not an echo.
        q = "Why did you use Docker in this project?"
        v = engagement_multiplier(q, "I used Docker in this project to containerize the services for consistent deploys.")
        self.assertGreaterEqual(v.multiplier, 0.999, v)


class TestEngagementInRound1(unittest.TestCase):
    """Through the real Round 1 path (conversation_engine -> evaluation_engine.evaluate)."""

    def setUp(self):
        profile = CandidateProfile(
            candidate_name="Test", skills=["Python", "Flask", "SQLite"],
            projects=[ProjectEntry(title="Interview Coach", summary="A Flask app that runs mock interviews.",
                                   technologies=["Python", "Flask", "SQLite"], concepts=["REST APIs"])],
        ).model_dump()
        payload, _ = conversation_engine.start_conversation(profile)
        self.cid = payload["conversation_id"]
        self.first_question = payload["question"]["text"]

    def tearDown(self):
        conversation_engine.end_conversation(self.cid)

    def test_echoing_the_question_back_is_pulled_down(self):
        payload, _ = conversation_engine.advance_conversation(self.cid, self.first_question)
        ev = payload["evaluation"]
        self.assertLessEqual(ev["overall_score"], 0.3)
        self.assertEqual(ev["grade"], "poor")

    def test_genuine_answer_is_not_pulled_down(self):
        payload, _ = conversation_engine.advance_conversation(
            self.cid,
            "I built the REST endpoints in Flask and stored every answer in SQLite as it was submitted, "
            "and I added an index on the session id when the history page got slow.")
        self.assertGreater(payload["evaluation"]["overall_score"], 0.3)


if __name__ == "__main__":
    unittest.main()
