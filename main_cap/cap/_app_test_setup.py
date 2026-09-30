"""
Shared setup for tests that import the real app.py: an in-memory
database, a temporary upload folder, and the DeBERTa bootstrap stubbed out
(it would otherwise download the model at import time). Import this module
instead of `app` so the environment is configured exactly once per test run.

Not a test module itself (no `test_` prefix).
"""

import atexit
import io
import os
import shutil
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UPLOAD_DIR = tempfile.mkdtemp()
os.environ["CAP_DATABASE_URL"] = "sqlite://"
os.environ["CAP_UPLOAD_DIR"] = UPLOAD_DIR
atexit.register(shutil.rmtree, UPLOAD_DIR, True)

with mock.patch("deployment_evaluator.bootstrap_production_evaluator"):
    import app as app_module

from candidate_profile_generator import CandidateProfile, ProjectEntry
from test_accounts import signup_form

app = app_module.app
app.config["TESTING"] = True

SAMPLE_PROFILE = CandidateProfile(
    candidate_name="Saved Resume User",
    skills=["Python", "Flask"],
    projects=[ProjectEntry(title="Interview Coach", summary="A Flask app for mock interviews.",
                           technologies=["Python", "Flask"], concepts=["REST APIs"])],
).model_dump()

_signups = 0


def signed_up_client(profile: dict = SAMPLE_PROFILE):
    """A test client logged in as a brand-new user (unique email), with one
    saved resume parsed as `profile`. Returns (client, signup response body)."""
    global _signups
    _signups += 1
    client = app.test_client()
    form = signup_form(email=f"user{_signups}@example.com")
    form["resume"] = (io.BytesIO(b"%PDF-1.4 x"), "signup_resume.pdf")
    with mock.patch("resume_store.parse_resume", return_value=profile):
        response = client.post("/api/auth/signup", data=form, content_type="multipart/form-data")
    assert response.status_code == 201, response.get_json()
    return client, response.get_json()
