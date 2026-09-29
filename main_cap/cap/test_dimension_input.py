"""Tests for Step 2: feeding grounding + expected concepts into the DeBERTa
dimension-model input.

Covers the deterministic construction of the contextual input, inclusion of
each element, safe handling of missing context, preservation of the
max_length tokenization safeguard, and that the existing evaluator still runs
end-to-end (no crash) with and without context. Uses the tiny random backbone
(never a full pretrained download).
"""

from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from model_backbone import (
    BackboneConfig,
    bounded_grounding_to_text,
    build_dimension_input_text,
    build_dimension_pair,
    build_tiny_random_encoder,
    build_tokenizer,
    grounding_to_text,
    tokenize_pair,
)
from model_evaluator import TrainedEvaluator
from model_heads import MultiTaskModel
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from training_experimentation import ExperimentConfig, assemble_checkpoint

_TOKENIZER = build_tokenizer(BackboneConfig())


# ── grounding_to_text ────────────────────────────────────────────────────────

def _project_grounding():
    return types.SimpleNamespace(
        project=types.SimpleNamespace(
            title="RD Platform", summary="A caching layer.",
            technologies=("Python", "Redis"), concepts=("Caching",),
        ),
        experience=None, certification=None,
    )


def test_grounding_to_text_project():
    text = grounding_to_text(_project_grounding())
    assert "RD Platform" in text and "Redis" in text and "Caching" in text


def test_grounding_to_text_experience():
    g = types.SimpleNamespace(
        project=None,
        experience=types.SimpleNamespace(role="Intern", company="HAL", summary="Did research."),
        certification=None,
    )
    text = grounding_to_text(g)
    assert "Intern" in text and "HAL" in text and "research" in text


def test_grounding_to_text_certification():
    g = types.SimpleNamespace(
        project=None, experience=None,
        certification=types.SimpleNamespace(name="AWS Certified"),
    )
    assert grounding_to_text(g) == "AWS Certified"


def test_grounding_to_text_empty_when_nothing_present():
    g = types.SimpleNamespace(project=None, experience=None, certification=None)
    assert grounding_to_text(g) == ""


# ── bounded_grounding_to_text (Phase 1 production input correction) ───────────
# The deployed single-overall-score checkpoint was trained on short grounding
# (median ~15 words, max 60); a full résumé summary (~85-92 words) is far
# out-of-distribution and collapses answer sensitivity. bounded_grounding_to_text
# caps ONLY the free-text summary while preserving title/technologies/concepts/
# role/company in full. grounding_to_text itself is unchanged (training/eval
# depend on it) -- see the tests above, which must still pass unmodified.

_LONG_SUMMARY = (
    "FraudScore is a real-time fraud detection platform I built to score incoming card "
    "transactions in under fifty milliseconds. It ingests a stream of transaction events, "
    "engineers velocity and device-fingerprint features, and feeds them to a gradient boosted "
    "tree model that the payments team consumes through a low-latency API."
)  # ~50 words, multiple sentences; first sentence ~19 words


def _long_project_grounding():
    return types.SimpleNamespace(
        project=types.SimpleNamespace(
            title="FraudScore", summary=_LONG_SUMMARY,
            technologies=("Python", "XGBoost"), concepts=("gradient boosting", "class imbalance"),
        ),
        experience=None, certification=None,
    )


def test_bounded_preserves_title_technologies_concepts():
    text = bounded_grounding_to_text(_long_project_grounding())
    for must in ("FraudScore", "Python", "XGBoost", "gradient boosting", "class imbalance"):
        assert must in text, f"bounded grounding dropped {must!r}"


def test_bounded_shortens_long_summary_to_first_sentence():
    text = bounded_grounding_to_text(_long_project_grounding())
    # First sentence (~19 words) fits the cap and is kept; later sentences are dropped.
    assert "under fifty milliseconds" in text
    assert "device-fingerprint" not in text  # from the dropped 2nd sentence


def test_bounded_is_substantially_shorter_than_unbounded_for_production_summary():
    g = _long_project_grounding()
    unbounded = grounding_to_text(g)
    bounded = bounded_grounding_to_text(g)
    assert len(bounded.split()) < len(unbounded.split())
    # The whole point of Phase 1: the bounded context lands in the training band.
    assert len(bounded.split()) <= 30


def test_bounded_leaves_short_summary_unchanged_ordering():
    # A summary already within the cap is preserved verbatim (whitespace-normalised).
    g = types.SimpleNamespace(
        project=types.SimpleNamespace(
            title="RD Platform", summary="A caching layer.",
            technologies=("Python", "Redis"), concepts=("Caching",),
        ),
        experience=None, certification=None,
    )
    assert bounded_grounding_to_text(g) == grounding_to_text(g)


def test_bounded_handles_empty_summary():
    g = types.SimpleNamespace(
        project=types.SimpleNamespace(
            title="RD Platform", summary="", technologies=("Python",), concepts=(),
        ),
        experience=None, certification=None,
    )
    assert bounded_grounding_to_text(g) == "RD Platform Python"


def test_bounded_word_caps_a_single_overlong_sentence():
    # No sentence boundary within the cap -> safe hard word cap on real text.
    long_run = "word " * 60  # 60 words, no punctuation
    g = types.SimpleNamespace(
        project=types.SimpleNamespace(
            title="T", summary=long_run.strip(), technologies=(), concepts=(),
        ),
        experience=None, certification=None,
    )
    text = bounded_grounding_to_text(g)
    # title (1) + 25 summary words = 26 tokens; never more.
    assert len(text.split()) <= 26


