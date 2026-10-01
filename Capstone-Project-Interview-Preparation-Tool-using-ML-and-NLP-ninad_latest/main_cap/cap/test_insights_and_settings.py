"""
Home-page insights (/api/insights, insights.py) and the Profile page's
account settings (change password, training consent).
"""

import unittest

from _app_test_setup import app, signed_up_client
from database import db
import insights
from models import (
    SESSION_ABANDONED, SESSION_COMPLETED, SESSION_TYPE_RESUME_DISCUSSION, SESSION_TYPE_TECHNICAL,
    InterviewSession, SessionTurn, utcnow,
)


def _evaluation(score, gaps=(), dims=None):
    return {
        "overall_score": score,
        "missing_reasoning": [{"category": c, "severity": 0.8, "explanation": "x"} for c in gaps],
        "dimensions": [{"name": n, "raw_score": v, "contributes_to_overall": True}
                       for n, v in (dims or {}).items()],
    }


def add_session(user_id, session_type, turns, status=SESSION_COMPLETED, attention=None):
    """turns: list of (score, evaluation-or-None, category)."""
    def build():
        session = InterviewSession(user_id=user_id, session_type=session_type, status=status,
                                   attention_metrics=attention)
        for i, (score, evaluation, category) in enumerate(turns, start=1):
            session.turns.append(SessionTurn(turn_number=i, question_text=f"Q{i}", category=category,
                                             answer_text="a", answered_at=utcnow(),
                                             overall_score=score, evaluation=evaluation))
        scores = [t[0] for t in turns]
        session.overall_score = sum(scores) / len(scores) if scores else None
        session.overall_grade = "good"
        session.questions_answered = len(turns)
        db.session.add(session)
        db.session.commit()
        return session.id
    with app.app_context():
        return build()


class TestInsights(unittest.TestCase):
    def setUp(self):
        self.client, account = signed_up_client()
        self.user_id = account["user"]["id"]

    def insights(self):
        response = self.client.get("/api/insights")
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_new_user_has_empty_insights(self):
        data = self.insights()
        self.assertEqual(data["stats"], {"sessions_finished": 0, "average_score": None,
                                         "best_score": None, "average_attention": None})
        self.assertIsNone(data["last_session"])
        self.assertEqual(data["trend"], [])
        self.assertEqual(data["focus"], [])

    def test_stats_trend_and_last_session(self):
        add_session(self.user_id, SESSION_TYPE_RESUME_DISCUSSION, [(0.4, None, None)], attention={"attentionScore": 80})
        add_session(self.user_id, SESSION_TYPE_TECHNICAL, [(0.8, None, "TCP")], attention={"attentionScore": 90})
        add_session(self.user_id, SESSION_TYPE_RESUME_DISCUSSION, [(0.9, None, None)], status=SESSION_ABANDONED)

        data = self.insights()
        self.assertEqual(data["stats"]["sessions_finished"], 2)          # abandoned doesn't count
        self.assertAlmostEqual(data["stats"]["average_score"], 0.6)
        self.assertAlmostEqual(data["stats"]["best_score"], 0.8)
        self.assertEqual(data["stats"]["average_attention"], 85)
        self.assertEqual(data["last_session"]["session_type"], "technical")
        self.assertEqual([t["score"] for t in data["trend"]], [0.4, 0.8])  # oldest first

    def test_focus_prefers_recurring_reasoning_gaps(self):
        turns = [
            (0.5, _evaluation(0.5, gaps=["tradeoff", "testing"]), None),
            (0.5, _evaluation(0.5, gaps=["tradeoff", "testing"]), None),
            (0.5, _evaluation(0.5, gaps=["tradeoff", "metrics"]), None),   # metrics only once
        ]
        add_session(self.user_id, SESSION_TYPE_RESUME_DISCUSSION, turns)
        focus = self.insights()["focus"]
        self.assertEqual([f["label"] for f in focus[:2]], ["Trade-off reasoning", "Testing approach"])
        self.assertEqual(focus[0]["reason"], "Missing in 3 of your last 3 answers")
        self.assertNotIn("Measurable results", [f["label"] for f in focus])

    def test_focus_falls_back_to_weak_dimensions_and_technical_topics(self):
        add_session(self.user_id, SESSION_TYPE_RESUME_DISCUSSION, [
            (0.4, _evaluation(0.4, dims={"completeness": 0.3, "communication": 0.9}), None),
            (0.4, _evaluation(0.4, dims={"completeness": 0.4, "communication": 0.8}), None),
        ])
        add_session(self.user_id, SESSION_TYPE_TECHNICAL, [(0.3, {"marks": 3}, "DNS"), (0.9, {"marks": 9}, "TCP")])
        labels = [f["label"] for f in self.insights()["focus"]]
        self.assertEqual(labels, ["Complete answers", "DNS (technical)"])

    def test_insights_are_per_user(self):
        add_session(self.user_id, SESSION_TYPE_TECHNICAL, [(0.8, None, "TCP")])
        other, _ = signed_up_client()
        self.assertEqual(other.get("/api/insights").get_json()["stats"]["sessions_finished"], 0)

    def test_focus_is_capped(self):
        gaps = list(insights.REASONING_GAP_LABELS)
        add_session(self.user_id, SESSION_TYPE_RESUME_DISCUSSION,
                    [(0.3, _evaluation(0.3, gaps=gaps), None)] * 3)
        self.assertEqual(len(self.insights()["focus"]), insights.FOCUS_LIMIT)


class TestAccountSettings(unittest.TestCase):
    def setUp(self):
        self.client, account = signed_up_client()
        self.email = account["user"]["email"]

    def test_change_password(self):
        response = self.client.post("/api/auth/change-password",
                                    json={"current_password": "secret123", "new_password": "newpass456"})
        self.assertEqual(response.status_code, 200)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.post("/api/auth/login", json={"email": self.email, "password": "secret123"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": self.email, "password": "newpass456"}).status_code, 200)

    def test_change_password_needs_the_current_one_and_a_strong_new_one(self):
        wrong = self.client.post("/api/auth/change-password",
                                 json={"current_password": "nope1234", "new_password": "newpass456"})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.get_json()["errors"][0]["field"], "current_password")
        weak = self.client.post("/api/auth/change-password",
                                json={"current_password": "secret123", "new_password": "short"})
        self.assertEqual(weak.status_code, 400)
        self.assertEqual(weak.get_json()["errors"][0]["field"], "new_password")

    def test_training_consent_can_be_toggled(self):
        on = self.client.patch("/api/auth/consent", json={"consent_training": True})
        self.assertEqual(on.status_code, 200)
        self.assertTrue(on.get_json()["user"]["consent_training"])
        self.assertTrue(self.client.get("/api/auth/me").get_json()["user"]["consent_training"])
        self.assertFalse(self.client.patch("/api/auth/consent", json={"consent_training": False})
                         .get_json()["user"]["consent_training"])
        self.assertEqual(self.client.patch("/api/auth/consent", json={"consent_training": "yes"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
