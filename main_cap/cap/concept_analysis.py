"""
Shared lexical concept analysis.

This is the SINGLE source of concept-coverage detection in the system. Both
consumers depend on it, so they can never disagree:

    concept_analysis  (this module)
        ├── strong_answer.build_improved_answer   (which concepts to insert)
        └── conversation_engine -> dashboard      (Concept Coverage %)

It is deliberately NOT part of the Improved Answer feature — the dashboard
depends on this shared module, never on strong_answer.py.

Method: deterministic, lightweight lexical overlap — normalise -> tokenise ->
common-prefix word match against each concept's DISTINCTIVE word. So "Network
Security" is recognised from "security"/"secure"/"secured", "Sensor
Integration" from "sensor"/"sensors", "Real-time Monitoring" from
"monitor"/"monitoring"/"real time". No NLP libraries, no embeddings.

DeBERTa / the evaluator / scoring are untouched: this reads only the
question's grounding concepts, the deterministically-derived expected concepts
(expected_concepts_registry), the candidate's answer text, and — as extra pool
members — the evaluator's already-computed non-demonstrated ConceptObservations.
"""

from __future__ import annotations

import re
from typing import Optional

from evaluation_result import ConceptObservationStatus, EvaluationResult
from expected_concepts_registry import expected_concepts_for
from interview_question import InterviewQuestion

# Generic connective/scaffolding words that never make a concept distinctive.
_GENERIC_TOKENS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "with",
    "system", "systems", "based", "using", "use", "management",
})

# Minimum shared leading characters for two DIFFERENT tokens to count as the
# same word stem. 5 unifies security/secure, sensor/sensors, monitor/monitoring,
# transmission/transmitted, integration/integrating, while staying long enough
# to avoid loose collisions.
_PREFIX_MATCH_LEN = 5


def _tokens(text: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9]+", " ", text.lower()).split() if t]


def _token_match(a: str, b: str) -> bool:
    """True if two tokens are the same word or share a long enough stem
    (common leading prefix), covering simple inflections/derivations."""
    if a == b:
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return common >= _PREFIX_MATCH_LEN


def _dedup_list(items: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        k = it.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it.strip())
    return out


def _distinctive_tokens(concept: str, pool_counts: dict[str, int]) -> list[str]:
    """The concept's own words minus generic scaffolding and minus words shared
    across two-or-more concepts in the same project (e.g. 'network' in both
    'Network Design' and 'Network Security'). Falls back to all significant
    words when nothing is uniquely distinctive."""
    significant = [t for t in _tokens(concept) if t not in _GENERIC_TOKENS]
    distinctive = [t for t in significant if pool_counts.get(t, 0) <= 1]
    return distinctive or significant


def concept_expressed(concept: str, answer_tokens: set[str], pool_counts: dict[str, int]) -> bool:
    """A concept is already expressed if any of its distinctive words appears
    (in any inflected form) among the candidate's own words."""
    for dt in _distinctive_tokens(concept, pool_counts):
        if any(_token_match(dt, at) for at in answer_tokens):
            return True
    return False


def concept_pool(question: InterviewQuestion, result: EvaluationResult) -> list[str]:
    """The set of concepts this turn is judged against: project grounding
    concepts + registry-derived expected concepts + any concepts the evaluator
    marked omitted/superficial. Empty for experience/certification turns (no
    project grounding). Deduplicated, order-preserving. Nothing invented."""
    proj = question.specification.grounding.project
    pool: list[str] = []
    if proj is not None:
        pool.extend(proj.concepts)
        pool.extend(expected_concepts_for((*proj.technologies, *proj.concepts, proj.title)))
    pool.extend(
        obs.concept for obs in result.concept_coverage
        if obs.status is not ConceptObservationStatus.DEMONSTRATED
    )
    return _dedup_list(tuple(pool))


def _pool_counts(pool: list[str]) -> dict[str, int]:
    """Per-turn word frequency across the pool, to spot non-distinctive shared
    words like 'network'."""
    counts: dict[str, int] = {}
    for concept in pool:
        for t in set(_tokens(concept)):
            if t not in _GENERIC_TOKENS:
                counts[t] = counts.get(t, 0) + 1
    return counts


def missing_concepts(
    question: InterviewQuestion, result: EvaluationResult, answer_text: str, limit: int,
) -> list[str]:
    """Pool concepts the candidate has NOT already expressed (by lexical
    overlap), capped at `limit`. Used by the Improved Answer generator."""
    pool = concept_pool(question, result)
    if not pool:
        return []
    answer_tokens = set(_tokens(answer_text))
    counts = _pool_counts(pool)
    missing = [c for c in pool if not concept_expressed(c, answer_tokens, counts)]
    return missing[:limit]


def concept_coverage_percent(
    question: InterviewQuestion, result: EvaluationResult, answer_text: str,
) -> Optional[float]:
    """Fraction of this turn's concept pool the candidate expressed, as a
    percentage (0-100), using the SAME lexical detector as `missing_concepts`
    so the two can never disagree. Returns None when there is no concept pool
    for the question (e.g. experience/certification turns) — the caller must
    exclude those turns from any average rather than treating them as 0%."""
    pool = concept_pool(question, result)
    if not pool:
        return None
    answer_tokens = set(_tokens(answer_text))
    counts = _pool_counts(pool)
    covered = sum(1 for c in pool if concept_expressed(c, answer_tokens, counts))
    return round(100.0 * covered / len(pool), 1)
