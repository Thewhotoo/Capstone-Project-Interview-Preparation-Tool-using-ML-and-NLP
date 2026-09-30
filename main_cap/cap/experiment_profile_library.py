"""
Experiment Profile Library — research-milestone data, not a new mechanism.

36 hand-authored `CandidateProfile`-shaped plain dicts spanning 12 technical
domains (3 profiles each: Backend, Frontend, Full Stack, AI/ML, Data
Engineering, Cloud/Infrastructure, DevOps/SRE, Cybersecurity, Mobile,
QA/Test Automation, Embedded/IoT, Blockchain/Web3). Every profile is
individually realistic — distinct company names, project names, technology
choices, and career narrative — not a combinatorial recombination of
interchangeable parts. The three profiles within a domain differ
meaningfully in seniority, project complexity, technology stack, and
experience/certification history, deliberately avoiding template variation.

Consumed by the existing, unmodified `Planner`/`TopicPool`/`QuestionRealizer`
(Phases 1/2) — nothing here defines a new generation mechanism, a new
schema, or a new architectural concept. Kept fully separate from
`experiment_candidate_profiles.py` (session 8's 5 profiles, untouched) so
the validation-target counts in SESSION_HANDOFF.md stay exact: this library
alone is the 36-profile pool `run_third_experiment.py` draws from.

`_profile(...)` below is a code-organization convenience only (avoids
repeating the same dict boilerplate 36 times) — every call site's actual
CONTENT (names, projects, technologies, narrative) is bespoke, not
parameterized/recombined. Each profile has 3 projects (one seeded for
project_deep_dive), 1-2 experience entries, up to 1 certification, and 3
traceable technical_topics -- sized to average ~10 discussion
specifications per profile per the approved validation target.
"""

from __future__ import annotations


def _profile(
    candidate_name: str,
    domain: str,
    experience_level: str,
    skills: list[str],
    experience: list[dict],
    projects: list[dict],
    certifications: list[str],
    resume_summary: str,
    technical_topics: list[dict],
    estimated_strengths: list[str],
) -> dict:
    return {
        "candidate_name": candidate_name,
        "contact_details": {"email": f"{candidate_name.lower().replace(' ', '.')}@example.com"},
        "skills": skills,
        "education": [],
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "predicted_domain": domain,
        "experience_level": experience_level,
        "confidence": 0.8,
        "resume_summary": resume_summary,
        "interview_blueprint": {
            "resume_verification_topics": [],
            "technical_topics": technical_topics,
            "starting_difficulty": "intermediate",
            "estimated_strengths": estimated_strengths,
            "estimated_weaknesses": [p["title"] for p in projects[:1]],
        },
    }


def _project(title: str, summary: str, technologies: list[str], concepts: list[str], seeds: list[str]) -> dict:
    return {"title": title, "summary": summary, "technologies": technologies, "concepts": concepts, "interview_seeds": seeds}


def _experience(role: str, company: str, duration: str, summary: str) -> dict:
    return {"role": role, "company": company, "duration": duration, "summary": summary}


def _topic(topic: str, evidence: str, originating_project: str = "", originating_experience: str = "") -> dict:
    return {"topic": topic, "originating_project": originating_project, "originating_experience": originating_experience, "evidence": evidence}


# ═════════════════════════════════════════════════════════════════════════════
# Backend Engineering
# ═════════════════════════════════════════════════════════════════════════════

def _backend_junior() -> dict:
    return _profile(
        "Priya Nandakumar", "Backend Engineering", "Junior",
        ["Python", "Django", "PostgreSQL", "Celery"],
        [_experience("Backend Engineering Intern", "Brightleaf Retail", "Summer 2024",
                      "Built order-processing endpoints for a small e-commerce platform.")],
        [
            _project("E-Commerce Order Service", "A Django service handling order placement and inventory checks.",
                      ["Python", "Django", "PostgreSQL", "Celery"], ["Task queues", "Database transactions"],
                      ["Why Celery for background order processing?", "How inventory race conditions were handled"]),
            _project("Personal Blog API", "A small Flask API backing a personal blog.",
                      ["Python", "Flask"], ["REST API design"], []),
            _project("Rate-Limited Public API Gateway", "A small Flask gateway adding rate limiting to a public API.",
                      ["Python", "Flask"], ["Rate limiting"], []),
        ],
        [],
        "A junior backend engineer with hands-on Django/Celery experience from an e-commerce internship.",
        [
            _topic("Handling concurrent inventory updates", "built order-processing endpoints with inventory checks", originating_project="E-Commerce Order Service"),
            _topic("Day-to-day intern responsibilities", "built order-processing endpoints for a small e-commerce platform", originating_experience="Backend Engineering Intern"),
            _topic("Adding rate limiting to a public API", "built a small Flask gateway adding rate limiting to a public API", originating_project="Rate-Limited Public API Gateway"),
        ],
        ["Comfortable with relational data modeling"],
    )


def _backend_mid() -> dict:
    return _profile(
        "Marcus Ojo", "Backend Engineering", "Intermediate",
        ["Java", "Spring Boot", "Kafka", "PostgreSQL", "AWS"],
        [
            _experience("Backend Engineer", "Ledgerway Financial", "2022-2024",
                         "Owned payment reconciliation services processing millions of daily transactions."),
            _experience("Software Engineering Intern", "Ledgerway Financial", "Summer 2021",
                         "Built internal admin tooling for the operations team."),
        ],
        [
            _project("Payment Reconciliation Service", "A Spring Boot service reconciling payment provider records against internal ledgers.",
                      ["Java", "Spring Boot", "Kafka", "PostgreSQL"], ["Event-driven architecture", "Idempotency"],
                      ["How duplicate payment events are handled", "Why Kafka over a direct database write here"]),
            _project("Internal Admin Dashboard API", "A Spring Boot API powering an internal operations dashboard.",
                      ["Java", "Spring Boot"], ["Role-based access control"], []),
            _project("Ledger Audit Log Service", "An append-only audit log service for tracking all ledger mutations.",
                      ["Java", "PostgreSQL"], ["Immutable logging"], []),
        ],
        ["AWS Certified Developer – Associate"],
        "A backend engineer specializing in event-driven financial systems.",
        [
            _topic("Ensuring idempotent payment processing", "reconciles payment provider records against internal ledgers", originating_project="Payment Reconciliation Service"),
            _topic("Reconciliation ownership at Ledgerway", "owned payment reconciliation services processing millions of daily transactions", originating_experience="Backend Engineer"),
            _topic("Designing an immutable audit log", "built an append-only audit log service for tracking all ledger mutations", originating_project="Ledger Audit Log Service"),
        ],
        ["Strong grasp of event-driven consistency"],
    )


