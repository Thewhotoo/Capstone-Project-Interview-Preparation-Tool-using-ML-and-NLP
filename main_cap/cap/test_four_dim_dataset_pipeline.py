"""Tests for the Step-3 four-dimension dataset-generation infrastructure.

Covers dimension profiles + hard cases, the independent rubric judge,
target-vs-judge agreement, leakage/quality filters, group-aware splitting,
the human-benchmark schema isolation, the acceptance gate, and a mocked
end-to-end run (target -> generate -> judge -> validate -> accept/reject ->
TrainingExample). No test calls a real Gemini API; the generation client and
judge are mocked.
"""

from __future__ import annotations

import ast
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import four_dim_dataset
from dataset_acceptance import AcceptanceConfig, evaluate_dataset
from dataset_filters import (
    check_example,
    duplicate_answer_counts,
    exact_qa_duplicate_indices,
    find_banned_phrases,
    near_duplicate_pairs,
    questions_over_cap,
)
from dimension_profiles import (
    HARD_CASES,
    DimensionProfile,
    coherent_profile,
    generation_guidance,
    sample_profile,
)
from evaluation_dimensions import CANONICAL_DIMENSIONS, EvaluationDimension
from four_dim_dataset import (
    LabeledExample,
    assemble_profiled_prompt,
    generate_and_label,
    profile_to_quality_tier,
    split_labeled,
)
from generation_client import GenerationOutput
from generation_recipe import GenerationRecipe
from human_benchmark import (
    HUMAN_BENCHMARK_ID_PREFIX,
    AdjudicationStatus,
    HumanAnnotation,
    HumanBenchmarkItem,
    HumanDimensionLabel,
    assert_disjoint_from_training,
)
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from rubric_judge import (
    JudgeVerdict,
    MismatchPolicy,
    build_judge_prompt,
    compute_agreement,
    judge_all_dimensions,
)
from training_example import QualityTier


# ── helpers / mocks ──────────────────────────────────────────────────────────

def _spec(source_id="RD Platform", techs=("Redis",)) -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="caching",
        grounding=Grounding(project=ProjectGrounding(title=source_id, technologies=techs, concepts=("Caching",))),
        source_type=SourceType.PROJECT, source_id=source_id, source_field="interview_seeds", reason="test",
    )


def _recipe(recipe_id="r1", source_id="RD Platform", tier=QualityTier.GOOD) -> GenerationRecipe:
    return GenerationRecipe(
        recipe_id=recipe_id, specification=_spec(source_id=source_id),
        question_text="How did you handle caching?", reasoning_type=ReasoningType.EXPLANATION,
        expected_concepts=(), quality_tier=tier, concept_targets=(), reasoning_targets=(),
        diversity_seed="diversity_001", style_seed="style_001",
    )


_CLEAN_ANSWER = "I built the caching layer myself and handled invalidation and retries carefully."


class MockClient:
    model_name = "mock-generator-v1"

    def __init__(self, answer=_CLEAN_ANSWER):
        self._answer = answer

    def generate(self, prompt):
        return GenerationOutput(answer_text=self._answer, concept_evidence=[], contradiction_note="")


class MockJudge:
    """Returns caller-specified scores per dimension — never a network call."""

    judge_version = "mock-judge-v1"

    def __init__(self, scores: dict[EvaluationDimension, int]):
        self._scores = scores

    def judge_dimension(self, dimension, question_text, answer_text, grounding_text, expected_concepts):
        return JudgeVerdict(
            dimension=dimension.value, score=self._scores[dimension],
            rationale="mock", judge_version=self.judge_version,
        )


def _scores(c, d, r, g) -> dict:
    return {
        EvaluationDimension.TECHNICAL_CORRECTNESS: c,
        EvaluationDimension.DEPTH_SPECIFICITY: d,
        EvaluationDimension.RELEVANCE_COMPLETENESS: r,
        EvaluationDimension.GROUNDING_OWNERSHIP: g,
    }


