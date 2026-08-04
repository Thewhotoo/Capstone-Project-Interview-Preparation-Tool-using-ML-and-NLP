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
entirely once Gemini is fully retired, not disabled before then. Do not
add a runtime code path that could reach this module from `app.py`.

Milestone 7 update: `run_shadow_comparison` now produces a real
CandidateProfile-shaped diff (`candidate_profile_mapper.py` exists as of
this milestone) instead of the Milestone 0 placeholder that compared
`AnnotatedCandidateProfile`'s raw internal shape. `compare_profiles` is
type-aware per field (scalars, flat string lists, structured entity
lists) so a discrepancy report reads as "what actually differs," not a
wall of "these two Python objects aren't `==`" noise — and every
discrepancy is CATEGORIZED (missing_in_engine / missing_in_gemini /
different_value / count_mismatch) so a human reviewer can triage by
category rather than reading every line. Neither profile is ever treated
as ground truth here — the categorization is structural (what kind of
difference this is), never a verdict on which side is "right."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Fields compared as order-independent sets of strings (a reordering or a
# synonym-cased duplicate isn't a meaningful discrepancy for this field
# type).
_FLAT_STRING_LIST_FIELDS = ("skills", "certifications")

# Fields compared as ordered/keyed lists of entities -- each entry has a
# natural "identity" key used to line up Gemini's and the engine's
# versions of "the same" entry before diffing their sub-fields.
_ENTITY_LIST_FIELDS = {
    "education": "institution",
    "experience": "role",
    "projects": "title",
}

_SCALAR_FIELDS = (
    "candidate_name", "predicted_domain", "experience_level", "confidence", "resume_summary",
)


@dataclass
class Discrepancy:
    field: str
    category: str  # "missing_in_engine" | "missing_in_gemini" | "different_value" | "count_mismatch"
    gemini_value: Any
    engine_value: Any
    note: str = ""


@dataclass
class ShadowComparisonResult:
    gemini_profile: dict
    engine_profile: dict
    discrepancies: list[Discrepancy] = field(default_factory=list)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.discrepancies:
            counts[d.category] = counts.get(d.category, 0) + 1
        return counts

    def by_category(self, category: str) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.category == category]


def _diff_scalar(field_name: str, gemini_profile: dict, engine_profile: dict) -> list[Discrepancy]:
    gemini_value = gemini_profile.get(field_name)
    engine_value = engine_profile.get(field_name)
    if gemini_value == engine_value:
        return []
    return [Discrepancy(field_name, "different_value", gemini_value, engine_value)]


def _diff_flat_string_list(field_name: str, gemini_profile: dict, engine_profile: dict) -> list[Discrepancy]:
    gemini_set = {str(v).lower() for v in (gemini_profile.get(field_name) or [])}
    engine_set = {str(v).lower() for v in (engine_profile.get(field_name) or [])}
    missing_in_engine = gemini_set - engine_set
    missing_in_gemini = engine_set - gemini_set
    discrepancies = []
    if missing_in_engine:
        discrepancies.append(
            Discrepancy(field_name, "missing_in_engine", sorted(missing_in_engine), None)
        )
    if missing_in_gemini:
        discrepancies.append(
            Discrepancy(field_name, "missing_in_gemini", None, sorted(missing_in_gemini))
        )
    return discrepancies


