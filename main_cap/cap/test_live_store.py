"""
Live interview state (live_store.py) and continuing interviews from it.

"Another worker" is simulated by clearing this process's caches between
requests: every request must then rebuild the interview from its stored
record alone, exactly what a second worker (or a restarted server with
Redis) has to do. The results must be identical to an uninterrupted run.

The Redis backend tests run only when CAP_TEST_REDIS_URL is set, e.g.
    CAP_TEST_REDIS_URL=redis://localhost:6379/15
(that Redis database is flushed by the tests).
"""

import os
import threading
import time
import unittest
from unittest import mock

import conversation_engine as ce
import live_store
import session_history
from _app_test_setup import app, signed_up_client
from candidate_profile_generator import CandidateProfile, ProjectEntry

PROFILE = CandidateProfile(
    candidate_name="Live Store User",
    skills=["Python", "Redis", "PostgreSQL", "Docker"],
    projects=[
        ProjectEntry(title="Rate Limiter Service", summary="A Flask API with Redis-backed rate limiting.",
                     technologies=["Python", "Flask", "Redis"], concepts=["Caching", "Sliding window"],
                     interview_seeds=["Why did you use Redis in this project?"]),
        ProjectEntry(title="Interview Coach", summary="A mock-interview platform with NLI grading.",
                     technologies=["Python", "PostgreSQL", "Docker"], concepts=["NLI", "Retrieval"],
                     interview_seeds=["How did you evaluate the grader?"]),
    ],
).model_dump()

ANSWERS = [
    "I built it myself with a Redis sliding window so the Flask API stayed fast under load.",
    "idk",
    "We measured p95 latency before and after; the cache cut it from 180 ms to 40 ms.",
    "I chose PostgreSQL for durability and Docker so teammates could run it with one command.",
    "The grader was checked against human labels on a fresh set we never tuned on.",
] * 3


