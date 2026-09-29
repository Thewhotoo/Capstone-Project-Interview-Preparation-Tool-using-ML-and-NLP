"""Tests for correctness_nli_scorer.py — the isolated, keyless, reference-
anchored evaluator. Model-free: the NLI/embedding models are INJECTED as
deterministic fakes so the suite is fast and needs no downloads. The real
models are exercised by the read-only benchmark, not here (same discipline the
repo uses elsewhere: heavy pretrained weights stay out of unit tests)."""

from __future__ import annotations

import os
import re
import sys
import hashlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from correctness_nli_scorer import (
    AnswerKey,
    CorrectnessNLIEvaluator,
    CoverageNLIScorer,
    DictClaimBank,
    degeneracy,
)
from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


# ── deterministic degeneracy gate (no model) ─────────────────────────────────

def test_degeneracy_flags_empty():
    assert degeneracy("").is_degenerate
    assert degeneracy("ok").is_degenerate  # near-empty (<3 tokens)


def test_degeneracy_flags_keyword_dump():
    kw = "hash table hash function bucket collision chaining open addressing load factor resize"
    assert degeneracy(kw).is_degenerate
    assert "keyword_dump_low_function_words" in degeneracy(kw).reasons


def test_degeneracy_does_not_flag_concise_correct():
    # A short, real technical answer must never be flagged (conservative gate).
    for a in [
        "A hash function maps a key to a bucket in constant time, and a bounded load factor keeps buckets small.",
        "Guard the increment with a mutex or an atomic add so the read-modify-write is indivisible.",
        "TCP retransmits lost segments using acknowledgements; UDP does not.",
    ]:
        assert not degeneracy(a).is_degenerate, a


def test_degeneracy_flags_pure_repetition():
    assert degeneracy("cache cache cache cache cache cache cache").is_degenerate


def test_degeneracy_flags_markup_code_control_and_symbol_soup():
    assert degeneracy("<script>alert('x')</script><b>I built</b> it").is_degenerate
    assert degeneracy("def handler(req):\n    return db.query('SELECT * FROM t')").is_degenerate
    assert degeneracy("'; DROP TABLE candidates; -- and then Redis").is_degenerate
    assert degeneracy("answer with \x00\x01\x02 embedded control bytes here").is_degenerate
    assert degeneracy("123 456 0.5 99% 40ms 2s 10x 88 :: ;; %%").is_degenerate


def test_degeneracy_does_not_flag_prose_with_numbers_or_semicolons():
    # Real technical answers contain numbers, hyphens and semicolons — must NOT be flagged.
    for a in [
        "I cut p95 from 1.8s to 40ms with a Redis cache in front of Postgres.",
        "TCP retransmits lost segments using acknowledgements; UDP does not.",
        "I used JWT with refresh tokens and cached the public keys in Redis.",
    ]:
        assert not degeneracy(a).is_degenerate, a


# ── injected fakes (order: [contradiction, entailment, neutral]) ─────────────

def fake_nli(pairs):
    out = []
    for premise, hyp in pairs:
        pw = set(re.findall(r"[a-z]+", premise.lower()))
        hw = set(re.findall(r"[a-z]+", hyp.lower()))
        overlap = len(pw & {w for w in hw if len(w) > 3})
        out.append([0.0, 4.0, 0.0] if overlap >= 3 else [0.0, 0.0, 3.0])  # entail vs neutral
    return out


def fake_embed(texts):
    vecs = []
    for t in texts:
        h = np.frombuffer(hashlib.md5(t.encode()).digest(), dtype=np.uint8).astype(float)[:16]
        n = np.linalg.norm(h) or 1.0
        vecs.append(h / n)
    return np.array(vecs)


def _scorer():
    return CoverageNLIScorer(nli_predict=fake_nli, embed=fake_embed)


def test_correct_answer_scores_higher_than_misconception():
    key = AnswerKey(
        key_points=("A hash function maps a key to a bucket in constant time.",),
        misconceptions=("A perfect hash guarantees no collisions ever occur.",),
    )
    s = _scorer()
    correct = s.score_answer(
        "A hash function maps a key directly to a bucket in constant time.", key)
    wrong = s.score_answer(
        "A perfect hash guarantees no collisions ever occur regardless of keys.", key)
    assert correct["technical_correctness"] > wrong["technical_correctness"]
    assert wrong["misconception_hit"] > 0.5  # the wrong answer entailed the known misconception


def test_degenerate_answer_is_gated_down():
    key = AnswerKey(key_points=("A hash function maps a key to a bucket in constant time.",))
    s = _scorer()
    kw = s.score_answer("hash table bucket collision chaining load factor resize probe", key)
    assert kw["degenerate"] and kw["technical_correctness"] <= 0.1


def test_length_independence_short_correct_not_penalized():
    key = AnswerKey(key_points=("A mutex makes the increment a single indivisible operation.",))
    s = _scorer()
    short = s.score_answer("A mutex makes the increment a single indivisible operation.", key)
    assert short["technical_correctness"] >= 0.6  # short but correct → high, not penalized


# ── Evaluator Protocol conformance / EvaluationResult shape ──────────────────

