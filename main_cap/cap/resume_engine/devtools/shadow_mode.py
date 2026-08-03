"""
Shadow Mode — a TEMPORARY development/QA tool, never a runtime fallback.
See docs/architecture/ResumeIntelligenceEngine.md Section 2.2 for the hard
constraints this module must respect for its entire lifetime:

  - Runs ONLY in developer/test tooling, never reachable from a real user
    request (nothing in app.py imports this package).
  - May compare the new engine's output against Gemini's, flag fields the
    new engine produced nothing for, and speed up building golden-corpus
    fixtures.
  - Must NEVER auto-fill a missing field, overwrite/merge into the
    deterministic engine's output, or be treated as ground truth without a
    human explicitly reviewing the specific discrepancy.

This module — and the Gemini call it depends on, via
candidate_profile_generator.generate_candidate_profile — is deleted
entirely at Milestone 7, not disabled. Do not add a runtime code path that
could reach this module from `app.py`.
"""

from __future__ import annotations

from typing import Any


def compare_profiles(gemini_profile: dict[str, Any], engine_profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Generic, field-by-field structural diff between the two profile
    dicts. Returns a list of discrepancies for a HUMAN to review — never
    applies, merges, or resolves them itself. Deliberately generic (no
    resume-specific parsing logic) so it can diff any two dict-shaped
    profiles, not only CandidateProfile ones."""
    discrepancies: list[dict[str, Any]] = []
    all_keys = set(gemini_profile.keys()) | set(engine_profile.keys())
    for key in sorted(all_keys):
        gemini_value = gemini_profile.get(key)
        engine_value = engine_profile.get(key)
        if gemini_value != engine_value:
            discrepancies.append(
                {
                    "field": key,
                    "gemini_value": gemini_value,
                    "engine_value": engine_value,
                }
            )
    return discrepancies


def run_shadow_comparison(resume_file_path: str, resume_text: str) -> list[dict[str, Any]]:
    """Runs both pipelines on the same resume and returns the diff for
    human review. The new engine has no real stage logic until later
    milestones land (Milestone 1 onward), so this raises
    NotImplementedError today — expected for Milestone 0. This function's
    shape is scaffolding for that future wiring, not a working comparison
    yet."""
    import candidate_profile_generator

    from resume_engine.factory import default_pipeline

    gemini_profile = candidate_profile_generator.generate_candidate_profile(resume_text)
    engine_result = default_pipeline().run(resume_file_path, source_format="pdf")

    # NOTE: engine_result is an AnnotatedCandidateProfile (confidence.py),
    # not yet translated into a CandidateProfile-shaped dict — that
    # translation is later-milestone work (see AnnotatedCandidateProfile's
    # docstring). compare_profiles() is ready for it once it exists.
    return compare_profiles(gemini_profile.model_dump(), vars(engine_result))