# ── 1-2. dimension keys + hard cases ─────────────────────────────────────────

def test_canonical_dimension_keys():
    assert [d.value for d in CANONICAL_DIMENSIONS] == [
        "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
    ]


def test_hard_case_matrix_matches_approved_vectors():
    # J and K were repaired post seed_v1 forensic analysis (see
    # dimension_profiles.py's REPAIR comment): the originally-approved
    # vectors coupled dimensions the rubric declares independent. This test
    # pins the CURRENT approved vectors, not the original Step-1 ones.
    expected = {
        "A": (4, 1, 3, 2), "B": (4, 4, 4, 3), "C": (1, 3, 3, 2), "D": (3, 2, 1, 3),
        "E": (1, 3, 4, 2), "F": (3, 4, 0, 2), "G": (4, 3, 3, 0), "H": (4, 4, 4, 4),
        "I": (2, 1, 3, 1), "J": (4, 2, 3, 0), "K": (4, 1, 4, 1), "L": (4, 4, 3, 1),
    }
    assert set(HARD_CASES) == set(expected)
    for key, vec in expected.items():
        assert HARD_CASES[key].as_tuple() == vec


# ── 3. serialization ─────────────────────────────────────────────────────────

def test_profile_roundtrip():
    p = HARD_CASES["H"]
    assert DimensionProfile.from_dict(p.as_dict()) == p
    assert DimensionProfile.from_tuple(p.as_tuple()) == p


def test_profile_validation_rejects_out_of_range():
    with pytest.raises(ValueError):
        DimensionProfile(technical_correctness=5, depth_specificity=0, relevance_completeness=0, grounding_ownership=0)


def test_sample_profile_is_deterministic():
    a = sample_profile("seed-x", hard_case_ratio=0.5)
    b = sample_profile("seed-x", hard_case_ratio=0.5)
    assert a == b


def test_coherent_profile_stays_near_base_tier():
    p = coherent_profile(2, "seed-y")
    assert all(1 <= t <= 3 for t in p.as_tuple())


# ── 4. profile -> generation metadata (no self-describing quality leak) ──────

def test_generation_guidance_includes_all_dimensions_and_is_deterministic():
    g1 = generation_guidance(HARD_CASES["B"])
    g2 = generation_guidance(HARD_CASES["B"])
    assert g1 == g2
    for d in CANONICAL_DIMENSIONS:
        assert d.value in g1


def test_generation_guidance_never_contains_banned_quality_phrases():
    for key, profile in HARD_CASES.items():
        assert find_banned_phrases(generation_guidance(profile)) == [], key


# ── 5. judge output + prompt ─────────────────────────────────────────────────

def test_judge_verdict_validation():
    JudgeVerdict(dimension="technical_correctness", score=3, judge_version="v")  # ok
    with pytest.raises(ValueError):
        JudgeVerdict(dimension="not_a_dim", score=3, judge_version="v")
    with pytest.raises(ValueError):
        JudgeVerdict(dimension="technical_correctness", score=9, judge_version="v")


def test_build_judge_prompt_contains_rubric_context_and_answer():
    system, user = build_judge_prompt(
        EvaluationDimension.GROUNDING_OWNERSHIP, "Q about caching?", "my answer text",
        "RD Platform Redis Caching", ("caching",),
    )
    assert "Grounding & Ownership" in system
    assert "QUESTION:" in user and "Q about caching?" in user
    assert "RELEVANT CONTEXT:" in user and "RD Platform" in user
    assert "EXPECTED CONCEPTS:" in user and "caching" in user
    assert "my answer text" in user


def test_judge_all_dimensions_returns_all_four():
    judge = MockJudge(_scores(4, 3, 2, 1))
    verdicts = judge_all_dimensions(judge, "q", "a", "ctx", ())
    assert set(verdicts) == set(CANONICAL_DIMENSIONS)
    assert verdicts[EvaluationDimension.TECHNICAL_CORRECTNESS].score == 4


