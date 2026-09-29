"""Regression tests for the seed_v1 forensic-analysis grounding-validator
repair (dataset_filters.hallucinated_technologies).

Covers exactly the three cases the forensic analysis identified: a spelling-
variant alias false positive (postgres/postgresql), a considered-and-
rejected-alternative false positive, and the genuine contradiction that must
keep being caught (seed_v1_037's AWS/SageMaker vs. Airflow answer).
"""

from __future__ import annotations

from dataset_filters import hallucinated_technologies


# ── Alias false positives (seed_v1_010, _076, _084) ──────────────────────────

def test_postgres_alias_not_flagged_when_grounding_says_postgresql():
    answer = (
        "Postgres guarantees the payment provider will never be called twice, "
        "even across retries."
    )
    assert hallucinated_technologies(answer, ["Django", "Celery", "PostgreSQL"]) == []


def test_postgresql_alias_not_flagged_when_grounding_says_postgres():
    # Symmetric direction of the same alias group.
    answer = "PostgreSQL guarantees the write happens exactly once."
    assert hallucinated_technologies(answer, ["Postgres"]) == []


def test_nodejs_alias_not_flagged_when_grounding_says_node_js():
    answer = "The server is a nodejs process behind a load balancer."
    assert hallucinated_technologies(answer, ["React", "Node.js"]) == []


# ── Considered-and-rejected-alternative false positives (seed_v1_025, _075) ──

def test_rejected_alternative_named_with_alternatives_marker_not_flagged():
    answer = (
        "Alternatives like RabbitMQ are usually preferred when strict "
        "per-message ordering matters less than flexible routing."
    )
    assert hallucinated_technologies(answer, ["Kafka", "gRPC", "Kubernetes"]) == []


def test_rejected_alternative_named_with_looked_at_but_marker_not_flagged():
    answer = (
        "I looked at AWS Secrets Manager briefly but Vault won out mostly "
        "because it wasn't tied to one cloud provider."
    )
    assert hallucinated_technologies(answer, ["Vault", "AES-256", "TLS"]) == []


# ── Genuine contradiction must still be caught (seed_v1_037) ─────────────────

def test_genuine_grounding_contradiction_still_flagged():
    answer = (
        "I deployed the model as a SageMaker endpoint and used AWS Step "
        "Functions to orchestrate the daily scoring job, since our whole ML "
        "stack ran on SageMaker pipelines end to end. Airflow wasn't really "
        "part of this -- we moved off it before I joined the churn project."
    )
    hits = hallucinated_technologies(answer, ["scikit-learn", "XGBoost", "Airflow"])
    assert "aws" in hits


def test_technology_claimed_as_used_elsewhere_still_flagged_despite_one_rejected_mention():
    # A technology genuinely claimed as used MUST still be flagged even if a
    # separate, unrelated mention of the same term also appears near a
    # rejection marker -- suppression requires EVERY occurrence to be
    # rejection-context, not just one.
    answer = (
        "We use AWS for the primary deployment. Separately, some alternatives "
        "to AWS were discussed early on but never adopted."
    )
    hits = hallucinated_technologies(answer, ["Vault", "AES-256", "TLS"])
    assert "aws" in hits
