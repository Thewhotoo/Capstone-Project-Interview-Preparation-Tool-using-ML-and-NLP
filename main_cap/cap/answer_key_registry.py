"""
Answer Key Registry — deterministic, growable lookup of per-question
`AnswerKey`s for the reference-anchored evaluator, consulted entirely inside
the orchestration layer (`evaluation_engine.py`).

Mirrors `expected_concepts_registry` exactly in spirit and shape: a hand-
curated, growable table; consulted at request-assembly time; a question with
no entry degrades gracefully to `None` (never an error, never invented, never
model-generated). Zero Planning-layer schema changes — QuestionSpecification /
Planner / TopicPool / Question Realizer / ConversationMemory are untouched;
the AnswerKey is attached only to the `EvaluationRequest` the Evaluator sees,
the same boundary `expected_concepts` uses.

SEED CONTENT: only the minimal representative fixtures needed to exercise the
pipeline end-to-end (the eight Phase-3 diagnostic questions). The full
population of AnswerKeys for the live question bank is deferred content-
authoring work, out of scope for this integration step.
"""

from __future__ import annotations

import logging

from answer_key import AnswerKey

logger = logging.getLogger(__name__)

_BY_QUESTION: dict[str, AnswerKey] = {}
_BY_SPEC_ID: dict[str, AnswerKey] = {}


class DuplicateAnswerKeyError(ValueError):
    """Raised if a key is already registered — re-registering would silently
    shadow an existing entry (same discipline as
    `expected_concepts_registry.register_expected_concepts`)."""


def _qkey(question_text: str) -> str:
    return " ".join((question_text or "").split()).casefold()


def register_answer_key(question_text: str, key: AnswerKey, *, spec_id: str | None = None) -> None:
    """Register an `AnswerKey` under a normalized question text (and optionally
    a specification id). Raises on duplicate registration under the same key."""
    qk = _qkey(question_text)
    if not qk and not spec_id:
        raise ValueError("must supply a non-empty question_text or spec_id")
    if qk:
        if qk in _BY_QUESTION:
            raise DuplicateAnswerKeyError(f"question already registered: {question_text!r}")
        _BY_QUESTION[qk] = key
    if spec_id:
        if spec_id in _BY_SPEC_ID:
            raise DuplicateAnswerKeyError(f"spec_id already registered: {spec_id!r}")
        _BY_SPEC_ID[spec_id] = key


def lookup(question_text: str = "", spec_id: str | None = None) -> AnswerKey | None:
    """Look up an AnswerKey by spec_id first (most specific), then normalized
    question text. Returns None if unrecognized — graceful degradation, logged
    for offline curation, never an error and never an invented key."""
    if spec_id and spec_id in _BY_SPEC_ID:
        return _BY_SPEC_ID[spec_id]
    key = _BY_QUESTION.get(_qkey(question_text))
    if key is None:
        logger.info("No answer-key table entry for question %r (spec_id=%r) — logged for offline curation",
                    question_text, spec_id)
    return key


def registered_count() -> int:
    return len(_BY_QUESTION) + len(_BY_SPEC_ID)


# ── Seed fixtures: the eight Phase-3 diagnostic questions (minimal, representative) ──
register_answer_key(
    "Why does a composite index on (user_id, created_at) help a query that filters by user_id and orders by created_at?",
    AnswerKey(
        key_points=(
            "A composite index lets the database satisfy the filter and the ordering from one index scan without a separate sort.",
            "The leading index column handles the equality lookup while the next column supplies sorted order.",
        ),
        misconceptions=(
            "PostgreSQL automatically merges two single-column indexes into a composite index.",
            "The composite index is faster only because it is smaller and stays cached in RAM.",
        )))
register_answer_key(
    "What is the difference between a process and a thread?",
    AnswerKey(
        key_points=(
            "Threads of the same process share one address space.",
            "Processes have separate isolated address spaces.",
        ),
        misconceptions=(
            "Each thread has its own isolated address space just like a process.",
            "Threads share CPU registers so only one thread's register state exists at a time.",
        )))
register_answer_key(
    "Why is TCP reliable while UDP is not?",
    AnswerKey(
        key_points=(
            "TCP retransmits lost segments using acknowledgements and sequence numbers.",
            "UDP provides no acknowledgement, retransmission, or ordering.",
        ),
        misconceptions=(
            "TCP is reliable because it reserves a dedicated physical circuit that cannot drop packets.",
            "TCP sends every packet twice along two paths and keeps whichever arrives first.",
        )))
register_answer_key(
    "What does the CAP theorem force a distributed system to trade off during a network partition?",
    AnswerKey(
        key_points=(
            "During a network partition a system must choose between consistency and availability.",
            "Partition tolerance is not optional in a real network.",
        ),
        misconceptions=(
            "A system permanently picks two of the three CAP properties for its whole lifetime.",
            "Most relational databases are CA and give up partition tolerance entirely.",
        )))
register_answer_key(
    "How do you prevent a race condition when multiple threads increment a shared counter?",
    AnswerKey(
        key_points=(
            "A mutex or an atomic fetch-and-add makes the increment a single indivisible operation.",
            "Without synchronization two threads can read the same value and lose an update.",
        ),
        misconceptions=(
            "Declaring the counter volatile makes the increment atomic across threads.",
            "Giving each thread a thread-local copy and summing them avoids the race.",
        )))
register_answer_key(
    "Why is the average lookup time of a hash table O(1)?",
    AnswerKey(
        key_points=(
            "A hash function maps a key to a bucket in constant time.",
            "Keeping the load factor bounded keeps the average bucket occupancy constant.",
        ),
        misconceptions=(
            "A perfect hash guarantees no collisions ever occur regardless of the number of keys.",
            "A hash table keeps its keys sorted and binary-searches the buckets.",
        )))
register_answer_key(
    "Why is accuracy a poor primary metric for a fraud model with a 0.1% positive rate?",
    AnswerKey(
        key_points=(
            "With a very low positive rate, predicting all-negative yields high accuracy while catching no fraud.",
            "Precision and recall on the positive class are the informative metrics.",
        ),
        misconceptions=(
            "Oversampling to a balanced set makes accuracy and F1 always agree so accuracy becomes the right metric.",
            "Scaling the model until 100 percent training accuracy removes the imbalance problem.",
        )))
register_answer_key(
    "What makes an HTTP endpoint idempotent, and why does it matter for retries?",
    AnswerKey(
        key_points=(
            "An idempotent endpoint produces the same server state whether called once or many times.",
            "An idempotency key lets the server dedupe a retried request.",
        ),
        misconceptions=(
            "An endpoint is idempotent when it responds fast enough that the client never retries.",
            "Only GET requests can be idempotent because any write changes state.",
        )))