def test_bounded_experience_caps_summary_preserves_role_company():
    g = types.SimpleNamespace(
        project=None,
        experience=types.SimpleNamespace(
            role="Backend Engineer", company="Acme",
            summary=_LONG_SUMMARY,
        ),
        certification=None,
    )
    text = bounded_grounding_to_text(g)
    assert "Backend Engineer" in text and "Acme" in text
    assert "device-fingerprint" not in text  # long tail dropped
    assert len(text.split()) <= 30


def test_bounded_certification_unchanged():
    g = types.SimpleNamespace(
        project=None, experience=None,
        certification=types.SimpleNamespace(name="AWS Certified"),
    )
    assert bounded_grounding_to_text(g) == "AWS Certified"


def test_bounded_empty_when_nothing_present():
    g = types.SimpleNamespace(project=None, experience=None, certification=None)
    assert bounded_grounding_to_text(g) == ""


# ── build_dimension_input_text ───────────────────────────────────────────────

def test_input_is_deterministic():
    a = build_dimension_input_text("Q?", "some context", ("caching", "ttl"))
    b = build_dimension_input_text("Q?", "some context", ("caching", "ttl"))
    assert a == b


def test_input_includes_question():
    text = build_dimension_input_text("How did you build it?", "ctx", ())
    assert "QUESTION:" in text
    assert "How did you build it?" in text


def test_input_includes_grounding_when_available():
    text = build_dimension_input_text("Q?", "RD Platform Redis Caching", ())
    assert "RELEVANT CONTEXT:" in text
    assert "RD Platform Redis Caching" in text


def test_input_includes_expected_concepts_when_available():
    text = build_dimension_input_text("Q?", "", ("caching", "invalidation"))
    assert "EXPECTED CONCEPTS:" in text
    assert "caching, invalidation" in text


def test_missing_grounding_and_concepts_are_omitted_safely():
    text = build_dimension_input_text("Q?", "", ())
    assert "QUESTION:" in text
    assert "RELEVANT CONTEXT:" not in text
    assert "EXPECTED CONCEPTS:" not in text


def test_empty_and_whitespace_inputs_do_not_crash():
    assert build_dimension_input_text("", "", ()) == "QUESTION:\n"
    # whitespace-only / falsy concepts are dropped, not emitted as blanks
    text = build_dimension_input_text("Q", "   ", ("", "  ", "real"))
    assert "RELEVANT CONTEXT:" not in text
    assert "EXPECTED CONCEPTS:\nreal" in text


# ── build_dimension_pair ─────────────────────────────────────────────────────

def test_pair_returns_context_and_answer():
    context, answer = build_dimension_pair("Q?", "ctx", ("c1",), "my answer")
    assert context.startswith("QUESTION:")
    assert "RELEVANT CONTEXT:" in context
    assert answer == "my answer"          # answer is preserved as segment B
    assert "my answer" not in context     # answer is NOT duplicated into text_a


def test_pair_handles_empty_answer():
    _, answer = build_dimension_pair("Q?", "", (), None)
    assert answer == ""


# ── tokenization safeguards ──────────────────────────────────────────────────

def test_tokenization_respects_max_length():
    context = build_dimension_input_text(
        "Why did you choose this?" * 40, "very long grounding " * 60, tuple(f"concept{i}" for i in range(40)),
    )
    long_answer = "a detailed answer " * 60
    encoding = tokenize_pair(_TOKENIZER, context, long_answer, max_length=32)
    assert len(encoding["input_ids"]) <= 32


def test_tokenization_preserves_answer_tokens_under_truncation():
    # HF longest-first truncation trims the (long) context before the (short)
    # answer, so a short answer survives even with a huge context.
    context = build_dimension_input_text("Q " * 200, "ctx " * 200, ())
    encoding = tokenize_pair(_TOKENIZER, context, "unique_answer_token", max_length=64)
    decoded = _TOKENIZER.decode(encoding["input_ids"])
    assert "unique_answer" in decoded.replace(" ", "")


# ── existing evaluator still runs end-to-end (no crash) ──────────────────────

def _tiny_evaluator() -> TrainedEvaluator:
    backbone = build_tiny_random_encoder(_TOKENIZER, hidden_size=16)
    model = MultiTaskModel(BackboneConfig(), backbone=backbone)
    config = ExperimentConfig(backbone_name="microsoft/deberta-v3-base", random_seed=1, dataset_version="v1")
    checkpoint = assemble_checkpoint(model_version="m1", experiment_config=config, artifact_uri="in-memory-test")
    return TrainedEvaluator(checkpoint, model, _TOKENIZER, BackboneConfig(max_length=32))


def _request(*, expected_concepts=("caching",), with_grounding=True) -> EvaluationRequest:
    grounding = (
        Grounding(project=ProjectGrounding(title="RD Platform", technologies=("Python", "Redis"), concepts=("Caching",)))
        if with_grounding else Grounding(project=ProjectGrounding(title="X"))
    )
    spec = QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="Redis caching",
        grounding=grounding, source_type=SourceType.PROJECT, source_id="RD Platform",
        source_field="interview_seeds", reason="test",
    )
    return EvaluationRequest(
        request_id="r1", requested_at="2026-07-24T00:00:00+00:00", specification=spec,
        question_text="Did Redis caching give you trouble?", reasoning_type=ReasoningType.DEBUGGING,
        answer_text="I fixed a cache invalidation bug in Redis.",
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=expected_concepts,
    )


def test_evaluator_runs_with_full_context():
    result = _tiny_evaluator().evaluate(_request(with_grounding=True, expected_concepts=("caching",)))
    assert result.dimensions  # produced a result without raising


def test_evaluator_runs_with_empty_context():
    result = _tiny_evaluator().evaluate(_request(with_grounding=False, expected_concepts=()))
    assert result.dimensions  # empty grounding/concepts must not crash the new input path