# ── 6. agreement ─────────────────────────────────────────────────────────────

def test_agreement_within_and_outside_tolerance():
    profile = HARD_CASES["H"]  # 4,4,4,4
    verdicts = MockJudge(_scores(4, 3, 4, 4))  # depth off by 1 -> acceptable
    report = compute_agreement(profile, judge_all_dimensions(verdicts, "q", "a", "c", ()))
    assert report.all_acceptable and report.max_delta == 1

    verdicts2 = MockJudge(_scores(4, 1, 4, 4))  # depth off by 3 -> not acceptable
    report2 = compute_agreement(profile, judge_all_dimensions(verdicts2, "q", "a", "c", ()))
    assert not report2.all_acceptable and report2.max_delta == 3


# ── 7. mismatch rejection vs relabel-keep; labels come from judge ────────────

def test_mismatch_is_discarded_under_default_policy():
    profile = HARD_CASES["H"]  # 4,4,4,4
    judge = MockJudge(_scores(4, 1, 4, 4))  # depth delta 3
    result = generate_and_label(
        _recipe(), profile, MockClient(), judge, profile_id="H", generation_batch_id="b1",
    )
    assert not result.accepted
    assert any("target_judge_mismatch" in r for r in result.reject_reasons)


def test_mismatch_kept_under_relabel_keep_with_judge_labels():
    profile = HARD_CASES["H"]  # target 4,4,4,4
    judge = MockJudge(_scores(2, 2, 2, 2))  # judge disagrees a lot
    result = generate_and_label(
        _recipe(), profile, MockClient(), judge, profile_id="H", generation_batch_id="b1",
        policy=MismatchPolicy.RELABEL_KEEP,
    )
    assert result.accepted
    labels = {d.name: d.score for d in result.example.labels.dimension_labels}
    # labels reflect the JUDGE (2/4 = 0.5), NOT the target (4/4 = 1.0)
    assert labels["technical_correctness"] == 0.5


def test_labels_come_from_judge_not_target_on_accept():
    profile = HARD_CASES["H"]  # target 4 across
    judge = MockJudge(_scores(3, 4, 4, 4))  # correctness judged 3 (within tol)
    result = generate_and_label(
        _recipe(), profile, MockClient(), judge, profile_id="H", generation_batch_id="b1",
    )
    assert result.accepted
    labels = {d.name: d.score for d in result.example.labels.dimension_labels}
    assert labels["technical_correctness"] == 0.75  # 3/4, the judge's score, not 1.0


# ── 8. banned-phrase + filters ───────────────────────────────────────────────

def test_banned_phrase_detection():
    assert find_banned_phrases("I mentioned briefly the cache.")
    assert find_banned_phrases("demonstrated with concrete functional detail")
    assert find_banned_phrases("This is a strong answer overall.")
    assert find_banned_phrases("generated to target the good tier")
    assert find_banned_phrases("a clean, specific explanation of caching") == []


def test_check_example_rejects_leaky_answer():
    v = check_example("I mentioned briefly how it works.", allowed_technologies=())
    assert not v.accepted


def test_check_example_rejects_hallucinated_technology():
    v = check_example("I deployed it on Kubernetes with Kafka.", allowed_technologies=("Redis",))
    assert not v.accepted
    assert any("hallucinated_technology" in r for r in v.reasons)


# ── 9. duplicate detection ───────────────────────────────────────────────────

def test_exact_and_answer_duplicate_detection():
    pairs = [("q1", "a"), ("q1", "a"), ("q2", "b")]
    assert exact_qa_duplicate_indices(pairs) == [1]
    assert duplicate_answer_counts(["a", "a", "b"]) == {"a": 2}


