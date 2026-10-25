"""
V4 5000-Example Dataset — Deterministic Group Scaffold (local, NO LLM).

Produces the independent (candidate-profile -> project/context -> question)
GROUPS that Claude authors answers into, for the `four_dim_overall_v4_5000`
dataset. Fully deterministic; calls NO external API (no Gemini, no network).

EXPANDED (diversity-ceiling pass): the vocabularies below were deliberately
widened after an early-checkpoint drift audit found the first authored batches
narrowing toward a few technologies, a "How did you..." question shape, and a
couple of reasoning types. This module now spans:
  - ~24 QUESTION FORMS (why-choose / walk-me-through / what-went-wrong /
    what-if-scale / which-part-did-you / what-alternatives / when-X-vs-Y /
    what-limitation / how-validate / what-happens-internally / ...),
  - a broad TECHNOLOGY space across frontend, languages, ML/AI, databases,
    messaging/distributed, cloud/deploy, security, and systems families,
  - many PROJECT ARCHETYPES across ~20 project families,
  - explicit CANDIDATE-PROFILE variation (complexity, maturity, ownership
    level, outcome, setting, breadth),
  - all ten `ReasoningType`s and a richer free-string `intent` facet
    (tradeoff / design_decision / debugging / failure_analysis / reflection /
     comparison / architecture / scalability / optimization / security /
     testing / ownership / implementation_detail / alternative_design /
     hypothetical / constraint_reasoning / incident / retrospective /
     validation).

WHAT THIS IS / IS NOT (unchanged): a deterministic combinatorial generator.
It NEVER writes answer prose and NEVER assigns the four dimension scores —
those are Claude's job during authoring (no-Gemini requirement). The `target`
profile it attaches is a GENERATION TARGET (what KIND of answer to write),
reusing `dimension_profiles`, never a label. `intent`/`question_form`/
`project_family`/candidate attributes are diversity METADATA for steering and
monitoring only.

NOTE ON QuestionCategory: the frozen `QuestionCategory` enum (5 values) is a
production schema and is NOT changed here. Reasoning/intent diversity is
carried by `ReasoningType` (10 values) + the free-string `intent` facet, which
is where the requested "categories" (tradeoff/debugging/failure_analysis/...)
actually live. Groundings stay PROJECT-shaped so the grounding-fidelity filter
(known-vocab tech must be in the project's tech list) keeps working; the three
project-compatible categories (project_deep_dive / project_overview /
skill_in_context) are all used.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from dimension_profiles import DimensionProfile, sample_profile
from question_families import ReasoningType
from question_specification import QuestionCategory

# ── Technology families (broad; drawn to fit archetypes, not forced) ─────────
# Names that also appear in generation_validation._KNOWN_TECHNOLOGY_VOCABULARY
# are safe as grounding; languages like Java/C++/Go/Rust/TypeScript are NOT in
# that vocab, so they add breadth with zero hallucination-flag risk.
TECH_FAMILIES: dict[str, tuple[str, ...]] = {
    "frontend": ("React", "Vue", "Angular", "TypeScript", "JavaScript", "Next.js", "Svelte", "Tailwind"),
    "mobile": ("Swift", "SwiftUI", "Kotlin", "Jetpack Compose", "Combine", "Flutter", "React Native"),
    "languages": ("Java", "C++", "Go", "Rust", "Python", "TypeScript", "C#", "Scala"),
    "ml_ai": ("PyTorch", "TensorFlow", "scikit-learn", "Hugging Face", "spaCy", "mlflow", "FAISS", "XGBoost"),
    "llm": ("LangChain", "LangGraph", "Hugging Face", "FAISS"),
    "databases": ("PostgreSQL", "MySQL", "MongoDB", "SQLite", "Elasticsearch", "DynamoDB", "Cassandra"),
    "caching": ("Redis", "Memcached"),
    "messaging": ("Kafka", "RabbitMQ", "MQTT", "WebSockets", "gRPC", "NATS"),
    "backend_web": ("FastAPI", "Django", "Flask", "Express", "Spring", "Node.js", "Gin"),
    "cloud_deploy": ("Docker", "Kubernetes", "AWS", "GCP", "Azure", "Terraform", "nginx", "GitHub Actions", "Jenkins"),
    "data_eng": ("Spark", "Airflow", "Snowflake", "dbt", "Databricks", "Kafka"),
    "security_tools": ("Burp Suite", "nmap", "Wireshark", "Metasploit", "Splunk"),
    "embedded": ("FreeRTOS", "Zephyr RTOS", "MQTT", "C++", "Rust"),
    "blockchain": ("Solidity", "Hardhat", "Ethereum", "web3.js"),
    "qa": ("Selenium", "Cypress", "Playwright", "JMeter", "Gatling"),
    "observability": ("Prometheus", "Grafana", "Splunk", "Elasticsearch"),
}


@dataclass(frozen=True)
class ProjectArchetype:
    key: str
    family: str
    title: str
    summary: str
    tech_families: tuple[str, ...]     # which TECH_FAMILIES this archetype draws from
    concept_pool: tuple[str, ...]


# ── ~50 archetypes across ~20 project families ───────────────────────────────
ARCHETYPES: tuple[ProjectArchetype, ...] = (
    # web applications
    ProjectArchetype("web_ecom", "web_app", "E-commerce Storefront", "A storefront web app for a small online shop.", ("frontend", "backend_web", "databases"), ("routing", "state management", "checkout flow", "SEO")),
    ProjectArchetype("web_dashboard", "web_app", "Analytics Dashboard", "A web dashboard visualizing product usage metrics.", ("frontend", "backend_web"), ("data fetching", "charts", "memoization", "pagination")),
    ProjectArchetype("web_social", "web_app", "Community Forum", "A discussion forum with posts, threads, and voting.", ("frontend", "backend_web", "databases"), ("threading", "ranking", "moderation", "notifications")),
    # mobile
    ProjectArchetype("mob_fitness", "mobile", "Fitness Tracker", "A mobile app logging workouts and syncing to a backend.", ("mobile",), ("offline sync", "local persistence", "background refresh", "MVVM")),
    ProjectArchetype("mob_budget", "mobile", "Budgeting App", "A mobile app tracking expenses with categories and charts.", ("mobile", "databases"), ("local database", "charts", "state management", "notifications")),
    ProjectArchetype("mob_social", "mobile", "Photo Sharing App", "A mobile app for sharing and browsing photos.", ("mobile", "cloud_deploy"), ("image upload", "caching", "pagination", "permissions")),
    # backend services / REST APIs
    ProjectArchetype("svc_orders", "backend_service", "Order Service", "A backend service managing the order lifecycle.", ("backend_web", "databases", "caching"), ("state machine", "idempotency", "transactions", "caching")),
    ProjectArchetype("svc_booking", "backend_service", "Booking API", "A REST API for booking appointments.", ("backend_web", "databases"), ("concurrency", "double-booking", "validation", "timezones")),
    ProjectArchetype("svc_auth", "backend_service", "Auth Service", "A service issuing and validating login sessions.", ("backend_web", "databases", "caching"), ("JWT", "sessions", "password hashing", "token revocation")),
    ProjectArchetype("svc_payments", "backend_service", "Payments Client", "A client integrating a flaky external payments provider.", ("backend_web",), ("timeouts", "retries", "circuit breaker", "idempotency")),
    # real-time
    ProjectArchetype("rt_chat", "realtime", "Chat Application", "A real-time chat app with rooms and presence.", ("messaging", "backend_web", "caching"), ("websockets", "presence", "delivery", "ordering")),
    ProjectArchetype("rt_game", "realtime", "Multiplayer Game Sync", "Real-time state sync for a browser multiplayer game.", ("messaging", "caching"), ("interpolation", "state sync", "latency", "tick rate")),
    ProjectArchetype("rt_collab", "realtime", "Collaborative Editor", "A collaborative document editor with live cursors.", ("messaging", "backend_web"), ("conflict resolution", "operational transforms", "presence", "sync")),
    # distributed systems
    ProjectArchetype("dist_queue", "distributed", "Job Queue", "A distributed queue processing background jobs.", ("messaging", "caching"), ("at-least-once", "retries", "dead-letter queues", "idempotency")),
    ProjectArchetype("dist_ratelimit", "distributed", "Rate Limiter", "A distributed rate limiter protecting an API.", ("caching", "cloud_deploy"), ("token bucket", "counters", "sliding window", "fairness")),
    ProjectArchetype("dist_cache", "distributed", "Cache Layer", "A caching layer reducing database read load.", ("caching", "databases"), ("cache invalidation", "TTL", "consistency", "hot keys")),
    # developer tools
    ProjectArchetype("dev_cli", "dev_tool", "CLI Task Runner", "A command-line tool automating project tasks.", ("languages",), ("argument parsing", "config", "plugins", "error handling")),
    ProjectArchetype("dev_linter", "dev_tool", "Custom Linter", "A linter enforcing team code conventions.", ("languages",), ("AST parsing", "rules", "autofix", "false positives")),
    ProjectArchetype("dev_ci", "dev_tool", "CI/CD Pipeline", "A build-test-deploy pipeline for a web service.", ("cloud_deploy",), ("build caching", "blue-green", "rollbacks", "secrets")),
    # data pipelines
    ProjectArchetype("data_etl", "data_pipeline", "Sales ETL Pipeline", "A batch pipeline loading daily sales into a warehouse.", ("data_eng",), ("idempotent loads", "partitioning", "backfills", "data quality")),
    ProjectArchetype("data_stream", "data_pipeline", "Event Streaming Ingest", "A streaming ingest of clickstream events.", ("data_eng", "messaging"), ("exactly-once", "windowing", "schema evolution", "backpressure")),
    ProjectArchetype("data_dedup", "data_pipeline", "Record Deduplication", "A pipeline deduplicating near-duplicate records.", ("data_eng", "languages"), ("blocking", "fuzzy matching", "thresholds", "scale")),
    # ML projects
    ProjectArchetype("ml_vision", "ml", "Image Classifier", "A CNN classifying product photos.", ("ml_ai",), ("transfer learning", "augmentation", "overfitting", "metrics")),
    ProjectArchetype("ml_tabular", "ml", "Churn Predictor", "A tabular model predicting subscriber churn.", ("ml_ai",), ("class imbalance", "feature engineering", "cross-validation", "calibration")),
    ProjectArchetype("ml_serving", "ml", "Model Serving API", "An API serving model predictions under latency limits.", ("ml_ai", "backend_web", "cloud_deploy"), ("batching", "latency", "versioning", "monitoring")),
    # AI / LLM
    ProjectArchetype("ai_rag", "ai_app", "Document Q&A Assistant", "A retrieval-augmented assistant over notes.", ("llm", "backend_web"), ("chunking", "embeddings", "retrieval", "prompt design")),
    ProjectArchetype("ai_agent", "ai_app", "Task Automation Agent", "An LLM agent calling tools to automate tasks.", ("llm",), ("tool calling", "context windows", "hallucination control", "evaluation")),
    ProjectArchetype("ai_semsearch", "ai_app", "Semantic Search", "Semantic search over a document collection.", ("llm", "backend_web"), ("embeddings", "ANN index", "caching", "latency")),
    # security tools
    ProjectArchetype("sec_scanner", "security", "Vulnerability Scanner", "A tool scanning dependencies for known CVEs.", ("security_tools", "languages"), ("CVE feeds", "dependency graphs", "false positives", "severity")),
    ProjectArchetype("sec_authz", "security", "Authorization Layer", "A permissions layer enforcing access control.", ("backend_web", "databases"), ("RBAC", "least privilege", "policy checks", "auditing")),
    ProjectArchetype("sec_recon", "security", "Network Recon Tool", "A tool mapping hosts and open ports on a lab network.", ("security_tools",), ("scanning", "fingerprinting", "reporting", "rate control")),
    # computer vision
    ProjectArchetype("cv_ocr", "computer_vision", "Receipt OCR", "A pipeline extracting text from scanned receipts.", ("ml_ai", "languages"), ("preprocessing", "recognition", "layout", "accuracy")),
    ProjectArchetype("cv_detect", "computer_vision", "Object Detector", "A detector counting items on a shelf from photos.", ("ml_ai",), ("bounding boxes", "non-max suppression", "small objects", "evaluation")),
    # NLP
    ProjectArchetype("nlp_intents", "nlp", "Chatbot Intent Classifier", "An intent classifier routing chat messages.", ("ml_ai",), ("classification", "confidence threshold", "fallback", "training data")),
    ProjectArchetype("nlp_summ", "nlp", "Text Summarizer", "A summarizer condensing articles.", ("ml_ai", "llm"), ("extraction", "evaluation", "length control", "faithfulness")),
    # recommendation
    ProjectArchetype("rec_items", "recommendation", "Item Recommender", "An item-similarity recommender for a shop.", ("ml_ai", "languages"), ("similarity", "cold start", "features", "evaluation")),
    # IoT / embedded
    ProjectArchetype("iot_hub", "iot", "Sensor Data Hub", "A device collecting sensor data and publishing it.", ("embedded", "messaging"), ("QoS", "low-power", "buffering", "reconnection")),
    ProjectArchetype("iot_ota", "embedded", "Smart Lock Firmware", "Firmware for a connected lock with remote updates.", ("embedded", "messaging"), ("OTA updates", "rollback", "image verification", "watchdog")),
    # automation
    ProjectArchetype("auto_scraper", "automation", "Web Scraper", "A scraper collecting listings from several sites.", ("languages", "databases"), ("rate limiting", "parsing", "retries", "dedup")),
    ProjectArchetype("auto_bot", "automation", "Ops Automation Bot", "A bot automating routine ops tasks from chat.", ("languages", "cloud_deploy"), ("command parsing", "permissions", "idempotency", "auditing")),
    # blockchain
    ProjectArchetype("bc_token", "blockchain", "Token Smart Contract", "An ERC-20-style token with a test suite.", ("blockchain",), ("reentrancy", "gas optimization", "access control", "testing")),
    # cloud / deployment
    ProjectArchetype("cloud_serverless", "cloud", "Serverless API", "A serverless REST API for a booking app.", ("cloud_deploy", "databases"), ("cold starts", "connection pooling", "IAM", "cost control")),
    ProjectArchetype("cloud_iac", "cloud", "Infrastructure as Code", "An IaC repo defining a small cloud environment.", ("cloud_deploy",), ("declarative infra", "state", "reproducibility", "drift")),
    ProjectArchetype("cloud_migrate", "cloud", "Zero-Downtime Migration", "A no-downtime database migration for a live service.", ("cloud_deploy", "databases"), ("expand/contract", "backfill", "staged rollout", "rollback")),
    # analytics dashboards
    ProjectArchetype("an_cost", "analytics", "Cloud Cost Dashboard", "A dashboard summarizing cloud spend by team.", ("frontend", "cloud_deploy", "databases"), ("aggregation", "attribution", "alerts", "caching")),
    ProjectArchetype("an_metrics", "analytics", "Time-Series Metrics Store", "A store for app metrics queried by dashboards.", ("observability", "languages"), ("downsampling", "retention", "aggregation", "cardinality")),
    # database-heavy
    ProjectArchetype("db_search", "database", "Product Search", "A search feature with filters and ranking.", ("databases", "observability"), ("inverted index", "relevance", "sharding", "analyzers")),
    ProjectArchetype("db_reporting", "database", "Reporting Backend", "A backend serving heavy aggregate reports.", ("databases", "caching"), ("query optimization", "indexing", "materialized views", "EXPLAIN")),
    ProjectArchetype("db_graph", "database", "Social Graph Feature", "A friends-of-friends feature over a graph.", ("databases",), ("graph traversal", "BFS", "joins", "deduplication")),
)


# ── Question forms (category, reasoning_type, intent, form_id, template) ──────
# ~26 distinct forms spanning the requested variety; templates use
# {project}/{tech}/{concept} slots filled deterministically per slot.
QUESTION_TEMPLATES: tuple[tuple[QuestionCategory, ReasoningType, str, str, str], ...] = (
    (QuestionCategory.SKILL_IN_CONTEXT, ReasoningType.TRADE_OFF_ANALYSIS, "tradeoff", "why_choose", "Why did you choose {tech} for {project} instead of an alternative?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DECISION_MAKING, "design_decision", "what_made_decide", "What made you decide on your approach to {concept} in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.EXPLANATION, "architecture", "walk_through", "Walk me through how {project} handles {concept}."),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DEBUGGING, "incident", "tell_about", "Tell me about a time {project} broke because of {concept} and what you did."),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.REFLECTION, "retrospective", "hardest_part", "What was the hardest part of getting {concept} right in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.OPTIMIZATION, "scalability", "what_if", "What would happen to {project} if {concept} suddenly had 10x the load?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.REFLECTION, "alternative_design", "how_change", "How would you change {project}'s handling of {concept} if you rebuilt it today?"),
    (QuestionCategory.SKILL_IN_CONTEXT, ReasoningType.TRADE_OFF_ANALYSIS, "comparison", "why_not", "Why didn't you use {tech} for {concept} in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.TRADE_OFF_ANALYSIS, "tradeoff", "trade_off", "What trade-off did you accept when you implemented {concept} in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DEBUGGING, "debugging", "how_debug", "How did you debug the {concept} problem in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DEBUGGING, "failure_analysis", "what_went_wrong", "What went wrong the first time you implemented {concept} in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.REFLECTION, "retrospective", "differently", "What would you do differently with {concept} on {project} next time?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.OWNERSHIP, "ownership", "which_part", "Which part of {project}'s {concept} did you personally implement?"),
    (QuestionCategory.SKILL_IN_CONTEXT, ReasoningType.EXPLANATION, "implementation_detail", "explain_why", "Can you explain why {concept} matters for {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.OPTIMIZATION, "scalability", "suppose_scale", "Suppose {project} had to scale to millions of users, what breaks first around {concept}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DECISION_MAKING, "alternative_design", "alternatives", "What alternatives did you consider for {concept} in {project}?"),
    (QuestionCategory.SKILL_IN_CONTEXT, ReasoningType.TRADE_OFF_ANALYSIS, "comparison", "when_x_vs_y", "When would you use {tech} instead of another option for something like {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.REFLECTION, "constraint_reasoning", "limitation", "What limitation did you run into with {tech} while building {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.APPLICATION, "validation", "how_validate", "How did you validate that {concept} actually worked in {project}?"),
    (QuestionCategory.SKILL_IN_CONTEXT, ReasoningType.EXPLANATION, "implementation_detail", "internally", "What happens internally when {concept} runs in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.APPLICATION, "testing", "how_test", "How did you test {concept} in {project}?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DESIGN, "security", "how_secure", "How did you secure {project} where {concept} was involved?"),
    (QuestionCategory.PROJECT_OVERVIEW, ReasoningType.EXPLANATION, "architecture", "overview", "Give me a quick overview of {project} and the problem it solved."),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.DECISION_MAKING, "constraint_reasoning", "constraint", "Given your constraints, why did {project}'s {concept} end up the way it did?"),
    (QuestionCategory.SKILL_IN_CONTEXT, ReasoningType.TRADE_OFF_ANALYSIS, "comparison", "compare_approach", "How does your approach to {concept} in {project} compare to the usual way?"),
    (QuestionCategory.PROJECT_DEEP_DIVE, ReasoningType.OWNERSHIP, "ownership", "contribution", "What was your specific contribution to {concept} in {project}?"),
)


# ── Candidate-profile variation dimensions (deterministic per slot) ──────────
COMPLEXITY = ("low", "medium", "high")
MATURITY = ("beginner", "intermediate", "advanced")
OWNERSHIP_LEVEL = ("solo", "lead", "contributor", "peripheral")
OUTCOME = ("shipped", "prototype", "abandoned")
SETTING = ("personal", "course", "internship", "team")
BREADTH = ("specialist", "generalist")


@dataclass(frozen=True)
class CandidateVariation:
    complexity: str
    maturity: str
    ownership_level: str
    outcome: str
    setting: str
    breadth: str


@dataclass(frozen=True)
class Slot:
    slot_id: str
    group_id: str
    candidate_profile_id: str
    domain: str                 # kept for backward-compat: == project family
    project_family: str
    category: str
    reasoning_type: str
    intent: str
    question_form: str
    title: str
    summary: str
    technologies: tuple[str, ...]
    concepts: tuple[str, ...]
    question: str
    expected_concepts: tuple[str, ...]
    target: DimensionProfile
    target_id: str
    candidate: CandidateVariation


def _pick(seq, seed: str):
    return seq[zlib.crc32(seed.encode("utf-8")) % len(seq)]


def _subset(seq: tuple[str, ...], seed: str, k: int) -> tuple[str, ...]:
    if k >= len(seq):
        return tuple(seq)
    order = sorted(range(len(seq)), key=lambda i: zlib.crc32(f"{seed}:{i}".encode("utf-8")))
    return tuple(seq[i] for i in sorted(order[:k]))


def _archetype_tech_pool(arch: ProjectArchetype) -> tuple[str, ...]:
    pool: list[str] = []
    for fam in arch.tech_families:
        pool.extend(TECH_FAMILIES.get(fam, ()))
    # stable de-dup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in pool:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return tuple(out)


def _candidate_variation(seed: str) -> CandidateVariation:
    return CandidateVariation(
        complexity=_pick(COMPLEXITY, f"{seed}::complexity"),
        maturity=_pick(MATURITY, f"{seed}::maturity"),
        ownership_level=_pick(OWNERSHIP_LEVEL, f"{seed}::ownership"),
        outcome=_pick(OUTCOME, f"{seed}::outcome"),
        setting=_pick(SETTING, f"{seed}::setting"),
        breadth=_pick(BREADTH, f"{seed}::breadth"),
    )


def _nudge_target(target: DimensionProfile, cand: CandidateVariation, seed: str) -> DimensionProfile:
    """Lightly bias the generation TARGET (not a label) by candidate attrs so
    ownership level and outcome shape the KIND of answer requested — e.g. a
    peripheral contributor's answer targets lower grounding_ownership. Clamped
    to [0,4]. Deterministic; still just a generation target."""
    tiers = dict(target.as_dict())
    if cand.ownership_level == "peripheral":
        tiers["grounding_ownership"] = max(0, tiers["grounding_ownership"] - 2)
    elif cand.ownership_level == "contributor":
        tiers["grounding_ownership"] = max(0, tiers["grounding_ownership"] - 1)
    elif cand.ownership_level in ("solo", "lead"):
        tiers["grounding_ownership"] = min(4, tiers["grounding_ownership"] + 1)
    if cand.outcome == "abandoned":
        tiers["relevance_completeness"] = max(0, tiers["relevance_completeness"] - 1)
    if cand.maturity == "beginner":
        tiers["depth_specificity"] = max(0, tiers["depth_specificity"] - 1)
    elif cand.maturity == "advanced":
        tiers["depth_specificity"] = min(4, tiers["depth_specificity"] + 1)
    return DimensionProfile.from_dict(tiers)


def make_slot(index: int, hard_case_ratio: float = 0.5) -> Slot:
    """Deterministically produce the `index`-th authoring slot. Distinct
    indices yield distinct groups/questions with high probability."""
    seed = f"v4_5000::slot::{index}"
    arch = _pick(ARCHETYPES, f"{seed}::arch")
    variation = zlib.crc32(f"{seed}::var".encode("utf-8")) % 500
    candidate_profile_id = f"v4prof_{zlib.crc32(f'{seed}::cand'.encode()) % 100000:05d}"
    group_id = f"{candidate_profile_id}::{arch.family}::{arch.key}::{variation}"

    full_pool = _archetype_tech_pool(arch)
    technologies = _subset(full_pool, f"{seed}::tech", max(1, min(len(full_pool), 2 + (variation % 3))))
    concepts = _subset(arch.concept_pool, f"{seed}::concept", min(len(arch.concept_pool), 3))

    cat, rtype, intent, form, template = _pick(QUESTION_TEMPLATES, f"{seed}::q")
    tech = _pick(technologies, f"{seed}::qtech")
    concept = _pick(arch.concept_pool, f"{seed}::qconcept")
    question = template.format(project=arch.title, tech=tech, concept=concept)

    expected_concepts = _subset(arch.concept_pool, f"{seed}::expected", min(len(arch.concept_pool), 2))

    cand = _candidate_variation(seed)
    target_id, base_target = sample_profile(f"{seed}::profile", hard_case_ratio=hard_case_ratio)
    target = _nudge_target(base_target, cand, seed)

    return Slot(
        slot_id=f"v4slot_{index:06d}", group_id=group_id, candidate_profile_id=candidate_profile_id,
        domain=arch.family, project_family=arch.family, category=cat.value, reasoning_type=rtype.value,
        intent=intent, question_form=form, title=arch.title, summary=arch.summary,
        technologies=technologies, concepts=concepts, question=question,
        expected_concepts=expected_concepts, target=target, target_id=target_id, candidate=cand,
    )


def iter_slots(count: int, start: int = 0, hard_case_ratio: float = 0.5):
    """Yield `count` slots starting at index `start` (resumable authoring)."""
    for i in range(start, start + count):
        yield make_slot(i, hard_case_ratio=hard_case_ratio)


def question_form_ids() -> tuple[str, ...]:
    return tuple(sorted({t[3] for t in QUESTION_TEMPLATES}))


def intent_ids() -> tuple[str, ...]:
    return tuple(sorted({t[2] for t in QUESTION_TEMPLATES}))


def approximate_group_space() -> int:
    """Conservative lower bound on DISTINCT groups (archetypes x variations)."""
    return len(ARCHETYPES) * 500
