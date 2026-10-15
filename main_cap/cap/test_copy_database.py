"""Tests for copy_database.py: every row and resume file copied, ids kept,
Windows-style resume paths normalized, a non-empty target left alone unless
--replace."""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from sqlalchemy import create_engine, select

from account_routes import init_accounts
from copy_database import MODELS, copy_database
from database import db
from models import InterviewSession, Resume, SessionTurn, StudentProfile, User


class TestCopyDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.source_url = "sqlite:///" + os.path.join(self.tmp, "source.db").replace("\\", "/")
        self.target_url = "sqlite:///" + os.path.join(self.tmp, "target.db").replace("\\", "/")
        self.source_uploads = os.path.join(self.tmp, "src_uploads")
        self.target_uploads = os.path.join(self.tmp, "dst_uploads")
        os.makedirs(os.path.join(self.source_uploads, "resumes", "7"))
        with open(os.path.join(self.source_uploads, "resumes", "7", "cv.pdf"), "wb") as f:
            f.write(b"%PDF-1.4 test")

        app = Flask(__name__)
        init_accounts(app, database_url=self.source_url, upload_dir=self.source_uploads)
        with app.app_context():
            user = User(id=7, email="a@example.com", avatar=b"\xff\xd8jpeg")
            user.set_password("secret123")
            db.session.add(user)
            db.session.add(StudentProfile(
                user_id=7, full_name="Asha Rao", date_of_birth=date(2004, 5, 12), phone="+919876543210",
                class10_board="CBSE", class10_score=92, class10_score_type="percentage", class10_year=2020,
                higher_secondary_type="class12", higher_secondary_board="State", higher_secondary_score=88,
                higher_secondary_score_type="percentage", higher_secondary_year=2022, college="PES University",
                degree="B.Tech", branch="CSE", cgpa=8.4, cgpa_scale=10, graduation_year=2026))
            # A path as written on Windows before paths were stored with "/".
            db.session.add(Resume(id=3, user_id=7, file_path="resumes\\7\\cv.pdf", original_filename="cv.pdf",
                                  content_type="application/pdf", size_bytes=13, sha256="0" * 64,
                                  parsed_profile={"name": "Asha Rao"}, is_current=True))
            db.session.add(InterviewSession(id=11, user_id=7, resume_id=3, session_type="technical",
                                            status="completed", overall_score=0.8))
            db.session.add(SessionTurn(session_id=11, turn_number=1, question_text="What is a mutex?",
                                       answer_text="A lock.", evaluation={"score": 0.8}))
            db.session.commit()
            db.session.remove()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rows(self, url):
        with create_engine(url).connect() as c:
            return {m.__tablename__: [dict(r._mapping) for r in c.execute(select(m.__table__).order_by(m.__table__.c.id))]
                    for m in MODELS}

    def copy(self, replace=False):
        return copy_database(self.source_url, self.target_url, self.source_uploads, self.target_uploads, replace)

    def test_copies_every_row_and_file_with_the_same_ids(self):
        counts = self.copy()
        self.assertEqual(counts, {"users": 1, "student_profiles": 1, "resumes": 1, "interview_sessions": 1,
                                  "session_turns": 1, "resume files": 1})
        source, target = self.rows(self.source_url), self.rows(self.target_url)
        source["resumes"][0]["file_path"] = "resumes/7/cv.pdf"
        self.assertEqual(source, target)
        self.assertEqual(target["users"][0]["avatar"], b"\xff\xd8jpeg")
        with open(os.path.join(self.target_uploads, "resumes", "7", "cv.pdf"), "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 test")

    def test_refuses_a_non_empty_target_unless_replace(self):
        self.copy()
        with self.assertRaises(SystemExit):
            self.copy()
        self.assertEqual(self.copy(replace=True)["users"], 1)
        self.assertEqual(len(self.rows(self.target_url)["users"]), 1)


if __name__ == "__main__":
    unittest.main()
