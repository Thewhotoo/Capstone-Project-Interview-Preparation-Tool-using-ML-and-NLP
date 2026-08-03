"""
Job-title gazetteer — Milestone 3 (Entity Parsing). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Used by `ExperienceParser` to disambiguate role vs. company on an entry's
header line, since template order varies ("Senior Engineer, Acme Corp" vs.
"Acme Corp — Senior Engineer") -- whichever half of the line matches this
gazetteer is `role`. A plain data file, matching `section_gazetteer.py`'s
precedent.
"""

from __future__ import annotations

JOB_TITLES: tuple[str, ...] = (
    "Software Engineer", "Senior Software Engineer", "Staff Engineer",
    "Principal Engineer", "Software Developer", "Backend Engineer",
    "Frontend Engineer", "Full Stack Engineer", "Full-Stack Developer",
    "Data Scientist", "Data Engineer", "Data Analyst", "Machine Learning Engineer",
    "ML Engineer", "AI Engineer", "Research Scientist",
    "DevOps Engineer", "Site Reliability Engineer", "SRE", "Cloud Engineer",
    "Platform Engineer", "Infrastructure Engineer",
    "Product Manager", "Senior Product Manager", "Program Manager",
    "Project Manager", "Engineering Manager", "Technical Lead", "Tech Lead",
    "Team Lead",
    "QA Engineer", "Test Engineer", "Quality Assurance Engineer",
    "Security Engineer", "Security Analyst",
    "Mobile Engineer", "iOS Engineer", "Android Engineer",
    "Systems Engineer", "Network Engineer", "Database Administrator",
    "Business Analyst", "Solutions Architect", "Technical Architect",
    "Intern", "Software Engineering Intern", "Research Intern",
    "Junior Engineer", "Junior Developer",
    "Consultant", "Technical Consultant",
    "Founder", "Co-Founder", "CTO", "VP of Engineering",
)
