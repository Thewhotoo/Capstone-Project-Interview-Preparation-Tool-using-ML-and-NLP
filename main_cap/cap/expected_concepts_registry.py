"""
Expected Concepts Registry — approved ML RFC extension (Expected Concepts,
final revision). Implemented exactly as approved: Option B (hand-curated,
growable lookup table), consulted entirely inside the orchestration layer
(`evaluation_engine.py`).

WHY THIS DESIGN (see the approved RFC for the full comparison): expected
concepts are a property of the GROUNDING (which technology/project/
certification is actually named), not of the answer — they are knowable
before the candidate ever speaks. They must therefore be deterministically
looked up, never predicted by a model and never invented. This module is
that lookup, mirroring the same open, registry-style extensibility pattern
already proven in `question_families.py` (`register_family`).

Zero Planning-layer schema changes (QuestionSpecification/Planner/
TopicPool are untouched). Zero Candidate Profile Generator changes. Zero
live Gemini calls — a name not found here degrades gracefully to an empty
list for that turn (never an error, never invented) and is logged for
OFFLINE, asynchronous curation (a human, or a scheduled batch job, adds a
table entry later) — never a dependency of the live evaluation path.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, tuple[str, ...]] = {}


class DuplicateExpectedConceptsEntryError(ValueError):
    """Raised by `register_expected_concepts` if a name is already
    registered — re-registering under the same name would silently shadow
    an existing entry rather than genuinely adding a new one (same
    discipline as `question_families.register_family`)."""


def register_expected_concepts(name: str, concepts: tuple[str, ...]) -> None:
    """Register the canonical expected-concept list for `name` (a
    technology, concept, or certification name — matched case-insensitively
    against grounding fields at lookup time)."""
    key = name.strip().lower()
    if not key:
        raise ValueError("name must not be empty")
    if not concepts:
        raise ValueError(f"concepts for {name!r} must not be empty")
    if key in _REGISTRY:
        raise DuplicateExpectedConceptsEntryError(f"{name!r} is already registered")
    _REGISTRY[key] = tuple(concepts)


def lookup(name: str) -> tuple[str, ...]:
    """Look up one name's registered expected concepts, or an empty tuple
    if unrecognized — graceful degradation, never an error."""
    return _REGISTRY.get(name.strip().lower(), ())


def expected_concepts_for(candidate_names: tuple[str, ...]) -> tuple[str, ...]:
    """
    Look up expected concepts for every candidate grounding name (typically
    a project's technologies + concepts + title, or a certification's
    name), deduplicated, in stable first-seen order. Unrecognized names
    contribute nothing and are logged for offline curation — this function
    NEVER raises for an unrecognized name and NEVER invents a concept not
    present in the registry.
    """
    seen: list[str] = []
    seen_set: set[str] = set()
    for name in candidate_names:
        found = lookup(name)
        if not found:
            logger.info(
                "No expected-concepts table entry for %r — logged for offline curation", name,
            )
            continue
        for concept in found:
            if concept not in seen_set:
                seen_set.add(concept)
                seen.append(concept)
    return tuple(seen)


def registered_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY.keys()))


# ── Seed entries — matching the approved RFC's own worked examples ─────────
register_expected_concepts("fastapi", (
    "ASGI", "async request handling", "dependency injection", "routing", "modularity",
))
register_expected_concepts("langgraph", (
    "graph nodes", "state transitions", "orchestration", "agents", "workflow execution",
))
register_expected_concepts("rag", (
    "retrieval", "embeddings", "vector search", "chunking", "grounding",
))
register_expected_concepts("retrieval-augmented generation", (
    "retrieval", "embeddings", "vector search", "chunking", "grounding",
))
