"""
The login requirement in app.py: every API route answers 401 without a
session, except signup and login; the page itself stays public.

Uses the real app.py via _app_test_setup (in-memory database, stubbed
DeBERTa bootstrap).
"""

import io
import unittest
from unittest import mock

from _app_test_setup import SAMPLE_PROFILE, app_module, signed_up_client
from candidate_profile_generator import CandidateProfile
from resume_store import ResumeUploadError
from test_accounts import signup_form

PROTECTED = [
    ("post", "/api/classify-resume"),
    ("get", "/api/candidate-profile/profile_x"),
    ("post", "/api/get-resume-discussion"),
    ("post", "/api/next_question"),
    ("post", "/api/evaluate"),
    ("post", "/api/resume-discussion-v2/start"),
    ("post", "/api/resume-discussion-v2/reply"),
    ("post", "/api/resume-discussion-v2/end"),
    ("post", "/api/resume-discussion/start"),
    ("get", "/api/auth/me"),
    ("get", "/api/resumes"),
    ("get", "/api/sessions"),
    ("get", "/api/sessions/1"),
    ("post", "/api/technical-sessions"),
    ("post", "/api/tech-interview/start"),
    ("post", "/api/tech-interview/1/answer"),
    ("post", "/api/tech-interview/1/end"),
]


class TestLoginRequired(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def test_page_and_health_are_public(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="auth-container"', page.data)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_api_routes_reject_anonymous_requests(self):
        for method, url in PROTECTED:
            with self.subTest(url):
                response = getattr(self.client, method)(url, json={})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "Please log in to continue.")

    def test_signup_and_login_stay_reachable_and_unlock_the_api(self):
        self.assertEqual(self.client.post("/api/auth/login", json={}).status_code, 400)  # reached the route

        profile = CandidateProfile(candidate_name="Guard Test").model_dump()
        form = signup_form(email="guard@example.com")
        form["resume"] = (io.BytesIO(b"%PDF-1.4 x"), "resume.pdf")
        with mock.patch("resume_store.parse_resume", return_value=profile):
            response = self.client.post("/api/auth/signup", data=form, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201, response.get_json())

        # Now logged in: the request reaches the route (404 = no such profile, not 401).
        response = self.client.post("/api/resume-discussion-v2/start", json={"session_id": "missing"})
        self.assertEqual(response.status_code, 404)


class TestSavedResume(unittest.TestCase):
    """The main page's two starting points: the account's saved resume
    (/api/resumes/<id>/use) or a new upload (/api/classify-resume), which is
    saved to the account."""

    PROFILE = SAMPLE_PROFILE

    def setUp(self):
        self.client, account = signed_up_client()
        self.saved = account["current_resume"]

    def test_use_saved_resume_starts_a_discussion_without_reuploading(self):
        response = self.client.post(f"/api/resumes/{self.saved['id']}/use")
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["name"], "Saved Resume User")
        self.assertEqual(body["resume"]["id"], self.saved["id"])

        start = self.client.post("/api/resume-discussion-v2/start", json={"session_id": body["session_id"]})
        self.assertEqual(start.status_code, 200, start.get_json())
        self.assertIn("Interview Coach", start.get_json()["question"]["text"])

    def test_another_users_resume_cannot_be_used(self):
        other, _ = signed_up_client()
        self.assertEqual(other.post(f"/api/resumes/{self.saved['id']}/use").status_code, 404)

    def test_main_page_upload_is_saved_as_the_new_current_resume(self):
        with mock.patch("resume_store.parse_resume", return_value=self.PROFILE):
            response = self.client.post(
                "/api/classify-resume",
                data={"file": (io.BytesIO(b"%PDF-1.4 new"), "updated_resume.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["resume"]["original_filename"], "updated_resume.pdf")
        self.assertTrue(response.get_json()["session_id"].startswith("profile_"))

        resumes = self.client.get("/api/resumes").get_json()["resumes"]
        self.assertEqual([r["original_filename"] for r in resumes], ["updated_resume.pdf", "signup_resume.pdf"])
        self.assertEqual([r["is_current"] for r in resumes], [True, False])
        me = self.client.get("/api/auth/me").get_json()
        self.assertEqual(me["current_resume"]["original_filename"], "updated_resume.pdf")

    def test_unreadable_upload_keeps_the_saved_resume(self):
        error = ResumeUploadError("We couldn't read this resume: scanned")
        with mock.patch("resume_store.parse_resume", side_effect=error):
            response = self.client.post(
                "/api/classify-resume",
                data={"file": (io.BytesIO(b"%PDF-1.4 bad"), "scan.pdf")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("couldn't read", response.get_json()["error"])
        resumes = self.client.get("/api/resumes").get_json()["resumes"]
        self.assertEqual(len(resumes), 1)
        self.assertTrue(resumes[0]["is_current"])

    def test_unsupported_format_is_rejected(self):
        response = self.client.post(
            "/api/classify-resume",
            data={"file": (io.BytesIO(b"old word file"), "resume.doc")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file format", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
