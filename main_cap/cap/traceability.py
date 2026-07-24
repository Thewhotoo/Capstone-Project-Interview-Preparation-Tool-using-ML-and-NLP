"""
Traceability Validation — Phase 1 of ResumeDiscussion_v2
(docs/architecture/ResumeDiscussion_v2.md, Chapters 8.4, 10.3, 11).

Two traceability gates exist in the architecture:

    1. Shape gate (Chapter 8.4) — enforced at profile-generation time in
       candidate_profile_generator.py's `_post_process`: a `TechnicalTopic`
       must cite exactly one origin field (project XOR experience), never
       both, never neither. This module does not re-implement that gate —
       it is out of scope for Resume Discussion, which receives an
       already-shape-validated profile.

    2. Substance gate (this module) — does the cited origin actually EXIST
       on THIS profile? A profile-generation-time claim ("originating_project
       = 'Order Management System'") is worthless if no such project is
       actually present on the profile being discussed right now. This is
       the gate TopicPool must run before a `skill_in_context` unit (or any
       other unit) is allowed to become a QuestionSpecification.

Every helper here is a pure function over plain profile data — no session
state, no side effects — so TopicPool (and its tests) can call these
directly without constructing a full pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class TraceabilityError(ValueError):
    """
    Raised when a would-be Question Specification cannot be traced to a real
    Candidate Profile entity. Callers (TopicPool._build) must catch this and
    reject the candidate unit — recording it in `TopicPool.rejected`
    (Chapter 11.3) — rather than letting it propagate and abort planning for
    the whole profile. An invalid unit must never enter the pool.
    """


@dataclass(frozen=True)
class TraceabilityCheckResult:
    """Outcome of a single traceability check, with a human-readable reason
    either way — success and failure are both worth being able to explain
    (Chapter 11.2's audit-trail requirement applies to rejections too)."""

    ok: bool
    reason: str


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def find_project_by_title(title: str, projects: list[Any]) -> Optional[Any]:
    """
    Exact (case-insensitive) title match against the profile's `projects`
    list. `projects` entries may be plain dicts or objects with a `.title`
    attribute (mirrors the dict-vs-Pydantic-model duality already handled in
    candidate_profile_generator.py's `_entry_to_dict`).
    """
    title_norm = _normalize(title)
    if not title_norm:
        return None
    for project in projects:
        candidate_title = (
            project.get("title", "") if isinstance(project, dict) else getattr(project, "title", "")
        )
        if _normalize(candidate_title) == title_norm:
            return project
    return None


def find_experience_by_label(label: str, experiences: list[Any]) -> Optional[Any]:
    """
    Matches a label against an experience entry's role, or "role at company"
    combination — mirrors the matching already used by the legacy
    `discussion_engine.TopicPool._build` so profiles that already validate
    against that logic continue to validate identically here.
    """
    label_norm = _normalize(label)
    if not label_norm:
        return None
    for exp in experiences:
        if isinstance(exp, dict):
            role = exp.get("role", "")
            company = exp.get("company", "")
        else:
            role = getattr(exp, "role", "")
            company = getattr(exp, "company", "")
        role_norm = _normalize(role)
        combo_norm = _normalize(f"{role} at {company}".strip()) if company else role_norm
        if label_norm in (role_norm, combo_norm) or (role_norm and role_norm in label_norm):
            return exp
    return None


def find_certification_by_name(name: str, certifications: list[Any]) -> Optional[Any]:
    """Exact (case-insensitive) name match against the profile's
    `certifications` list. Certification entries may be plain strings or
    dicts with a `name` key."""
    name_norm = _normalize(name)
    if not name_norm:
        return None
    for cert in certifications:
        cert_name = cert.get("name", "") if isinstance(cert, dict) else str(cert)
        if _normalize(cert_name) == name_norm:
            return cert
    return None


def validate_project_exists(title: str, projects: list[Any]) -> TraceabilityCheckResult:
    match = find_project_by_title(title, projects)
    if match is None:
        return TraceabilityCheckResult(
            ok=False, reason=f"no project titled {title!r} exists on this profile"
        )
    return TraceabilityCheckResult(ok=True, reason=f"projects[title={title!r}] found")


def validate_experience_exists(label: str, experiences: list[Any]) -> TraceabilityCheckResult:
    match = find_experience_by_label(label, experiences)
    if match is None:
        return TraceabilityCheckResult(
            ok=False, reason=f"no experience entry matching {label!r} exists on this profile"
        )
    return TraceabilityCheckResult(ok=True, reason=f"experience[role~={label!r}] found")


def validate_certification_exists(name: str, certifications: list[Any]) -> TraceabilityCheckResult:
    match = find_certification_by_name(name, certifications)
    if match is None:
        return TraceabilityCheckResult(
            ok=False, reason=f"no certification named {name!r} exists on this profile"
        )
    return TraceabilityCheckResult(ok=True, reason=f"certifications[name={name!r}] found")


def validate_technical_topic_origin(
    originating_project: str,
    originating_experience: str,
    projects: list[Any],
    experiences: list[Any],
) -> TraceabilityCheckResult:
    """
    Substance-gate check for a `technical_topics` entry (Chapter 8.4's
    second traceability gate; Chapter 10.3's `skill_in_context` rejection
    path; Chapter 11.3's concrete rejected-unit example).

    Shape validity (exactly one of the two origin fields set) is assumed
    already enforced upstream (`_post_process`, Chapter 8.4) — this function
    only checks whether the cited origin actually exists on THIS profile.
    """
    if bool(originating_project.strip()) == bool(originating_experience.strip()):
        # Should already be impossible after _post_process, but a defensive
        # check here means a malformed entry is still rejected rather than
        # silently mis-attributed to whichever branch happens to run first.
        return TraceabilityCheckResult(
            ok=False,
            reason=(
                "malformed technical_topic: exactly one of originating_project/"
                "originating_experience must be set, found "
                f"project={originating_project!r} experience={originating_experience!r}"
            ),
        )
    if originating_project.strip():
        return validate_project_exists(originating_project, projects)
    return validate_experience_exists(originating_experience, experiences)
