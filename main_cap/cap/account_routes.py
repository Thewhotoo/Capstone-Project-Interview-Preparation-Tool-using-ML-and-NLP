"""
Accounts API — signup, login/logout, profile, resumes, account deletion.

All endpoints speak JSON (signup and resume upload take multipart form
data because they carry a file). Login state is a Flask-Login session
cookie (HttpOnly, SameSite=Lax); every data endpoint only ever reads or
writes the logged-in user's own rows — another user's resume id returns
404, never 403, so ids can't be probed.

    POST   /api/auth/signup                multipart: profile fields + email/password + consents + `resume`
                                           (+ optional `avatar` image)
    GET    /api/auth/avatar                the profile photo (JPEG); 404 if none
    POST   /api/auth/avatar                multipart `avatar` — set / replace the photo
    DELETE /api/auth/avatar                remove it (the UI falls back to initials)
    POST   /api/auth/login                 {email, password, remember?}
    POST   /api/auth/logout
    GET    /api/auth/me                    user + profile + current resume
    DELETE /api/auth/account               {password}  — deletes everything, including files
    PATCH  /api/profile                    any subset of the profile fields
    GET    /api/resumes                    list
    POST   /api/resumes                    multipart `resume` — becomes the current one
    GET    /api/resumes/<id>               metadata + parsed profile (frontend format)
    GET    /api/resumes/<id>/file          the file itself (?download=1 to force download)
    POST   /api/resumes/<id>/make-current
    DELETE /api/resumes/<id>               not allowed for the account's only resume

Email verification is not implemented yet: accounts are created with
`email_verified = False` and nothing checks it.

`init_accounts(app)` wires all of this (database, login manager, routes,
upload size limit) into a Flask app.
"""

from __future__ import annotations

import io
import logging
from datetime import timedelta

from flask import Blueprint, Flask, jsonify, request, send_file
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from pydantic import ValidationError
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

import resume_store
from avatar_store import AvatarError, process_avatar
from account_schemas import ProfileFields, SignupRequest, password_problem, validation_errors
from database import configure_database, db
from models import CONSENT_VERSION, Resume, StudentProfile, User, utcnow
from resume_store import ResumeUploadError

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Checked when the email doesn't exist, so a login attempt takes about as
# long either way and response time doesn't reveal which emails have accounts.
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-password")

accounts_bp = Blueprint("accounts", __name__)
login_manager = LoginManager()


def _error(message: str, status: int, **extra):
    return jsonify({"error": message, **extra}), status


def _account_payload(user: User) -> dict:
    current = user.current_resume()
    return {
        "user": user.to_dict(),
        "profile": user.profile.to_dict() if user.profile else None,
        "current_resume": current.to_dict() if current else None,
    }


def own_resume(resume_id: int) -> Resume | None:
    """The logged-in user's resume with this id, or None (also for other users' ids)."""
    return db.session.scalar(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )


def _store_and_parse(file, user_id: int | None) -> tuple[resume_store.StoredResume, dict]:
    """Save the upload and run the resume engine on it. On any failure the
    saved file is removed again before the error propagates."""
    stored = resume_store.save_resume_file(file, user_id)
    try:
        return stored, resume_store.parse_resume(stored.relative_path)
    except Exception:
        resume_store.delete_resume_file(stored.relative_path)
        raise


def add_resume_for_user(user: User, file) -> Resume:
    """Store, parse and save a newly uploaded resume as the user's current
    one. Raises `ResumeUploadError` (safe to show) if the file is missing,
    unsupported or unreadable; nothing is saved in that case."""
    stored, parsed_profile = _store_and_parse(file, user.id)
    try:
        for existing in user.resumes:
            existing.is_current = False
        resume = _resume_row(user.id, stored, parsed_profile)
        db.session.add(resume)
        db.session.commit()
    except Exception:
        db.session.rollback()
        resume_store.delete_resume_file(stored.relative_path)
        raise
    return resume


def _resume_row(user_id: int, stored: resume_store.StoredResume, parsed_profile: dict) -> Resume:
    return Resume(
        user_id=user_id,
        file_path=stored.relative_path,
        original_filename=stored.original_filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        parsed_profile=parsed_profile,
        is_current=True,
    )


# ── Auth ────────────────────────────────────────────────────────────────────

