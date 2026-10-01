"""
Session history: both interview types are saved turn by turn, finished as
completed / terminated / abandoned, listed, reopened and deleted — and
only ever by their owner.

Uses the real app.py and the real conversation engine + HeuristicEvaluator
(via _app_test_setup); only resume parsing is stubbed.
"""

import unittest
from datetime import timedelta

from _app_test_setup import app, signed_up_client
from candidate_profile_generator import CandidateProfile, ProjectEntry
from database import db
import session_history
from models import InterviewSession, SessionTurn, utcnow

# One project with one interview seed -> two questions (deep dive + overview).
PROFILE = CandidateProfile(
    candidate_name="History User",
    skills=["Python", "Redis"],
    projects=[ProjectEntry(
        title="Rate Limiter Service", summary="A Flask API with Redis-backed rate limiting.",
        technologies=["Python", "Flask", "Redis"], concepts=["Caching"],
        interview_seeds=["Why did you use Redis in this project?"],
    )],
).model_dump()

ANSWER = ("I built the rate limiter myself using a Redis sliding window, because it kept the "
          "Flask API fast under load; I tested it with a load generator and tuned the TTLs.")

ATTENTION = {"totalWarnings": 1, "faceAbsentWarnings": 0, "totalDeviationMs": 4200.4,
             "livenessRechecks": 0, "livenessFailures": 0, "sessionMs": 90000,
             "attentionScore": 95, "somethingElse": "dropped", "livenessFailures_str": "x"}


def db_query(fn):
    with app.app_context():
        return fn()


class HistoryTestCase(unittest.TestCase):
    def setUp(self):
        self.client, account = signed_up_client(PROFILE)
        self.resume = account["current_resume"]

    def start_discussion(self, client=None):
        client = client or self.client
        profile = client.post(f"/api/resumes/{self.resume['id']}/use").get_json()
        start = client.post("/api/resume-discussion-v2/start", json={"session_id": profile["session_id"]})
        self.assertEqual(start.status_code, 200, start.get_json())
        return start.get_json()

    def reply(self, conversation_id, answer=ANSWER, client=None):
        return (client or self.client).post(
            "/api/resume-discussion-v2/reply", json={"session_id": conversation_id, "answer": answer})

    def end(self, conversation_id, integrity=None, client=None):
        return (client or self.client).post("/api/resume-discussion-v2/end", json={
            "session_id": conversation_id,
            "integrity": integrity or {"terminated": False},
            "attention_metrics": ATTENTION,
        })

    def sessions(self, client=None, **params):
        response = (client or self.client).get("/api/sessions", query_string=params)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["sessions"]


