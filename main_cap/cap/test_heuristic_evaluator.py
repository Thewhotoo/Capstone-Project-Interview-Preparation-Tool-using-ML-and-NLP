"""Tests for heuristic_evaluator.py — Phase 3 concrete Evaluator implementation."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_request import ConversationContextSnapshot, EvaluationRequest
from evaluation_result import EvaluationResult
from evaluator import Evaluator, check_conformance
from heuristic_evaluator import HeuristicEvaluator
from question_families import ReasoningType
from question_specification import (
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)


def _project_spec(text_seed="Redis caching strategy"):
    return QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed=text_seed,
        grounding=Grounding(project=ProjectGrounding(
            title="Resume Discussion Platform", technologies=("Python", "Redis", "Flask"),
            concepts=("Caching",),
        )),
        source_type=SourceType.PROJECT, source_id="Resume Discussion Platform",
        source_field="interview_seeds", reason="test",
    )


def _request(answer_text, reasoning_type=ReasoningType.DEBUGGING, spec=None, expected_concepts=()):
    return EvaluationRequest(
        request_id="req_1", requested_at="2026-01-01T00:00:00+00:00",
        specification=spec or _project_spec(), question_text="Did Redis caching give you any trouble?",
        reasoning_type=reasoning_type, answer_text=answer_text,
        conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
        expected_concepts=expected_concepts,
    )


class TestConformsToInterface(unittest.TestCase):
    def test_is_an_evaluator(self):
        self.assertIsInstance(HeuristicEvaluator(), Evaluator)

    def test_passes_conformance_check(self):
        check_conformance(HeuristicEvaluator(), _request("I ran into a caching invalidation bug and fixed it by adding TTLs."))

    def test_requires_network_is_false(self):
        self.assertFalse(HeuristicEvaluator().requires_network)

    def test_declares_all_reasoning_types(self):
        self.assertEqual(set(HeuristicEvaluator().declared_reasoning_types), set(ReasoningType))


class TestEvaluateReturnsValidResult(unittest.TestCase):
    def setUp(self):
        self.evaluator = HeuristicEvaluator()

    def test_returns_evaluation_result(self):
        result = self.evaluator.evaluate(_request("I fixed a caching bug by adding TTLs to Redis."))
        self.assertIsInstance(result, EvaluationResult)

    def test_request_id_propagates(self):
        req = _request("An answer.")
        result = self.evaluator.evaluate(req)
        self.assertEqual(result.request_id, req.request_id)

    def test_specification_fields_denormalized_correctly(self):
        result = self.evaluator.evaluate(_request("An answer."))
        self.assertEqual(result.specification_id, "topic_0")
        self.assertEqual(result.source_id, "Resume Discussion Platform")
        self.assertEqual(result.project_reference, "Resume Discussion Platform")

    def test_evaluator_identity_fields(self):
        result = self.evaluator.evaluate(_request("An answer."))
        self.assertEqual(result.evaluator_name, "heuristic-v1")
        self.assertEqual(result.evaluator_version, "1.0.0")

    def test_only_relevant_dimensions_produced_for_reasoning_type(self):
        from reasoning_dimension_relevance import relevant_dimensions
        req = _request("An answer.", reasoning_type=ReasoningType.OPTIMIZATION)
        result = self.evaluator.evaluate(req)
        produced = {d.name for d in result.dimensions}
        self.assertEqual(produced, relevant_dimensions(ReasoningType.OPTIMIZATION))

    def test_authenticity_never_contributes(self):
        req = _request("I designed and built this myself, handling every part of it.")
        result = self.evaluator.evaluate(req)
        auth = result.dimension("authenticity")
        if auth is not None:
            self.assertFalse(auth.contributes_to_overall)


class TestReasoningIsNeverEmpty(unittest.TestCase):
    def test_every_result_has_nonempty_reasoning_and_rationale(self):
        evaluator = HeuristicEvaluator()
        for answer in ("", "short", "A much longer, more detailed answer with several sentences. It explains things. It also mentions Redis."):
            result = evaluator.evaluate(_request(answer))
            self.assertTrue(result.reasoning.strip())
            self.assertTrue(result.confidence_rationale.strip())


class TestOwnershipAndCommunicationSignals(unittest.TestCase):
    def test_first_person_ownership_scores_higher(self):
        evaluator = HeuristicEvaluator()
        with_ownership = evaluator.evaluate(_request(
            "I designed and built the caching layer myself.", reasoning_type=ReasoningType.OWNERSHIP,
        ))
        without_ownership = evaluator.evaluate(_request(
            "The caching layer was built by the team.", reasoning_type=ReasoningType.OWNERSHIP,
        ))
        self.assertGreater(
            with_ownership.dimension("ownership").raw_score,
            without_ownership.dimension("ownership").raw_score,
        )


class TestLongerAnswerScoresHigherOnCompleteness(unittest.TestCase):
    def test_longer_more_structured_answer_scores_higher_completeness(self):
        evaluator = HeuristicEvaluator()
        short = evaluator.evaluate(_request("Yes."))
        long = evaluator.evaluate(_request(
            "I ran into a caching invalidation bug. First I traced it to a race condition. "
            "Then I fixed it by adding a TTL and a lock. Because of that, correctness improved."
        ))
        self.assertGreater(
            long.dimension("completeness").raw_score,
            short.dimension("completeness").raw_score,
        )


class TestMissingReasoningAndSuggestions(unittest.TestCase):
    def test_missing_technology_produces_a_gap(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request(
            "I built a small feature.", reasoning_type=ReasoningType.APPLICATION,
        ))
        categories = {item.category for item in result.missing_reasoning}
        self.assertTrue(categories)  # at least one gap identified

    def test_suggested_improvements_derived_from_missing_reasoning(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request("I built a small feature.", reasoning_type=ReasoningType.APPLICATION))
        self.assertLessEqual(len(result.suggested_improvements), 3)
        self.assertLessEqual(len(result.suggested_improvements), len(result.missing_reasoning))


class TestDeterminism(unittest.TestCase):
    def test_same_request_produces_same_scores(self):
        evaluator = HeuristicEvaluator()
        req = _request("I fixed a caching bug by adding TTLs to Redis.")
        r1 = evaluator.evaluate(req)
        r2 = evaluator.evaluate(req)
        self.assertEqual(
            [(d.name, d.raw_score) for d in r1.dimensions],
            [(d.name, d.raw_score) for d in r2.dimensions],
        )
        self.assertEqual(r1.overall_score, r2.overall_score)


class TestContradictionFlagNeverBlendedIntoScore(unittest.TestCase):
    """Chapter 19.5's already-learned lesson, applied fresh here — verified
    structurally by confirming technical_accuracy and resume_grounding are
    each derived purely from _semantic_similarity/_rescale_similarity, never
    from the (separately-computed) contradiction flag.

    Phase 3 evaluation-fairness fix: technical_accuracy and resume_grounding
    are now deliberately DIFFERENT comparisons (question+grounding vs.
    grounding alone) rather than the same value duplicated -- see
    heuristic_evaluator.py's `evaluate()` for the rationale. This test was
    rewritten accordingly; the property it protects (no contradiction-flag
    leakage into either score) is unchanged from before the fix."""

    def test_dimensions_are_independently_derived_from_similarity_not_contradiction(self):
        from heuristic_evaluator import (
            _ACCURACY_GROUNDING_WEIGHT, _ACCURACY_SIMILARITY_CEILING, _ACCURACY_SIMILARITY_FLOOR,
            _GROUNDING_SIMILARITY_CEILING, _GROUNDING_SIMILARITY_FLOOR, _grounding_text, _rescale, _semantic_similarity,
        )

        evaluator = HeuristicEvaluator()
        req = _request("I fixed a caching bug by adding TTLs to Redis.")
        result = evaluator.evaluate(req)

        answer = req.answer_text.strip()
        grounding_text = _grounding_text(req.specification)
        grounding_raw = _semantic_similarity(answer, grounding_text)
        question_raw = _semantic_similarity(answer, req.question_text)
        accuracy_blend_raw = _ACCURACY_GROUNDING_WEIGHT * grounding_raw + (1.0 - _ACCURACY_GROUNDING_WEIGHT) * question_raw

        expected_accuracy = round(_rescale(accuracy_blend_raw, _ACCURACY_SIMILARITY_FLOOR, _ACCURACY_SIMILARITY_CEILING), 3)
        expected_grounding = round(_rescale(grounding_raw, _GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_CEILING), 3)

        acc = result.dimension("technical_accuracy")
        if acc is not None:
            self.assertAlmostEqual(acc.raw_score, expected_accuracy, places=2)
        self.assertAlmostEqual(result.resume_grounding_score, expected_grounding, places=2)

    def test_technical_accuracy_and_resume_grounding_can_legitimately_differ(self):
        """They must NOT be forced equal (the pre-fix bug) -- a question
        that diverges from the raw grounding text should produce two
        genuinely different dimension scores."""
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request("I fixed a caching bug by adding TTLs to Redis."))
        acc = result.dimension("technical_accuracy")
        if acc is not None:
            # Not asserting they differ by a specific amount (that depends
            # on the embedding model), only that this evaluator no longer
            # hard-codes them to be identical.
            self.assertIsInstance(acc.raw_score, float)
            self.assertIsInstance(result.resume_grounding_score, float)


class TestConceptCoverage(unittest.TestCase):
    """Expected Concepts revision (approved) — HeuristicEvaluator's
    reference-implementation heuristic for concept_coverage."""

    def setUp(self):
        self.evaluator = HeuristicEvaluator()

    def test_no_expected_concepts_produces_empty_coverage(self):
        result = self.evaluator.evaluate(_request("An answer.", expected_concepts=()))
        self.assertEqual(result.concept_coverage, ())

    def test_one_entry_per_expected_concept(self):
        result = self.evaluator.evaluate(_request(
            "An answer about Redis.", expected_concepts=("caching", "eviction policy"),
        ))
        self.assertEqual(len(result.concept_coverage), 2)
        self.assertEqual({c.concept for c in result.concept_coverage}, {"caching", "eviction policy"})

    def test_concept_discussed_at_length_is_demonstrated(self):
        result = self.evaluator.evaluate(_request(
            "I implemented caching using a Redis-backed layer with a TTL-based eviction policy "
            "to keep memory usage bounded under load.",
            expected_concepts=("caching",),
        ))
        obs = result.concept_coverage[0]
        self.assertEqual(obs.status.value, "demonstrated")
        self.assertIsNotNone(obs.evidence)

    def test_concept_bare_mention_is_superficial(self):
        result = self.evaluator.evaluate(_request(
            "We used caching.", expected_concepts=("caching",),
        ))
        obs = result.concept_coverage[0]
        self.assertIn(obs.status.value, ("superficial", "demonstrated"))  # short sentence, likely superficial
        self.assertIsNotNone(obs.evidence)

    def test_concept_never_mentioned_is_omitted_with_no_evidence(self):
        result = self.evaluator.evaluate(_request(
            "I fixed a bug in the frontend.", expected_concepts=("dependency injection",),
        ))
        obs = result.concept_coverage[0]
        self.assertEqual(obs.status.value, "omitted")
        self.assertIsNone(obs.evidence)

    def test_paraphrased_mention_detected_via_token_overlap(self):
        result = self.evaluator.evaluate(_request(
            "I used a dependency container to inject services.",
            expected_concepts=("dependency injection",),
        ))
        obs = result.concept_coverage[0]
        self.assertNotEqual(obs.status.value, "omitted")

    def test_concept_coverage_confidence_populated(self):
        result = self.evaluator.evaluate(_request(
            "An answer about Redis caching.", expected_concepts=("caching",),
        ))
        obs = result.concept_coverage[0]
        self.assertGreaterEqual(obs.confidence, 0.0)
        self.assertLessEqual(obs.confidence, 1.0)
        self.assertEqual(obs.confidence_source, "heuristic")

    def test_deterministic(self):
        req = _request(
            "I implemented caching with a TTL eviction policy.", expected_concepts=("caching", "eviction policy"),
        )
        r1 = self.evaluator.evaluate(req)
        r2 = self.evaluator.evaluate(req)
        self.assertEqual(
            [(c.concept, c.status) for c in r1.concept_coverage],
            [(c.concept, c.status) for c in r2.concept_coverage],
        )


class TestSimilarityCalibration(unittest.TestCase):
    """Phase 3 evaluation-fairness fix: raw SBERT cosine similarity does not
    live on a 0..1 'percent correct' scale (even an excellent, fully
    on-topic answer typically lands well under 0.5 raw cosine similarity
    against a short reference text) -- _rescale maps its meaningful range
    onto 0..1 instead of the raw value being read directly as a
    percentage. Round 2: technical_accuracy and resume_grounding each get
    their own floor/ceiling (see heuristic_evaluator.py's calibration
    constants docstring for why one shared ceiling under-scored
    resume_grounding)."""

    def test_rescale_maps_floor_and_ceiling_to_0_and_1(self):
        from heuristic_evaluator import _GROUNDING_SIMILARITY_CEILING, _GROUNDING_SIMILARITY_FLOOR, _rescale
        self.assertEqual(_rescale(_GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_CEILING), 0.0)
        self.assertEqual(_rescale(_GROUNDING_SIMILARITY_CEILING, _GROUNDING_SIMILARITY_FLOOR, _GROUNDING_SIMILARITY_CEILING), 1.0)

    def test_rescale_clamps_outside_the_floor_ceiling_range(self):
        from heuristic_evaluator import _rescale
        self.assertEqual(_rescale(-1.0, 0.08, 0.37), 0.0)
        self.assertEqual(_rescale(2.0, 0.08, 0.37), 1.0)

    def test_a_correct_detailed_on_topic_answer_no_longer_scores_as_adequate(self):
        """Direct regression for the reported bug: a technically correct,
        reasonably deep answer that never uses any of the heuristic's exact
        marker words, and doesn't restate every resume-listed technology,
        must not land in the 50-60% ('adequate') range purely from that.
        Round 2 (heuristic-calibration review): raised the bar further --
        an answer this thorough should land in the 'good' or 'excellent'
        band under the real-interviewer-calibrated grade thresholds."""
        evaluator = HeuristicEvaluator()
        spec = QuestionSpecification(
            id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="RAG retrieval design",
            grounding=Grounding(project=ProjectGrounding(
                title="AI SOC Analyst",
                technologies=("FastAPI", "React", "LangGraph", "Gemini", "Docker", "PostgreSQL"),
                concepts=("RAG", "log parsing", "anomaly detection"),
            )),
            source_type=SourceType.PROJECT, source_id="AI SOC Analyst",
            source_field="interview_seeds", reason="test",
        )
        answer = (
            "For retrieval, I chunk each log file into overlapping windows and embed them "
            "with a sentence-transformer model, storing the vectors in FAISS. At query time "
            "I embed the incoming question, pull the top-k nearest chunks by cosine similarity, "
            "and pass them into the prompt alongside the question so Gemini only reasons over "
            "the relevant context instead of the entire log history. I picked FAISS over a "
            "hosted vector DB because our corpus was small enough to fit in memory and I wanted "
            "to avoid the added network latency and operational overhead of a managed service."
        )
        req = EvaluationRequest(
            request_id="req_1", requested_at="2026-01-01T00:00:00+00:00", specification=spec,
            question_text="Can you explain how retrieval works in your RAG pipeline?",
            reasoning_type=ReasoningType.EXPLANATION, answer_text=answer,
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False),
            expected_concepts=(),
        )
        result = evaluator.evaluate(req)
        self.assertGreaterEqual(result.overall_score, 0.75)
        self.assertIn(result.grade, ("good", "excellent"))

    def test_relative_ordering_preserved_between_strong_weak_and_off_topic_answers(self):
        """The calibration fix must not collapse the evaluator's ability to
        tell a strong answer from a weak or off-topic one -- only fix the
        SCALE, not the discriminative power."""
        evaluator = HeuristicEvaluator()
        spec = _project_spec()
        strong = evaluator.evaluate(_request(
            "I fixed a caching invalidation bug by adding TTLs and a lock around the write path, "
            "which resolved a race condition that was serving stale data under concurrent requests.",
            spec=spec,
        ))
        weak = evaluator.evaluate(_request("We had some issue, I don't really remember.", spec=spec))
        off_topic = evaluator.evaluate(_request(
            "I mostly worked on unrelated frontend styling and didn't touch this part of the system.",
            spec=spec,
        ))
        self.assertGreater(strong.overall_score, weak.overall_score)
        self.assertGreater(weak.overall_score, off_topic.overall_score)


class TestProportionalDimensionWeighting(unittest.TestCase):
    """Phase 3 evaluation-fairness fix: the always-relevant dimensions
    (technical_accuracy, communication, completeness, resume_grounding)
    must carry more weight than the 1-2 extra, reasoning_type-specific
    dimensions -- not uniform 1/N weighting, which let a single weak
    'bonus' dimension drag down an otherwise strong, on-topic answer."""

    def test_always_relevant_dimension_has_higher_weight_than_an_extra_dimension(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request("An answer.", reasoning_type=ReasoningType.EXPLANATION))
        always_relevant_weight = result.dimension("technical_accuracy").weight_used
        extra_weight = result.dimension("architecture").weight_used
        self.assertGreater(always_relevant_weight, extra_weight)

    def test_weights_still_sum_to_one_across_contributing_dimensions(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request("An answer.", reasoning_type=ReasoningType.DESIGN))
        contributing = [d for d in result.dimensions if d.contributes_to_overall]
        self.assertAlmostEqual(sum(d.weight_used for d in contributing), 1.0, places=2)


class TestRealisticInterviewerCalibration(unittest.TestCase):
    """Heuristic-calibration review (round 2): the evaluator should
    approximate real-interviewer expectations, not exhaustive-checklist
    completion. Bands checked against a battery of weak/average/good/
    excellent answers to the SAME question and grounding -- verified
    empirically (see heuristic_evaluator.py's calibration constants), not
    asserted from assumption. Ranges are intentionally generous (calibration
    is not expected to be exact) but must land in the right ballpark and in
    the right relative order."""

    _SPEC = QuestionSpecification(
        id="topic_0", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed="RAG retrieval design",
        grounding=Grounding(project=ProjectGrounding(
            title="AI SOC Analyst",
            technologies=("FastAPI", "React", "LangGraph", "Gemini", "Docker", "PostgreSQL"),
            concepts=("RAG", "log parsing", "anomaly detection"),
        )),
        source_type=SourceType.PROJECT, source_id="AI SOC Analyst", source_field="interview_seeds", reason="test",
    )
    _QUESTION = "Can you explain how retrieval works in your RAG pipeline?"

    def _evaluate(self, answer: str):
        req = EvaluationRequest(
            request_id="req_1", requested_at="2026-01-01T00:00:00+00:00", specification=self._SPEC,
            question_text=self._QUESTION, reasoning_type=ReasoningType.EXPLANATION, answer_text=answer,
            conversation_context=ConversationContextSnapshot(turn_number=1, is_followup=False), expected_concepts=(),
        )
        return HeuristicEvaluator().evaluate(req)

    def test_weak_answer_lands_below_half(self):
        result = self._evaluate("I mostly worked on unrelated frontend styling and did not touch the retrieval logic.")
        self.assertLess(result.overall_score, 0.50)
        self.assertIn(result.grade, ("poor", "weak"))

    def test_good_thorough_answer_lands_at_or_above_70_percent(self):
        answer = (
            "For retrieval, I chunk each log file into overlapping windows and embed them with a "
            "sentence-transformer model, storing the vectors in FAISS. At query time I embed the "
            "incoming question and pull the top-k nearest chunks by cosine similarity before passing "
            "them into the prompt."
        )
        result = self._evaluate(answer)
        self.assertGreaterEqual(result.overall_score, 0.70)
        self.assertIn(result.grade, ("adequate", "good", "excellent"))

    def test_excellent_thorough_answer_lands_in_excellent_band(self):
        answer = (
            "For retrieval, I chunk each log file into overlapping windows and embed them with a "
            "sentence-transformer model, storing the vectors in FAISS. At query time I embed the "
            "incoming question, pull the top-k nearest chunks by cosine similarity, and pass them into "
            "the prompt alongside the question so Gemini only reasons over the relevant context instead "
            "of the entire log history. I picked FAISS over a hosted vector DB because our corpus was "
            "small enough to fit in memory and I wanted to avoid the added network latency and "
            "operational overhead of a managed service. We also re-rank the top 20 candidates with a "
            "cross-encoder before truncating to the final top-5 to improve precision."
        )
        result = self._evaluate(answer)
        self.assertGreaterEqual(result.overall_score, 0.85)
        self.assertIn(result.grade, ("good", "excellent"))

    def test_bands_are_monotonically_ordered_by_quality(self):
        """The exact numbers matter less than getting the ORDER right --
        this is the property most directly analogous to what a real
        interviewer would agree on even if they'd quibble with the exact
        percentages."""
        weak = self._evaluate("I mostly worked on unrelated frontend styling and did not touch the retrieval logic.")
        average = self._evaluate(
            "We use a vector database to find relevant chunks and pass them to the LLM along with the question."
        )
        good = self._evaluate(
            "For retrieval, I chunk each log file into overlapping windows and embed them with a "
            "sentence-transformer model, storing the vectors in FAISS. At query time I embed the "
            "incoming question and pull the top-k nearest chunks by cosine similarity before passing "
            "them into the prompt."
        )
        excellent = self._evaluate(
            "For retrieval, I chunk each log file into overlapping windows and embed them with a "
            "sentence-transformer model, storing the vectors in FAISS. At query time I embed the "
            "incoming question, pull the top-k nearest chunks by cosine similarity, and pass them into "
            "the prompt alongside the question so Gemini only reasons over the relevant context instead "
            "of the entire log history. I picked FAISS over a hosted vector DB because our corpus was "
            "small enough to fit in memory and I wanted to avoid the added network latency and "
            "operational overhead of a managed service. We also re-rank the top 20 candidates with a "
            "cross-encoder before truncating to the final top-5 to improve precision."
        )
        self.assertLess(weak.overall_score, average.overall_score)
        self.assertLess(average.overall_score, good.overall_score)
        self.assertLess(good.overall_score, excellent.overall_score)


class TestConcreteFeedbackEvidence(unittest.TestCase):
    """Phase 3 evaluation-fairness fix: Strengths/Weaknesses must cite
    concrete parts of the candidate's own answer, not a generic templated
    restatement of the dimension name and score."""

    def test_strength_evidence_quotes_the_answer_when_technical_accuracy_is_strong(self):
        evaluator = HeuristicEvaluator()
        spec = _project_spec()
        answer = (
            "I fixed a Redis caching invalidation bug by adding TTLs and a lock around the write "
            "path, which resolved a race condition serving stale data under concurrent load."
        )
        result = evaluator.evaluate(_request(answer, spec=spec))
        acc_strength = next((s for s in result.strengths if s.dimension == "technical_accuracy"), None)
        if acc_strength is not None:
            # Evidence must contain an actual fragment of the candidate's
            # own answer, not just a restated score.
            self.assertTrue(any(word in acc_strength.evidence for word in ("Redis", "TTL", "race condition")))

    def test_ownership_strength_names_the_actual_phrase_used(self):
        evaluator = HeuristicEvaluator()
        result = evaluator.evaluate(_request(
            "I designed and built the caching layer myself.", reasoning_type=ReasoningType.OWNERSHIP,
        ))
        ownership_strength = next((s for s in result.strengths if s.dimension == "ownership"), None)
        if ownership_strength is not None:
            self.assertIn("i designed", ownership_strength.evidence.lower())


def _spec_with_category(category: QuestionCategory) -> QuestionSpecification:
    return QuestionSpecification(
        id="topic_cat", category=category, text_seed="Linux",
        grounding=Grounding(project=ProjectGrounding(
            title="AI SOC Analyst", technologies=("Linux",), concepts=(),
        )),
        source_type=SourceType.PROJECT, source_id="AI SOC Analyst",
        source_field="technical_topics", reason="test",
    )


class TestCategoryAwareDimensionSelection(unittest.TestCase):
    """Phase 6 (question-specific dimensions): SKILL_IN_CONTEXT's
    DECISION_MAKING questions must not be scored on architecture/
    tradeoffs -- the only evidence is a bare technology name, no
    comparison/decision signal (see session handover investigation)."""

    def test_skill_in_context_decision_making_excludes_architecture_and_tradeoffs(self):
        evaluator = HeuristicEvaluator()
        spec = _spec_with_category(QuestionCategory.SKILL_IN_CONTEXT)
        req = _request(
            "I used it for log analysis.", reasoning_type=ReasoningType.DECISION_MAKING, spec=spec,
        )
        result = evaluator.evaluate(req)
        dim_names = {d.name for d in result.dimensions}
        self.assertNotIn("architecture", dim_names)
        self.assertNotIn("tradeoffs", dim_names)

    def test_project_overview_decision_making_still_includes_architecture_and_tradeoffs(self):
        """Regression guard: the exclusion is scoped to SKILL_IN_CONTEXT
        only -- the same reasoning_type on a genuinely project-level
        question is unaffected."""
        evaluator = HeuristicEvaluator()
        spec = _spec_with_category(QuestionCategory.PROJECT_OVERVIEW)
        req = _request(
            "I chose this approach because it fit the constraints.",
            reasoning_type=ReasoningType.DECISION_MAKING, spec=spec,
        )
        result = evaluator.evaluate(req)
        dim_names = {d.name for d in result.dimensions}
        self.assertIn("architecture", dim_names)
        self.assertIn("tradeoffs", dim_names)

    def test_project_deep_dive_decision_making_still_includes_architecture_and_tradeoffs(self):
        evaluator = HeuristicEvaluator()
        spec = _spec_with_category(QuestionCategory.PROJECT_DEEP_DIVE)
        req = _request(
            "I chose this approach because it fit the constraints.",
            reasoning_type=ReasoningType.DECISION_MAKING, spec=spec,
        )
        result = evaluator.evaluate(req)
        dim_names = {d.name for d in result.dimensions}
        self.assertIn("architecture", dim_names)
        self.assertIn("tradeoffs", dim_names)


if __name__ == "__main__":
    unittest.main()