class StoreContract:
    """Behaviour every backend must have."""

    def make_store(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.make_store()

    def test_put_get_delete(self):
        self.store.put("t:a", {"x": 1, "items": [1, 2]})
        self.assertEqual(self.store.get("t:a"), {"x": 1, "items": [1, 2]})
        self.store.delete("t:a")
        self.assertIsNone(self.store.get("t:a"))
        self.assertIsNone(self.store.get("t:never-written"))

    def test_records_are_copies_not_shared_objects(self):
        value = {"turns": []}
        self.store.put("t:b", value)
        value["turns"].append("changed after saving")
        self.assertEqual(self.store.get("t:b"), {"turns": []})

    def test_records_expire(self):
        self.store.put("t:c", {"x": 1}, ttl=1)
        time.sleep(1.2)
        self.assertIsNone(self.store.get("t:c"))

    def test_lock_serialises_writers_and_is_reentrant(self):
        self.store.put("t:counter", {"n": 0})

        def bump():
            for _ in range(20):
                with self.store.lock("t:counter"):
                    with self.store.lock("t:counter"):        # re-entrant
                        value = self.store.get("t:counter")
                        value["n"] += 1
                        self.store.put("t:counter", value)

        threads = [threading.Thread(target=bump) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.store.get("t:counter")["n"], 80)


class TestMemoryStore(StoreContract, unittest.TestCase):
    def make_store(self):
        return live_store.MemoryLiveStore()


@unittest.skipUnless(os.environ.get("CAP_TEST_REDIS_URL"), "set CAP_TEST_REDIS_URL to test the Redis backend")
class TestRedisStore(StoreContract, unittest.TestCase):
    def make_store(self):
        store = live_store.RedisLiveStore(os.environ["CAP_TEST_REDIS_URL"])
        store._client.flushdb()
        return store


class TestLocalCache(unittest.TestCase):
    def test_reused_only_for_the_same_version(self):
        cache = live_store.LocalCache()
        cache.put("k", 3, "objects")
        self.assertEqual(cache.get("k", 3), "objects")
        self.assertIsNone(cache.get("k", 4))      # another worker wrote version 4
        cache.drop("k")
        self.assertIsNone(cache.get("k", 3))


def _run_round1(forget_between_turns: bool):
    """Questions, scores and summary of one Round 1 conversation."""
    result, status = ce.start_conversation(PROFILE)
    assert status == 200, result
    cid = result["conversation_id"]
    questions, scores = [result["question"]["text"]], []
    for answer in ANSWERS:
        if forget_between_turns:
            ce._cache.drop(cid)
        reply, status = ce.advance_conversation(cid, answer)
        assert status == 200, reply
        scores.append(reply["evaluation"]["overall_score"])
        if reply["is_completed"]:
            break
        questions.append(reply["next_question"]["text"])
    if forget_between_turns:
        ce._cache.drop(cid)
    summary, status = ce.end_conversation(cid)
    assert status == 200, summary
    summary.pop("integrity", None)
    return questions, scores, summary


class TestRound1ContinuesFromItsRecord(unittest.TestCase):
    def test_rebuilt_every_turn_matches_an_uninterrupted_run(self):
        uninterrupted = _run_round1(forget_between_turns=False)
        rebuilt = _run_round1(forget_between_turns=True)
        self.assertGreaterEqual(len(uninterrupted[0]), 3)
        self.assertEqual(rebuilt, uninterrupted)

    def test_rebuild_uses_stored_scores_without_re_evaluating(self):
        result, _ = ce.start_conversation(PROFILE)
        cid = result["conversation_id"]
        ce.advance_conversation(cid, ANSWERS[0])
        ce._cache.drop(cid)
        evaluator = ce._resolve_session_evaluator()
        with mock.patch.object(type(evaluator), "evaluate", side_effect=AssertionError("re-evaluated")):
            session = ce._load(cid)
        self.assertEqual(len(session["evaluation_ledger"].all()), 1)
        ce.end_conversation(cid)

    def test_a_record_that_no_longer_replays_is_treated_as_expired(self):
        result, _ = ce.start_conversation(PROFILE)
        cid = result["conversation_id"]
        record = live_store.get_store().get(ce._key(cid))
        record["current_question"]["text"] = "a question this profile never produces"
        live_store.get_store().put(ce._key(cid), record)
        ce._cache.drop(cid)
        reply, status = ce.advance_conversation(cid, ANSWERS[0])
        self.assertEqual(status, 404)
        live_store.get_store().delete(ce._key(cid))


class TestTechnicalInterviewContinuesFromItsRecord(unittest.TestCase):
    def _run(self, client, forget_between_answers: bool):
        start = client.post("/api/tech-interview/start", json={"mode": "round2"})
        self.assertEqual(start.status_code, 201, start.get_json())
        session_id = start.get_json()["session"]["id"]
        prompts = [start.get_json()["prompt"]]
        for answer in ANSWERS * 2:
            if forget_between_answers:
                session_history._tech_cache.drop(str(session_id))
            reply = client.post(f"/api/tech-interview/{session_id}/answer", json={"answer": answer})
            self.assertEqual(reply.status_code, 200, reply.get_json())
            body = reply.get_json()
            if body["finished"]:
                break
            prompts.append(body["prompt"])
        if forget_between_answers:
            session_history._tech_cache.drop(str(session_id))
        end = client.post(f"/api/tech-interview/{session_id}/end", json={})
        self.assertEqual(end.status_code, 200)
        report = end.get_json()
        return prompts, report["summary"], [(q["question"], q["score"], q["covered"], q["exchanges"]) for q in report["questions"]]

    def test_rebuilt_every_answer_matches_an_uninterrupted_run(self):
        fixed_questions = None

        def same_questions(bank, n, **_):
            return fixed_questions[:n]

        from tech_interview.bank import load_bank
        fixed_questions = list(load_bank())[:8]
        with mock.patch("session_routes.select_questions", side_effect=same_questions):
            first_client, _ = signed_up_client()
            uninterrupted = self._run(first_client, forget_between_answers=False)
            second_client, _ = signed_up_client()
            rebuilt = self._run(second_client, forget_between_answers=True)
        self.assertEqual(len(uninterrupted[2]), 8)
        self.assertEqual(rebuilt, uninterrupted)


if __name__ == "__main__":
    unittest.main()
