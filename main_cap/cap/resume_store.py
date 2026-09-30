"""
Resume file storage.

Uploaded files live on the server's disk under
`<UPLOAD_DIR>/resumes/<user_id>/<random name>.<ext>`; the database row
(`models.Resume`) keeps the path, original filename, size, SHA-256 and the
parsed Candidate Profile. Because the file sits on the server, a user sees
the same resume from any device they log in on.

Files are saved under a random name (never the user's filename) so an
upload can't overwrite another file or escape the upload directory.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass

from flask import current_app
from werkzeug.datastructures import FileStorage

_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


class ResumeUploadError(ValueError):
    """The upload itself is unusable (missing, wrong type, unreadable,
    unparseable). The message is safe to show to the user."""


@dataclass(frozen=True)
class StoredResume:
    relative_path: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str


def _upload_root() -> str:
    return current_app.config["UPLOAD_DIR"]


def absolute_path(relative_path: str) -> str:
    return os.path.join(_upload_root(), relative_path)


def _extension_of(file: FileStorage | None) -> str:
    if file is None or not file.filename:
        raise ResumeUploadError("Please upload your resume.")
    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in _CONTENT_TYPES:
        raise ResumeUploadError("Unsupported file format. Please upload a PDF, DOCX, or TXT resume.")
    return extension


def _user_folder(user_id: int | None) -> str:
    # Signup parses the resume before the account row exists, so the file is
    # staged in a shared "_pending" folder and then moved (claim_for_user).
    return os.path.join("resumes", str(user_id) if user_id is not None else "_pending")


def save_resume_file(file: FileStorage | None, user_id: int | None) -> StoredResume:
    """Write the upload to the user's folder (or the pending folder when
    `user_id` is None). Raises `ResumeUploadError` for a missing, empty, or
    unsupported file."""
    extension = _extension_of(file)
    data = file.read()
    if not data:
        raise ResumeUploadError("The uploaded resume is empty.")

    relative_path = os.path.join(_user_folder(user_id), f"{uuid.uuid4().hex}{extension}")
    target = absolute_path(relative_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(data)

    return StoredResume(
        relative_path=relative_path,
        original_filename=os.path.basename(file.filename)[:255],
        content_type=_CONTENT_TYPES[extension],
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def claim_for_user(stored: StoredResume, user_id: int) -> StoredResume:
    """Move a file saved with `user_id=None` into that user's folder."""
    new_relative = os.path.join(_user_folder(user_id), os.path.basename(stored.relative_path))
    target = absolute_path(new_relative)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    os.replace(absolute_path(stored.relative_path), target)
    return StoredResume(new_relative, stored.original_filename, stored.content_type,
                        stored.size_bytes, stored.sha256)


def parse_resume(relative_path: str) -> dict:
    """Run the Resume Intelligence Engine on a stored file and return the
    Candidate Profile dict. Raises `ResumeUploadError` if the file can't be
    read (corrupt, scanned, password-protected)."""
    from candidate_profile_generator import generate_candidate_profile_via_engine
    from resume_engine.extractor import ExtractionFailure

    try:
        return generate_candidate_profile_via_engine(absolute_path(relative_path))
    except ExtractionFailure as e:
        raise ResumeUploadError(f"We couldn't read this resume: {e}") from e


def delete_resume_file(relative_path: str) -> None:
    try:
        os.remove(absolute_path(relative_path))
    except FileNotFoundError:
        pass


def delete_user_files(user_id: int) -> None:
    shutil.rmtree(absolute_path(os.path.join("resumes", str(user_id))), ignore_errors=True)
