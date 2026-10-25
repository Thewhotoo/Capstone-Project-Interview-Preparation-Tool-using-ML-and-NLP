"""
Builder for the v5_short_quality_calibration_80 dataset — a SEPARATE, isolated
80-example calibration set targeting the length/quality confound found in the
audited four_dim_overall_v4_5000 (1003-example) dataset (word-count <-> overall
tier Pearson r = 0.720).

Read-only w.r.t. the frozen 1003 dataset and the V4 diagnostic set: this script
never opens either for writing, and writes only under
artifacts/v5_short_quality_calibration_80/.

No Gemini / external LLM API anywhere in this file. All 80 examples are
authored inline as plain Python data below (Claude-authored, deterministic,
reproducible). Schema reuses TrainingExample verbatim (training_example.py);
scoring reuses the existing tier scale (evaluation_dimensions.score buckets,
four canonical dimensions, equal-weight-mean overall policy already used by
four_dim_experiment_split.py / overall_dataset.py) rather than inventing a new
scheme.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from evaluation_dimensions import tier_label
from evaluation_result import ConceptObservationStatus  # noqa: F401 (schema import parity)
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from training_example import (
    ContradictionLabel,
    DimensionLabel,
    OverallLabel,
    ProvenanceSource,
    QualityTier,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
    TrainingExampleSyntheticMeta,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_VERSION = "v5_short_quality_calibration_80"
OUT_DIR = os.path.join(_HERE, "artifacts", DATASET_VERSION)
DATASET_DIR = os.path.join(OUT_DIR, "dataset")
REPORTS_DIR = os.path.join(OUT_DIR, "reports")

CREATED_AT = "2026-09-20T00:00:00+00:00"
BATCH_ID = "v5_short_quality_calibration"
_MAX_TIER = 4.0

_TIER_TO_QUALITY = {
    0: QualityTier.POOR,
    1: QualityTier.WEAK,
    2: QualityTier.ADEQUATE,
    3: QualityTier.GOOD,
    4: QualityTier.EXCELLENT,
}


def _overall_score_to_tier(score: float) -> int:
    """Byte-identical cutpoints to model_dataset.score_to_tier /
    overall_dataset.overall_score_to_tier (0.80/0.60/0.40/0.25), duplicated
    locally so this authoring script has zero import dependency on the model
    training stack (same "deliberate independence" precedent used elsewhere
    in this codebase)."""
    if score >= 0.80:
        return 4
    if score >= 0.60:
        return 3
    if score >= 0.40:
        return 2
    if score >= 0.25:
        return 1
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# Example authoring data
# ═══════════════════════════════════════════════════════════════════════════
# Each row: (
#   slug, category_num, length_bucket, question, project_title, project_summary,
#   technologies, concepts, answer, (tc, ds, rc, go) tiers 0-4, reasoning_type,
#   expected_concepts,
# )

ROWS: list[tuple] = [
    # ── Category 1: short + strong (15) ──────────────────────────────────
    ("redis_cache_strong", 1, "short",
     "Why did you add a Redis cache in front of the product catalog service?",
     "Catalog Service", "Product catalog read service for an e-commerce backend.",
     ["Redis", "PostgreSQL"], ["caching", "TTL", "cache invalidation"],
     "The catalog reads outnumbered writes by roughly 50 to 1, so I put Redis in front with a short TTL and invalidated the key on any product update.",
     (4, 3, 4, 3), "trade_off_analysis", ["read/write ratio", "cache invalidation"]),

    ("kafka_pipeline_strong", 1, "short",
     "Why did you choose Kafka for the event pipeline instead of a simpler queue?",
     "Order Events Pipeline", "Event pipeline distributing order lifecycle events to multiple consumers.",
     ["Kafka", "RabbitMQ"], ["event streaming", "consumer replay"],
     "We needed multiple independent consumers replaying the same order events at their own pace, and Kafka's retained log gives us that without duplicating the events per consumer.",
     (4, 4, 4, 3), "trade_off_analysis", ["multiple consumers", "log retention"]),

    ("composite_index_strong", 1, "short",
     "Why did you add a composite index on (user_id, created_at) for the orders table?",
     "Orders API", "Order history API backed by PostgreSQL.",
     ["PostgreSQL"], ["indexing", "query planning"],
     "Almost every query filtered by user_id and sorted by created_at, so a composite index on both let Postgres satisfy the filter and the sort in one index scan.",
     (4, 4, 4, 3), "trade_off_analysis", ["composite index", "index scan"]),

    ("grpc_strong", 1, "short",
     "Why did you use gRPC for the internal service-to-service calls instead of REST?",
     "Internal Services Mesh", "Internal microservices communicating over gRPC.",
     ["gRPC", "REST", "Docker"], ["protobuf", "HTTP/2"],
     "These calls happen thousands of times a second between internal services, and gRPC's binary protobuf framing over HTTP/2 cut serialization overhead and let us reuse connections.",
     (4, 3, 4, 3), "trade_off_analysis", ["serialization overhead", "connection reuse"]),

    ("docker_multistage_strong", 1, "short",
     "Why did you switch the build to a multi-stage Dockerfile?",
     "Deployment Pipeline", "CI/CD build pipeline producing container images.",
     ["Docker"], ["image size", "build stages"],
     "The old image shipped the whole build toolchain, so I split it into a build stage and a slim runtime stage, cutting the final image from 1.2GB to under 200MB.",
     (4, 4, 4, 4), "trade_off_analysis", ["build stage", "runtime stage"]),

    ("hpa_strong", 1, "short",
     "Why did you configure horizontal pod autoscaling on the API deployment?",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker"], ["autoscaling", "CPU utilization"],
     "Traffic spikes 5x during business hours, so I set HPA to scale on CPU utilization above 70%, keeping us within capacity without paying for peak-sized pods all day.",
     (4, 3, 4, 3), "trade_off_analysis", ["autoscaling trigger", "cost efficiency"]),

    ("jwt_strong", 1, "short",
     "Why did you use short-lived JWTs with refresh tokens instead of long-lived sessions?",
     "Auth Service", "Authentication service issuing tokens for the web app.",
     ["JWT"], ["token expiry", "refresh tokens"],
     "A stolen long-lived token stays valid until it expires, so I set access tokens to expire in 15 minutes and used a rotating refresh token to limit that window.",
     (4, 3, 4, 3), "trade_off_analysis", ["token lifetime", "exposure window"]),

    ("row_lock_strong", 1, "short",
     "Why did you add a row-level lock around the inventory decrement?",
     "Inventory Service", "Inventory tracking service for checkout.",
     ["PostgreSQL"], ["concurrency", "row locking"],
     "Two concurrent checkouts could both read the same stock count and both succeed, overselling the item, so I wrapped the read-decrement in a SELECT FOR UPDATE.",
     (4, 4, 4, 3), "debugging", ["race condition", "SELECT FOR UPDATE"]),

    ("n_plus_1_strong", 1, "short",
     "What caused the dashboard endpoint to slow down under load, and how did you fix it?",
     "Analytics Dashboard", "Internal dashboard aggregating owner data per row.",
     ["PostgreSQL"], ["N+1 queries", "joins"],
     "Each dashboard row was triggering a separate query for its owner, an N+1 pattern, so I switched to a single join and the endpoint's p95 dropped from 900ms to 80ms.",
     (4, 4, 4, 4), "debugging", ["N+1 query pattern", "join"]),

    ("rabbitmq_strong", 1, "short",
     "Why did you pick RabbitMQ for the notification service instead of Kafka?",
     "Notification Service", "Per-user notification delivery service.",
     ["RabbitMQ", "Kafka"], ["routing keys", "exchanges"],
     "Notifications are short-lived, low-volume, and need per-message routing by user tier, so RabbitMQ's exchange/routing-key model fit better than Kafka's log-partition model for this case.",
     (4, 4, 4, 3), "trade_off_analysis", ["routing by tier", "message volume"]),

    ("grad_accum_strong", 1, "short",
     "Why did you use gradient accumulation when training the ranking model?",
     "Ranking Model", "Learning-to-rank model trained on GPU.",
     ["PyTorch"], ["gradient accumulation", "batch size"],
     "The batch size that fit in GPU memory was too small to give a stable gradient estimate, so I accumulated gradients over 4 steps before each optimizer update.",
     (4, 3, 4, 3), "trade_off_analysis", ["GPU memory limit", "effective batch size"]),

    ("react_context_strong", 1, "short",
     "Why did you move the cart state into a context provider instead of prop drilling?",
     "Storefront Frontend", "React storefront with a shared shopping cart.",
     ["React"], ["state management", "context API"],
     "The cart count needed to update in the header, the product page, and the checkout button, and passing it through five layers of props got unmanageable, so I lifted it into context.",
     (4, 3, 4, 3), "trade_off_analysis", ["prop drilling", "shared state"]),

    ("pytorch_tf_strong", 1, "short",
     "Why did you pick PyTorch over TensorFlow for this project?",
     "Ranking Model", "Learning-to-rank model trained on GPU.",
     ["PyTorch", "TensorFlow"], ["eager execution", "debugging"],
     "The team needed to debug custom loss functions interactively, and PyTorch's eager execution let us step through the forward pass in a normal debugger instead of a graph.",
     (4, 3, 4, 3), "trade_off_analysis", ["eager execution", "custom loss debugging"]),

    ("raii_strong", 1, "short",
     "Why did you wrap the socket handle in a RAII class?",
     "Network Client Library", "C++ client library managing raw socket handles.",
     ["C++"], ["RAII", "resource cleanup"],
     "A raw handle leaked on early-return error paths, so I wrapped it in a class that closes the socket in its destructor, guaranteeing cleanup regardless of how the function exits.",
     (4, 4, 4, 3), "debugging", ["resource leak", "destructor cleanup"]),

    ("rate_limiter_strong", 1, "short",
     "Why did you implement the rate limiter with a token bucket instead of a fixed window?",
     "API Gateway", "Gateway service rate-limiting client requests.",
     ["Redis"], ["token bucket", "rate limiting"],
     "A fixed window let a client burst double the limit right at the window boundary, so I used a token bucket, which smooths that out by refilling continuously.",
     (4, 4, 4, 3), "trade_off_analysis", ["window boundary burst", "continuous refill"]),

    # ── Category 2: short + mediocre/shallow (10) ────────────────────────
    ("redis_cache_shallow", 2, "short",
     "Why did you add a Redis cache in front of the product catalog service?",
     "Catalog Service", "Product catalog read service for an e-commerce backend.",
     ["Redis", "PostgreSQL"], ["caching"],
     "Redis is fast so we added it to make the catalog service perform better.",
     (3, 0, 1, 0), "trade_off_analysis", ["read/write ratio", "cache invalidation"]),

    ("kafka_pipeline_shallow", 2, "short",
     "Why did you choose Kafka for the event pipeline instead of a simpler queue?",
     "Order Events Pipeline", "Event pipeline distributing order lifecycle events to multiple consumers.",
     ["Kafka", "RabbitMQ"], ["event streaming"],
     "Kafka is popular for event pipelines and scales well, so that's what we used.",
     (3, 0, 1, 0), "trade_off_analysis", ["multiple consumers", "log retention"]),

    ("composite_index_shallow", 2, "short",
     "Why did you add a composite index on (user_id, created_at) for the orders table?",
     "Orders API", "Order history API backed by PostgreSQL.",
     ["PostgreSQL"], ["indexing"],
     "Indexes make queries faster, so I added one to speed up the orders table.",
     (2, 0, 1, 0), "trade_off_analysis", ["composite index", "index scan"]),

    ("grpc_shallow", 2, "short",
     "Why did you use gRPC for the internal service-to-service calls instead of REST?",
     "Internal Services Mesh", "Internal microservices communicating over gRPC.",
     ["gRPC", "REST", "Docker"], ["protobuf"],
     "gRPC is more efficient than REST, so we switched the internal calls to use it.",
     (3, 0, 1, 0), "trade_off_analysis", ["serialization overhead", "connection reuse"]),

    ("docker_multistage_shallow", 2, "short",
     "Why did you switch the build to a multi-stage Dockerfile?",
     "Deployment Pipeline", "CI/CD build pipeline producing container images.",
     ["Docker"], ["image size"],
     "Multi-stage builds make Docker images smaller, so I changed the Dockerfile to use one.",
     (3, 0, 1, 0), "trade_off_analysis", ["build stage", "runtime stage"]),

    ("hpa_shallow", 2, "short",
     "Why did you configure horizontal pod autoscaling on the API deployment?",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker"], ["autoscaling"],
     "Autoscaling helps handle traffic spikes automatically, so I turned it on for the deployment.",
     (3, 0, 1, 0), "trade_off_analysis", ["autoscaling trigger", "cost efficiency"]),

    ("jwt_shallow", 2, "short",
     "Why did you use short-lived JWTs with refresh tokens instead of long-lived sessions?",
     "Auth Service", "Authentication service issuing tokens for the web app.",
     ["JWT"], ["token expiry"],
     "Short-lived tokens are more secure than long sessions, so we went with refresh tokens.",
     (3, 0, 1, 0), "trade_off_analysis", ["token lifetime", "exposure window"]),

    ("row_lock_shallow", 2, "short",
     "Why did you add a row-level lock around the inventory decrement?",
     "Inventory Service", "Inventory tracking service for checkout.",
     ["PostgreSQL"], ["concurrency"],
     "Locks prevent race conditions, so I added one around the inventory update to be safe.",
     (3, 0, 1, 0), "debugging", ["race condition", "SELECT FOR UPDATE"]),

    ("n_plus_1_shallow", 2, "short",
     "What caused the dashboard endpoint to slow down under load, and how did you fix it?",
     "Analytics Dashboard", "Internal dashboard aggregating owner data per row.",
     ["PostgreSQL"], ["N+1 queries"],
     "The dashboard was slow because of too many database calls, so I optimized the queries.",
     (3, 0, 1, 0), "debugging", ["N+1 query pattern", "join"]),

    ("rabbitmq_shallow", 2, "short",
     "Why did you pick RabbitMQ for the notification service instead of Kafka?",
     "Notification Service", "Per-user notification delivery service.",
     ["RabbitMQ", "Kafka"], ["routing keys"],
     "RabbitMQ is reliable and easy to set up, so we picked it for notifications.",
     (3, 0, 1, 0), "trade_off_analysis", ["routing by tier", "message volume"]),

    # ── Category 3: short + technically wrong (10) ───────────────────────
    ("redis_cache_wrong", 3, "short",
     "Why did you add a Redis cache in front of the product catalog service?",
     "Catalog Service", "Product catalog read service for an e-commerce backend.",
     ["Redis", "PostgreSQL"], ["caching"],
     "We added Redis because Postgres can't handle read queries at all without a cache in front of it.",
     (0, 1, 3, 1), "trade_off_analysis", ["read/write ratio", "cache invalidation"]),

    ("kafka_pipeline_wrong", 3, "short",
     "Why did you choose Kafka for the event pipeline instead of a simpler queue?",
     "Order Events Pipeline", "Event pipeline distributing order lifecycle events to multiple consumers.",
     ["Kafka", "RabbitMQ"], ["event streaming"],
     "We chose Kafka because it guarantees messages are delivered exactly once with zero configuration needed.",
     (1, 1, 3, 1), "trade_off_analysis", ["multiple consumers", "log retention"]),

    ("composite_index_wrong", 3, "short",
     "Why did you add a composite index on (user_id, created_at) for the orders table?",
     "Orders API", "Order history API backed by PostgreSQL.",
     ["PostgreSQL"], ["indexing"],
     "I added the composite index because indexes make INSERT and UPDATE statements faster automatically.",
     (0, 1, 3, 1), "trade_off_analysis", ["composite index", "index scan"]),

    ("grpc_wrong", 3, "short",
     "Why did you use gRPC for the internal service-to-service calls instead of REST?",
     "Internal Services Mesh", "Internal microservices communicating over gRPC.",
     ["gRPC", "REST", "Docker"], ["protobuf"],
     "We switched to gRPC because it works over plain HTTP/1.1 and needed no other infrastructure changes.",
     (0, 1, 3, 1), "trade_off_analysis", ["serialization overhead", "connection reuse"]),

    ("docker_multistage_wrong", 3, "short",
     "Why did you switch the build to a multi-stage Dockerfile?",
     "Deployment Pipeline", "CI/CD build pipeline producing container images.",
     ["Docker"], ["image size"],
     "Multi-stage Dockerfiles run all stages inside a single container at runtime, which is why the image got faster.",
     (0, 1, 3, 1), "trade_off_analysis", ["build stage", "runtime stage"]),

    ("hpa_wrong", 3, "short",
     "Why did you configure horizontal pod autoscaling on the API deployment?",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker"], ["autoscaling"],
     "Horizontal pod autoscaling automatically increases the size of each pod's memory and CPU limits under load.",
     (0, 1, 3, 1), "trade_off_analysis", ["autoscaling trigger", "cost efficiency"]),

    ("jwt_wrong", 3, "short",
     "Why did you use short-lived JWTs with refresh tokens instead of long-lived sessions?",
     "Auth Service", "Authentication service issuing tokens for the web app.",
     ["JWT"], ["token expiry"],
     "We use short-lived JWTs because the server can revoke an individual token immediately by blacklisting its signature.",
     (1, 1, 3, 1), "trade_off_analysis", ["token lifetime", "exposure window"]),

    ("row_lock_wrong", 3, "short",
     "Why did you add a row-level lock around the inventory decrement?",
     "Inventory Service", "Inventory tracking service for checkout.",
     ["PostgreSQL"], ["concurrency"],
     "The row-level lock prevents any other transaction from reading the inventory row until the lock is released.",
     (1, 2, 3, 1), "debugging", ["race condition", "SELECT FOR UPDATE"]),

    ("n_plus_1_wrong", 3, "short",
     "What caused the dashboard endpoint to slow down under load, and how did you fix it?",
     "Analytics Dashboard", "Internal dashboard aggregating owner data per row.",
     ["PostgreSQL"], ["N+1 queries"],
     "The dashboard was slow because the database didn't have enough RAM, so I fixed it by adding an index.",
     (0, 1, 2, 1), "debugging", ["N+1 query pattern", "join"]),

    ("rabbitmq_wrong", 3, "short",
     "Why did you pick RabbitMQ for the notification service instead of Kafka?",
     "Notification Service", "Per-user notification delivery service.",
     ["RabbitMQ", "Kafka"], ["routing keys"],
     "We picked RabbitMQ because it can retain and replay the full message history the way Kafka's log does.",
     (0, 1, 3, 1), "trade_off_analysis", ["routing by tier", "message volume"]),

    # ── Category 4: medium + strong (10) ──────────────────────────────────
    ("fastapi_async_strong", 4, "medium",
     "Walk me through how the async endpoints in the FastAPI service avoid blocking on slow downstream calls.",
     "Order Management API", "FastAPI backend calling payment and inventory services.",
     ["FastAPI", "Docker"], ["async I/O", "event loop", "thread pool"],
     "The endpoints that call downstream services, payment and inventory, are defined with async def and use httpx's async client, so while one request is waiting on a network call, the event loop picks up other requests instead of blocking a worker thread. CPU-bound work like PDF generation still runs in a thread pool via run_in_executor so it doesn't stall the loop.",
     (4, 4, 4, 3), "explanation", ["async I/O", "thread pool offload"]),

    ("feature_store_strong", 4, "medium",
     "Explain how the feature store keeps training and serving features consistent.",
     "Fraud Feature Store", "Feature store shared between model training and online serving.",
     ["PyTorch", "Redis"], ["feature store", "training-serving skew"],
     "Training reads features from the offline store, a batch of Parquet tables computed nightly, while serving reads the same feature definitions from a Redis-backed online store updated by the same pipeline. Both paths compute from the same feature definition code, so the values a model sees in training match what it sees at inference, which avoids the training-serving skew we hit before this existed.",
     (4, 4, 4, 3), "explanation", ["offline/online store", "shared feature definitions"]),

    ("raft_strong", 4, "medium",
     "Explain how the leader election works in the service's Raft-based coordination layer.",
     "Coordination Layer", "Internal service coordination using a Raft consensus implementation.",
     [], ["Raft", "leader election", "consensus"],
     "Each node starts as a follower and times out after a randomized interval if it hasn't heard from a leader, then becomes a candidate and requests votes from the others. Randomizing the timeout keeps two nodes from starting elections simultaneously most of the time. Once a candidate gets a majority, it becomes leader and starts sending heartbeats to reset everyone else's timeout.",
     (4, 4, 4, 3), "explanation", ["randomized timeout", "majority vote"]),

    ("cache_invalidation_strong", 4, "medium",
     "Walk me through how you invalidate the product cache when a price changes.",
     "Catalog Service", "Product catalog read service for an e-commerce backend.",
     ["Redis", "PostgreSQL"], ["cache invalidation", "delete-on-write"],
     "The price-update endpoint writes the new price to Postgres and then deletes the product's cache key in the same request, rather than trying to update the cached value in place. The next read simply misses and repopulates from the database. Delete-on-write is simpler to reason about than keeping two copies in sync, even though it costs one extra read after every price change.",
     (4, 4, 4, 3), "explanation", ["delete-on-write", "cache repopulation"]),

    ("isolation_level_strong", 4, "medium",
     "Explain why you chose REPEATABLE READ isolation for the payment service's transactions.",
     "Payment Service", "Service handling account balance debits during checkout.",
     ["PostgreSQL"], ["transaction isolation", "double-spend"],
     "Payments read the account balance and then write a debit in the same transaction, and under READ COMMITTED another transaction could commit a change to that balance in between, letting two concurrent payments both read the pre-debit balance. REPEATABLE READ freezes the snapshot for the duration of the transaction, so the second payment's write conflicts and retries instead of silently double-spending.",
     (4, 4, 4, 3), "trade_off_analysis", ["snapshot isolation", "concurrent debit conflict"]),

    ("idempotency_strong", 4, "medium",
     "Walk me through how the payment consumer avoids processing the same Kafka message twice.",
     "Payment Consumer", "Kafka consumer applying payment events.",
     ["Kafka", "PostgreSQL"], ["idempotency key", "at-least-once delivery"],
     "Each Kafka message carries the order's idempotency key, and before processing, the consumer checks a table that records which keys it has already handled inside the same transaction as the payment write. If the key is already there, it commits the offset and skips reprocessing. Keeping that check in the same transaction as the write is what stops a crash between the two from causing a duplicate charge.",
     (4, 4, 4, 3), "debugging", ["idempotency key", "transactional check"]),

    ("load_balancing_strong", 4, "medium",
     "Explain how requests get distributed across the backend pods.",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes"], ["load balancing", "readiness probe"],
     "The ingress sits in front of the service and load-balances with a round-robin policy across whichever pods are currently passing their readiness probe. A pod that's still warming up or failing its dependency checks gets pulled out of rotation automatically, so traffic only goes to pods that can actually serve it, not just ones that are running.",
     (4, 3, 4, 3), "explanation", ["readiness probe", "round-robin"]),

    ("gc_tuning_strong", 4, "medium",
     "Walk me through why you switched the service to the G1 garbage collector.",
     "Order Processing Service", "Java service processing orders under sustained load.",
     ["Java"], ["garbage collection", "pause time"],
     "The old default collector was pausing for over a second under load because it was doing full-heap stop-the-world collections. G1 divides the heap into regions and collects the ones with the most garbage first, which let us set a target max pause time instead of letting the collector decide, and our p99 latency stopped spiking during GC.",
     (4, 4, 4, 3), "trade_off_analysis", ["region-based collection", "target pause time"]),

    ("pagination_strong", 4, "medium",
     "Explain how the listings endpoint's pagination works under concurrent writes.",
     "Listings API", "API serving paginated listing results under heavy write traffic.",
     ["PostgreSQL"], ["keyset pagination", "cursor"],
     "The listings endpoint uses keyset pagination, the client passes the last seen id and created_at, and the query filters for rows after that cursor instead of using OFFSET. Offset pagination re-numbers rows as new listings get inserted, so a client paging through would skip or repeat rows; cursoring on a stable, indexed column avoids that under concurrent writes.",
     (4, 4, 4, 3), "explanation", ["cursor-based pagination", "offset drift"]),

    ("memory_leak_strong", 4, "medium",
     "Walk me through how you tracked down the memory leak in the ingestion worker.",
     "Ingestion Worker", "Background worker processing incoming messages.",
     ["Node.js"], ["heap snapshot", "event listener leak"],
     "I took heap snapshots a few minutes apart and diffed them, which showed a steadily growing number of retained message objects. Tracing the retainers back showed an event listener registered on every incoming message that was never removed, so each processed message kept its handler, and the handler's closure, alive indefinitely. Removing the listener once the message finished processing fixed it.",
     (4, 4, 4, 4), "debugging", ["heap diffing", "listener cleanup"]),

    # ── Category 5: medium + mediocre/shallow (10) ────────────────────────
    ("fastapi_async_shallow", 5, "medium",
     "Walk me through how the async endpoints in the FastAPI service avoid blocking on slow downstream calls.",
     "Order Management API", "FastAPI backend calling payment and inventory services.",
     ["FastAPI", "Docker"], ["async I/O"],
     "The FastAPI service uses async endpoints because async is generally faster and more scalable than synchronous code. Async lets the server handle more requests at once, which is important for performance. We made sure the important endpoints were async so that the API would be responsive and not slow down when there's a lot of traffic coming in.",
     (2, 0, 1, 0), "explanation", ["async I/O", "thread pool offload"]),

    ("feature_store_shallow", 5, "medium",
     "Explain how the feature store keeps training and serving features consistent.",
     "Fraud Feature Store", "Feature store shared between model training and online serving.",
     ["PyTorch", "Redis"], ["feature store"],
     "The feature store keeps things consistent by making sure training and serving use the same features. It's basically a central place where all the feature data lives, so there's less chance of things getting out of sync. Having a single source of truth for features is a good practice that helps avoid a lot of common ML problems in production.",
     (2, 0, 1, 0), "explanation", ["offline/online store", "shared feature definitions"]),

    ("raft_shallow", 5, "medium",
     "Explain how the leader election works in the service's Raft-based coordination layer.",
     "Coordination Layer", "Internal service coordination using a Raft consensus implementation.",
     [], ["Raft"],
     "Leader election works by having the nodes agree on who should be the leader based on the Raft algorithm. The nodes communicate with each other and eventually settle on one leader that coordinates everything. This is a well-known consensus approach that's used in a lot of distributed systems to keep things consistent.",
     (2, 0, 1, 0), "explanation", ["randomized timeout", "majority vote"]),

    ("cache_invalidation_shallow", 5, "medium",
     "Walk me through how you invalidate the product cache when a price changes.",
     "Catalog Service", "Product catalog read service for an e-commerce backend.",
     ["Redis", "PostgreSQL"], ["cache invalidation"],
     "When the price changes, the cache gets invalidated so users don't see old data. Cache invalidation is important because stale caches can cause bugs and confuse customers. We made sure to handle this carefully so that the cached product information always reflects whatever is currently in the database.",
     (2, 0, 1, 0), "explanation", ["delete-on-write", "cache repopulation"]),

    ("isolation_level_shallow", 5, "medium",
     "Explain why you chose REPEATABLE READ isolation for the payment service's transactions.",
     "Payment Service", "Service handling account balance debits during checkout.",
     ["PostgreSQL"], ["transaction isolation"],
     "REPEATABLE READ was chosen because it provides a good balance of consistency and performance for the payment service. Isolation levels control how transactions interact with each other, and higher isolation generally means safer but slower transactions, so we picked a level that seemed appropriate for handling money.",
     (2, 0, 1, 0), "trade_off_analysis", ["snapshot isolation", "concurrent debit conflict"]),

    ("idempotency_shallow", 5, "medium",
     "Walk me through how the payment consumer avoids processing the same Kafka message twice.",
     "Payment Consumer", "Kafka consumer applying payment events.",
     ["Kafka", "PostgreSQL"], ["idempotency key"],
     "The consumer avoids processing the same message twice by checking whether it has seen that message before. This is a common pattern for message queues since messages can sometimes get delivered more than once, and you don't want that to cause duplicate side effects in a payment system.",
     (2, 0, 1, 0), "debugging", ["idempotency key", "transactional check"]),

    ("load_balancing_shallow", 5, "medium",
     "Explain how requests get distributed across the backend pods.",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes"], ["load balancing"],
     "Requests get distributed across the pods using a load balancer, which spreads traffic out so no single pod gets overwhelmed. Load balancing is a standard part of running multiple replicas of a service, and it generally makes the system more reliable and able to handle more traffic overall.",
     (2, 0, 1, 0), "explanation", ["readiness probe", "round-robin"]),

    ("gc_tuning_shallow", 5, "medium",
     "Walk me through why you switched the service to the G1 garbage collector.",
     "Order Processing Service", "Java service processing orders under sustained load.",
     ["Java"], ["garbage collection"],
     "We switched to G1 because it's a newer, more modern garbage collector that's generally recommended for larger heaps. Garbage collection tuning can be complicated, but G1 is usually a safe default choice that improves performance compared to older collectors without much extra configuration needed.",
     (2, 0, 1, 0), "trade_off_analysis", ["region-based collection", "target pause time"]),

    ("pagination_shallow", 5, "medium",
     "Explain how the listings endpoint's pagination works under concurrent writes.",
     "Listings API", "API serving paginated listing results under heavy write traffic.",
     ["PostgreSQL"], ["pagination"],
     "The pagination works by returning pages of results so the client doesn't get everything at once. This keeps responses fast and manageable. We made sure it works correctly even when there's a lot of data and multiple users are using the endpoint at the same time.",
     (2, 0, 1, 0), "explanation", ["cursor-based pagination", "offset drift"]),

    ("memory_leak_shallow", 5, "medium",
     "Walk me through how you tracked down the memory leak in the ingestion worker.",
     "Ingestion Worker", "Background worker processing incoming messages.",
     ["Node.js"], ["debugging"],
     "I looked into the memory leak by checking the logs and monitoring the service's memory usage over time. Eventually I found the part of the code that was causing the issue and fixed it. Memory leaks can be tricky to track down, but careful debugging usually gets to the root cause.",
     (2, 0, 1, 0), "debugging", ["heap diffing", "listener cleanup"]),

    # ── Category 6: long + strong (5) ─────────────────────────────────────
    ("order_arch_strong", 6, "long",
     "Walk me through the overall architecture of the order processing system and how the pieces fit together.",
     "Order Management API", "Backend service handling the order lifecycle for an e-commerce site.",
     ["FastAPI", "PostgreSQL", "Redis", "gRPC", "Docker"], ["layered architecture", "state machine", "idempotency"],
     "The order service is split into three layers: a FastAPI routing layer, a service layer holding the order state machine, and a repository layer over Postgres. Orders move through pending, paid, fulfilled, and cancelled, and the service layer is the only place that enforces those transitions, so a route handler can never write an invalid state directly. Redis sits in front of the read-heavy status endpoint with a short TTL, invalidated on any write to that order. Payment and inventory are separate services we call over gRPC, and each call carries an idempotency key so a retried request can't double-charge or double-decrement stock. Everything ships in Docker so the Postgres, Redis, and library versions in every environment match what I actually test against locally.",
     (4, 4, 4, 4), "explanation", ["layered architecture", "state machine", "idempotency key"]),

    ("ml_pipeline_strong", 6, "long",
     "Walk me through the end-to-end training pipeline for the fraud detection model.",
     "Fraud Detection Pipeline", "ML pipeline training a fraud classifier on transaction data.",
     ["PyTorch"], ["time-based split", "precision at recall", "model promotion"],
     "The pipeline starts by pulling labeled transactions from the warehouse, joining them against the feature store's offline tables so training sees the same feature definitions serving will use later. I hold out the most recent month as a time-based test split rather than a random split, since a random split would leak future fraud patterns into training and inflate the offline metrics. The model is a gradient-boosted tree ensemble, retrained weekly, and before promotion it has to beat the currently deployed model on precision at a fixed recall on that held-out month, not just on average AUC, because at our review capacity, precision at that operating point is what actually determines analyst workload. Every trained model's metrics and the data snapshot it trained on get logged so a regression can be traced back to a specific run.",
     (4, 4, 4, 4), "explanation", ["time-based holdout", "precision at fixed recall"]),

    ("url_shortener_strong", 6, "long",
     "Design a URL shortener service that needs to handle high read traffic. Walk me through your approach.",
     "URL Shortener Design", "System design exercise for a high-read-traffic URL shortener.",
     ["Redis", "PostgreSQL", "DynamoDB", "Snowflake"], ["base62 encoding", "caching", "CDN"],
     "Writes are cheap and rare compared to reads, so I'd optimize hard for read latency. Short codes get generated from a base62-encoded counter rather than hashing the URL, which avoids collision handling entirely and keeps codes short. The mapping lives in a key-value store like DynamoDB or Postgres with a unique index on the code, and a CDN or Redis layer sits in front of it since the same popular links get hit constantly and the mapping almost never changes after creation, making it ideal to cache aggressively with a long TTL. Redirects themselves return a 301 so browsers cache them client-side too, cutting repeat traffic to the service further. I'd shard the counter or use a coordination-free ID scheme like Snowflake IDs if a single counter became a write bottleneck.",
     (4, 4, 4, 3), "design", ["base62 counter", "aggressive read caching"]),

    ("k8s_rollout_strong", 6, "long",
     "Walk me through how you designed the deployment and rollout strategy for the service on Kubernetes.",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker", "PostgreSQL"], ["rolling update", "readiness probe", "canary"],
     "The service uses a rolling update strategy with maxSurge and maxUnavailable both set to 1, so Kubernetes brings up one new pod, waits for it to pass its readiness probe, then retires one old pod, rather than replacing everything at once. The readiness probe checks a real dependency, a lightweight database ping, not just that the process is alive, so a pod that started but can't reach Postgres never receives traffic. I added a PodDisruptionBudget requiring at least two pods available at all times so a node drain or autoscaler event can't take the whole deployment down together. For riskier changes I route a small percentage of traffic to the new version first through a canary deployment and watch error rates before scaling it up to full replacement.",
     (4, 4, 4, 4), "design", ["rolling update", "PodDisruptionBudget", "canary"]),

    ("migration_strong", 6, "long",
     "Walk me through how you handled the zero-downtime schema migration for the orders table.",
     "Orders API", "Order history API backed by PostgreSQL.",
     ["PostgreSQL"], ["staged migration", "backfill", "constraint validation"],
     "The orders table needed a new non-nullable column, so I did it in stages instead of one blocking migration. First I added the column as nullable with a default, which on Postgres 11+ is a fast metadata-only change that doesn't rewrite the table. Then I backfilled existing rows in small batches during low-traffic hours so each batch's lock was brief instead of holding one long lock on the whole table. Application code was deployed first to write the new column on every new order, so by the time I added the NOT NULL constraint, every row already satisfied it and Postgres could validate the constraint without a full table scan. Each stage was a separate deploy, so if a batch caused replication lag I could pause without rolling anything back.",
     (4, 4, 4, 4), "debugging", ["staged rollout", "batched backfill"]),

    # ── Category 7: long + mediocre/shallow (5) ───────────────────────────
    ("order_arch_shallow", 7, "long",
     "Walk me through the overall architecture of the order processing system and how the pieces fit together.",
     "Order Management API", "Backend service handling the order lifecycle for an e-commerce site.",
     ["FastAPI", "PostgreSQL", "Redis", "gRPC", "Docker"], ["layered architecture"],
     "The order system is built with good software engineering practices in mind, following a layered architecture that separates concerns properly. We have a layer for handling requests, a layer for business logic, and a layer for talking to the database, which is a pretty standard and well-understood pattern in the industry. Using this kind of architecture makes the codebase easier to maintain over time and easier for new engineers to understand when they join the team. We also made sure to use modern tools and containerization so that the whole system is portable and can run consistently across different environments, which is generally considered a best practice for backend systems like this one today.",
     (2, 0, 1, 0), "explanation", ["layered architecture", "state machine", "idempotency key"]),

    ("ml_pipeline_shallow", 7, "long",
     "Walk me through the end-to-end training pipeline for the fraud detection model.",
     "Fraud Detection Pipeline", "ML pipeline training a fraud classifier on transaction data.",
     ["PyTorch"], ["training pipeline"],
     "The training pipeline follows standard machine learning best practices from start to finish. We gather the data, clean it up, and prepare it in a way that's suitable for training a model. Then we train the model using a solid, well-established algorithm that's known to work well for this kind of problem, and we evaluate it using the usual metrics people look at to judge whether a model is doing a good job. Once we're happy with the results, the model gets deployed so it can start making predictions in production, and we keep an eye on it over time to make sure everything continues to work the way it's supposed to.",
     (2, 0, 1, 0), "explanation", ["time-based holdout", "precision at fixed recall"]),

    ("url_shortener_shallow", 7, "long",
     "Design a URL shortener service that needs to handle high read traffic. Walk me through your approach.",
     "URL Shortener Design", "System design exercise for a high-read-traffic URL shortener.",
     ["Redis", "PostgreSQL"], ["caching"],
     "For a URL shortener handling a lot of read traffic, the main thing is to design it for scalability from the start. You'd want a database that can handle the load, and probably some caching involved since caching generally helps with performance for services like this. You'd also want to think about reliability and making sure the system stays available even as traffic grows, using good infrastructure practices like load balancing and redundancy. Overall the goal is a system that's fast, scalable, and reliable, which is what you'd want from any well-designed high-traffic web service in general.",
     (2, 0, 1, 0), "design", ["base62 counter", "aggressive read caching"]),

    ("k8s_rollout_shallow", 7, "long",
     "Walk me through how you designed the deployment and rollout strategy for the service on Kubernetes.",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker"], ["rolling update"],
     "For deploying on Kubernetes, we followed the standard recommended approach for rolling out new versions safely. Kubernetes has built-in support for updating deployments gradually, which is generally the safest way to release changes without causing downtime for users. We also made sure to have health checks configured, since that's considered a best practice for any production service running in a cluster. Overall the deployment process is designed to be reliable and to minimize risk when we ship new code, following the kind of practices that are widely recommended for cloud-native applications running in Kubernetes today.",
     (2, 0, 1, 0), "design", ["rolling update", "PodDisruptionBudget", "canary"]),

    ("migration_shallow", 7, "long",
     "Walk me through how you handled the zero-downtime schema migration for the orders table.",
     "Orders API", "Order history API backed by PostgreSQL.",
     ["PostgreSQL"], ["migration"],
     "Schema migrations are always a bit risky, so we were careful and followed best practices to make sure nothing broke. We planned the migration ahead of time, tested it in a staging environment first, and made sure we had a rollback plan in case anything went wrong during the process. Communication with the team was also important so everyone knew what was happening and when. In the end the migration went smoothly because we took the necessary precautions that you'd normally take for a change like this on a production database.",
     (2, 0, 1, 0), "debugging", ["staged rollout", "batched backfill"]),

    # ── Category 8: long + technically wrong (5) ──────────────────────────
    ("order_arch_wrong", 8, "long",
     "Walk me through the overall architecture of the order processing system and how the pieces fit together.",
     "Order Management API", "Backend service handling the order lifecycle for an e-commerce site.",
     ["FastAPI", "PostgreSQL", "Redis", "gRPC", "Docker"], ["layered architecture"],
     "The order service architecture centers on storing all order state directly inside Redis, since Redis is a database and can persist data just as durably as Postgres once persistence is enabled, so we use it as the primary store rather than a cache. The routing layer talks straight to Redis for both reads and writes, which removes the need for a separate database layer entirely and simplifies the stack. Because Redis operations are single-threaded, every write is automatically transactional across multiple keys, so I don't need explicit transactions or locking anywhere in the order state machine, a state transition that touches the order and the inventory count is safe by default. Postgres is only used for an offline nightly export in case we need historical reporting later.",
     (0, 2, 3, 1), "explanation", ["layered architecture", "state machine", "idempotency key"]),

    ("ml_pipeline_wrong", 8, "long",
     "Walk me through the end-to-end training pipeline for the fraud detection model.",
     "Fraud Detection Pipeline", "ML pipeline training a fraud classifier on transaction data.",
     ["PyTorch"], ["training pipeline"],
     "The fraud model is retrained by taking the current production model and continuing to train it on whatever new labeled transactions arrived that week, without touching the original training set again, since starting from the existing weights and just adding new data is strictly better than retraining from scratch. I evaluate the new version using overall accuracy on the same week's data it was just trained on, which gives a clean read on whether the update helped, and if accuracy went up I promote it immediately. I don't hold out a separate test period because the model already sees a representative mix of fraud and non-fraud cases during training, so a held-out set would just be throwing away useful training signal for no real benefit.",
     (0, 2, 3, 1), "explanation", ["time-based holdout", "precision at fixed recall"]),

    ("url_shortener_wrong", 8, "long",
     "Design a URL shortener service that needs to handle high read traffic. Walk me through your approach.",
     "URL Shortener Design", "System design exercise for a high-read-traffic URL shortener.",
     ["Redis", "PostgreSQL"], ["caching"],
     "For the short codes, I'd hash the full URL with MD5 and use the whole 128-bit hash as the code, which guarantees every URL gets a unique code with no possibility of collision, so there's never a need to check the database before inserting a new mapping. For the high read traffic, I wouldn't bother with a cache in front of the database, because a well-indexed relational database can already serve millions of reads per second directly with no caching layer needed as long as the code column has a primary key on it. Redirects should return a 500 status temporarily until the destination is confirmed reachable, so browsers know to retry the request instead of caching a broken link.",
     (0, 2, 3, 1), "design", ["base62 counter", "aggressive read caching"]),

    ("k8s_rollout_wrong", 8, "long",
     "Walk me through how you designed the deployment and rollout strategy for the service on Kubernetes.",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker"], ["rolling update"],
     "The rollout strategy is a recreate strategy, where all old pods are terminated at once and then the new pods start up, which actually causes zero downtime because Kubernetes automatically buffers incoming requests at the API server level until the new pods are ready to receive them. Readiness probes aren't really necessary in this setup since Kubernetes already knows a pod is ready as soon as its container process starts running, so I skip configuring them to keep the deployment manifest simpler. If something goes wrong with a rollout, Kubernetes automatically detects the failure from CPU metrics alone and rolls back without any configuration needed on my part.",
     (0, 2, 3, 1), "design", ["rolling update", "PodDisruptionBudget", "canary"]),

    ("migration_wrong", 8, "long",
     "Walk me through how you handled the zero-downtime schema migration for the orders table.",
     "Orders API", "Order history API backed by PostgreSQL.",
     ["PostgreSQL"], ["migration"],
     "Since the orders table needed a new NOT NULL column, I just ran a single ALTER TABLE statement adding the column as NOT NULL with a default value directly against the production table during business hours, because Postgres applies default values to existing rows instantly at the metadata level regardless of table size, so there's no meaningful lock held even on a table with hundreds of millions of rows. I didn't need to backfill separately or stage the constraint, since the ALTER TABLE command handles populating every existing row with the default as part of the same fast, non-blocking operation, and application code could keep writing to the table the entire time without any risk of contention.",
     (0, 2, 3, 1), "debugging", ["staged rollout", "batched backfill"]),

    # ── Category 9: relevance contrast (5) — same question as a cat-1 pair, irrelevant-but-valid answer ──
    ("redis_cache_irrelevant", 9, "short",
     "Why did you add a Redis cache in front of the product catalog service?",
     "Catalog Service", "Product catalog read service for an e-commerce backend.",
     ["Redis", "PostgreSQL", "Docker"], ["caching"],
     "We containerized the whole stack with Docker so every developer's local environment matches production exactly, which cut down on a lot of 'works on my machine' issues during onboarding.",
     (4, 3, 0, 2), "trade_off_analysis", ["read/write ratio", "cache invalidation"]),

    ("grpc_irrelevant", 9, "short",
     "Why did you use gRPC for the internal service-to-service calls instead of REST?",
     "Internal Services Mesh", "Internal microservices communicating over gRPC.",
     ["gRPC", "REST", "Docker"], ["logging"],
     "We set up centralized structured logging with correlation ids so a single request could be traced across every service it touched, which made debugging production issues much faster.",
     (4, 3, 0, 2), "trade_off_analysis", ["serialization overhead", "connection reuse"]),

    ("n_plus_1_irrelevant", 9, "short",
     "What caused the dashboard endpoint to slow down under load, and how did you fix it?",
     "Analytics Dashboard", "Internal dashboard aggregating owner data per row.",
     ["PostgreSQL"], ["CDN"],
     "We added a CDN in front of the static assets so images and JS bundles load faster for users in other regions, which noticeably improved page load times.",
     (4, 3, 0, 2), "debugging", ["N+1 query pattern", "join"]),

    ("react_context_irrelevant", 9, "short",
     "Why did you move the cart state into a context provider instead of prop drilling?",
     "Storefront Frontend", "React storefront with a shared shopping cart.",
     ["React", "Playwright"], ["testing"],
     "We added end-to-end tests with Playwright covering the checkout flow, which caught several regressions before they reached production.",
     (4, 2, 0, 2), "trade_off_analysis", ["prop drilling", "shared state"]),

    ("idempotency_irrelevant", 9, "short",
     "Walk me through how the payment consumer avoids processing the same Kafka message twice.",
     "Payment Consumer", "Kafka consumer applying payment events.",
     ["Kafka", "PostgreSQL"], ["monitoring"],
     "We set up Prometheus and Grafana dashboards for the payment service so we could see error rates and latency percentiles at a glance instead of digging through logs.",
     (4, 3, 0, 2), "debugging", ["idempotency key", "transactional check"]),

    # ── Category 10: grounding/ownership contrast (5) — generic textbook, no project ownership ──
    ("feature_store_generic", 10, "medium",
     "Explain how the feature store keeps training and serving features consistent.",
     "Fraud Feature Store", "Feature store shared between model training and online serving.",
     ["PyTorch", "Redis"], ["feature store"],
     "A feature store is a centralized repository for machine learning features that solves the training-serving skew problem. It typically has an offline store for batch training and an online store for low-latency serving, both computed from the same feature definitions, ensuring consistency between training and inference so that models perform the same way in production as they did during training.",
     (4, 3, 3, 0), "explanation", ["offline/online store", "shared feature definitions"]),

    ("isolation_level_generic", 10, "medium",
     "Explain why you chose REPEATABLE READ isolation for the payment service's transactions.",
     "Payment Service", "Service handling account balance debits during checkout.",
     ["PostgreSQL"], ["transaction isolation"],
     "REPEATABLE READ is one of the four standard SQL isolation levels defined in the ANSI SQL standard, alongside READ UNCOMMITTED, READ COMMITTED, and SERIALIZABLE. It prevents non-repeatable reads by ensuring a transaction sees a consistent snapshot of the data for its entire duration, which is generally recommended for financial systems where consistency during a transaction matters more than raw throughput.",
     (4, 3, 2, 0), "trade_off_analysis", ["snapshot isolation", "concurrent debit conflict"]),

    ("hpa_generic", 10, "medium",
     "Why did you configure horizontal pod autoscaling on the API deployment?",
     "API Deployment", "Public API service running on Kubernetes.",
     ["Kubernetes", "Docker"], ["autoscaling"],
     "Horizontal Pod Autoscaling is a Kubernetes feature that automatically adjusts the number of pod replicas in a deployment based on observed metrics like CPU or memory utilization, scaling out under load and back in when demand drops, which is the standard way to handle variable traffic in a Kubernetes-native application.",
     (4, 2, 3, 0), "trade_off_analysis", ["autoscaling trigger", "cost efficiency"]),

    ("kafka_pipeline_generic", 10, "medium",
     "Why did you choose Kafka for the event pipeline instead of a simpler queue?",
     "Order Events Pipeline", "Event pipeline distributing order lifecycle events to multiple consumers.",
     ["Kafka", "RabbitMQ"], ["event streaming"],
     "Kafka is a distributed event streaming platform that stores records in an ordered, append-only log split into partitions, and multiple consumers can read from the same log independently at their own pace, which is a common reason teams choose it over traditional message queues for event-driven systems.",
     (4, 3, 3, 0), "trade_off_analysis", ["multiple consumers", "log retention"]),

    ("pagination_generic", 10, "medium",
     "Explain how the listings endpoint's pagination works under concurrent writes.",
     "Listings API", "API serving paginated listing results under heavy write traffic.",
     ["PostgreSQL"], ["pagination"],
     "Keyset pagination, also called cursor-based pagination, is a well-known alternative to offset-based pagination where instead of skipping a number of rows, the query filters for rows after a given cursor value, which avoids the performance and consistency problems that offset pagination has on large, frequently-updated tables.",
     (4, 3, 3, 0), "explanation", ["cursor-based pagination", "offset drift"]),

    # ── Category 11 (addendum, human-review follow-up): short + genuinely
    # good-but-not-excellent (5) — correct and relevant, but limited depth/
    # completeness, landing Tier 3 rather than Tier 4. The original 80-example
    # set had zero short (<=30 word) Tier-3 examples; this addendum fills
    # that specific gap. Distinct topics from the original 80, so these are
    # neither duplicates nor rewrites of any existing example. ──
    ("websocket_updates_t3", 11, "short",
     "Why did you use WebSockets for the live order-status updates instead of polling?",
     "Order Status Updates", "Live order-status feature for the storefront frontend.",
     ["WebSocket"], ["push updates", "polling overhead"],
     "Polling meant clients kept hitting the endpoint even when nothing had changed, so I switched to a WebSocket connection that only pushes an update when the order status changes.",
     (4, 3, 3, 2), "trade_off_analysis", ["push vs poll", "status change event"]),

    ("circuit_breaker_t3", 11, "short",
     "Why did you add a circuit breaker around the calls to the shipping-rate provider?",
     "Shipping Rate Integration", "Checkout integration calling a third-party shipping-rate provider.",
     [], ["circuit breaker", "downstream failure"],
     "The shipping-rate provider would sometimes hang for 30+ seconds, and without a circuit breaker every checkout request piled up waiting on it too.",
     (4, 3, 3, 2), "trade_off_analysis", ["cascading latency", "downstream hang"]),

    ("connection_pool_t3", 11, "short",
     "Why did you add a connection pool in front of the database instead of opening a new connection per request?",
     "Database Connection Layer", "Shared connection layer used by the API's request handlers.",
     ["PostgreSQL"], ["connection pooling", "latency"],
     "Opening a new connection per request was adding noticeable latency under load, so a pool of reusable connections cut that overhead and kept response times more consistent.",
     (4, 3, 3, 2), "trade_off_analysis", ["connection overhead", "reuse"]),

    ("sharding_t3", 11, "short",
     "Why did you shard the users table by user_id instead of keeping it as a single table?",
     "Users Service", "User account service backed by PostgreSQL.",
     ["PostgreSQL"], ["sharding", "write scaling"],
     "The single table was becoming a write bottleneck as we grew, so splitting it into shards by user_id spread the write load across multiple databases.",
     (4, 3, 3, 2), "trade_off_analysis", ["write bottleneck", "shard key"]),

    ("read_replica_t3", 11, "short",
     "Why did you add a read replica for the reporting queries instead of running them against the primary?",
     "Reporting Service", "Internal reporting service running long queries against production data.",
     ["PostgreSQL"], ["read replica", "query isolation"],
     "The reporting queries were long-running and competing with normal traffic for the same database, so I pointed them at a read replica to keep the primary responsive.",
     (4, 3, 3, 2), "trade_off_analysis", ["query contention", "primary responsiveness"]),
]

assert len(ROWS) == 85, f"expected 85 rows, got {len(ROWS)}"

_DIMENSION_NAMES = (
    "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
)


def build_example(i: int, row: tuple) -> TrainingExample:
    (slug, category_num, length_bucket, question, proj_title, proj_summary,
     technologies, concepts, answer, tiers, reasoning_type, expected_concepts) = row

    example_id = f"v5cal_{i:03d}"
    tc, ds, rc, go = tiers
    dim_scores = {
        "technical_correctness": tc / _MAX_TIER,
        "depth_specificity": ds / _MAX_TIER,
        "relevance_completeness": rc / _MAX_TIER,
        "grounding_ownership": go / _MAX_TIER,
    }
    overall_score = round(sum(dim_scores.values()) / len(dim_scores), 4)
    overall_tier = _overall_score_to_tier(overall_score)
    grade = tier_label(overall_tier)

    specification = QuestionSpecification(
        id=example_id,
        category=QuestionCategory.PROJECT_DEEP_DIVE,
        text_seed=proj_title,
        text_seed_is_sentence=False,
        grounding=Grounding(
            project=ProjectGrounding(
                title=proj_title,
                summary=proj_summary,
                technologies=tuple(technologies),
                concepts=tuple(concepts),
            ),
        ),
        priority_boost=False,
        source_type=SourceType.PROJECT,
        source_id=f"v5cal_{slug}",
        source_field="v5_short_quality_calibration",
        reason="claude_authored_v5_calibration",
    )

    inputs = TrainingExampleInputs(
        specification=specification,
        question_text=question,
        reasoning_type=ReasoningType(reasoning_type),
        answer_text=answer,
        expected_concepts=tuple(expected_concepts),
    )

    synthetic = TrainingExampleSyntheticMeta(
        generation_prompt_id="claude_authored_v5_calibration",
        prompt_version="v1",
        generator_model="claude-authored",
        generation_batch_id=BATCH_ID,
        intended_quality_tier=_TIER_TO_QUALITY[overall_tier],
        diversity_seed=f"v5cal_{slug}",
        style_seed=example_id,
    )

    labels = TrainingExampleLabels(
        label_source="synthetic_ground_truth",
        dimension_labels=tuple(
            DimensionLabel(name=name, score=round(dim_scores[name], 4)) for name in _DIMENSION_NAMES
        ),
        contradiction_label=ContradictionLabel(contradiction_present=False),
        overall_label=OverallLabel(
            score=overall_score,
            grade=grade,
            rationale=(
                "Overall target derived by equal-weight mean of the four Claude-authored dimension "
                f"labels (category {category_num}: length={length_bucket}, "
                f"tiers tc={tc}/ds={ds}/rc={rc}/go={go})."
            ),
        ),
    )

    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=example_id, created_at=CREATED_AT),
        provenance=TrainingExampleProvenance(source=ProvenanceSource.SYNTHETIC, collection_batch_id=BATCH_ID),
        inputs=inputs,
        privacy=TrainingExamplePrivacy(contains_pii=False, anonymized=True),
        synthetic=synthetic,
        labels=labels,
    ), category_num, length_bucket


def main() -> None:
    os.makedirs(DATASET_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    examples = []
    meta_rows = []
    for i, row in enumerate(ROWS, start=1):
        ex, category_num, length_bucket = build_example(i, row)
        examples.append(ex)
        meta_rows.append({"example_id": ex.metadata.example_id, "category_num": category_num, "length_bucket": length_bucket})

    examples_path = os.path.join(DATASET_DIR, "examples.jsonl")
    with open(examples_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(ex.model_dump_json() + "\n")

    metadata = {
        "dataset_version": DATASET_VERSION,
        "total_examples": len(examples),
        "created_at": CREATED_AT,
        "purpose": "Isolated calibration set to counter answer-length/quality confound found in four_dim_overall_v4_5000 (r=0.720). NOT merged into the 1003 dataset.",
        "generation": "Claude-authored, no Gemini/LLM API, deterministic/reproducible from this checked-in script.",
        "collection_batch_id": BATCH_ID,
        "composition": {
            "1_short_strong": 15, "2_short_mediocre": 10, "3_short_wrong": 10,
            "4_medium_strong": 10, "5_medium_mediocre": 10,
            "6_long_strong": 5, "7_long_mediocre": 5, "8_long_wrong": 5,
            "9_relevance_contrast": 5, "10_grounding_contrast": 5,
            "11_short_good_not_excellent_addendum": 5,
        },
        "addendum_note": (
            "Category 11 (5 examples) added after a human-review pass found zero "
            "short (<=30 word) Tier-3 examples in the original 80. These fill that "
            "gap: correct + relevant, but limited depth/completeness, landing Tier 3 "
            "under the existing rubric. Original 80 examples/labels were NOT modified."
        ),
    }
    with open(os.path.join(DATASET_DIR, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    with open(os.path.join(DATASET_DIR, "row_categories.json"), "w", encoding="utf-8") as f:
        json.dump(meta_rows, f, indent=2)

    print(f"Wrote {len(examples)} examples to {examples_path}")


if __name__ == "__main__":
    main()
