"""
Technical-concept gazetteer — Milestone 3 (Entity Parsing). See
docs/architecture/ResumeIntelligenceEngine.md Section 4.4.

Used by `ProjectParser` to filter KeyBERT-proposed keyphrases down to
concepts worth surfacing (bounded, deterministic given fixed model weights
-- KeyBERT proposes candidates, this gazetteer decides which ones count).
A plain data file, matching `section_gazetteer.py`'s precedent.
"""

from __future__ import annotations

CONCEPTS: tuple[str, ...] = (
    "Caching", "Microservices", "Monolith", "Event-Driven Architecture",
    "Message Queue", "Pub/Sub", "Load Balancing", "Rate Limiting",
    "Authentication", "Authorization", "OAuth", "Single Sign-On",
    "Distributed Systems", "Distributed Tracing", "Consensus",
    "Horizontal Scaling", "Vertical Scaling", "Auto Scaling",
    "CI/CD", "Continuous Integration", "Continuous Deployment",
    "Unit Testing", "Integration Testing", "Test-Driven Development",
    "RAG", "Retrieval-Augmented Generation", "Embeddings", "Vector Search",
    "Machine Learning", "Deep Learning", "Natural Language Processing",
    "Computer Vision", "Recommendation System", "A/B Testing",
    "REST API", "GraphQL API", "Webhooks", "API Gateway",
    "Database Sharding", "Database Replication", "Indexing", "Query Optimization",
    "Data Pipeline", "ETL", "Batch Processing", "Stream Processing",
    "Infrastructure as Code", "Containerization", "Orchestration",
    "Serverless", "Multi-Tenancy", "Feature Flags", "Observability",
    "Logging", "Monitoring", "Alerting", "Incident Response",
    "Encryption", "Data Privacy", "Accessibility", "Responsive Design",
    "Real-Time Updates", "WebSockets", "State Management",
)
