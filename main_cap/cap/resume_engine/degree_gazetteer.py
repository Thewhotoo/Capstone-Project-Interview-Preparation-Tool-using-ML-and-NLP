"""
Degree gazetteer — Milestone 5 (Entity Parsing continued). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Used by `EducationParser` to recognize a degree line -- a small, closed,
well-known vocabulary (per the architecture doc: "one of the easiest
sub-problems in the whole engine"). A plain data file, matching
`technology_gazetteer.py`/`job_title_gazetteer.py`'s precedent.
"""

from __future__ import annotations

DEGREES: tuple[str, ...] = (
    "Bachelor of Science", "Bachelor of Arts", "Bachelor of Engineering",
    "Bachelor of Technology", "Bachelor's Degree", "BS", "B.S.", "BA", "B.A.",
    "BE", "B.E.", "BTech", "B.Tech", "BSc", "B.Sc",
    "Master of Science", "Master of Arts", "Master of Engineering",
    "Master of Business Administration", "Master's Degree",
    "MS", "M.S.", "MA", "M.A.", "MEng", "M.Eng", "MTech", "M.Tech",
    "MSc", "M.Sc", "MBA",
    "Doctor of Philosophy", "PhD", "Ph.D.", "Doctorate",
    "Associate of Science", "Associate of Arts", "Associate Degree",
    "Diploma", "Certificate Program",
)