@accounts_bp.post("/api/auth/signup")
def signup():
    if current_user.is_authenticated:
        return _error("You are already logged in.", 400)
    try:
        form = SignupRequest.model_validate(request.form.to_dict())
    except ValidationError as e:
        return _error("Please fix the highlighted fields.", 400, errors=validation_errors(e))

    if db.session.scalar(select(User.id).where(User.email == form.email)) is not None:
        return _error("An account with this email already exists.", 409)

    avatar = None
    if request.files.get("avatar") and request.files["avatar"].filename:   # optional
        try:
            avatar = process_avatar(request.files["avatar"])
        except AvatarError as e:
            return _error(str(e), 400, errors=[{"field": "avatar", "message": str(e)}])

    try:
        stored, parsed_profile = _store_and_parse(request.files.get("resume"), user_id=None)
    except ResumeUploadError as e:
        return _error(str(e), 400, errors=[{"field": "resume", "message": str(e)}])

    try:
        user = User(
            email=form.email,
            consent_data=form.consent_data,
            consent_training=form.consent_training,
            consent_version=CONSENT_VERSION,
        )
        user.set_password(form.password)
        if avatar is not None:
            user.avatar, user.avatar_updated_at = avatar, utcnow()
        user.profile = StudentProfile(**form.profile_fields())
        db.session.add(user)
        db.session.flush()  # assigns user.id

        stored = resume_store.claim_for_user(stored, user.id)
        db.session.add(_resume_row(user.id, stored, parsed_profile))
        user.last_login_at = utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        resume_store.delete_resume_file(stored.relative_path)
        raise

    login_user(user)
    logger.info("New account created: user %s", user.id)
    return jsonify(_account_payload(user)), 201


@accounts_bp.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not email or not password:
        return _error("Enter your email and password.", 400)

    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        check_password_hash(_DUMMY_PASSWORD_HASH, password)
        return _error("Invalid email or password.", 401)
    if not user.check_password(password):
        return _error("Invalid email or password.", 401)
    if not user.is_active:
        return _error("This account has been disabled.", 403)

    login_user(user, remember=bool(data.get("remember")))
    user.last_login_at = utcnow()
    db.session.commit()
    return jsonify(_account_payload(user)), 200


