"""
Non-answer gate (answer_gate.py) and its hook in evaluation_engine.evaluate.
"""

import unittest

import conversation_engine
from answer_gate import GATED_MAX_SCORE, check_answer
from candidate_profile_generator import CandidateProfile, ProjectEntry

JUNK = [
    "idk", "I don't know.", "I'm not sure, I don't remember.", "no idea honestly", "pass", "nope",
    "I don't really remember the difference between TCP and UDP, sorry.",
    "I haven't studied that pattern properly, so I don't know how to answer this.",
    "Flask SQLite Python REST API JWT Docker Redis microservices scalability caching",
    "python, flask, sql, docker, redis, aws, kubernetes, react",
    "asdf qwer zxcv lorem blah blah hmm", "yes yes yes yes yes yes yes yes yes yes",
    "<script>alert('x')</script>", "def f(x): return x + 1", "12345 67890 !!!! ???? 111",
]
REAL = [
    "I passed all the integration tests after fixing the retry bug.",
    "We weren't sure about the load, so I benchmarked three databases and picked Postgres.",
    "The function should return the cached value if it is still fresh, otherwise it refetches.",
    "I select the rows from the cache first and only hit the database on a miss.",
    "I didn't know React well at first, so I built a small prototype to learn it before the real UI.",
    "I don't know the exact number, but it cut latency by about 40% after I added the index.",
    "List<String> list = new ArrayList<>(); here List is the interface and ArrayList is the implementation",
    "They use tunneling, where the IPv6 packet is wrapped inside an IPv4 packet so it can pass through the IPv4 routers.",
    "Without an index, a SELECT with a WHERE condition has to do a full table scan, reading every block.",
    "Redis, because it was fast.",
]


class TestCheckAnswer(unittest.TestCase):
    def test_junk_is_gated(self):
        for text in JUNK:
            self.assertTrue(check_answer(text).gated, text)

    def test_real_answers_pass(self):
        for text in REAL:
            self.assertFalse(check_answer(text).gated, (text, check_answer(text).reason))

    def test_long_answers_are_not_called_repetitive(self):
        long_answer = " ".join(
            ["I stored each interview session in the database and saved every answer as a turn."] * 1
            + ["When the server restarted, the data was still in the database, so nothing was lost,"
               " and I added an index on the user id because the history page became slow with more data."] * 1
            + ["I also measured the page load time before and after the index, and it dropped from two seconds"
               " to about two hundred milliseconds, which was the main thing users noticed."])
        self.assertFalse(check_answer(long_answer).gated)


class TestGateInRound1(unittest.TestCase):
    """Through the real Round 1 path (conversation_engine -> evaluation_engine.evaluate)."""

    def setUp(self):
        profile = CandidateProfile(
            candidate_name="Test", skills=["Python", "Flask", "SQLite"],
            projects=[ProjectEntry(title="Interview Coach", summary="A Flask app that runs mock interviews.",
                                   technologies=["Python", "Flask", "SQLite"], concepts=["REST APIs"])],
        ).model_dump()
        payload, _ = conversation_engine.start_conversation(profile)
        self.cid = payload["conversation_id"]

    def tearDown(self):
        conversation_engine.end_conversation(self.cid)

    def _score(self, answer):
        payload, _ = conversation_engine.advance_conversation(self.cid, answer)
        return payload["evaluation"]["overall_score"], payload["evaluation"]["grade"], payload["evaluation"]

    def test_keyword_dump_is_poor(self):
        score, grade, ev = self._score("Flask SQLite Python REST API JWT Docker Redis microservices scalability caching")
        self.assertLessEqual(score, GATED_MAX_SCORE)
        self.assertEqual(grade, "poor")
        self.assertFalse(ev.get("strengths"))

    def test_real_answer_is_not_capped(self):
        score, _, _ = self._score(
            "I built the answer storage myself: every answer is saved in SQLite as it is submitted, so a restart "
            "loses nothing, and I added an index on the session id when the history page slowed down.")
        self.assertGreater(score, GATED_MAX_SCORE)


if __name__ == "__main__":
    unittest.main()
