"""Phase 1 end-to-end regression: the ORIGINAL three-project plain-text
failure, parsed through the REAL pipeline (extractor -> layout -> sections ->
parsers -> cross-reference -> mapper), asserting not merely that projects were
detected but that the right technologies stayed attached to the right project,
that no project was dropped, that a SKILLS section does not bleed into project
technologies, and that dateless experience entries do not merge.

Realistic-fixture spirit (Phase 1F): a flat plain-text resume with no dates on
projects, disjoint technology stacks, ambiguous English words in prose, and a
Skills section listing technologies that must NOT be attributed to projects.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from resume_engine.candidate_profile_mapper import map_to_candidate_profile
from resume_engine.factory import default_pipeline

RESUME = """\
Jordan Avery Mehta
jordan.mehta@example.com | github.com/jmehta-dev

EXPERIENCE

Software Engineer, Northwind Logistics
Owned the shipment-tracking API and reduced p99 latency with a read-through cache.

Software Engineering Intern, BrightData Systems
Built a rate limiter and raised integration-test coverage.

PROJECTS

DriftGuard - Real-time anomaly detection service
Built using Python and PostgreSQL.
Implemented a sliding-window scoring pipeline and worker retries.

QuizForge - Collaborative quiz platform
Built using React and Node.js.
Implemented WebSocket score broadcasting; the UI would react to live updates.

PaperTrail - Personal finance ledger
Built using Go and SQLite.
Implemented double-entry accounting; the daemon can go back to a safe state.

SKILLS
Python, React, PostgreSQL, Go, Redis, Kafka, Docker, Flask
"""


@pytest.fixture(scope="module")
def profile():
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(RESUME)
        path = f.name
    try:
        annotated = default_pipeline().run(path, "txt")
        yield map_to_candidate_profile(annotated)
    finally:
        Path(path).unlink(missing_ok=True)


def _projects(profile):
    return {p["title"]: set(p["technologies"]) for p in profile.get("projects", [])}


def test_three_projects_detected(profile):
    projs = _projects(profile)
    assert len(projs) == 3, f"expected 3 projects, got {list(projs)}"
    names = list(projs)
    assert any("DriftGuard" in n for n in names)
    assert any("QuizForge" in n for n in names)
    assert any("PaperTrail" in n for n in names)


def test_technologies_stay_with_the_correct_project(profile):
    projs = _projects(profile)
    drift = next(t for n, t in projs.items() if "DriftGuard" in n)
    quiz = next(t for n, t in projs.items() if "QuizForge" in n)
    paper = next(t for n, t in projs.items() if "PaperTrail" in n)

    assert {"Python", "PostgreSQL"} <= drift
    assert {"React", "Node.js"} <= quiz
    assert {"Go", "SQLite"} <= paper

    # No cross-contamination between projects:
    assert "React" not in drift and "Go" not in drift and "Node.js" not in drift
    assert "Python" not in quiz and "Go" not in quiz and "PostgreSQL" not in quiz
    assert "React" not in paper and "PostgreSQL" not in paper


def test_pairwise_disjoint_where_genuinely_disjoint(profile):
    projs = _projects(profile)
    sets = list(projs.values())
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            assert sets[i] & sets[j] == set(), f"contamination: {sets[i]} ∩ {sets[j]}"


def test_skills_section_does_not_bleed_into_projects(profile):
    projs = _projects(profile)
    # Redis, Kafka, Docker, Flask appear ONLY in the SKILLS section, never in
    # any project body -- they must not be attributed to a project.
    for skill_only in ("Redis", "Kafka", "Docker", "Flask"):
        for name, techs in projs.items():
            assert skill_only not in techs, f"{skill_only} bled into project {name}"


def test_ambiguous_english_words_in_prose_are_not_technologies(profile):
    projs = _projects(profile)
    quiz = next(t for n, t in projs.items() if "QuizForge" in n)
    paper = next(t for n, t in projs.items() if "PaperTrail" in n)
    # "the UI would react to live updates" -> React only from "Built using React"
    # (already asserted present); "the daemon can go back" must NOT add Go to
    # QuizForge, and Go in PaperTrail comes from "Built using Go".
    assert "Go" not in quiz


def test_experience_entries_do_not_merge(profile):
    exps = profile.get("experience") or []
    assert len(exps) == 2, f"expected 2 experience entries, got {exps}"
    companies = " ".join(e.get("company", "") for e in exps)
    assert "Northwind" in companies and "BrightData" in companies
