"""
Section header alias gazetteer — Milestone 2 (Section Detection). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.3.

A curated, static mapping from each canonical section label to the header
phrasings real resumes actually use for it. This is deliberately a plain
data file, not a class or a loader with fallback logic — the "gazetteer
maintenance burden" the architecture doc names as an accepted, ongoing cost
(Section 11) is meant to be a one-line, reviewable diff (add a phrase to a
list), not a code change.

`CANONICAL_LABELS` is the full label set Section Detection assigns,
including "contact" and "summary" (which have no dedicated entity parser
yet, per Milestone 3's roadmap) and "unknown" (the catch-all for a
structurally header-like line with no confident match — it deliberately
has no alias list of its own).
"""

from __future__ import annotations

SECTION_ALIASES: dict[str, list[str]] = {
    "contact": [
        "Contact",
        "Contact Information",
        "Contact Details",
        "Personal Information",
    ],
    "summary": [
        "Summary",
        "Professional Summary",
        "Career Summary",
        "Objective",
        "Career Objective",
        "Profile",
        "About Me",
        "Executive Summary",
    ],
    "experience": [
        "Experience",
        "Work Experience",
        "Professional Experience",
        "Employment History",
        "Work History",
        "Career History",
        "Relevant Experience",
        "Appointments",
    ],
    "projects": [
        "Projects",
        "Personal Projects",
        "Selected Projects",
        "Academic Projects",
        "Key Projects",
        "Side Projects",
    ],
    "education": [
        "Education",
        "Education and Training",
        "Academic Background",
        "Academic History",
    ],
    "skills": [
        "Skills",
        "Technical Skills",
        "Core Skills",
        "Key Skills",
        "Skills and Abilities",
        "Areas of Expertise",
        "Competencies",
    ],
    "certifications": [
        "Certifications",
        "Certifications and Licenses",
        "Licenses and Certifications",
        "Professional Certifications",
    ],
}

# "unknown" is intentionally excluded from SECTION_ALIASES -- it is never a
# fuzzy-match target, only the outcome when no canonical label matches
# confidently (Tier 3/4, sections.py).
CANONICAL_LABELS: tuple[str, ...] = (*SECTION_ALIASES.keys(), "unknown")
