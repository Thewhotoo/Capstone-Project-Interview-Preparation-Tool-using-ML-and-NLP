"""Fast, model-free tests for resume_evidence_evaluator's scoring logic:
the evidence composition (never rewards length) and the concreteness signal.
Model-backed behavior (real similarity/contradiction) is exercised by the
adversarial smoke, not here."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resume_evidence_evaluator import EvidenceBreakdown, _compose_overall, _concreteness

NV = "not_independently_verified"


def _ev(relevance, grounding, concreteness, ownership, flags=()):
    return EvidenceBreakdown(relevance, grounding, concreteness, ownership, NV, tuple(flags))


def test_short_concrete_beats_long_vague():
    short_good = _ev(0.70, 0.70, 0.85, 0.80)     # short but concrete + grounded
    long_vague = _ev(0.55, 0.15, 0.05, 0.20)     # verbose but no grounding/specifics
    assert _compose_overall(short_good) > _compose_overall(long_vague)
    assert _compose_overall(short_good) >= 0.60
    assert _compose_overall(long_vague) <= 0.40


def test_non_answer_is_capped_low():
    assert _compose_overall(_ev(0.6, 0.6, 0.6, 0.6, flags=("non_answer",))) <= 0.10


def test_degenerate_is_capped_low():
    assert _compose_overall(_ev(0.6, 0.6, 0.6, 0.6, flags=("degenerate:keyword_dump_low_function_words",))) <= 0.10


def test_generic_textbook_is_penalized():
    base = _ev(0.8, 0.2, 0.1, 0.2)
    generic = _ev(0.8, 0.2, 0.1, 0.2, flags=("generic_textbook",))
    assert _compose_overall(generic) < _compose_overall(base)


def test_conflicting_ownership_penalized():
    base = _ev(0.6, 0.5, 0.5, 0.5)
    conflict = _ev(0.6, 0.5, 0.5, 0.15, flags=("unsupported_or_conflicting_ownership",))
    assert _compose_overall(conflict) < _compose_overall(base)


def test_overall_never_rewards_length_directly():
    # identical evidence, only "length" would differ — but length is not an input,
    # so two answers with the same evidence get the same score by construction.
    a = _ev(0.6, 0.6, 0.6, 0.6)
    assert _compose_overall(a) == _compose_overall(_ev(0.6, 0.6, 0.6, 0.6))


def test_concreteness_rewards_numbers_and_resume_terms_not_length():
    terms = ("Redis", "PostgreSQL")
    concrete_short, n_num, n_term = _concreteness(
        "I cut p95 from 2s to 50ms with a Redis cache.", "i cut p95 from 2s to 50ms with a redis cache.", terms)
    vague_long, _, _ = _concreteness(
        "We worked really hard on it and iterated a lot and in the end everyone on the team was quite happy "
        "with how responsive and polished the whole thing turned out to be after all our effort.",
        "we worked really hard ...", terms)
    assert concrete_short > 0.5
    assert vague_long == 0.0
    assert concrete_short > vague_long


def test_concreteness_no_terms_uses_numbers_only():
    score, _, _ = _concreteness("reduced latency to 40 ms and 3 nines", "reduced latency to 40 ms and 3 nines", ())
    assert score > 0.0
