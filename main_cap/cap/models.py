"""
Database models — accounts, student profiles, resumes, and interview
history.

    users ──1:1── student_profiles
      ├──1:many── resumes              (every upload; one marked current)
      └──1:many── interview_sessions   (Resume Discussion + Technical Interview)
                     └──1:many── session_turns (question, answer, evaluation)

Deleting a user deletes everything below it (ON DELETE CASCADE, plus ORM
cascades); the resume *files* on disk are removed by
`resume_store.delete_user_files`. Deleting a resume keeps any interview
sessions that used it — their `resume_id` is set to NULL.

Evaluation results, integrity records, attention metrics and session
summaries are stored as JSON: their shape is already fixed by
`EvaluationResult` / `conversation_engine._result_payload`, and keeping
them as JSON means old sessions stay readable when the evaluator changes.

`interview_sessions` / `session_turns` are written by session_history.py
as interviews happen.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from flask_login import UserMixin
from sqlalchemy import JSON, ForeignKey, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

CONSENT_VERSION = "v1"

ROLE_CANDIDATE = "candidate"
ROLE_ANNOTATOR = "annotator"
ROLE_ADMIN = "admin"

SESSION_TYPE_RESUME_DISCUSSION = "resume_discussion"
SESSION_TYPE_TECHNICAL = "technical"

SESSION_IN_PROGRESS = "in_progress"
SESSION_COMPLETED = "completed"
SESSION_TERMINATED = "terminated"
SESSION_ABANDONED = "abandoned"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: Optional[datetime | date]) -> Optional[str]:
    """ISO string for the API. SQLite hands datetimes back without a
    timezone; every stored datetime is UTC, so say so explicitly —
    otherwise browsers read it as local time (5h30 off in India)."""
    if value is None:
        return None
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Email verification is not built yet; every account starts unverified
    # and nothing checks this flag until it is.
    email_verified: Mapped[bool] = mapped_column(default=False)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_CANDIDATE)
    # Also satisfies Flask-Login's `is_active` (a disabled account can't log in).
    is_active: Mapped[bool] = mapped_column(default=True)

    consent_data: Mapped[bool] = mapped_column(default=False)
    consent_training: Mapped[bool] = mapped_column(default=False)
    consent_version: Mapped[str] = mapped_column(String(20), default=CONSENT_VERSION)
    consented_at: Mapped[datetime] = mapped_column(default=utcnow)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[Optional[datetime]]

    # Profile photo: a 256x256 JPEG re-encoded on upload (avatar_store.py);
    # None -> the UI shows initials. Deferred: only loaded when the photo is served.
    avatar: Mapped[Optional[bytes]] = mapped_column(LargeBinary, deferred=True)
    avatar_updated_at: Mapped[Optional[datetime]]

    profile: Mapped[Optional["StudentProfile"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True,
    )
    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True,
        order_by="(Resume.uploaded_at.desc(), Resume.id.desc())",  # id breaks same-timestamp ties
    )
    sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True,
        order_by="InterviewSession.started_at.desc()",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def current_resume(self) -> Optional["Resume"]:
        return next((r for r in self.resumes if r.is_current), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "email_verified": self.email_verified,
            "role": self.role,
            "consent_training": self.consent_training,
            "created_at": iso_utc(self.created_at),
            "last_login_at": iso_utc(self.last_login_at),
            # versioned so a new photo is never served from the browser cache
            "avatar_url": (f"/api/auth/avatar?v={int(self.avatar_updated_at.timestamp())}"
                           if self.avatar_updated_at else None),
        }


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    full_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date]
    phone: Mapped[str] = mapped_column(String(20))

    class10_board: Mapped[str] = mapped_column(String(100))
    class10_score: Mapped[float]
    class10_score_type: Mapped[str] = mapped_column(String(12))  # "percentage" | "cgpa"
    class10_year: Mapped[int]

    # Class 12 or Diploma (lateral entry) -- exactly one, chosen by type.
    higher_secondary_type: Mapped[str] = mapped_column(String(10))  # "class12" | "diploma"
    higher_secondary_board: Mapped[str] = mapped_column(String(150))  # board, or diploma institute
    higher_secondary_score: Mapped[float]
    higher_secondary_score_type: Mapped[str] = mapped_column(String(12))
    higher_secondary_year: Mapped[int]

    college: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str] = mapped_column(String(100))
    branch: Mapped[str] = mapped_column(String(100))
    cgpa: Mapped[float]
    cgpa_scale: Mapped[float]  # 4 or 10
    graduation_year: Mapped[int]

    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="profile")

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_name": self.full_name,
            "date_of_birth": iso_utc(self.date_of_birth),
            "phone": self.phone,
            "class10_board": self.class10_board,
            "class10_score": self.class10_score,
            "class10_score_type": self.class10_score_type,
            "class10_year": self.class10_year,
            "higher_secondary_type": self.higher_secondary_type,
            "higher_secondary_board": self.higher_secondary_board,
            "higher_secondary_score": self.higher_secondary_score,
            "higher_secondary_score_type": self.higher_secondary_score_type,
            "higher_secondary_year": self.higher_secondary_year,
            "college": self.college,
            "degree": self.degree,
            "branch": self.branch,
            "cgpa": self.cgpa,
            "cgpa_scale": self.cgpa_scale,
            "graduation_year": self.graduation_year,
            "updated_at": iso_utc(self.updated_at),
        }


class Resume(db.Model):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Relative to the app's UPLOAD_DIR, so the folder can move without a data migration.
    file_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    # The Candidate Profile the resume engine produced at upload time, so an
    # interview can start without re-parsing the file.
    parsed_profile: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_current: Mapped[bool] = mapped_column(default=False)
    uploaded_at: Mapped[datetime] = mapped_column(default=utcnow)

    user: Mapped[User] = relationship(back_populates="resumes")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "is_current": self.is_current,
            "uploaded_at": iso_utc(self.uploaded_at),
        }


class InterviewSession(db.Model):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))

    session_type: Mapped[str] = mapped_column(String(30))  # resume_discussion | technical
    status: Mapped[str] = mapped_column(String(20), default=SESSION_IN_PROGRESS)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[Optional[datetime]]
    # Updated on start, every answered turn, and finish; an in-progress
    # session idle for too long is marked abandoned (session_history.py).
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(default=utcnow)

    overall_score: Mapped[Optional[float]]
    overall_grade: Mapped[Optional[str]] = mapped_column(String(20))
    questions_answered: Mapped[int] = mapped_column(default=0)
    evaluator_name: Mapped[Optional[str]] = mapped_column(String(100))
    evaluator_version: Mapped[Optional[str]] = mapped_column(String(50))

    integrity: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    attention_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    summary: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="sessions")
    resume: Mapped[Optional[Resume]] = relationship()
    turns: Mapped[list["SessionTurn"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True,
        order_by="SessionTurn.turn_number",
    )

    def to_dict(self, include_turns: bool = False) -> dict[str, Any]:
        data = {
            "id": self.id,
            "session_type": self.session_type,
            "status": self.status,
            "started_at": iso_utc(self.started_at),
            "ended_at": iso_utc(self.ended_at),
            "last_activity_at": iso_utc(self.last_activity_at),
            "overall_score": self.overall_score,
            "overall_grade": self.overall_grade,
            "questions_answered": self.questions_answered,
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "resume": ({"id": self.resume.id, "original_filename": self.resume.original_filename}
                       if self.resume else None),
            "integrity": self.integrity,
            "attention_metrics": self.attention_metrics,
        }
        if include_turns:
            data["summary"] = self.summary
            data["turns"] = [turn.to_dict() for turn in self.turns]
        return data


class SessionTurn(db.Model):
    __tablename__ = "session_turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True,
    )
    turn_number: Mapped[int]

    question_text: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    family: Mapped[Optional[str]] = mapped_column(String(50))
    reasoning_type: Mapped[Optional[str]] = mapped_column(String(50))
    project_reference: Mapped[Optional[str]] = mapped_column(String(300))
    source_id: Mapped[Optional[str]] = mapped_column(String(300))
    is_followup: Mapped[bool] = mapped_column(default=False)

    answer_text: Mapped[Optional[str]] = mapped_column(Text)
    answered_at: Mapped[Optional[datetime]]
    overall_score: Mapped[Optional[float]]
    grade: Mapped[Optional[str]] = mapped_column(String(20))
    evaluation: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    session: Mapped[InterviewSession] = relationship(back_populates="turns")

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_number": self.turn_number,
            "question_text": self.question_text,
            "category": self.category,
            "family": self.family,
            "reasoning_type": self.reasoning_type,
            "project_reference": self.project_reference,
            "source_id": self.source_id,
            "is_followup": self.is_followup,
            "answer_text": self.answer_text,
            "answered_at": iso_utc(self.answered_at),
            "overall_score": self.overall_score,
            "grade": self.grade,
            "evaluation": self.evaluation,
        }