class TestResumeDiscussionHistory(HistoryTestCase):
    def test_full_discussion_is_saved_and_can_be_reopened(self):
        started = self.start_discussion()
        conversation_id = started["conversation_id"]
        first_question = started["question"]["text"]

        # In the list from the first question on.
        listed = self.sessions()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "in_progress")
        self.assertEqual(listed[0]["session_type"], "resume_discussion")

        completed = False
        answers = 0
        while not completed:
            reply = self.reply(conversation_id).get_json()
            answers += 1
            completed = reply["is_completed"]
        self.assertEqual(answers, 2)
        self.assertEqual(self.end(conversation_id).status_code, 200)

        [session] = self.sessions()
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["questions_answered"], 2)
        self.assertEqual(session["resume"]["original_filename"], "signup_resume.pdf")
        self.assertEqual(session["evaluator_name"], "heuristic-v1")
        self.assertIsNotNone(session["overall_score"])
        self.assertIn(session["overall_grade"], {"excellent", "good", "adequate", "weak", "poor"})
        self.assertTrue(session["ended_at"].endswith("+00:00"))
        self.assertEqual(session["attention_metrics"]["attentionScore"], 95)
        self.assertNotIn("somethingElse", session["attention_metrics"])
        self.assertFalse(session["integrity"]["terminated"])

        detail = self.client.get(f"/api/sessions/{session['id']}").get_json()["session"]
        self.assertEqual([t["turn_number"] for t in detail["turns"]], [1, 2])
        self.assertEqual(detail["turns"][0]["question_text"], first_question)
        self.assertEqual(detail["turns"][0]["answer_text"], ANSWER)
        evaluation = detail["turns"][0]["evaluation"]
        self.assertIn("dimensions", evaluation)
        self.assertIn("coaching_note", evaluation)
        self.assertEqual(detail["turns"][0]["overall_score"], evaluation["overall_score"])
        self.assertIn("timeline", detail["summary"])
        self.assertNotIn("evaluations", detail["summary"])  # stored per turn instead

    def test_terminated_discussion_is_saved_as_terminated(self):
        conversation_id = self.start_discussion()["conversation_id"]
        self.reply(conversation_id)
        self.end(conversation_id, integrity={"terminated": True, "type": "tab_switch",
                                              "label": "Switched to another tab", "at_turn": 2})
        [session] = self.sessions()
        self.assertEqual(session["status"], "terminated")
        self.assertEqual(session["integrity"]["type"], "tab_switch")
        self.assertEqual(session["questions_answered"], 1)

    def test_starting_a_new_interview_abandons_the_unfinished_one(self):
        first = self.start_discussion()["conversation_id"]
        self.reply(first)
        second = self.start_discussion()["conversation_id"]

        by_status = {s["status"]: s for s in self.sessions()}
        self.assertEqual(set(by_status), {"abandoned", "in_progress"})
        self.assertEqual(by_status["abandoned"]["questions_answered"], 1)  # answered turn kept
        self.assertIsNotNone(by_status["abandoned"]["ended_at"])
        # The abandoned conversation is closed; the new one works.
        self.assertEqual(self.reply(first).status_code, 404)
        self.assertEqual(self.reply(second).status_code, 200)

    def test_idle_sessions_become_abandoned(self):
        self.start_discussion()

        def age_it():
            session = db.session.scalars(db.select(InterviewSession)).all()[-1]
            session.last_activity_at = utcnow() - session_history.STALE_AFTER - timedelta(minutes=1)
            db.session.commit()
        db_query(age_it)
        self.assertEqual(self.sessions()[0]["status"], "abandoned")

    def test_restart_abandons_every_open_session(self):
        self.start_discussion()
        count = db_query(session_history.abandon_all_open_sessions)
        self.assertGreaterEqual(count, 1)
        self.assertEqual(self.sessions()[0]["status"], "abandoned")

    def test_other_users_cannot_touch_my_conversation_or_sessions(self):
        conversation_id = self.start_discussion()["conversation_id"]
        session_id = self.sessions()[0]["id"]
        other, _ = signed_up_client(PROFILE)

        self.assertEqual(self.reply(conversation_id, client=other).status_code, 404)
        self.assertEqual(self.end(conversation_id, client=other).status_code, 404)
        self.assertEqual(other.get(f"/api/sessions/{session_id}").status_code, 404)
        self.assertEqual(other.delete(f"/api/sessions/{session_id}").status_code, 404)
        self.assertEqual(self.sessions(client=other), [])
        # ...and my session is untouched.
        self.assertEqual(self.reply(conversation_id).status_code, 200)

    def test_profile_session_ids_are_not_shareable(self):
        profile = self.client.post(f"/api/resumes/{self.resume['id']}/use").get_json()
        other, _ = signed_up_client(PROFILE)
        response = other.post("/api/resume-discussion-v2/start", json={"session_id": profile["session_id"]})
        self.assertEqual(response.status_code, 404)

    def test_deleting_a_session_removes_it_and_its_turns(self):
        conversation_id = self.start_discussion()["conversation_id"]
        self.reply(conversation_id)
        session_id = self.sessions()[0]["id"]

        self.assertEqual(self.client.delete(f"/api/sessions/{session_id}").status_code, 200)
        self.assertEqual(self.sessions(), [])
        self.assertEqual(self.client.get(f"/api/sessions/{session_id}").status_code, 404)
        self.assertEqual(db_query(lambda: db.session.query(SessionTurn)
                                  .filter_by(session_id=session_id).count()), 0)
        # Deleting a live interview also closes it.
        self.assertEqual(self.reply(conversation_id).status_code, 404)