def _diff_entity_list(
    field_name: str, key_field: str, gemini_profile: dict, engine_profile: dict
) -> list[Discrepancy]:
    gemini_entries = gemini_profile.get(field_name) or []
    engine_entries = engine_profile.get(field_name) or []
    discrepancies: list[Discrepancy] = []

    if len(gemini_entries) != len(engine_entries):
        discrepancies.append(
            Discrepancy(
                field_name,
                "count_mismatch",
                len(gemini_entries),
                len(engine_entries),
                note=f"gemini has {len(gemini_entries)} entries, engine has {len(engine_entries)}",
            )
        )

    gemini_by_key = {str(e.get(key_field, "")).strip().lower(): e for e in gemini_entries if isinstance(e, dict)}
    engine_by_key = {str(e.get(key_field, "")).strip().lower(): e for e in engine_entries if isinstance(e, dict)}

    for key, gemini_entry in gemini_by_key.items():
        if key and key not in engine_by_key:
            discrepancies.append(
                Discrepancy(f"{field_name}[{key_field}={key!r}]", "missing_in_engine", gemini_entry, None)
            )
    for key, engine_entry in engine_by_key.items():
        if key and key not in gemini_by_key:
            discrepancies.append(
                Discrepancy(f"{field_name}[{key_field}={key!r}]", "missing_in_gemini", None, engine_entry)
            )

    for key in gemini_by_key.keys() & engine_by_key.keys():
        gemini_entry = gemini_by_key[key]
        engine_entry = engine_by_key[key]
        for sub_field in sorted(set(gemini_entry.keys()) | set(engine_entry.keys())):
            gemini_value = gemini_entry.get(sub_field)
            engine_value = engine_entry.get(sub_field)
            if isinstance(gemini_value, list) and isinstance(engine_value, list):
                if {str(v).lower() for v in gemini_value} != {str(v).lower() for v in engine_value}:
                    discrepancies.append(
                        Discrepancy(
                            f"{field_name}[{key_field}={key!r}].{sub_field}",
                            "different_value", gemini_value, engine_value,
                        )
                    )
            elif gemini_value != engine_value:
                discrepancies.append(
                    Discrepancy(
                        f"{field_name}[{key_field}={key!r}].{sub_field}",
                        "different_value", gemini_value, engine_value,
                    )
                )

    return discrepancies


def compare_profiles(gemini_profile: dict[str, Any], engine_profile: dict[str, Any]) -> list[Discrepancy]:
    """Type-aware, field-by-field diff between two `CandidateProfile`-
    shaped dicts. Returns a list of `Discrepancy` for a HUMAN to review --
    never applies, merges, or resolves them itself, and never labels one
    side "correct." Handles scalars, flat string lists (skills/
    certifications, compared as sets), and structured entity lists
    (education/experience/projects, matched by a natural key and diffed
    field-by-field) -- everything else (contact_details,
    interview_blueprint) falls back to a direct equality diff, since
    those are either small flat dicts or genuinely engine-vs-Gemini
    synthesis differences worth seeing in full rather than partially
    summarized."""
    discrepancies: list[Discrepancy] = []

    for field_name in _SCALAR_FIELDS:
        discrepancies.extend(_diff_scalar(field_name, gemini_profile, engine_profile))

    for field_name in _FLAT_STRING_LIST_FIELDS:
        discrepancies.extend(_diff_flat_string_list(field_name, gemini_profile, engine_profile))

    for field_name, key_field in _ENTITY_LIST_FIELDS.items():
        discrepancies.extend(_diff_entity_list(field_name, key_field, gemini_profile, engine_profile))

    for field_name in ("contact_details", "interview_blueprint"):
        gemini_value = gemini_profile.get(field_name)
        engine_value = engine_profile.get(field_name)
        if gemini_value != engine_value:
            discrepancies.append(Discrepancy(field_name, "different_value", gemini_value, engine_value))

    return discrepancies


def run_shadow_comparison(resume_file_path: str, resume_text: str) -> ShadowComparisonResult:
    """Runs BOTH pipelines on the same resume and returns the categorized
    diff for human review. Gemini is called via the existing production
    function (`generate_candidate_profile`, text-based); the engine is
    called via `generate_candidate_profile_via_engine` (file-based,
    Milestone 7's own wrapper) -- both already produce the identical
    public `CandidateProfile` shape, so this is a genuine apples-to-apples
    comparison for the first time (Milestone 0's version of this function
    could not do this, since the engine had no output-shape translation
    yet)."""
    import candidate_profile_generator

    gemini_profile = candidate_profile_generator.generate_candidate_profile(resume_text)
    engine_profile = candidate_profile_generator.generate_candidate_profile_via_engine(resume_file_path)

    discrepancies = compare_profiles(gemini_profile, engine_profile)
    return ShadowComparisonResult(
        gemini_profile=gemini_profile, engine_profile=engine_profile, discrepancies=discrepancies
    )
