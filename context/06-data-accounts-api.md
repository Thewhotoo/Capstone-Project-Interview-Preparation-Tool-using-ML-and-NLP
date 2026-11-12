# 06 — Data model, accounts, session history, full HTTP API

Owner: Nandu (Postgres/Redis support: Ninad). Files: `database.py`, `models.py`, `migrations/`, `account_routes.py`, `account_schemas.py`,
`resume_store.py`, `avatar_store.py`, `session_history.py`, `session_routes.py`, `insights.py`, `copy_database.py`, `db_manage.py`.

## Database (`database.py`)
- `CAP_DATABASE_URL` default `sqlite:///main_cap/cap/instance/app.db`; Postgres `postgresql+psycopg://…` (psycopg 3; UTC pinned, `pool_pre_ping`).
- SQLite: `PRAGMA foreign_keys=ON`, `journal_mode=WAL` on every connection.
- `configure_database(app, database_url, upload_dir, auto_upgrade=True)` → Alembic `upgrade` at startup (`render_as_batch=True` for SQLite). Tests pass `auto_upgrade=False` + `db.create_all()`.
- Secret key: `CAP_SECRET_KEY` or generated once into `instance/secret_key`.
- `instance/` (git-ignored): `app.db`, `uploads/resumes/<user_id>/<uuid>.<ext>` (`_pending/` during signup), `secret_key`.
- Migrations (`migrations/versions/`): `ee1633ec7576` initial (accounts, profiles, resumes, sessions), `eeeb3959ae84` `last_activity_at`, `a7c3e91f2b40` profile photo. New migration: `flask --app db_manage db migrate -m "..."` (db_manage.py skips ML model loading).

## Tables (`models.py`)
- `users`: id, email (unique), password_hash (werkzeug), email_verified (unused), role (candidate/annotator/admin), is_active, consent_data, consent_training, consent_version "v1", consented_at, created_at, last_login_at, avatar (LargeBinary, deferred), avatar_updated_at.
- `student_profiles` (1:1): full_name, date_of_birth, phone, class10_{board,score,score_type,year}, higher_secondary_{type class12|diploma, board, score, score_type, year}, college, degree, branch, cgpa, cgpa_scale (4|10), graduation_year, updated_at.
- `resumes`: user_id, file_path (relative, "/"-separated), original_filename, content_type, size_bytes, sha256, **parsed_profile (JSON CandidateProfile)**, is_current, uploaded_at.
- `interview_sessions`: user_id, resume_id (SET NULL on delete), session_type `resume_discussion|technical`, status `in_progress|completed|terminated|abandoned`, started_at, ended_at, last_activity_at, overall_score, overall_grade, questions_answered, evaluator_name/version, integrity JSON, attention_metrics JSON, summary JSON.
- `session_turns`: session_id, turn_number (unique per session), question_text, category, family, reasoning_type, project_reference, source_id, is_followup, answer_text, answered_at, overall_score, grade, evaluation JSON.
  - Round 2 reuses columns: `category`=topic, `family`=subject, `reasoning_type`=difficulty, `source_id`=question_id, `evaluation`=full TechInterview record.
- All cascades from user. `_fit_strings_to_columns` trims long strings before insert/update (Postgres enforces VARCHAR length).
- `iso_utc()` adds tz to naive datetimes for the API.

## Session history (`session_history.py`)
- `session_grade(avg)`: ≥.80 excellent, ≥.60 good, ≥.40 adequate, ≥.25 weak, else poor (matches frontend `rdOverallGrade`; **differs from per-turn evaluator cutpoints .90/.75/.55/.30**).
- `_new_session` abandons the user's other in-progress sessions first. `STALE_AFTER = 2h`.
- Round 1: `begin_resume_discussion`, `owns_conversation`, `record_resume_discussion_turn`, `_apply_regrades`, `finish_resume_discussion` (summary stored without per-turn `evaluations`).
- Round 2: `technical_history(user)` → (seen question ids, mean score per topic_id), `begin_tech_interview`, `tech_interview_lock`, `live_tech_interview`, `save_tech_interview`, `record_tech_interview_turn`, `apply_tech_regrades`, `finish_tech_interview`.
- `_sanitize_attention` keeps numeric `totalWarnings, faceAbsentWarnings, totalDeviationMs, livenessRechecks, livenessFailures, sessionMs, attentionScore`.
- A full interview is stored as TWO sessions (Round 1 + Round 2), not linked.

