"""
Implementation-level technical vocabulary — the words engineers use when they
describe HOW something works ("TTL", "idempotent", "offset", "salt",
"collider"), as opposed to the résumé-level buzzwords in
resume_engine/concept_gazetteer.py ("Caching", "Microservices").

Used by resume_evidence_evaluator (scoring v2) as a specificity signal: an
answer that names mechanisms is more specific than one that names topics.
Deliberately broad across domains (backend, data, security, ML, frontend,
mobile, game/VR, devops, systems) so it is not tuned to any one project.
A plain data file: adding a term is a one-line, reviewable change.

Single words match on word boundaries, case-insensitively; multi-word terms
match as phrases. Words that are common in everyday English ("cache",
"index", "queue", "model") are excluded on purpose — they don't show
specificity on their own.
"""

from __future__ import annotations

IMPLEMENTATION_TERMS: tuple[str, ...] = (
    # caching / performance
    "ttl", "cache hit", "cache miss", "cache-aside", "write-through", "write-back", "eviction", "lru",
    "invalidation", "invalidate", "memoize", "memoization", "p50", "p95", "p99", "latency", "throughput",
    "hot path", "cold start", "warm up", "prefetch", "lazy loading", "debounce", "throttle", "pagination",
    "connection pool", "connection pooling", "n+1", "batching", "backpressure",
    # concurrency / distributed systems
    "idempotent", "idempotency", "at-least-once", "at-most-once", "exactly-once", "race condition",
    "deadlock", "mutex", "semaphore", "lock contention", "optimistic locking", "pessimistic locking",
    "compare-and-swap", "atomic", "atomically", "lease", "heartbeat", "leader election", "quorum",
    "partition", "partitions", "rebalance", "rebalancing", "replica", "replication lag", "sharding",
    "consistent hashing", "eventual consistency", "two-phase commit", "saga", "outbox", "dead letter",
    "dead-letter", "retry", "retries", "exponential backoff", "jitter", "circuit breaker", "timeout",
    "watermark", "event time", "windowing", "sliding window", "tumbling window", "offset", "offsets",
    "consumer group", "auto-commit", "commit", "ack", "acknowledgement", "redelivery", "ordering",
    "fan-out", "fan-in", "pub/sub", "topic", "broker", "producer", "consumer",
    # databases
    "transaction", "isolation level", "foreign key", "unique constraint", "composite index", "b-tree",
    "query plan", "explain analyze", "normalization", "normalized", "denormalized", "migration",
    "stored procedure", "trigger", "materialized view", "upsert", "primary key", "schema",
    # security / auth
    "salt", "salted", "pepper", "hashing", "bcrypt", "argon2", "pbkdf2", "work factor", "cost factor",
    "jwt", "refresh token", "access token", "csrf", "xss", "sql injection", "parameterized",
    "rate limiter", "lockout", "brute force", "rbac", "least privilege", "tls", "https", "cors",
    "oauth", "session token", "signature", "encryption at rest", "secrets manager",
    # web / api / frontend
    "endpoint", "middleware", "websocket", "server-sent events", "sse", "polling", "long polling",
    "302", "301", "status code", "payload", "serialization", "deserialize", "schema validation",
    "virtual dom", "re-render", "state management", "hydration", "client-side", "server-side",
    "code splitting", "bundle size", "service worker", "cors preflight",
    # data / ml
    "embedding", "embeddings", "vector index", "cosine similarity", "chunking", "chunk size",
    "top-k", "reranker", "re-ranking", "fine-tune", "fine-tuned", "fine-tuning", "overfitting",
    "train/test split", "validation set", "cross-validation", "precision", "recall", "f1",
    "learning rate", "batch size", "epoch", "epochs", "tokenizer", "prompt template", "temperature",
    "hallucination", "ground truth", "labelled", "labeled", "feature engineering", "baseline",
    "confusion matrix", "class imbalance", "data leakage", "inference", "quantization",
    # devops / infra
    "dockerfile", "docker compose", "container", "health check", "readiness probe", "liveness probe",
    "load balancer", "reverse proxy", "autoscaling", "horizontal scaling", "blue-green", "canary",
    "rollback", "ci pipeline", "environment variable", "env var", "secrets", "observability",
    "structured logging", "tracing", "metrics", "alerting", "serverless", "cold starts",
    "advertised listeners", "port mapping", "volume mount",
    # systems / os / low-level
    "inode", "syscall", "system call", "file descriptor", "copy-on-write", "page fault", "mmap",
    "fork", "thread pool", "event loop", "async", "asynchronously", "coroutine", "garbage collection",
    "memory leak", "stack trace", "core dump", "profiler", "profiling",
    # game / vr / graphics / mobile
    "collider", "rigidbody", "raycast", "socket interactor", "xr interaction toolkit", "grab interactable",
    "haptic", "haptics", "frame rate", "fps", "shader", "prefab", "scene graph", "physics engine",
    "render loop", "draw call", "occlusion", "navmesh", "push notification", "deep link",
    "offline-first", "background task",
    # testing / debugging method
    "unit test", "unit tests", "integration test", "regression test", "repro", "reproduce",
    "root cause", "bisect", "breakpoint", "logging", "mock", "fixture", "flaky", "load test",
    "benchmark", "benchmarked", "a/b test",
)
