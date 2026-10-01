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
        "Profile Summary",
        "About Me",
        "About",
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
        "Training and Certifications",
        "Training & Certifications",
        "Courses and Certifications",
        "Certifications and Courses",
    ],
    # ── Isolation-only labels (Phase 1, parser generalization) ──────────────
    # These are real, common resume sections with NO dedicated entity parser
    # today. Recognizing them matters anyway: an UNrecognized heading lets
    # its prose fall through into whatever section preceded it -- e.g. an
    # "Areas of Interest" paragraph bleeding into the Skills list and being
    # comma-split into junk "skills". Giving each its own canonical label
    # ISOLATES that content in its own (unparsed) Section, so no other
    # parser ingests it. When these headings appear as inline sub-labels
    # inside another section rather than as their own heading, the relevant
    # parser (e.g. SkillsParser) guards against them separately; this
    # gazetteer covers the case where they are true section headings.
    "coursework": [
        "Coursework",
        "Relevant Coursework",
        "Relevant Courses",
        "Key Courses",
        "Academic Coursework",
    ],
    "soft_skills": [
        "Soft Skills",
        "Interpersonal Skills",
    ],
    "interests": [
        "Interests",
        "Areas of Interest",
        "Hobbies",
        "Hobbies and Interests",
        "Personal Interests",
    ],
    "awards": [
        "Awards",
        "Achievements",
        "Awards and Achievements",
        "Awards & Achievements",
        "Honors and Awards",
        "Honors & Awards",
        "Accomplishments",
    ],
    "leadership": [
        "Leadership",
        "Positions of Responsibility",
        "Leadership and Activities",
        "Extracurricular Activities",
        "Activities",
    ],
}

# "unknown" is intentionally excluded from SECTION_ALIASES -- it is never a
# fuzzy-match target, only the outcome when no canonical label matches
# confidently (Tier 3/4, sections.py).
CANONICAL_LABELS: tuple[str, ...] = (*SECTION_ALIASES.keys(), "unknown")
