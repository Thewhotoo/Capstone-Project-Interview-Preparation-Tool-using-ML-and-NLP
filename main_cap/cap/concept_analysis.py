"""
Shared lexical concept analysis.

    concept_analysis  (this module)
        ├── strong_answer.build_improved_answer   (which concepts to insert)
        └── concept_pool / missing_concepts        (pool reconstruction, still
            lexical-overlap based -- used by the Improved Answer feature above)

`concept_coverage_percent` (the dashboard's Concept Coverage %) is DELIBERATELY
NOT part of that lexical-overlap pipeline as of the production-audit fix below
-- it is derived directly from `EvaluationResult.concept_coverage`, the exact
per-concept DEMONSTRATED/SUPERFICIAL/OMITTED list already shown to the user,
so the percentage and the visible breakdown can never disagree.

FOUND DURING A REAL END-TO-END DEMO: the percentage used to be computed by
re-scanning the raw answer text with this module's OWN independent lexical
detector (`concept_expressed`), entirely decoupled from the `status` values
already computed (by the evaluator) for the SAME concepts in
`result.concept_coverage`. The two could and did disagree -- the same 5
concepts, all shown "omitted" in the array, produced 20%/40%/0% on different
turns, because the percentage was never actually reading that array. Fixed by
making the percentage a pure function of `result.concept_coverage`'s own
statuses (see `concept_coverage_percent` below) -- no new concept-mastery
model, no change to how the evaluator decides a concept's status.

Method (unchanged, still used by `concept_pool`/`missing_concepts` for the
Improved Answer feature): deterministic, lightweight lexical overlap --
normalise -> tokenise -> common-prefix word match against each concept's
DISTINCTIVE word. So "Network Security" is recognised from
"security"/"secure"/"secured", "Sensor Integration" from
"sensor"/"sensors", "Real-time Monitoring" from
"monitor"/"monitoring"/"real time". No NLP libraries, no embeddings.

DeBERTa / the evaluator / scoring are untouched by this module either way.
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


# Credit per per-concept status, applied deterministically in
# `concept_coverage_percent` below. DEMONSTRATED = full credit, OMITTED =
# zero -- unambiguous from the schema itself (evaluation_result.py).
# SUPERFICIAL (mentioned but not clearly demonstrated) is intentionally
# worth partial, not full or zero, credit -- there is no pre-existing
# documented weight for it elsewhere in the codebase, so this is the
# smallest reasonable, explicit choice consistent with the schema's own
# three-way distinction (a superficial mention is genuinely worth more
# than an omission and genuinely worth less than a demonstration).
_STATUS_CREDIT: dict[ConceptObservationStatus, float] = {
    ConceptObservationStatus.DEMONSTRATED: 1.0,
    ConceptObservationStatus.SUPERFICIAL: 0.5,
    ConceptObservationStatus.OMITTED: 0.0,
}


def concept_coverage_percent(result: EvaluationResult) -> Optional[float]:
    """The dashboard's Concept Coverage % for one turn, as a percentage
    (0-100) -- derived DETERMINISTICALLY from `result.concept_coverage`,
    the exact per-concept DEMONSTRATED/SUPERFICIAL/OMITTED list already
    shown to the user, so the percentage and the visible breakdown can
    never disagree (see module docstring for the bug this replaced).
    Returns None when `result.concept_coverage` is empty -- no concept pool
    for this question (e.g. experience/certification turns), never treated
    as 0%; the caller must exclude those turns from any average."""
    pool = result.concept_coverage
    if not pool:
        return None
    total_credit = sum(_STATUS_CREDIT[obs.status] for obs in pool)
    return round(100.0 * total_credit / len(pool), 1)
