"""
Technology/tool gazetteer — Milestone 3 (Entity Parsing). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Shared, single source of truth between `ProjectParser` (built in Milestone
3) and `SkillsParser` (Milestone 5) -- the architecture doc explicitly warns
against each maintaining its own list, which would drift. A plain data
file, matching `section_gazetteer.py`'s precedent: the maintenance cost
(new frameworks emerging) is meant to be a one-line, reviewable diff, not a
code change.

Matching is case-insensitive substring/word-boundary matching against
`TECHNOLOGIES` (done by the caller, not here) -- this file is just the
curated vocabulary.
"""

from __future__ import annotations

TECHNOLOGIES: tuple[str, ...] = (
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "SQL",
    # Web / frontend
    "React", "React Native", "Angular", "Vue", "Next.js", "Node.js",
    "Express", "HTML", "CSS", "Tailwind", "Redux", "GraphQL", "REST",
    # Backend / frameworks
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", ".NET", "Rails",
    "Laravel",
    # Data / ML
    "Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch", "Keras",
    "Spark", "Hadoop", "Airflow", "Kafka", "dbt",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Cassandra",
    "DynamoDB", "Elasticsearch", "Snowflake", "BigQuery",
    # Cloud / infra
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible",
    "Jenkins", "GitHub Actions", "CircleCI", "Nginx",
    # Tools
    "Git", "Linux", "Bash", "Jira", "Figma", "Postman",
)
