"""
Domain-classification gazetteer — Milestone 7 (Cutover). See
docs/architecture/Milestone7_ValidationReport.md.

Used by `candidate_profile_mapper.py` to deterministically score
`predicted_domain` against the same closed label set
`candidate_profile_generator.DOMAIN_LABELS` already defines -- a small,
curated keyword-per-domain gazetteer, matching every other gazetteer's
precedent in this engine (a one-line, reviewable diff to extend).
"""

from __future__ import annotations

# Keys MUST exactly match candidate_profile_generator.DOMAIN_LABELS.
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Software Engineering": (
        "software", "backend", "frontend", "full stack", "api", "microservices",
        "python", "java", "javascript", "typescript", "react", "node", "docker",
        "kubernetes", "git", "rest", "graphql", "sql", "cloud", "aws", "azure", "gcp",
    ),
    "Data Science": (
        "data science", "machine learning", "deep learning", "pandas", "numpy",
        "scikit-learn", "tensorflow", "pytorch", "statistics", "regression",
        "classification", "nlp", "data analysis", "jupyter", "data scientist",
    ),
    "Finance": (
        "finance", "financial", "trading", "portfolio", "investment", "banking",
        "equity", "accounting", "risk management", "financial modeling", "audit",
    ),
    "Healthcare": (
        "healthcare", "clinical", "patient", "hipaa", "medical", "nursing",
        "pharma", "diagnosis", "hospital", "ehr", "electronic health record",
    ),
    "Marketing": (
        "marketing", "seo", "sem", "campaign", "branding", "social media",
        "content strategy", "growth marketing", "email marketing", "advertising",
    ),
    "Law": (
        "law", "legal", "litigation", "contract", "compliance", "paralegal",
        "attorney", "regulatory", "intellectual property",
    ),
    "Education": (
        "education", "teaching", "curriculum", "classroom", "instructor",
        "pedagogy", "lesson plan", "tutor", "professor",
    ),
    "Mechanical Engineering": (
        "mechanical engineering", "cad", "solidworks", "thermodynamics",
        "autocad", "manufacturing", "hvac", "finite element", "mechanical design",
    ),
    "Cybersecurity": (
        "cybersecurity", "penetration testing", "soc", "firewall", "vulnerability",
        "incident response", "siem", "malware", "encryption", "security engineer",
    ),
    "Product Management": (
        "product management", "roadmap", "stakeholder", "prd", "product owner",
        "user research", "product strategy", "agile", "scrum", "backlog",
    ),
}