class TestTechnicalHistory(HistoryTestCase):
    QUESTION = {
        "question": "Explain the TCP three-way handshake.",
        "reference_answer": "The client sends SYN, the server replies SYN-ACK, and the client sends ACK.",
        "user_answer": "The client sends a SYN, the server answers with SYN-ACK and the client sends ACK.",
        "user_fill_mask": "SYN",
        "reference_fill_mask": "SYN",
        "fill_question": "The first packet is ___.",
        "topic": "TCP",
        "difficulty": "medium",
    }

    def start(self, client=None):
        response = (client or self.client).post("/api/technical-sessions")
        self.assertEqual(response.status_code, 201)
        return response.get_json()["session"]["id"]

    def evaluate(self, session_id, client=None):
        return (client or self.client).post("/api/evaluate", json={**self.QUESTION, "session_id": session_id})

    def test_quiz_turns_are_saved_and_the_session_finished(self):
        session_id = self.start()
        for _ in range(2):
            self.assertEqual(self.evaluate(session_id).status_code, 200)
        response = self.client.post(f"/api/technical-sessions/{session_id}/end",
                                    json={"attention_metrics": ATTENTION})
        self.assertEqual(response.status_code, 200)

        [session] = self.sessions(type="technical")
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["questions_answered"], 2)
        self.assertIsNone(session["resume"])
        detail = self.client.get(f"/api/sessions/{session_id}").get_json()["session"]
        turn = detail["turns"][0]
        self.assertEqual(turn["question_text"], self.QUESTION["question"])
        self.assertEqual(turn["category"], "TCP")
        self.assertEqual(turn["answer_text"], self.QUESTION["user_answer"])
        self.assertEqual(turn["evaluation"]["user_fill_mask"], "SYN")
        self.assertIn("marks", turn["evaluation"])
        self.assertAlmostEqual(session["overall_score"], turn["overall_score"])

        # Finished sessions can't be ended again or written to.
        self.assertEqual(self.client.post(f"/api/technical-sessions/{session_id}/end").status_code, 404)
        self.evaluate(session_id)
        self.assertEqual(self.sessions()[0]["questions_answered"], 2)

    def test_integrity_violation_marks_the_technical_session_terminated(self):
        session_id = self.start()
        self.evaluate(session_id)
        response = self.client.post(f"/api/technical-sessions/{session_id}/end", json={
            "attention_metrics": ATTENTION,
            "integrity": {"terminated": True, "type": "fullscreen_exit", "label": "Left full screen", "at_turn": 2},
        })
        self.assertEqual(response.status_code, 200)
        [session] = self.sessions(type="technical")
        self.assertEqual(session["status"], "terminated")
        self.assertEqual(session["integrity"]["type"], "fullscreen_exit")
        self.assertEqual(session["questions_answered"], 1)

    def test_evaluate_without_or_with_a_foreign_session_still_works_but_saves_nothing(self):
        session_id = self.start()
        other, _ = signed_up_client(PROFILE)
        self.assertEqual(other.post("/api/evaluate", json=self.QUESTION).status_code, 200)
        self.assertEqual(self.evaluate(session_id, client=other).status_code, 200)
        self.assertEqual(self.sessions()[0]["questions_answered"], 0)

    def test_list_can_be_filtered_by_type(self):
        self.start()
        self.start_discussion()   # abandons the technical one — one interview at a time
        self.assertEqual({s["session_type"] for s in self.sessions()}, {"technical", "resume_discussion"})
        self.assertEqual([s["session_type"] for s in self.sessions(type="resume_discussion")], ["resume_discussion"])
        self.assertEqual(self.client.get("/api/sessions?type=bogus").status_code, 400)


class TestAccountDeletionRemovesHistory(HistoryTestCase):
    def test_deleting_the_account_deletes_its_sessions(self):
        conversation_id = self.start_discussion()["conversation_id"]
        self.reply(conversation_id)
        user_id = self.client.get("/api/auth/me").get_json()["user"]["id"]
        self.assertEqual(self.client.delete("/api/auth/account", json={"password": "secret123"}).status_code, 200)
        self.assertEqual(db_query(lambda: db.session.query(InterviewSession).filter_by(user_id=user_id).count()), 0)


if __name__ == "__main__":
    unittest.main()