def _backend_senior() -> dict:
    return _profile(
        "Elena Kovacs", "Backend Engineering", "Senior",
        ["Go", "gRPC", "Redis", "Kubernetes", "Envoy"],
        [_experience("Senior Backend Engineer", "Northstar Systems", "2019-2024",
                      "Led the migration of a monolithic API to a distributed gRPC service mesh.")],
        [
            _project("Distributed Rate Limiter", "A Go/Redis rate limiter shared across dozens of internal services.",
                      ["Go", "gRPC", "Redis", "Kubernetes"], ["Distributed systems", "Sliding window algorithms"],
                      ["How the rate limiter stays consistent across replicas", "Why Redis over an in-memory approach"]),
            _project("Service Mesh Migration", "Migrated 40+ services from REST to gRPC behind an Envoy mesh.",
                      ["Go", "Envoy", "gRPC"], ["Service mesh", "Zero-downtime migration"],
                      ["How the migration avoided downtime"]),
            _project("gRPC Client Library for Internal Teams", "A shared Go gRPC client library used by 40+ services.",
                      ["Go", "gRPC"], ["Client library design"], []),
        ],
        ["Certified Kubernetes Application Developer (CKAD)"],
        "A senior backend engineer focused on distributed systems and service mesh architecture.",
        [
            _topic("Distributed rate limiting consistency", "built a Go/Redis rate limiter shared across dozens of services", originating_project="Distributed Rate Limiter"),
            _topic("Leading a zero-downtime service migration", "led the migration of a monolithic API to a distributed gRPC service mesh", originating_experience="Senior Backend Engineer"),
            _topic("Designing a reusable gRPC client library", "built a shared Go gRPC client library used by 40+ services", originating_project="gRPC Client Library for Internal Teams"),
        ],
        ["Deep experience with distributed systems tradeoffs"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Frontend Engineering
# ═════════════════════════════════════════════════════════════════════════════

def _frontend_junior() -> dict:
    return _profile(
        "Jamal Whitfield", "Frontend Engineering", "Junior",
        ["JavaScript", "React", "Redux", "CSS"],
        [_experience("Frontend Intern", "Recipeo", "Summer 2024", "Built UI features for a recipe-sharing web app.")],
        [
            _project("Recipe Sharing App", "A React/Redux app for browsing and saving recipes.",
                      ["React", "Redux", "JavaScript"], ["State management", "Component reuse"],
                      ["How recipe state is shared across components", "Why Redux instead of plain context"]),
            _project("Personal Portfolio Site", "A static portfolio site built with vanilla JS.",
                      ["HTML", "CSS", "JavaScript"], ["Responsive design"], []),
            _project("Weather Widget Component", "A reusable React weather widget embedded in multiple pages.",
                      ["React"], ["Component reuse"], []),
        ],
        [],
        "A junior frontend engineer with practical React/Redux experience.",
        [
            _topic("Structuring Redux state for recipes", "built a React/Redux app for browsing and saving recipes", originating_project="Recipe Sharing App"),
            _topic("Intern responsibilities at Recipeo", "built UI features for a recipe-sharing web app", originating_experience="Frontend Intern"),
            _topic("Building a reusable weather widget", "built a reusable React weather widget embedded in multiple pages", originating_project="Weather Widget Component"),
        ],
        ["Solid fundamentals in component-based UI"],
    )


def _frontend_mid() -> dict:
    return _profile(
        "Sofia Delgado", "Frontend Engineering", "Intermediate",
        ["TypeScript", "Vue", "Vuex", "Vite"],
        [
            _experience("Frontend Engineer", "Ledgerway Financial", "2021-2024", "Owned the internal CRM's UI layer."),
            _experience("Junior Frontend Developer", "PixelForge Studio", "2020-2021", "Built landing pages for client campaigns."),
        ],
        [
            _project("Internal CRM UI", "A Vue/TypeScript rewrite of the internal customer-relationship-management tool.",
                      ["Vue", "TypeScript", "Vuex"], ["Type safety", "Form validation"],
                      ["Why TypeScript was adopted mid-project", "How complex forms are validated"]),
            _project("Design Token Pipeline", "A pipeline generating CSS from a shared design-token source of truth.",
                      ["TypeScript"], ["Design systems"], []),
            _project("Accessibility Audit Tooling", "A TypeScript tool automating accessibility checks in CI.",
                      ["TypeScript"], ["Accessibility"], []),
        ],
        [],
        "A frontend engineer who led a TypeScript migration for an internal CRM.",
        [
            _topic("Migrating a large Vue app to TypeScript", "owned a Vue/TypeScript rewrite of the internal CRM's UI layer", originating_project="Internal CRM UI"),
            _topic("Ownership of the CRM UI", "owned the internal CRM's UI layer", originating_experience="Frontend Engineer"),
            _topic("Automating accessibility audits", "built a TypeScript tool automating accessibility checks in CI", originating_project="Accessibility Audit Tooling"),
        ],
        ["Strong grasp of type-safe frontend architecture"],
    )


def _frontend_senior() -> dict:
    return _profile(
        "Tobias Lindqvist", "Frontend Engineering", "Senior",
        ["Angular", "Module Federation", "Storybook", "RxJS"],
        [_experience("Senior Frontend Engineer", "Northstar Systems", "2018-2024",
                      "Led the adoption of micro-frontends across five product teams.")],
        [
            _project("Micro-Frontend Platform", "An Angular/Module Federation platform letting teams ship independently.",
                      ["Angular", "Module Federation", "RxJS"], ["Micro-frontends", "Independent deployability"],
                      ["How independent teams avoid version conflicts", "Why Module Federation over iframes"]),
            _project("Shared Design System", "A component library used across all five product teams.",
                      ["Angular", "Storybook"], ["Design systems"],
                      ["How the design system stays backward compatible"]),
            _project("Cross-Team Component Versioning Tool", "A tool tracking component version compatibility across teams.",
                      ["Angular"], ["Dependency management"], []),
        ],
        [],
        "A senior frontend engineer specializing in micro-frontend architecture.",
        [
            _topic("Avoiding dependency conflicts across teams", "built an Angular/Module Federation platform for independent team deployments", originating_project="Micro-Frontend Platform"),
            _topic("Leading micro-frontend adoption", "led the adoption of micro-frontends across five product teams", originating_experience="Senior Frontend Engineer"),
            _topic("Managing component versioning across teams", "built a tool tracking component version compatibility across teams", originating_project="Cross-Team Component Versioning Tool"),
        ],
        ["Deep experience with large-scale frontend architecture"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Full Stack Engineering
# ═════════════════════════════════════════════════════════════════════════════

def _fullstack_junior() -> dict:
    return _profile(
        "Aditi Rao", "Full Stack Engineering", "Junior",
        ["JavaScript", "Node.js", "Express", "MongoDB", "React"],
        [_experience("Full Stack Intern", "TaskFlow", "Summer 2024", "Built features across the MERN stack task-management app.")],
        [
            _project("Task Management App", "A MERN app for team task tracking.",
                      ["MongoDB", "Express", "React", "Node.js"], ["Full stack CRUD", "Authentication"],
                      ["How user authentication was implemented", "Why MongoDB over a relational database"]),
            _project("Weather Dashboard", "A Node/React app showing weather forecasts from a public API.",
                      ["Node.js", "React"], ["Third-party API integration"], []),
            _project("Expense Splitter App", "A Node/React app for splitting shared expenses among users.",
                      ["Node.js", "React"], ["Full stack CRUD"], []),
        ],
        [],
        "A junior full stack engineer with MERN-stack project experience.",
        [
            _topic("Implementing authentication end to end", "built a MERN app for team task tracking", originating_project="Task Management App"),
            _topic("Full stack intern responsibilities", "built features across the MERN stack task-management app", originating_experience="Full Stack Intern"),
            _topic("Splitting expenses fairly among users", "built a Node/React app for splitting shared expenses among users", originating_project="Expense Splitter App"),
        ],
        ["Comfortable across the full stack"],
    )


def _fullstack_mid() -> dict:
    return _profile(
        "Daniel Osei", "Full Stack Engineering", "Intermediate",
        ["Python", "Django", "React", "PostgreSQL"],
        [
            _experience("Full Stack Engineer", "Marketplace Collective", "2022-2024", "Built the seller-facing marketplace platform end to end."),
            _experience("Software Engineering Intern", "Marketplace Collective", "Summer 2021", "Built internal reporting tools."),
        ],
        [
            _project("Marketplace Platform", "A Django/React platform for sellers to manage listings and orders.",
                      ["Django", "React", "PostgreSQL"], ["Full stack architecture", "Search and filtering"],
                      ["How listing search is implemented", "Why Django over a lighter framework"]),
            _project("Internal Reporting Suite", "A Django/React tool for internal sales reporting.",
                      ["Django", "React"], ["Data visualization"], []),
            _project("Seller Onboarding Wizard", "A guided multi-step onboarding flow for new sellers.",
                      ["Django", "React"], ["Multi-step forms"], []),
        ],
        [],
        "A full stack engineer who built a marketplace platform end to end.",
        [
            _topic("Implementing fast listing search", "built a Django/React platform for sellers to manage listings and orders", originating_project="Marketplace Platform"),
            _topic("End-to-end platform ownership", "built the seller-facing marketplace platform end to end", originating_experience="Full Stack Engineer"),
            _topic("Streamlining seller onboarding", "built a guided multi-step onboarding flow for new sellers", originating_project="Seller Onboarding Wizard"),
        ],
        ["Strong grasp of full stack tradeoffs"],
    )


def _fullstack_senior() -> dict:
    return _profile(
        "Grace Chen", "Full Stack Engineering", "Senior",
        ["TypeScript", "Next.js", "GraphQL", "PostgreSQL", "WebSockets"],
        [_experience("Senior Full Stack Engineer", "Analytics Peak", "2019-2024", "Built a SaaS analytics platform from its first commit.")],
        [
            _project("SaaS Analytics Platform", "A Next.js/GraphQL platform for real-time product analytics.",
                      ["Next.js", "GraphQL", "PostgreSQL"], ["Server-side rendering", "Query batching"],
                      ["Why GraphQL over REST for this platform", "How dashboards stay performant at scale"]),
            _project("Realtime Collaboration Tool", "A WebSocket-based tool for collaborative dashboard editing.",
                      ["Next.js", "WebSockets"], ["Real-time synchronization"],
                      ["How conflicting concurrent edits are resolved"]),
            _project("Usage-Based Billing Engine", "A billing engine computing charges from metered product usage.",
                      ["Next.js", "PostgreSQL"], ["Metered billing"], []),
        ],
        ["AWS Certified Solutions Architect – Associate"],
        "A senior full stack engineer who built a SaaS analytics platform from scratch.",
        [
            _topic("Keeping dashboards performant at scale", "built a Next.js/GraphQL platform for real-time product analytics", originating_project="SaaS Analytics Platform"),
            _topic("Building a platform from its first commit", "built a SaaS analytics platform from its first commit", originating_experience="Senior Full Stack Engineer"),
            _topic("Building a usage-based billing engine", "built a billing engine computing charges from metered product usage", originating_project="Usage-Based Billing Engine"),
        ],
        ["Deep experience shipping a platform from zero to scale"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# AI / Machine Learning
# ═════════════════════════════════════════════════════════════════════════════

def _aiml_junior() -> dict:
    return _profile(
        "Noah Kim", "AI / Machine Learning", "Junior",
        ["Python", "scikit-learn", "Pandas"],
        [_experience("ML Intern", "RetailSense", "Summer 2024", "Built customer segmentation models for a retail analytics team.")],
        [
            _project("Customer Segmentation Model", "A scikit-learn clustering model grouping customers by purchase behavior.",
                      ["Python", "scikit-learn", "Pandas"], ["Feature engineering", "Clustering"],
                      ["How features were engineered from raw transactions", "Why k-means over another clustering method"]),
            _project("Movie Recommendation Engine", "A collaborative-filtering recommender for a movie catalog.",
                      ["Python", "Pandas"], ["Collaborative filtering"], []),
            _project("Churn Prediction Notebook", "A scikit-learn notebook predicting churn from behavioral features.",
                      ["Python", "scikit-learn"], ["Classification"], []),
        ],
        [],
        "A junior ML engineer with hands-on scikit-learn experience from a retail analytics internship.",
        [
            _topic("Feature engineering for customer segments", "built a scikit-learn clustering model grouping customers by purchase behavior", originating_project="Customer Segmentation Model"),
            _topic("ML intern responsibilities at RetailSense", "built customer segmentation models for a retail analytics team", originating_experience="ML Intern"),
            _topic("Predicting churn from behavioral features", "built a scikit-learn notebook predicting churn from behavioral features", originating_project="Churn Prediction Notebook"),
        ],
        ["Solid fundamentals in classical ML"],
    )


def _aiml_mid() -> dict:
    return _profile(
        "Fatima Al-Sayed", "AI / Machine Learning", "Intermediate",
        ["Python", "PyTorch", "Hugging Face", "spaCy"],
        [
            _experience("Machine Learning Engineer", "Helios Analytics", "2022-2024", "Built NLP models for customer support automation."),
            _experience("ML Intern", "Helios Analytics", "Summer 2021", "Prototyped early support-ticket classifiers."),
        ],
        [
            _project("Support Ticket Classifier", "A fine-tuned transformer classifying incoming support tickets by urgency.",
                      ["PyTorch", "Hugging Face"], ["Transfer learning", "Model evaluation"],
                      ["Why a fine-tuned transformer over a bag-of-words model", "How class imbalance was handled"]),
            _project("Sentiment Analysis Pipeline", "A spaCy/PyTorch pipeline scoring support ticket sentiment.",
                      ["PyTorch", "spaCy"], ["NLP preprocessing"], []),
            _project("Named Entity Recognition Service", "A spaCy service extracting product/account entities from tickets.",
                      ["spaCy"], ["Named entity recognition"], []),
        ],
        ["TensorFlow Developer Certificate"],
        "An ML engineer specializing in NLP for customer support automation.",
        [
            _topic("Handling class imbalance in ticket classification", "built a fine-tuned transformer classifying support tickets by urgency", originating_project="Support Ticket Classifier"),
            _topic("Owning NLP models for support automation", "built NLP models for customer support automation", originating_experience="Machine Learning Engineer"),
            _topic("Extracting entities from support tickets", "built a spaCy service extracting product/account entities from tickets", originating_project="Named Entity Recognition Service"),
        ],
        ["Strong grasp of applied NLP"],
    )


def _aiml_senior() -> dict:
    return _profile(
        "Viktor Petrov", "AI / Machine Learning", "Senior",
        ["Python", "PyTorch", "LangChain", "FAISS", "MLflow"],
        [_experience("Senior ML Engineer", "Cortex Labs", "2019-2024", "Led development of a retrieval-augmented generation platform.")],
        [
            _project("Retrieval-Augmented Generation Platform", "A LangChain/FAISS platform grounding LLM answers in internal documents.",
                      ["PyTorch", "LangChain", "FAISS"], ["Retrieval-augmented generation", "Vector search"],
                      ["How retrieval quality was evaluated", "Why FAISS over a managed vector database"]),
            _project("Model Serving Infrastructure", "An MLflow/Kubernetes platform serving dozens of production models.",
                      ["MLflow", "Kubernetes"], ["Model versioning", "Serving infrastructure"],
                      ["How model rollbacks are handled safely"]),
            _project("LLM Evaluation Harness", "A harness systematically evaluating LLM output quality across prompts.",
                      ["PyTorch"], ["LLM evaluation"], []),
        ],
        ["AWS Certified Machine Learning – Specialty"],
        "A senior ML engineer specializing in retrieval-augmented generation and model serving.",
        [
            _topic("Evaluating retrieval quality", "built a LangChain/FAISS platform grounding LLM answers in internal documents", originating_project="Retrieval-Augmented Generation Platform"),
            _topic("Leading the RAG platform's development", "led development of a retrieval-augmented generation platform", originating_experience="Senior ML Engineer"),
            _topic("Evaluating LLM output quality systematically", "built a harness systematically evaluating LLM output quality across prompts", originating_project="LLM Evaluation Harness"),
        ],
        ["Deep experience with production LLM systems"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Data Engineering
# ═════════════════════════════════════════════════════════════════════════════

def _dataeng_junior() -> dict:
    return _profile(
        "Lucas Ferreira", "Data Engineering", "Junior",
        ["Python", "SQL", "Airflow", "PostgreSQL"],
        [_experience("Data Engineering Intern", "RetailSense", "Summer 2024", "Built ETL pipelines for daily sales reporting.")],
        [
            _project("Sales ETL Pipeline", "An Airflow pipeline aggregating daily sales data into a reporting warehouse.",
                      ["Python", "Airflow", "PostgreSQL"], ["ETL orchestration", "Data validation"],
                      ["How pipeline failures are retried", "Why Airflow over a cron script"]),
            _project("Data Quality Dashboard", "A dashboard flagging anomalies in incoming sales data.",
                      ["SQL", "Pandas"], ["Data quality checks"], []),
            _project("Data Catalog Prototype", "A prototype cataloging available internal datasets and owners.",
                      ["Python"], ["Data cataloging"], []),
        ],
        [],
        "A junior data engineer with Airflow-based ETL experience.",
        [
            _topic("Retrying failed pipeline stages", "built an Airflow pipeline aggregating daily sales data", originating_project="Sales ETL Pipeline"),
            _topic("Intern responsibilities at RetailSense", "built ETL pipelines for daily sales reporting", originating_experience="Data Engineering Intern"),
            _topic("Cataloging available datasets", "built a prototype cataloging available internal datasets and owners", originating_project="Data Catalog Prototype"),
        ],
        ["Comfortable with pipeline orchestration"],
    )


def _dataeng_mid() -> dict:
    return _profile(
        "Ingrid Solberg", "Data Engineering", "Intermediate",
        ["Scala", "Spark", "Kafka", "Snowflake"],
        [
            _experience("Data Engineer", "Analytics Peak", "2021-2024", "Built streaming analytics pipelines processing billions of events daily."),
            _experience("Junior Data Engineer", "Analytics Peak", "2020-2021", "Maintained batch ETL jobs before the streaming migration."),
        ],
        [
            _project("Streaming Analytics Pipeline", "A Spark/Kafka pipeline computing real-time product usage metrics.",
                      ["Spark", "Kafka", "Scala"], ["Stream processing", "Windowed aggregation"],
                      ["How late-arriving events are handled", "Why Spark Streaming over Flink here"]),
            _project("Data Warehouse Migration", "Migrated the batch warehouse from Redshift to Snowflake.",
                      ["Snowflake"], ["Data warehousing"], []),
            _project("Backfill Automation Tool", "A tool automating historical data backfills after schema changes.",
                      ["Spark"], ["Data backfilling"], []),
        ],
        [],
        "A data engineer who migrated a batch pipeline to real-time streaming.",
        [
            _topic("Handling late-arriving events", "built a Spark/Kafka pipeline computing real-time product usage metrics", originating_project="Streaming Analytics Pipeline"),
            _topic("Scaling to billions of daily events", "built streaming analytics pipelines processing billions of events daily", originating_experience="Data Engineer"),
            _topic("Automating historical data backfills", "built a tool automating historical data backfills after schema changes", originating_project="Backfill Automation Tool"),
        ],
        ["Strong grasp of stream processing"],
    )


def _dataeng_senior() -> dict:
    return _profile(
        "Chidi Okafor", "Data Engineering", "Senior",
        ["Databricks", "Delta Lake", "dbt", "Snowflake"],
        [_experience("Senior Data Engineer", "Ledgerway Financial", "2018-2024", "Built the company's first lakehouse platform.")],
        [
            _project("Lakehouse Platform", "A Databricks/Delta Lake platform unifying batch and streaming data.",
                      ["Databricks", "Delta Lake", "dbt"], ["Lakehouse architecture", "Schema evolution"],
                      ["How schema evolution is handled without breaking downstream jobs", "Why a lakehouse over a traditional warehouse"]),
            _project("Data Governance Framework", "A dbt-based framework enforcing data quality and lineage standards.",
                      ["dbt", "Snowflake"], ["Data governance", "Lineage tracking"],
                      ["How data lineage is tracked across dozens of pipelines"]),
            _project("Cross-Team Data Contract Framework", "A framework enforcing schema contracts between producing and consuming teams.",
                      ["dbt"], ["Data contracts"], []),
        ],
        ["Databricks Certified Data Engineer Associate"],
        "A senior data engineer who built a company's first lakehouse platform.",
        [
            _topic("Handling schema evolution safely", "built a Databricks/Delta Lake platform unifying batch and streaming data", originating_project="Lakehouse Platform"),
            _topic("Building the first lakehouse platform", "built the company's first lakehouse platform", originating_experience="Senior Data Engineer"),
            _topic("Enforcing data contracts across teams", "built a framework enforcing schema contracts between producing and consuming teams", originating_project="Cross-Team Data Contract Framework"),
        ],
        ["Deep experience with lakehouse architecture"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Cloud / Infrastructure
# ═════════════════════════════════════════════════════════════════════════════

def _cloud_junior() -> dict:
    return _profile(
        "Hana Suzuki", "Cloud / Infrastructure", "Junior",
        ["AWS", "Terraform", "S3", "CloudFront"],
        [_experience("Cloud Infrastructure Intern", "Brightleaf Retail", "Summer 2024", "Set up static site hosting infrastructure on AWS.")],
        [
            _project("Static Site Hosting Pipeline", "A Terraform-managed S3/CloudFront pipeline for marketing sites.",
                      ["AWS", "Terraform"], ["Infrastructure as code", "CDN configuration"],
                      ["Why CloudFront over serving directly from S3", "How the Terraform state is managed"]),
            _project("Internal VPN Setup", "Configured a site-to-site VPN between the office and AWS VPC.",
                      ["AWS"], ["Networking"], []),
            _project("Cost Alerting Script", "A script alerting the team when AWS spend exceeds a threshold.",
                      ["AWS"], ["Cost monitoring"], []),
        ],
        [],
        "A junior cloud engineer with hands-on Terraform/AWS experience.",
        [
            _topic("Managing Terraform state safely", "built a Terraform-managed S3/CloudFront pipeline for marketing sites", originating_project="Static Site Hosting Pipeline"),
            _topic("Cloud intern responsibilities", "set up static site hosting infrastructure on AWS", originating_experience="Cloud Infrastructure Intern"),
            _topic("Alerting on unexpected cloud spend", "built a script alerting the team when AWS spend exceeds a threshold", originating_project="Cost Alerting Script"),
        ],
        ["Comfortable with infrastructure as code"],
    )


def _cloud_mid() -> dict:
    return _profile(
        "Omar Haddad", "Cloud / Infrastructure", "Intermediate",
        ["AWS", "Azure", "Terraform"],
        [
            _experience("Cloud Engineer", "Northstar Systems", "2021-2024", "Built a multi-account AWS landing zone for 15 product teams."),
            _experience("Infrastructure Intern", "Northstar Systems", "Summer 2020", "Automated manual AWS account provisioning."),
        ],
        [
            _project("Multi-Account AWS Landing Zone", "A Terraform-managed landing zone with per-team account isolation.",
                      ["AWS", "Terraform"], ["Account isolation", "Guardrails"],
                      ["How cross-account access is controlled", "Why per-team accounts over a shared account"]),
            _project("Disaster Recovery Pipeline", "A cross-region failover pipeline spanning AWS and Azure.",
                      ["AWS", "Azure"], ["Disaster recovery"], []),
            _project("Automated Account Provisioning Tool", "A Terraform tool automating new AWS account setup for teams.",
                      ["Terraform"], ["Account automation"], []),
        ],
        ["AWS Certified SysOps Administrator"],
        "A cloud engineer who built a multi-account AWS landing zone from scratch.",
        [
            _topic("Controlling cross-account access", "built a Terraform-managed landing zone with per-team account isolation", originating_project="Multi-Account AWS Landing Zone"),
            _topic("Scaling infrastructure to 15 teams", "built a multi-account AWS landing zone for 15 product teams", originating_experience="Cloud Engineer"),
            _topic("Automating new account provisioning", "built a Terraform tool automating new AWS account setup for teams", originating_project="Automated Account Provisioning Tool"),
        ],
        ["Strong grasp of account-level cloud security"],
    )


def _cloud_senior() -> dict:
    return _profile(
        "Isabella Marino", "Cloud / Infrastructure", "Senior",
        ["AWS", "GCP", "Terraform", "FinOps"],
        [_experience("Senior Cloud Architect", "Cortex Labs", "2017-2024", "Led a zero-downtime migration from AWS to GCP.")],
        [
            _project("Hybrid Cloud Cost Optimization Platform", "A Terraform-managed platform tracking spend across AWS and GCP.",
                      ["AWS", "GCP", "Terraform"], ["FinOps", "Cost attribution"],
                      ["How cost is attributed accurately across shared resources", "Why a hybrid setup instead of full migration"]),
            _project("Zero-Downtime Migration to GCP", "Migrated 200+ services from AWS to GCP without downtime.",
                      ["GCP", "Terraform"], ["Cloud migration"],
                      ["How the migration was sequenced to avoid downtime"]),
            _project("Cross-Cloud IAM Standardization", "Standardized IAM policy definitions across AWS and GCP accounts.",
                      ["Terraform"], ["Identity and access management"], []),
        ],
        ["Google Professional Cloud Architect"],
        "A senior cloud architect who led a large-scale zero-downtime cloud migration.",
        [
            _topic("Attributing cost across shared cloud resources", "built a platform tracking spend across AWS and GCP", originating_project="Hybrid Cloud Cost Optimization Platform"),
            _topic("Leading a 200-service cloud migration", "led a zero-downtime migration from AWS to GCP", originating_experience="Senior Cloud Architect"),
            _topic("Standardizing IAM policies across clouds", "standardized IAM policy definitions across AWS and GCP accounts", originating_project="Cross-Cloud IAM Standardization"),
        ],
        ["Deep experience with large-scale cloud migrations"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# DevOps / SRE
# ═════════════════════════════════════════════════════════════════════════════

def _devops_junior() -> dict:
    return _profile(
        "Ryan O'Connell", "DevOps / SRE", "Junior",
        ["Docker", "GitHub Actions", "Bash"],
        [_experience("DevOps Intern", "TaskFlow", "Summer 2024", "Built CI/CD pipelines for a microservices codebase.")],
        [
            _project("CI/CD Pipeline for Microservices", "A GitHub Actions pipeline building and deploying a dozen microservices.",
                      ["Docker", "GitHub Actions"], ["Continuous integration", "Deployment automation"],
                      ["How the pipeline avoids deploying broken builds", "Why GitHub Actions over Jenkins here"]),
            _project("Automated Deployment Scripts", "Bash/Docker scripts standardizing local dev environment setup.",
                      ["Docker", "Bash"], ["Developer tooling"], []),
            _project("Local Dev Environment Bootstrapper", "A script bootstrapping a full local dev environment in one command.",
                      ["Docker", "Bash"], ["Developer tooling"], []),
        ],
        [],
        "A junior DevOps engineer with hands-on CI/CD pipeline experience.",
        [
            _topic("Preventing broken builds from deploying", "built a GitHub Actions pipeline building and deploying a dozen microservices", originating_project="CI/CD Pipeline for Microservices"),
            _topic("DevOps intern responsibilities", "built CI/CD pipelines for a microservices codebase", originating_experience="DevOps Intern"),
            _topic("Bootstrapping local dev environments", "built a script bootstrapping a full local dev environment in one command", originating_project="Local Dev Environment Bootstrapper"),
        ],
        ["Comfortable automating deployment workflows"],
    )


def _devops_mid() -> dict:
    return _profile(
        "Katarzyna Wojcik", "DevOps / SRE", "Intermediate",
        ["Kubernetes", "Prometheus", "Grafana", "Ansible"],
        [
            _experience("DevOps Engineer", "Ledgerway Financial", "2022-2024", "Built the observability stack for a Kubernetes platform."),
            _experience("Systems Intern", "Ledgerway Financial", "Summer 2021", "Automated server patching with Ansible."),
        ],
        [
            _project("Kubernetes Cluster Observability Stack", "A Prometheus/Grafana stack monitoring 50+ Kubernetes clusters.",
                      ["Kubernetes", "Prometheus", "Grafana"], ["Observability", "Alerting"],
                      ["How alert fatigue was reduced", "Why Prometheus over a managed monitoring service"]),
            _project("Incident Response Automation", "Ansible playbooks automating common incident remediation steps.",
                      ["Ansible"], ["Runbook automation"], []),
            _project("On-Call Rotation Automation", "A tool automating fair on-call rotation scheduling across teams.",
                      ["Ansible"], ["On-call scheduling"], []),
        ],
        ["Certified Kubernetes Administrator (CKA)"],
        "A DevOps engineer specializing in Kubernetes observability.",
        [
            _topic("Reducing alert fatigue", "built a Prometheus/Grafana stack monitoring 50+ Kubernetes clusters", originating_project="Kubernetes Cluster Observability Stack"),
            _topic("Building observability for the platform", "built the observability stack for a Kubernetes platform", originating_experience="DevOps Engineer"),
            _topic("Automating on-call rotation scheduling", "built a tool automating fair on-call rotation scheduling across teams", originating_project="On-Call Rotation Automation"),
        ],
        ["Strong grasp of observability tradeoffs"],
    )


def _devops_senior() -> dict:
    return _profile(
        "Anders Berg", "DevOps / SRE", "Senior",
        ["Kubernetes", "Prometheus", "Chaos Engineering"],
        [_experience("Senior Site Reliability Engineer", "Cortex Labs", "2018-2024", "Defined SLOs and led chaos engineering practice company-wide.")],
        [
            _project("Service-Level Objective Framework", "A Prometheus-based framework tracking SLOs across 60 services.",
                      ["Prometheus", "Grafana"], ["SLOs", "Error budgets"],
                      ["How error budgets influence release decisions", "Why SLOs over raw uptime targets"]),
            _project("Chaos Engineering Platform", "A platform injecting controlled failures into production-like environments.",
                      ["Kubernetes"], ["Chaos engineering", "Resilience testing"],
                      ["How blast radius is limited during chaos experiments"]),
            _project("Deployment Freeze Automation", "Automation that freezes deployments cluster-wide during active incidents.",
                      ["Kubernetes"], ["Incident response automation"], []),
        ],
        [],
        "A senior SRE who introduced SLO-driven reliability practices company-wide.",
        [
            _topic("Using error budgets to gate releases", "built a Prometheus-based framework tracking SLOs across 60 services", originating_project="Service-Level Objective Framework"),
            _topic("Leading company-wide chaos engineering adoption", "defined SLOs and led chaos engineering practice company-wide", originating_experience="Senior Site Reliability Engineer"),
            _topic("Automating deployment freezes during incidents", "built automation that freezes deployments cluster-wide during active incidents", originating_project="Deployment Freeze Automation"),
        ],
        ["Deep experience with reliability engineering practice"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Cybersecurity
# ═════════════════════════════════════════════════════════════════════════════

def _security_junior() -> dict:
    return _profile(
        "Zainab Hussain", "Cybersecurity", "Junior",
        ["Python", "Nmap", "Security fundamentals"],
        [_experience("Security Intern", "Brightleaf Retail", "Summer 2024", "Ran vulnerability scans across internal web applications.")],
        [
            _project("Vulnerability Scanning Automation", "A Python/Nmap tool scheduling and reporting on internal vulnerability scans.",
                      ["Python", "Nmap"], ["Vulnerability scanning", "Reporting automation"],
                      ["How scan results are prioritized", "Why Nmap was chosen over a commercial scanner"]),
            _project("Phishing Awareness Tool", "A Python tool generating simulated phishing campaigns for employee training.",
                      ["Python"], ["Security awareness"], []),
            _project("Password Policy Auditor", "A Python tool auditing accounts for weak or reused passwords.",
                      ["Python"], ["Password policy"], []),
        ],
        [],
        "A junior security engineer with hands-on vulnerability scanning experience.",
        [
            _topic("Prioritizing vulnerability scan findings", "built a Python/Nmap tool scheduling internal vulnerability scans", originating_project="Vulnerability Scanning Automation"),
            _topic("Security intern responsibilities", "ran vulnerability scans across internal web applications", originating_experience="Security Intern"),
            _topic("Auditing password policy compliance", "built a Python tool auditing accounts for weak or reused passwords", originating_project="Password Policy Auditor"),
        ],
        ["Comfortable with vulnerability assessment basics"],
    )


def _security_mid() -> dict:
    return _profile(
        "Diego Fuentes", "Cybersecurity", "Intermediate",
        ["Burp Suite", "Metasploit", "Splunk"],
        [
            _experience("Security Engineer", "Ledgerway Financial", "2022-2024", "Ran internal penetration tests and built incident response tooling."),
            _experience("Security Intern", "Ledgerway Financial", "Summer 2021", "Assisted with quarterly access reviews."),
        ],
        [
            _project("Internal Penetration Testing Toolkit", "A Burp Suite/Metasploit-based toolkit for quarterly internal pentests.",
                      ["Burp Suite", "Metasploit"], ["Penetration testing", "Exploit development"],
                      ["How findings are responsibly reported to engineering teams", "Why an internal toolkit over a third-party vendor"]),
            _project("Security Incident Response Runbooks", "Splunk-integrated runbooks standardizing incident response.",
                      ["Splunk"], ["Incident response"], []),
            _project("Access Review Automation Tool", "A tool automating quarterly user access reviews.",
                      ["Python"], ["Access reviews"], []),
        ],
        ["CompTIA Security+"],
        "A security engineer specializing in internal penetration testing.",
        [
            _topic("Responsibly reporting pentest findings", "built a Burp Suite/Metasploit toolkit for quarterly internal pentests", originating_project="Internal Penetration Testing Toolkit"),
            _topic("Running internal penetration tests", "ran internal penetration tests and built incident response tooling", originating_experience="Security Engineer"),
            _topic("Automating quarterly access reviews", "built a tool automating quarterly user access reviews", originating_project="Access Review Automation Tool"),
        ],
        ["Strong grasp of offensive security practices"],
    )


def _security_senior() -> dict:
    return _profile(
        "Yuki Tanaka", "Cybersecurity", "Senior",
        ["Splunk", "Wireshark", "Threat Intelligence"],
        [_experience("Senior Security Engineer", "Cortex Labs", "2017-2024", "Built the company's SOC and threat intelligence program.")],
        [
            _project("SIEM Correlation Rule Engine", "A Splunk-based engine correlating security events across 30+ data sources.",
                      ["Splunk", "Wireshark"], ["SIEM", "Alert correlation"],
                      ["How correlation rules avoid alert fatigue", "Why Splunk over an open-source SIEM"]),
            _project("Threat Intelligence Pipeline", "A pipeline enriching alerts with external threat intelligence feeds.",
                      ["Python", "Splunk"], ["Threat intelligence"],
                      ["How intelligence feeds are validated before use"]),
            _project("Insider Threat Detection Model", "A Splunk-based model flagging anomalous internal access patterns.",
                      ["Splunk"], ["Insider threat detection"], []),
        ],
        ["Certified Information Systems Security Professional (CISSP)"],
        "A senior security engineer who built a company's SOC from the ground up.",
        [
            _topic("Avoiding SIEM alert fatigue", "built a Splunk-based engine correlating security events across 30+ data sources", originating_project="SIEM Correlation Rule Engine"),
            _topic("Building the SOC from the ground up", "built the company's SOC and threat intelligence program", originating_experience="Senior Security Engineer"),
            _topic("Detecting insider threats from log data", "built a Splunk-based model flagging anomalous internal access patterns", originating_project="Insider Threat Detection Model"),
        ],
        ["Deep experience building security operations from scratch"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Mobile Development
# ═════════════════════════════════════════════════════════════════════════════

def _mobile_junior() -> dict:
    return _profile(
        "Camila Rivas", "Mobile Development", "Junior",
        ["React Native", "JavaScript"],
        [_experience("Mobile Intern", "Recipeo", "Summer 2024", "Built screens for a cross-platform fitness tracking app.")],
        [
            _project("Fitness Tracker App", "A React Native app tracking workouts and progress photos.",
                      ["React Native"], ["Local storage", "Camera integration"],
                      ["How workout history is stored offline", "Why React Native over separate native codebases"]),
            _project("Recipe Finder App", "A React Native app for browsing recipes by available ingredients.",
                      ["React Native"], ["Search and filtering"], []),
            _project("Grocery List Widget", "A home-screen widget showing the user's current grocery list.",
                      ["React Native"], ["Home-screen widgets"], []),
        ],
        [],
        "A junior mobile engineer with React Native app-building experience.",
        [
            _topic("Storing workout history offline", "built a React Native app tracking workouts and progress photos", originating_project="Fitness Tracker App"),
            _topic("Mobile intern responsibilities", "built screens for a cross-platform fitness tracking app", originating_experience="Mobile Intern"),
            _topic("Building a home-screen grocery widget", "built a home-screen widget showing the user's current grocery list", originating_project="Grocery List Widget"),
        ],
        ["Comfortable with cross-platform mobile development"],
    )


def _mobile_mid() -> dict:
    return _profile(
        "Ethan Brooks", "Mobile Development", "Intermediate",
        ["Kotlin", "Jetpack Compose", "Room"],
        [
            _experience("Android Engineer", "Northstar Systems", "2022-2024", "Built the ride-sharing driver app's core booking flow."),
            _experience("Mobile Intern", "Northstar Systems", "Summer 2021", "Fixed bugs in the passenger app's notification system."),
        ],
        [
            _project("Ride-Sharing Android App", "A Kotlin/Jetpack Compose app handling real-time ride matching.",
                      ["Kotlin", "Jetpack Compose"], ["Real-time updates", "Location tracking"],
                      ["How real-time location updates stay battery-efficient", "Why Jetpack Compose over the older View system"]),
            _project("Offline Notes App", "A Room-backed notes app syncing when connectivity returns.",
                      ["Kotlin", "Room"], ["Offline-first architecture"], []),
            _project("In-App Rating Prompt Module", "A reusable module showing a non-intrusive rating prompt at the right moment.",
                      ["Kotlin"], ["User experience timing"], []),
        ],
        ["Associate Android Developer"],
        "An Android engineer who built a ride-sharing app's core booking flow.",
        [
            _topic("Keeping location tracking battery-efficient", "built a Kotlin/Jetpack Compose app handling real-time ride matching", originating_project="Ride-Sharing Android App"),
            _topic("Owning the core booking flow", "built the ride-sharing driver app's core booking flow", originating_experience="Android Engineer"),
            _topic("Designing a non-intrusive rating prompt", "built a reusable module showing a non-intrusive rating prompt at the right moment", originating_project="In-App Rating Prompt Module"),
        ],
        ["Strong grasp of real-time mobile architecture"],
    )


def _mobile_senior() -> dict:
    return _profile(
        "Amara Nwosu", "Mobile Development", "Senior",
        ["Swift", "SwiftUI", "Combine"],
        [_experience("Senior iOS Engineer", "Ledgerway Financial", "2018-2024", "Led a modular architecture migration for the banking app.")],
        [
            _project("Banking iOS App", "A SwiftUI/Combine banking app handling transfers and bill pay.",
                      ["Swift", "SwiftUI", "Combine"], ["Reactive programming", "Security"],
                      ["How sensitive financial data is protected on-device", "Why Combine over completion handlers here"]),
            _project("Modular iOS Architecture Migration", "Migrated a monolithic app into independently buildable feature modules.",
                      ["Swift"], ["Modular architecture"],
                      ["How the migration was staged without blocking feature teams"]),
            _project("Biometric Login Module", "A reusable module implementing Face ID / Touch ID login securely.",
                      ["Swift"], ["Biometric authentication"], []),
        ],
        [],
        "A senior iOS engineer who led a modular architecture migration for a banking app.",
        [
            _topic("Protecting sensitive financial data on-device", "built a SwiftUI/Combine banking app handling transfers and bill pay", originating_project="Banking iOS App"),
            _topic("Leading the modular architecture migration", "led a modular architecture migration for the banking app", originating_experience="Senior iOS Engineer"),
            _topic("Implementing biometric login securely", "built a reusable module implementing Face ID / Touch ID login securely", originating_project="Biometric Login Module"),
        ],
        ["Deep experience with secure, modular iOS architecture"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# QA / Test Automation
# ═════════════════════════════════════════════════════════════════════════════

def _qa_junior() -> dict:
    return _profile(
        "Beatriz Lima", "QA / Test Automation", "Junior",
        ["Python", "Selenium"],
        [_experience("QA Intern", "TaskFlow", "Summer 2024", "Wrote regression tests for the task-management app's core flows.")],
        [
            _project("Regression Test Suite", "A Selenium/Python suite covering the app's core user flows.",
                      ["Python", "Selenium"], ["Test automation", "Regression testing"],
                      ["How flaky tests were identified and fixed", "Why Selenium over manual regression testing"]),
            _project("Bug Tracking Dashboard", "A Python tool summarizing open bugs by severity and age.",
                      ["Python"], ["Bug triage"], []),
            _project("Test Data Generator", "A Python tool generating realistic randomized test data.",
                      ["Python"], ["Test data generation"], []),
        ],
        [],
        "A junior QA engineer with Selenium-based regression testing experience.",
        [
            _topic("Diagnosing and fixing flaky tests", "built a Selenium/Python suite covering the app's core user flows", originating_project="Regression Test Suite"),
            _topic("QA intern responsibilities", "wrote regression tests for the task-management app's core flows", originating_experience="QA Intern"),
            _topic("Generating realistic test data", "built a Python tool generating realistic randomized test data", originating_project="Test Data Generator"),
        ],
        ["Comfortable with browser test automation"],
    )


def _qa_mid() -> dict:
    return _profile(
        "Mateusz Kaminski", "QA / Test Automation", "Intermediate",
        ["Cypress", "TypeScript", "Postman"],
        [
            _experience("QA Automation Engineer", "Marketplace Collective", "2022-2024", "Built the end-to-end test framework for the marketplace platform."),
            _experience("QA Intern", "Marketplace Collective", "Summer 2021", "Manually tested new seller-facing features."),
        ],
        [
            _project("End-to-End Test Framework", "A Cypress/TypeScript framework covering the marketplace's critical paths.",
                      ["Cypress", "TypeScript"], ["End-to-end testing", "CI integration"],
                      ["How the suite stays fast enough to run on every pull request", "Why Cypress over Selenium here"]),
            _project("API Test Automation Suite", "A Postman/Newman suite validating the platform's public API.",
                      ["Postman"], ["API testing"], []),
            _project("Visual Regression Testing Tool", "A tool catching unintended visual changes across releases.",
                      ["TypeScript"], ["Visual regression testing"], []),
        ],
        ["ISTQB Certified Tester"],
        "A QA automation engineer who built an end-to-end test framework from scratch.",
        [
            _topic("Keeping the test suite fast in CI", "built a Cypress/TypeScript framework covering the marketplace's critical paths", originating_project="End-to-End Test Framework"),
            _topic("Building the E2E framework from scratch", "built the end-to-end test framework for the marketplace platform", originating_experience="QA Automation Engineer"),
            _topic("Catching visual regressions automatically", "built a tool catching unintended visual changes across releases", originating_project="Visual Regression Testing Tool"),
        ],
        ["Strong grasp of CI-integrated test automation"],
    )


def _qa_senior() -> dict:
    return _profile(
        "Sarah Whitmore", "QA / Test Automation", "Senior",
        ["JMeter", "Gatling", "Playwright"],
        [_experience("Senior QA Engineer", "Analytics Peak", "2018-2024", "Overhauled the company's test strategy across five product teams.")],
        [
            _project("Performance Testing Platform", "A JMeter/Gatling platform load-testing the analytics platform before releases.",
                      ["JMeter", "Gatling"], ["Load testing", "Performance benchmarking"],
                      ["How realistic load patterns are modeled", "Why Gatling was added alongside JMeter"]),
            _project("Test Strategy & Framework Overhaul", "Replaced five teams' inconsistent test approaches with a shared Playwright framework.",
                      ["Playwright"], ["Test strategy"],
                      ["How teams were migrated without blocking their release cadence"]),
            _project("Cross-Browser Test Grid", "A grid running the shared test suite across multiple browser configurations.",
                      ["Playwright"], ["Cross-browser testing"], []),
        ],
        [],
        "A senior QA engineer who overhauled test strategy across five product teams.",
        [
            _topic("Modeling realistic load patterns", "built a JMeter/Gatling platform load-testing the analytics platform", originating_project="Performance Testing Platform"),
            _topic("Overhauling test strategy company-wide", "overhauled the company's test strategy across five product teams", originating_experience="Senior QA Engineer"),
            _topic("Running tests across browser configurations", "built a grid running the shared test suite across multiple browser configurations", originating_project="Cross-Browser Test Grid"),
        ],
        ["Deep experience with performance testing and test strategy"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Embedded / IoT
# ═════════════════════════════════════════════════════════════════════════════

def _embedded_junior() -> dict:
    return _profile(
        "Tomas Novak", "Embedded / IoT", "Junior",
        ["C++", "Arduino", "MQTT"],
        [_experience("Embedded Systems Intern", "SensorWorks", "Summer 2024", "Built firmware for home automation sensor nodes.")],
        [
            _project("Home Automation Sensor Network", "An Arduino/MQTT sensor network reporting temperature and motion.",
                      ["Arduino", "MQTT"], ["Sensor networks", "Low-power design"],
                      ["How sensor nodes conserve battery", "Why MQTT over HTTP polling here"]),
            _project("Weather Station Firmware", "C++ firmware reading weather sensors and logging readings locally.",
                      ["Arduino", "C++"], ["Firmware development"], []),
            _project("Soil Moisture Sensor Node", "A battery-powered sensor node reading soil moisture reliably outdoors.",
                      ["Arduino"], ["Outdoor sensor reliability"], []),
        ],
        [],
        "A junior embedded engineer with Arduino/MQTT sensor network experience.",
        [
            _topic("Conserving battery on sensor nodes", "built an Arduino/MQTT sensor network reporting temperature and motion", originating_project="Home Automation Sensor Network"),
            _topic("Embedded intern responsibilities", "built firmware for home automation sensor nodes", originating_experience="Embedded Systems Intern"),
            _topic("Reading soil moisture reliably outdoors", "built a battery-powered sensor node reading soil moisture reliably outdoors", originating_project="Soil Moisture Sensor Node"),
        ],
        ["Comfortable with low-power sensor design"],
    )


def _embedded_mid() -> dict:
    return _profile(
        "Nadia Rahman", "Embedded / IoT", "Intermediate",
        ["C", "FreeRTOS", "BLE"],
        [
            _experience("Embedded Software Engineer", "SensorWorks", "2022-2024", "Built firmware for a wearable health-monitoring device."),
            _experience("Firmware Intern", "SensorWorks", "Summer 2021", "Wrote unit tests for existing sensor drivers."),
        ],
        [
            _project("Wearable Device Firmware", "FreeRTOS-based firmware managing sensor sampling and BLE data transfer.",
                      ["FreeRTOS", "C"], ["Real-time scheduling", "Power management"],
                      ["How sensor sampling and BLE transfer are scheduled together", "Why FreeRTOS over a bare-metal loop"]),
            _project("Bluetooth Low Energy Sensor Hub", "A BLE hub aggregating readings from multiple wearables.",
                      ["BLE", "C++"], ["Wireless protocols"], []),
            _project("Firmware OTA Update Mechanism", "A mechanism delivering firmware updates over the air safely.",
                      ["C"], ["Over-the-air updates"], []),
        ],
        [],
        "An embedded engineer who built firmware for a wearable health-monitoring device.",
        [
            _topic("Scheduling sensor sampling and BLE transfer together", "built FreeRTOS-based firmware managing sensor sampling and BLE data transfer", originating_project="Wearable Device Firmware"),
            _topic("Building the wearable's firmware", "built firmware for a wearable health-monitoring device", originating_experience="Embedded Software Engineer"),
            _topic("Delivering firmware updates over the air safely", "built a mechanism delivering firmware updates over the air safely", originating_project="Firmware OTA Update Mechanism"),
        ],
        ["Strong grasp of real-time embedded scheduling"],
    )


def _embedded_senior() -> dict:
    return _profile(
        "Hiroshi Yamamoto", "Embedded / IoT", "Senior",
        ["Zephyr RTOS", "MQTT", "TensorFlow Lite"],
        [_experience("Senior Embedded Engineer", "Cortex Labs", "2017-2024", "Led firmware development for an industrial IoT gateway product line.")],
        [
            _project("Industrial IoT Gateway Platform", "A Zephyr RTOS platform aggregating factory sensor data for cloud upload.",
                      ["Zephyr RTOS", "MQTT"], ["Industrial protocols", "Edge aggregation"],
                      ["How the gateway handles intermittent connectivity", "Why Zephyr over a custom RTOS"]),
            _project("Predictive Maintenance Edge Pipeline", "An edge ML pipeline flagging equipment failures before they happen.",
                      ["C++", "TensorFlow Lite"], ["Edge machine learning"],
                      ["How the model was compressed to run on constrained hardware"]),
            _project("Multi-Protocol Gateway Bridge", "A bridge translating between several industrial sensor protocols.",
                      ["Zephyr RTOS"], ["Protocol translation"], []),
        ],
        [],
        "A senior embedded engineer who led firmware for an industrial IoT gateway product line.",
        [
            _topic("Handling intermittent factory-floor connectivity", "built a Zephyr RTOS platform aggregating factory sensor data for cloud upload", originating_project="Industrial IoT Gateway Platform"),
            _topic("Leading the gateway product line's firmware", "led firmware development for an industrial IoT gateway product line", originating_experience="Senior Embedded Engineer"),
            _topic("Bridging multiple industrial protocols", "built a bridge translating between several industrial sensor protocols", originating_project="Multi-Protocol Gateway Bridge"),
        ],
        ["Deep experience with industrial edge systems"],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Blockchain / Web3
# ═════════════════════════════════════════════════════════════════════════════

def _blockchain_junior() -> dict:
    return _profile(
        "Leilani Kahale", "Blockchain / Web3", "Junior",
        ["Solidity", "Hardhat", "Web3.js"],
        [_experience("Blockchain Intern", "ChainForge", "Summer 2024", "Built and tested smart contracts for an NFT marketplace.")],
        [
            _project("NFT Minting DApp", "A Solidity/Hardhat DApp letting users mint and trade NFTs.",
                      ["Solidity", "Hardhat"], ["Smart contract development", "Gas optimization"],
                      ["How gas costs were reduced in the minting function", "Why Hardhat over Truffle here"]),
            _project("Simple Token Wallet", "A Web3.js wallet UI for sending and receiving a custom ERC-20 token.",
                      ["Web3.js", "Solidity"], ["Token standards"], []),
            _project("Gas Fee Estimator Tool", "A Web3.js tool estimating gas fees accurately before a transaction.",
                      ["Web3.js"], ["Gas estimation"], []),
        ],
        [],
        "A junior blockchain engineer with Solidity smart contract experience.",
        [
            _topic("Reducing gas costs in a minting function", "built a Solidity/Hardhat DApp letting users mint and trade NFTs", originating_project="NFT Minting DApp"),
            _topic("Blockchain intern responsibilities", "built and tested smart contracts for an NFT marketplace", originating_experience="Blockchain Intern"),
            _topic("Estimating gas fees accurately", "built a Web3.js tool estimating gas fees accurately before a transaction", originating_project="Gas Fee Estimator Tool"),
        ],
        ["Comfortable with smart contract fundamentals"],
    )


def _blockchain_mid() -> dict:
    return _profile(
        "Kwame Asante", "Blockchain / Web3", "Intermediate",
        ["Solidity", "Truffle", "Ethereum"],
        [
            _experience("Blockchain Engineer", "ChainForge", "2022-2024", "Built a decentralized lending protocol handling millions in TVL."),
            _experience("Smart Contract Intern", "ChainForge", "Summer 2021", "Wrote test suites for early protocol prototypes."),
        ],
        [
            _project("Decentralized Lending Protocol", "A Solidity/Truffle protocol enabling collateralized crypto lending.",
                      ["Solidity", "Truffle", "Ethereum"], ["DeFi", "Collateralization"],
                      ["How liquidations are triggered safely", "Why an over-collateralization model was chosen"]),
            _project("On-Chain Governance Voting System", "A Solidity contract letting token holders vote on protocol changes.",
                      ["Solidity"], ["On-chain governance"], []),
            _project("Protocol Analytics Dashboard", "A dashboard tracking protocol usage and TVL on-chain.",
                      ["Solidity"], ["On-chain analytics"], []),
        ],
        [],
        "A blockchain engineer who built a DeFi lending protocol handling millions in TVL.",
        [
            _topic("Triggering liquidations safely", "built a Solidity/Truffle protocol enabling collateralized crypto lending", originating_project="Decentralized Lending Protocol"),
            _topic("Building a protocol handling millions in TVL", "built a decentralized lending protocol handling millions in TVL", originating_experience="Blockchain Engineer"),
            _topic("Tracking protocol usage on-chain", "built a dashboard tracking protocol usage and TVL on-chain", originating_project="Protocol Analytics Dashboard"),
        ],
        ["Strong grasp of DeFi protocol design"],
    )


def _blockchain_senior() -> dict:
    return _profile(
        "Renata Souza", "Blockchain / Web3", "Senior",
        ["Solidity", "Ethereum", "Slither"],
        [_experience("Senior Blockchain Engineer", "ChainForge", "2018-2024", "Led smart contract security audits across the company's protocol suite.")],
        [
            _project("Layer 2 Rollup Prototype", "An Ethereum layer-2 rollup prototype reducing transaction costs by 90%.",
                      ["Solidity", "Ethereum"], ["Layer 2 scaling", "Rollups"],
                      ["How the rollup ensures data availability", "Why an optimistic rollup over a zk-rollup here"]),
            _project("Smart Contract Security Audit Toolkit", "A Slither-based toolkit automating common vulnerability detection.",
                      ["Solidity", "Slither"], ["Smart contract security"],
                      ["How the toolkit catches reentrancy vulnerabilities"]),
            _project("Formal Verification Pipeline", "A pipeline formally verifying critical contract invariants before deployment.",
                      ["Solidity"], ["Formal verification"], []),
        ],
        ["Certified Blockchain Security Professional (CBSP)"],
        "A senior blockchain engineer specializing in smart contract security and layer-2 scaling.",
        [
            _topic("Ensuring data availability in a rollup", "built an Ethereum layer-2 rollup prototype reducing transaction costs by 90%", originating_project="Layer 2 Rollup Prototype"),
            _topic("Leading smart contract security audits", "led smart contract security audits across the company's protocol suite", originating_experience="Senior Blockchain Engineer"),
            _topic("Formally verifying critical contract invariants", "built a pipeline formally verifying critical contract invariants before deployment", originating_project="Formal Verification Pipeline"),
        ],
        ["Deep experience with smart contract security"],
    )


def all_experiment_profiles() -> tuple[dict, ...]:
    """All 36 curated profiles (12 domains x 3), independent of
    `experiment_candidate_profiles.py`'s original 5 -- this is the exact
    36-profile pool `run_third_experiment.py` draws from."""
    return (
        _backend_junior(), _backend_mid(), _backend_senior(),
        _frontend_junior(), _frontend_mid(), _frontend_senior(),
        _fullstack_junior(), _fullstack_mid(), _fullstack_senior(),
        _aiml_junior(), _aiml_mid(), _aiml_senior(),
        _dataeng_junior(), _dataeng_mid(), _dataeng_senior(),
        _cloud_junior(), _cloud_mid(), _cloud_senior(),
        _devops_junior(), _devops_mid(), _devops_senior(),
        _security_junior(), _security_mid(), _security_senior(),
        _mobile_junior(), _mobile_mid(), _mobile_senior(),
        _qa_junior(), _qa_mid(), _qa_senior(),
        _embedded_junior(), _embedded_mid(), _embedded_senior(),
        _blockchain_junior(), _blockchain_mid(), _blockchain_senior(),
    )
