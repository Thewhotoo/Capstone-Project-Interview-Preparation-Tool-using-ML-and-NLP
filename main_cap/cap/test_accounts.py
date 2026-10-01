"""
Tests for the accounts backend (account_routes.py, account_schemas.py,
resume_store.py, models.py).

Each test gets a fresh Flask app with an in-memory SQLite database and a
temporary upload folder. The resume engine is stubbed out
(`resume_store.parse_resume`) except in `TestRealResumeParsing`, which runs
one golden-corpus PDF through the real pipeline end to end.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask

import resume_store
from account_routes import init_accounts
from candidate_profile_generator import CandidateProfile
from database import db
from models import InterviewSession, Resume, SessionTurn, StudentProfile, User

FAKE_PROFILE = CandidateProfile(candidate_name="Asha Rao", skills=["Python", "Flask"]).model_dump()
PDF_BYTES = b"%PDF-1.4 stand-in resume bytes"
GOLDEN_PDF = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "resume_engine", "tests", "golden_corpus", "full_entity_resume_pdf", "resume.pdf",
)


def signup_form(**overrides) -> dict:
    form = {
        "email": "Asha@Example.com",
        "password": "secret123",
        "full_name": "Asha Rao",
        "date_of_birth": "2004-05-12",
        "phone": "+91 98765 43210",
        "class10_board": "CBSE",
        "class10_score": "92.4",
        "class10_score_type": "percentage",
        "class10_year": "2020",
        "higher_secondary_type": "class12",
        "higher_secondary_board": "Karnataka State Board",
        "higher_secondary_score": "88",
        "higher_secondary_score_type": "percentage",
        "higher_secondary_year": "2022",
        "college": "PES University",
        "degree": "B.Tech",
        "branch": "Computer Science",
        "cgpa": "8.4",
        "cgpa_scale": "10",
        "graduation_year": "2026",
        "consent_data": "true",
        "consent_training": "false",
    }
    form.update(overrides)
    return {k: v for k, v in form.items() if v is not None}


class AccountsTestCase(unittest.TestCase):
    def setUp(self):
        self.upload_dir = tempfile.mkdtemp()
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        init_accounts(self.app, database_url="sqlite://", upload_dir=self.upload_dir, auto_upgrade=False)
        with self.app.app_context():
            db.create_all()
        self.client = self.app.test_client()
        self.parse_patch = mock.patch("resume_store.parse_resume", return_value=FAKE_PROFILE)
        self.parse_mock = self.parse_patch.start()

    def tearDown(self):
        self.parse_patch.stop()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        shutil.rmtree(self.upload_dir, ignore_errors=True)

    # ── helpers ──
    def signup(self, client=None, filename="resume.pdf", data=PDF_BYTES, **overrides):
        form = signup_form(**overrides)
        if filename is not None:
            form["resume"] = (io.BytesIO(data), filename)
        return (client or self.client).post("/api/auth/signup", data=form, content_type="multipart/form-data")

    def login(self, email="asha@example.com", password="secret123", client=None):
        return (client or self.client).post("/api/auth/login", json={"email": email, "password": password})

    def upload(self, filename="resume_v2.pdf", data=PDF_BYTES, client=None):
        return (client or self.client).post(
            "/api/resumes", data={"resume": (io.BytesIO(data), filename)}, content_type="multipart/form-data",
        )

    def query(self, fn):
        with self.app.app_context():
            return fn()


class TestSignup(AccountsTestCase):
    def test_signup_creates_account_profile_and_resume_and_logs_in(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201, response.get_json())
        body = response.get_json()
        self.assertEqual(body["user"]["email"], "asha@example.com")  # normalized
        self.assertFalse(body["user"]["email_verified"])
        self.assertEqual(body["profile"]["phone"], "+919876543210")
        self.assertEqual(body["profile"]["higher_secondary_type"], "class12")
        self.assertTrue(body["current_resume"]["is_current"])
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

        def check():
            user = db.session.scalars(db.select(User)).one()
            self.assertNotEqual(user.password_hash, "secret123")
            self.assertTrue(user.check_password("secret123"))
            self.assertTrue(user.consent_data)
            self.assertFalse(user.consent_training)
            resume = user.resumes[0]
            self.assertEqual(resume.parsed_profile["candidate_name"], "Asha Rao")
            self.assertTrue(resume.file_path.startswith(os.path.join("resumes", str(user.id))))
            with open(resume_store.absolute_path(resume.file_path), "rb") as f:
                self.assertEqual(f.read(), PDF_BYTES)
        self.query(check)
        pending = os.path.join(self.upload_dir, "resumes", "_pending")
        self.assertEqual(os.listdir(pending) if os.path.isdir(pending) else [], [])

    def test_diploma_is_accepted_instead_of_class12(self):
        response = self.signup(higher_secondary_type="diploma", higher_secondary_board="Govt Polytechnic",
                               higher_secondary_score="8.1", higher_secondary_score_type="cgpa")
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["profile"]["higher_secondary_type"], "diploma")

    def test_resume_is_required(self):
        response = self.signup(filename=None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["errors"][0]["field"], "resume")
        self.assertEqual(self.query(lambda: db.session.query(User).count()), 0)

    def test_unsupported_resume_format_is_rejected(self):
        response = self.signup(filename="resume.doc")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file format", response.get_json()["error"])

    def test_invalid_fields_are_reported_and_nothing_is_saved(self):
        cases = {
            "phone": {"phone": "12345"},
            "cgpa above scale": {"cgpa": "9.5", "cgpa_scale": "4"},
            "unknown cgpa scale": {"cgpa_scale": "5"},
            "percentage above 100": {"class10_score": "105"},
            "cgpa-type score above 10": {"class10_score": "11", "class10_score_type": "cgpa"},
            "too young": {"date_of_birth": "2020-01-01"},
            "weak password": {"password": "onlyletters"},
            "bad email": {"email": "not-an-email"},
            "12th before 10th": {"higher_secondary_year": "2018"},
            "no consent": {"consent_data": "false"},
            "missing field": {"college": None},
            "unknown field": {"favourite_colour": "blue"},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                response = self.signup(**overrides)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertTrue(response.get_json()["errors"])
        self.assertEqual(self.query(lambda: db.session.query(User).count()), 0)
        self.parse_mock.assert_not_called()

    def test_duplicate_email_is_rejected_case_insensitively(self):
        self.assertEqual(self.signup().status_code, 201)
        other = self.app.test_client()
        self.assertEqual(self.signup(client=other, email="ASHA@example.com").status_code, 409)

    def test_unreadable_resume_leaves_no_account_and_no_file(self):
        self.parse_mock.side_effect = resume_store.ResumeUploadError("We couldn't read this resume: scanned")
        response = self.signup()
        self.assertEqual(response.status_code, 400)
        self.assertIn("couldn't read", response.get_json()["error"])
        self.assertEqual(self.query(lambda: db.session.query(User).count()), 0)
        stored = [f for _, _, files in os.walk(self.upload_dir) for f in files]
        self.assertEqual(stored, [])

    def test_upload_over_size_limit_returns_json_413(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 1024
        response = self.signup(data=b"x" * 4096)
        self.assertEqual(response.status_code, 413)
        self.assertIn("too large", response.get_json()["error"])


class TestLoginLogout(AccountsTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.client.post("/api/auth/logout")

    def test_login_with_correct_credentials(self):
        response = self.login(email="  ASHA@example.com ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["profile"]["full_name"], "Asha Rao")
        self.assertIsNotNone(self.query(lambda: db.session.scalars(db.select(User)).one().last_login_at))

    def test_wrong_password_and_unknown_email_get_the_same_error(self):
        wrong = self.login(password="wrong123")
        unknown = self.login(email="nobody@example.com")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.get_json(), unknown.get_json())

    def test_disabled_account_cannot_log_in(self):
        def disable():
            db.session.scalars(db.select(User)).one().is_active = False
            db.session.commit()
        self.query(disable)
        self.assertEqual(self.login().status_code, 403)

    def test_logout_ends_the_session(self):
        self.login()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_protected_endpoints_require_login(self):
        for method, url in [("get", "/api/auth/me"), ("get", "/api/resumes"), ("patch", "/api/profile"),
                            ("delete", "/api/auth/account"), ("get", "/api/resumes/1/file")]:
            with self.subTest(url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "Please log in to continue.")


class TestProfile(AccountsTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def test_partial_update(self):
        response = self.client.patch("/api/profile", json={"cgpa": 8.9, "branch": "AI & ML"})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["profile"]["cgpa"], 8.9)
        self.assertEqual(response.get_json()["profile"]["branch"], "AI & ML")
        self.assertEqual(response.get_json()["profile"]["college"], "PES University")

    def test_update_is_validated_against_the_rest_of_the_profile(self):
        self.assertEqual(self.client.patch("/api/profile", json={"cgpa_scale": 4}).status_code, 400)  # 8.4 > 4
        self.assertEqual(self.client.patch("/api/profile", json={"email": "x@y.com"}).status_code, 400)
        self.assertEqual(self.client.patch("/api/profile", json={}).status_code, 400)
        self.assertEqual(self.client.get("/api/auth/me").get_json()["profile"]["cgpa_scale"], 10)


class TestResumes(AccountsTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def resumes(self):
        return self.client.get("/api/resumes").get_json()["resumes"]

    def test_new_upload_becomes_current(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        listed = self.resumes()
        self.assertEqual(len(listed), 2)
        self.assertEqual([r["is_current"] for r in listed], [True, False])  # newest first
        self.assertEqual(listed[0]["original_filename"], "resume_v2.pdf")

    def test_make_current(self):
        self.upload()
        older = self.resumes()[1]["id"]
        self.assertEqual(self.client.post(f"/api/resumes/{older}/make-current").status_code, 200)
        self.assertEqual({r["id"]: r["is_current"] for r in self.resumes()}[older], True)
        self.assertEqual(sum(r["is_current"] for r in self.resumes()), 1)

    def test_resume_detail_and_file_are_available_from_a_new_login(self):
        resume_id = self.resumes()[0]["id"]
        other_device = self.app.test_client()
        self.login(client=other_device)
        detail = other_device.get(f"/api/resumes/{resume_id}").get_json()
        self.assertEqual(detail["profile"]["name"], "Asha Rao")
        file_response = other_device.get(f"/api/resumes/{resume_id}/file?download=1")
        self.assertEqual(file_response.status_code, 200)
        self.assertEqual(file_response.data, PDF_BYTES)
        self.assertIn("attachment", file_response.headers["Content-Disposition"])
        file_response.close()

    def test_cannot_delete_the_only_resume(self):
        only = self.resumes()[0]["id"]
        self.assertEqual(self.client.delete(f"/api/resumes/{only}").status_code, 409)

    def test_deleting_the_current_resume_promotes_the_next_newest_and_removes_the_file(self):
        self.upload()
        current = self.resumes()[0]
        path = self.query(lambda: db.session.get(Resume, current["id"]).file_path)
        self.assertEqual(self.client.delete(f"/api/resumes/{current['id']}").status_code, 200)
        remaining = self.resumes()
        self.assertEqual(len(remaining), 1)
        self.assertTrue(remaining[0]["is_current"])
        self.assertFalse(os.path.exists(os.path.join(self.upload_dir, path)))

    def test_users_cannot_see_each_others_resumes(self):
        asha_resume = self.resumes()[0]["id"]
        other = self.app.test_client()
        self.signup(client=other, email="ravi@example.com", full_name="Ravi Kumar")
        for method, url in [("get", f"/api/resumes/{asha_resume}"), ("get", f"/api/resumes/{asha_resume}/file"),
                            ("post", f"/api/resumes/{asha_resume}/make-current"),
                            ("delete", f"/api/resumes/{asha_resume}")]:
            with self.subTest(url):
                self.assertEqual(getattr(other, method)(url).status_code, 404)
        self.assertEqual(len(other.get("/api/resumes").get_json()["resumes"]), 1)


def image_bytes(fmt="PNG", size=(640, 480), mode="RGB", exif_rotate=False) -> bytes:
    from PIL import Image
    img = Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128))
    out = io.BytesIO()
    if exif_rotate:
        exif = Image.Exif()
        exif[0x0112] = 6            # "rotate 90 degrees": width and height swap when applied
        img.save(out, fmt, exif=exif)
    else:
        img.save(out, fmt)
    return out.getvalue()


class TestProfilePhoto(AccountsTestCase):
    def avatar_of(self, client=None):
        from PIL import Image
        response = (client or self.client).get("/api/auth/avatar")
        return response, (Image.open(io.BytesIO(response.data)) if response.status_code == 200 else None)

    def test_signup_without_photo_uses_initials(self):
        self.assertEqual(self.signup().status_code, 201)
        self.assertIsNone(self.client.get("/api/auth/me").get_json()["user"]["avatar_url"])
        self.assertEqual(self.client.get("/api/auth/avatar").status_code, 404)

    def test_signup_with_photo(self):
        form = signup_form()
        form["resume"] = (io.BytesIO(PDF_BYTES), "resume.pdf")
        form["avatar"] = (io.BytesIO(image_bytes("PNG", (640, 480))), "me.png")
        response = self.client.post("/api/auth/signup", data=form, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertTrue(response.get_json()["user"]["avatar_url"].startswith("/api/auth/avatar?v="))
        resp, img = self.avatar_of()
        self.assertEqual(resp.mimetype, "image/jpeg")
        self.assertEqual((img.format, img.size), ("JPEG", (256, 256)))   # re-encoded, square-cropped

    def test_bad_photo_at_signup_is_a_field_error_and_no_account(self):
        form = signup_form()
        form["resume"] = (io.BytesIO(PDF_BYTES), "resume.pdf")
        form["avatar"] = (io.BytesIO(b"<script>not an image</script>"), "evil.png")
        response = self.client.post("/api/auth/signup", data=form, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["errors"][0]["field"], "avatar")
        with self.app.app_context():
            self.assertEqual(db.session.query(User).count(), 0)

    def test_change_and_remove_photo(self):
        self.signup()
        first = self.client.post("/api/auth/avatar", data={"avatar": (io.BytesIO(image_bytes("JPEG")), "a.jpg")},
                                 content_type="multipart/form-data")
        self.assertEqual(first.status_code, 200)
        url = first.get_json()["user"]["avatar_url"]
        _, img = self.avatar_of()
        self.assertEqual(img.size, (256, 256))
        # transparent PNG is flattened, not rejected
        second = self.client.post("/api/auth/avatar", data={"avatar": (io.BytesIO(image_bytes("PNG", mode="RGBA")), "b.png")},
                                  content_type="multipart/form-data")
        self.assertEqual(second.status_code, 200)
        removed = self.client.delete("/api/auth/avatar")
        self.assertIsNone(removed.get_json()["user"]["avatar_url"])
        self.assertEqual(self.client.get("/api/auth/avatar").status_code, 404)
        self.assertTrue(url)

    def test_phone_rotation_is_applied_and_metadata_dropped(self):
        from PIL import Image
        self.signup()
        self.client.post("/api/auth/avatar", data={"avatar": (io.BytesIO(image_bytes("JPEG", (300, 100), exif_rotate=True)), "p.jpg")},
                         content_type="multipart/form-data")
        _, img = self.avatar_of()
        self.assertEqual(img.size, (256, 256))
        self.assertFalse(dict(img.getexif()))

    def test_rejects_non_images_and_needs_login(self):
        self.signup()
        for data, name in [(b"%PDF-1.4 nope", "doc.pdf"), (b"", "empty.png")]:
            r = self.client.post("/api/auth/avatar", data={"avatar": (io.BytesIO(data), name)}, content_type="multipart/form-data")
            self.assertEqual(r.status_code, 400)
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/auth/avatar").status_code, 401)
        self.assertEqual(anon.post("/api/auth/avatar").status_code, 401)


class TestAccountDeletion(AccountsTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.upload()

    def test_wrong_password_keeps_the_account(self):
        response = self.client.delete("/api/auth/account", json={"password": "wrong123"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.query(lambda: db.session.query(User).count()), 1)

    def test_deletion_removes_every_row_and_file(self):
        def add_session():
            user = db.session.scalars(db.select(User)).one()
            session = InterviewSession(user_id=user.id, resume_id=user.resumes[0].id,
                                       session_type="resume_discussion")
            session.turns.append(SessionTurn(turn_number=1, question_text="Why Flask?"))
            db.session.add(session)
            db.session.commit()
            return user.id
        user_id = self.query(add_session)

        response = self.client.delete("/api/auth/account", json={"password": "secret123"})
        self.assertEqual(response.status_code, 200)
        for model in (User, StudentProfile, Resume, InterviewSession, SessionTurn):
            with self.subTest(model.__tablename__):
                self.assertEqual(self.query(lambda: db.session.query(model).count()), 0)
        self.assertFalse(os.path.exists(os.path.join(self.upload_dir, "resumes", str(user_id))))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_database_cascades_even_without_the_orm(self):
        """ON DELETE CASCADE must hold at the database level (SQLite needs
        PRAGMA foreign_keys=ON per connection for this)."""
        def delete_with_sql():
            db.session.execute(db.text("DELETE FROM users"))
            db.session.commit()
            return db.session.query(StudentProfile).count(), db.session.query(Resume).count()
        self.assertEqual(self.query(delete_with_sql), (0, 0))


@unittest.skipUnless(os.path.exists(GOLDEN_PDF), "golden corpus fixture not found")
class TestRealResumeParsing(AccountsTestCase):
    """One signup through the real resume engine (no stub)."""

    def setUp(self):
        super().setUp()
        self.parse_patch.stop()

    def tearDown(self):
        self.parse_patch.start()
        super().tearDown()

    def test_signup_with_a_real_pdf_stores_the_parsed_profile(self):
        with open(GOLDEN_PDF, "rb") as f:
            response = self.signup(data=f.read())
        self.assertEqual(response.status_code, 201, response.get_json())
        profile = self.query(lambda: db.session.scalars(db.select(Resume)).one().parsed_profile)
        self.assertIn("projects", profile)
        self.assertIn("interview_blueprint", profile)


if __name__ == "__main__":
    unittest.main()
