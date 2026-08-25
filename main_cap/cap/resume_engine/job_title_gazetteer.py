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
    # Fix #3 (role/company inversion investigation): the gazetteer above is
    # entirely software/tech-track titles -- a candidate whose actual role
    # is a non-tech business/operations title (e.g. "Operations Executive")
    # can never gazetteer-match, forcing _disambiguate_role_company's
    # documented "first segment = role" positional fallback, which guesses
    # wrong for any resume template that puts company before role.
    # Specific, multi-word titles only (same convention every entry above
    # already follows) -- never a bare generic noun like "Executive" or
    # "Manager" alone, which would risk matching unrelated text on other
    # resumes. Deliberately small and growable, same philosophy as every
    # other gazetteer in this engine (technology_gazetteer.py, etc.).
    "Operations Executive", "Marketing Executive", "Account Executive",
)