def test_near_duplicate_with_injected_similarity():
    answers = ["alpha", "beta", "gamma"]
    def sim(a, b):
        return 0.99 if {a, b} == {"alpha", "beta"} else 0.0
    hits = near_duplicate_pairs(answers, threshold=0.9, similarity_fn=sim)
    assert hits == [(0, 1, 0.99)]


def test_answer_per_question_cap():
    pairs = [("q1", f"a{i}") for i in range(5)] + [("q2", "a")]
    assert questions_over_cap(pairs, cap=3) == {"q1": 5}


# ── 10. group-aware split (leak-free) ────────────────────────────────────────

def _accepted_example(source_id, question, answer, profile_id="H"):
    judge = MockJudge(_scores(4, 4, 4, 4))
    recipe = GenerationRecipe(
        recipe_id=f"r_{source_id}_{question}", specification=_spec(source_id=source_id),
        question_text=question, reasoning_type=ReasoningType.EXPLANATION, expected_concepts=(),
        quality_tier=QualityTier.GOOD, concept_targets=(), reasoning_targets=(),
        diversity_seed="d", style_seed="s",
    )
    return generate_and_label(
        recipe, HARD_CASES[profile_id], MockClient(answer=answer), judge,
        profile_id=profile_id, generation_batch_id="b", group_key=source_id,
    )


def test_group_split_keeps_sources_and_answers_within_one_split():
    labeled = []
    for src in ("ProjA", "ProjB", "ProjC", "ProjD", "ProjE", "ProjF"):
        labeled.append(_accepted_example(src, f"Q about {src}?", f"I built {src} carefully and shipped it myself."))
    split = split_labeled(labeled, split_ratios=(0.6, 0.2, 0.2), seed="seed1")
    # Every accepted example must appear in exactly one split
    all_ids = set(split.train_ids) | set(split.val_ids) | set(split.test_ids)
    accepted_ids = {le.example.metadata.example_id for le in labeled if le.accepted}
    assert accepted_ids == all_ids
    # Acceptance-gate leakage checks must pass on this split
    report = evaluate_dataset(labeled, split, AcceptanceConfig(min_distinct_sources=1, min_hard_case_coverage=1))
    for name in ("no_cross_split_leakage_answers", "no_cross_split_leakage_questions", "no_cross_split_leakage_source_ids"):
        assert report.get(name).passed


# ── 11. human benchmark isolation ────────────────────────────────────────────

def _human_item(item_id="hb_1", q="Q?", a="A real answer here.", source="ProjA"):
    labels = tuple(HumanDimensionLabel(dimension=d.value, score=3) for d in CANONICAL_DIMENSIONS)
    ann = HumanAnnotation(annotator_id="ann1", rubric_version="v1", dimension_labels=labels)
    return HumanBenchmarkItem(item_id=item_id, question_text=q, answer_text=a, grounding_source=source, annotations=(ann,))


def test_human_item_requires_namespace_and_is_not_training_example():
    from training_example import TrainingExample
    item = _human_item()
    assert item.item_id.startswith(HUMAN_BENCHMARK_ID_PREFIX)
    assert not isinstance(item, TrainingExample)
    with pytest.raises(ValueError):
        HumanBenchmarkItem(item_id="no_prefix", question_text="q", answer_text="a", grounding_source="s")


def test_human_annotation_requires_all_four_dimensions():
    partial = (HumanDimensionLabel(dimension="technical_correctness", score=3),)
    with pytest.raises(ValueError):
        HumanAnnotation(annotator_id="a", rubric_version="v", dimension_labels=partial)


def test_assert_disjoint_from_training_flags_shared_pair():
    le = _accepted_example("ProjA", "Shared Q?", "Shared answer text here.")
    training = [le.example]
    conflicting = _human_item(q="Shared Q?", a="Shared answer text here.")
    with pytest.raises(ValueError):
        assert_disjoint_from_training([conflicting], training)
    # a disjoint item is fine
    assert_disjoint_from_training([_human_item(q="Different?", a="Different answer.")], training)