@accounts_bp.post("/api/auth/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"status": "logged_out"}), 200


@accounts_bp.get("/api/auth/me")
@login_required
def me():
    return jsonify(_account_payload(current_user)), 200


@accounts_bp.post("/api/auth/change-password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    if not current_user.check_password(str(data.get("current_password", ""))):
        return _error("Current password is incorrect.", 401,
                      errors=[{"field": "current_password", "message": "Current password is incorrect."}])
    new_password = str(data.get("new_password", ""))
    problem = password_problem(new_password)
    if problem:
        return _error(problem, 400, errors=[{"field": "new_password", "message": problem}])
    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({"status": "password_changed"}), 200


@accounts_bp.patch("/api/auth/consent")
@login_required
def update_consent():
    """Only the optional model-training consent can be changed here; data
    storage consent is what the account exists on (withdraw it by deleting
    the account)."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("consent_training"), bool):
        return _error("consent_training must be true or false.", 400)
    current_user.consent_training = data["consent_training"]
    current_user.consented_at = utcnow()
    current_user.consent_version = CONSENT_VERSION
    db.session.commit()
    return jsonify({"user": current_user.to_dict()}), 200


@accounts_bp.delete("/api/auth/account")
@login_required
def delete_account():
    data = request.get_json(silent=True) or {}
    if not current_user.check_password(str(data.get("password", ""))):
        return _error("Password is incorrect.", 401)

    user = db.session.get(User, current_user.id)
    user_id = user.id
    logout_user()
    db.session.delete(user)
    db.session.commit()
    resume_store.delete_user_files(user_id)
    logger.info("Account deleted: user %s", user_id)
    return jsonify({"status": "deleted"}), 200


# ── Profile photo ───────────────────────────────────────────────────────────

@accounts_bp.get("/api/auth/avatar")
@login_required
def get_avatar():
    user = db.session.get(User, current_user.id)
    if not user.avatar:
        return _error("No profile photo.", 404)
    response = send_file(io.BytesIO(user.avatar), mimetype="image/jpeg")
    # the URL carries ?v=<updated time>, so a cached copy is never stale
    response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return response


@accounts_bp.post("/api/auth/avatar")
@login_required
def upload_avatar():
    try:
        image = process_avatar(request.files.get("avatar"))
    except AvatarError as e:
        return _error(str(e), 400)
    user = db.session.get(User, current_user.id)
    user.avatar, user.avatar_updated_at = image, utcnow()
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200


@accounts_bp.delete("/api/auth/avatar")
@login_required
def delete_avatar():
    user = db.session.get(User, current_user.id)
    user.avatar, user.avatar_updated_at = None, None
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200


# ── Profile ─────────────────────────────────────────────────────────────────

@accounts_bp.patch("/api/profile")
@login_required
def update_profile():
    changes = request.get_json(silent=True)
    if not isinstance(changes, dict) or not changes:
        return _error("Send the profile fields to update as a JSON object.", 400)

    profile = current_user.profile
    merged = {name: getattr(profile, name) for name in ProfileFields.model_fields}
    merged.update(changes)
    try:
        validated = ProfileFields.model_validate(merged)
    except ValidationError as e:
        return _error("Please fix the highlighted fields.", 400, errors=validation_errors(e))

    for name, value in validated.model_dump().items():
        setattr(profile, name, value)
    db.session.commit()
    return jsonify({"profile": profile.to_dict()}), 200


# ── Resumes ─────────────────────────────────────────────────────────────────

@accounts_bp.get("/api/resumes")
@login_required
def list_resumes():
    return jsonify({"resumes": [r.to_dict() for r in current_user.resumes]}), 200


@accounts_bp.post("/api/resumes")
@login_required
def upload_resume():
    try:
        resume = add_resume_for_user(current_user, request.files.get("resume"))
    except ResumeUploadError as e:
        return _error(str(e), 400)
    return jsonify({"resume": resume.to_dict()}), 201


@accounts_bp.get("/api/resumes/<int:resume_id>")
@login_required
def get_resume(resume_id: int):
    from candidate_profile_generator import profile_to_frontend_format

    resume = own_resume(resume_id)
    if resume is None:
        return _error("Resume not found.", 404)
    return jsonify({
        "resume": resume.to_dict(),
        "profile": profile_to_frontend_format(resume.parsed_profile),
    }), 200


@accounts_bp.get("/api/resumes/<int:resume_id>/file")
@login_required
def download_resume(resume_id: int):
    resume = own_resume(resume_id)
    if resume is None:
        return _error("Resume not found.", 404)
    return send_file(
        resume_store.absolute_path(resume.file_path),
        mimetype=resume.content_type,
        as_attachment=request.args.get("download") == "1",
        download_name=resume.original_filename,
    )


@accounts_bp.post("/api/resumes/<int:resume_id>/make-current")
@login_required
def make_resume_current(resume_id: int):
    resume = own_resume(resume_id)
    if resume is None:
        return _error("Resume not found.", 404)
    for existing in current_user.resumes:
        existing.is_current = existing.id == resume.id
    db.session.commit()
    return jsonify({"resume": resume.to_dict()}), 200


@accounts_bp.delete("/api/resumes/<int:resume_id>")
@login_required
def delete_resume(resume_id: int):
    resume = own_resume(resume_id)
    if resume is None:
        return _error("Resume not found.", 404)
    if len(current_user.resumes) <= 1:
        return _error("You need at least one resume on your account.", 409)

    was_current = resume.is_current
    file_path = resume.file_path
    db.session.delete(resume)
    db.session.flush()
    if was_current:
        # `resumes` is ordered newest first.
        remaining = [r for r in current_user.resumes if r.id != resume_id]
        remaining[0].is_current = True
    db.session.commit()
    resume_store.delete_resume_file(file_path)
    return jsonify({"status": "deleted"}), 200


# ── Wiring ──────────────────────────────────────────────────────────────────

@login_manager.user_loader
def _load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def _unauthorized():
    return _error("Please log in to continue.", 401)


def init_accounts(
    app: Flask,
    *,
    database_url: str | None = None,
    upload_dir: str | None = None,
    auto_upgrade: bool = True,
) -> None:
    """Attach the database, login handling and accounts routes to `app`."""
    app.config.setdefault("MAX_CONTENT_LENGTH", MAX_UPLOAD_BYTES)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_DURATION", timedelta(days=30))

    configure_database(app, database_url=database_url, upload_dir=upload_dir, auto_upgrade=auto_upgrade)
    login_manager.init_app(app)
    app.register_blueprint(accounts_bp)

    @app.errorhandler(413)
    def _upload_too_large(_error_obj):
        return _error(f"File is too large (maximum {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).", 413)