def _request(question, answer, expected=(), answer_key=None):
    grounding = Grounding(project=ProjectGrounding(title="Hashing", technologies=("Python",)))
    spec = QuestionSpecification(
        id="spec1", category=QuestionCategory.SKILL_IN_CONTEXT, text_seed="Hashing",
        grounding=grounding, source_type=SourceType.PROJECT, source_id="s1",
        source_field="skills", reason="test")
    return EvaluationRequest(
        request_id="r1", requested_at="2026-09-29T00:00:00Z", specification=spec,
        question_text=question, reasoning_type=ReasoningType.EXPLANATION,
        answer_text=answer, conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=tuple(expected), answer_key=answer_key)


def test_evaluator_returns_valid_result():
    bank = DictClaimBank(by_spec_id={"spec1": AnswerKey(
        key_points=("A hash function maps a key to a bucket in constant time.",),
        misconceptions=("A perfect hash guarantees no collisions ever occur.",))})
    ev = CorrectnessNLIEvaluator(claim_bank=bank, scorer=_scorer())
    res = ev.evaluate(_request("Why is hash lookup O(1)?",
                               "A hash function maps a key directly to a bucket in constant time."))
    assert 0.0 <= res.overall_score <= 1.0
    assert res.grade in {"excellent", "good", "adequate", "weak", "poor"}
    assert len(res.dimensions) == 4  # four canonical diagnostic dimensions preserved
    assert res.evaluator_name == "correctness-nli-scorer-v1"
    assert 0.0 <= res.confidence <= 1.0


def test_evaluator_correctness_gates_overall():
    bank = DictClaimBank(by_spec_id={"spec1": AnswerKey(
        key_points=("A hash function maps a key to a bucket in constant time.",),
        misconceptions=("A perfect hash guarantees no collisions ever occur.",))})
    ev = CorrectnessNLIEvaluator(claim_bank=bank, scorer=_scorer())
    correct = ev.evaluate(_request("Why O(1)?",
                                   "A hash function maps a key directly to a bucket in constant time."))
    wrong = ev.evaluate(_request("Why O(1)?",
                                 "A perfect hash guarantees no collisions ever occur regardless of keys."))
    assert correct.overall_score > wrong.overall_score


def test_claim_bank_falls_back_to_expected_concepts():
    ev = CorrectnessNLIEvaluator(claim_bank=DictClaimBank(), scorer=_scorer())
    res = ev.evaluate(_request("Q?", "some answer text about hashing buckets", expected=("hashing",)))
    assert 0.0 <= res.overall_score <= 1.0  # graceful degradation, no crash
    assert res.confidence_source == "expected_concepts_only"
    assert "PARTIAL correctness" in res.reasoning


# ── AnswerKey flows through the request (production path) ─────────────────────

_KEY = AnswerKey(
    key_points=("A hash function maps a key to a bucket in constant time.",),
    misconceptions=("A perfect hash guarantees no collisions ever occur.",))


def test_request_answer_key_is_received_and_used_full_mode():
    ev = CorrectnessNLIEvaluator(claim_bank=None, scorer=_scorer())  # no claim bank; key comes from request
    correct = ev.evaluate(_request(
        "Why O(1)?", "A hash function maps a key directly to a bucket in constant time.", answer_key=_KEY))
    wrong = ev.evaluate(_request(
        "Why O(1)?", "A perfect hash guarantees no collisions ever occur regardless of keys.", answer_key=_KEY))
    assert correct.reasoning.startswith("Reference-anchored correctness")  # FULL mode
    assert correct.confidence_source == "nli_margin_derived"
    assert correct.overall_score > wrong.overall_score  # misconception detected


def test_no_answer_key_makes_fallback_explicit():
    ev = CorrectnessNLIEvaluator(claim_bank=None, scorer=_scorer())
    res = ev.evaluate(_request("Some unknown question?",
                               "A fluent, plausible-sounding technical answer with no key to grade against."))
    assert res.confidence_source == "no_answer_key_fallback"
    assert "CORRECTNESS NOT EVALUATED" in res.reasoning
    assert res.confidence <= 0.3
    assert len(res.dimensions) == 4  # diagnostic dimensions still present


def test_no_key_empty_answer_is_zero():
    ev = CorrectnessNLIEvaluator(claim_bank=None, scorer=_scorer())
    res = ev.evaluate(_request("Q?", ""))
    assert res.overall_score == 0.0 and res.grade == "poor"


# ── registry + orchestration lookup ──────────────────────────────────────────

def test_registry_returns_key_for_seeded_question_and_none_otherwise():
    from answer_key_registry import lookup
    seeded = "Why is the average lookup time of a hash table O(1)?"
    key = lookup(question_text=seeded)
    assert key is not None and key.has_key_points and key.misconceptions
    assert lookup(question_text="a totally unregistered question about llamas") is None


def test_evaluation_engine_lookup_answer_key_wires_registry():
    import types
    from evaluation_engine import _lookup_answer_key
    seeded = "Why is TCP reliable while UDP is not?"
    key = _lookup_answer_key(types.SimpleNamespace(id="unmatched_spec"), seeded)
    assert key is not None and key.has_key_points
    assert _lookup_answer_key(types.SimpleNamespace(id="unmatched_spec"), "unknown question") is None