## Accounts (`account_routes.py`)
- Signup: multipart form → `SignupRequest` (account_schemas.py: email, password rules via `password_problem`, profile fields with score bounds, `consent_data` required, `consent_training` optional) + `resume` file (parsed BEFORE user row exists, staged in `_pending`, then `claim_for_user`) + optional `avatar`.
- Login: JSON `{email, password, remember}`; dummy hash check for unknown email (timing); lockout after 5 fails/email or 20/IP in 15 min (live store, 429). Session cookies SameSite=Lax, remember 30 days. No CSRF tokens.
- Avatar (`avatar_store.py`): decode + re-encode to 256×256 JPEG, strip EXIF, ≤5 MB, ≤40 MP.
- Can't delete your last resume (409). Deleting account removes files (`resume_store.delete_user_files`).

## Full HTTP API
| Method & path | Module | Notes |
|---|---|---|
| GET `/` · GET `/health` | app.py | page (public) · health |
| POST `/api/auth/signup` · `/login` · `/logout` | account_routes | signup/login public |
| GET `/api/auth/me` | | `{user, profile, current_resume}` |
| POST `/api/auth/change-password` · PATCH `/api/auth/consent` · DELETE `/api/auth/account` | | |
| GET/POST/DELETE `/api/auth/avatar` | | |
| PATCH `/api/profile` | | partial ProfileFields JSON |
| GET/POST `/api/resumes` · GET `/api/resumes/<id>` · GET `/<id>/file` · POST `/<id>/make-current` · DELETE `/<id>` | | |
| POST `/api/resumes/<id>/use` · POST `/api/classify-resume` | app.py | start a profile session (upload variant also saves as current) |
| GET `/api/candidate-profile/<sid>` | app.py | profile from live store |
| POST `/api/resume-discussion-v2/start` `{session_id: profile sid}` | app.py | → `{conversation_id, question, total_questions}` |
| POST `/api/resume-discussion-v2/reply` `{session_id: conv id, answer}` | app.py | → `{next_question, is_completed, turn_number, evaluation}` |
| POST `/api/resume-discussion-v2/end` `{session_id, integrity, attention_metrics}` | app.py | → summary (see 02) |
| POST `/api/tech-interview/start` `{mode}` · `/<id>/answer` `{answer}` · `/<id>/end` `{attention_metrics, integrity}` | session_routes | see 04 |
| GET `/api/sessions[?type=]` · GET/DELETE `/api/sessions/<id>` | session_routes | list triggers stale-abandon |
| GET `/api/insights` | session_routes → insights | |
| POST `/api/transcribe` (multipart `audio`) | speech_to_text | `{text}`; ≤330 s |

## Insights (`insights.py`)
`build_insights(user_id)` from completed/terminated sessions: stats, `TREND_LENGTH = 10` score trend, "Focus next" (`FOCUS_LIMIT = 3`): recurring `missing_reasoning` categories (≥ `MIN_RECURRENCE = 2` in last `FOCUS_WINDOW_SESSIONS = 5`), then weak dimensions (< `WEAK_SCORE = .55`), then weak technical topics.

## copy_database.py
`python copy_database.py --from sqlite:////tmp/app.db --from-uploads /tmp/uploads [--replace]` — copies all tables in FK order with same ids, fixes Postgres sequences, copies resume files, converts "\\" paths.

## Tests
`test_accounts.py`, `test_app_auth_guard.py`, `test_session_history.py`, `test_insights_and_settings.py`, `test_lifecycle_hardening.py`, `test_live_store.py`, `test_copy_database.py`. `_test_db.py`: `CAP_TEST_DATABASE_URL` runs tests on Postgres.