# ── 12. acceptance gate behavior ─────────────────────────────────────────────

def test_acceptance_gate_reports_and_correlation_is_diagnostic():
    labeled = [_accepted_example(f"Proj{i}", f"Q{i}?", f"I built Proj{i} myself and shipped it carefully.") for i in range(6)]
    split = split_labeled(labeled, seed="seed2")
    report = evaluate_dataset(labeled, split, AcceptanceConfig(min_distinct_sources=1))
    corr = report.get("four_dimension_correlation_DIAGNOSTIC")
    assert corr is not None and corr.passed is None  # diagnostic, never a hard pass/fail
    assert report.get("all_four_dimensions_present").passed
    # correlation not being computable/high must not drag the hard verdict:
    assert isinstance(report.passed, bool)


def test_acceptance_gate_fails_on_banned_phrase():
    good = _accepted_example("ProjA", "QA?", "I built ProjA myself carefully.")
    bad = _accepted_example("ProjB", "QB?", "I built ProjB and mentioned briefly the cache.")
    # `bad` should have been rejected at generation; force a leaky accepted example
    # by constructing the acceptance input directly to test the gate itself.
    labeled = [good]
    # inject a leaky example bypassing the per-example filter to prove the gate catches it too
    leaky = good.example.model_copy(update={
        "inputs": good.example.inputs.model_copy(update={"answer_text": "I mentioned briefly the cache."}),
    })
    labeled_with_leak = [good, LabeledExample(
        accepted=True, profile_id="H", group_key="ProjZ", profile=HARD_CASES["H"], example=leaky,
    )]
    split = split_labeled(labeled_with_leak, seed="s")
    report = evaluate_dataset(labeled_with_leak, split, AcceptanceConfig(min_distinct_sources=1))
    assert not report.get("no_banned_quality_phrases").passed
    assert not report.passed


# ── determinism + profile->tier + no FakeGenerationClient ────────────────────

def test_assemble_profiled_prompt_deterministic_and_has_guidance():
    p = HARD_CASES["B"]
    a = assemble_profiled_prompt(_recipe(), p)
    b = assemble_profiled_prompt(_recipe(), p)
    assert a.user_text == b.user_text
    assert "per-aspect targets" in a.user_text


def test_profile_to_quality_tier_mapping():
    assert profile_to_quality_tier(HARD_CASES["H"]) == QualityTier.EXCELLENT   # 4,4,4,4
    assert profile_to_quality_tier(HARD_CASES["I"]) in (QualityTier.WEAK, QualityTier.ADEQUATE)  # 2,1,3,1 -> avg 1.75


def test_pipeline_does_not_reference_fake_generation_client():
    # Checks actual imports/usage (AST names), not the module's own prose --
    # the docstring legitimately explains "FakeGenerationClient NOT used
    # here", which would false-positive on a raw substring check.
    src = inspect.getsource(four_dim_dataset)
    tree = ast.parse(src)
    names = set()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imported_names.add(alias.asname or alias.name)
    assert "FakeGenerationClient" not in names
    assert "FakeGenerationClient" not in imported_names
    assert not hasattr(four_dim_dataset, "FakeGenerationClient")


def test_end_to_end_mocked_accept_produces_training_example():
    from training_example import TrainingExample
    profile = HARD_CASES["H"]
    judge = MockJudge(_scores(4, 4, 4, 4))
    result = generate_and_label(
        _recipe(), profile, MockClient(), judge, profile_id="H", generation_batch_id="batch-1",
    )
    assert result.accepted
    assert isinstance(result.example, TrainingExample)
    assert result.example.provenance.source.value == "synthetic"
    assert {d.name for d in result.example.labels.dimension_labels} == {d.value for d in CANONICAL_DIMENSIONS}
    assert result.example.labels.label_source == "synthetic_ground_truth"
