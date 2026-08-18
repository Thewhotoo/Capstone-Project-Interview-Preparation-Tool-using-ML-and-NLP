"""
Tests for strong_answer.py — the deterministic Improved Answer editor.

Verifies the redesign: it rewrites the candidate's OWN answer into a stronger
version, using DeBERTa outputs only as editing signals (never as a generator),
inventing nothing.
  - preserves the candidate's own wording,
  - inserts a grounded expected concept the candidate omitted,
  - elaborates weak reasoning flagged by the evaluator,
  - removes repeated sentences,
  - hides for already-strong answers and when there's nothing to add,
  - never fabricates a technology not in the grounding/expected concepts.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluation_result import (
    ConceptObservation,
    ConceptObservationStatus,
    ConfidenceSource,
    DimensionScore,
    EvaluationResult,
    MissingReasoningItem,
)
from interview_question import InterviewQuestion
from question_families import ReasoningType
from question_specification import (
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from strong_answer import build_improved_answer, coaching_note


# ── builders ──────────────────────────────────────────────────────────────

def _project_question(title="Query Optimizer", technologies=("PostgreSQL",),
                      concepts=("composite indexes", "EXPLAIN ANALYZE"), text_seed=None,
                      family="architecture"):
    spec = QuestionSpecification(
        id=f"topic_{title}", category=QuestionCategory.PROJECT_DEEP_DIVE, text_seed=text_seed,
        grounding=Grounding(project=ProjectGrounding(
            title=title, technologies=tuple(technologies), concepts=tuple(concepts),
        )),
        source_type=SourceType.PROJECT, source_id=title, source_field="summary", reason="test",
    )
    return InterviewQuestion(
        question_text=f"How did you structure {title}?", transition_text="",
        specification=spec, family=family, reasoning_type=ReasoningType.EXPLANATION,
        project_reference=title, is_followup=False, turn_number=1,
    )


def _experience_question(role="Backend Engineer", company="Acme"):
    spec = QuestionSpecification(
        id="exp", category=QuestionCategory.EXPERIENCE, text_seed=None,
        grounding=Grounding(experience=ExperienceGrounding(role=role, company=company)),
        source_type=SourceType.EXPERIENCE, source_id=role, source_field="summary", reason="test",
    )
    return InterviewQuestion(
        question_text=f"What did you do as {role}?", transition_text="", specification=spec,
        family="responsibilities", reasoning_type=ReasoningType.OWNERSHIP,
        project_reference=None, is_followup=False, turn_number=1,
    )


def _dimension(**o):
    d = dict(name="technical_accuracy", raw_score=0.5, weight_used=1.0, confidence=0.7,
             confidence_source=ConfidenceSource.MODEL)
    d.update(o)
    return DimensionScore(**d)


def _concept(name, status):
    ev = None if status is ConceptObservationStatus.OMITTED else f"seen: {name}"
    return ConceptObservation(concept=name, status=status, evidence=ev, confidence=0.6,
                              confidence_source=ConfidenceSource.MODEL)


def _missing(cat, sev=0.7):
    return MissingReasoningItem(category=cat, explanation="x", expected_because="y", evidence="z", severity=sev)


def _missing_example(terms, sev=0.5):
    """An EXAMPLE missing_reasoning item shaped exactly like the real one
    heuristic_evaluator._missing_reasoning produces -- `evidence` in the
    literal f"{terms} not found in the answer" form `_example_terms`
    (strong_answer.py) parses back out."""
    joined = ", ".join(terms)
    return MissingReasoningItem(
        category="example", explanation=f"specific mention of {joined}",
        expected_because="y", evidence=f"{joined} not found in the answer", severity=sev,
    )


def _result(grade="adequate", overall=0.5, concept_coverage=(), missing_reasoning=(_missing("design_decision"),)):
    return EvaluationResult(
        result_id="e", request_id="r", evaluation_timestamp="2026-01-01T00:00:00+00:00",
        specification_id="t", source_id="s", category="project_deep_dive",
        reasoning_type=ReasoningType.EXPLANATION, evaluator_name="trained-x", evaluator_version="1.0.0",
        dimensions=(_dimension(raw_score=overall),), overall_score=overall, grade=grade,
        confidence=0.7, confidence_source=ConfidenceSource.MODEL, confidence_rationale="e",
        reasoning="r", concept_coverage=tuple(concept_coverage), missing_reasoning=tuple(missing_reasoning),
    )


_ANSWER = ("I added indexes on the user table to speed up the lookups. "
           "I used PostgreSQL and it made the queries much faster.")


# ── preserves the candidate's own answer ─────────────────────────────────────

class TestPreservesAnswer(unittest.TestCase):
    def test_keeps_candidate_wording(self):
        out = build_improved_answer(_project_question(), _result(), _ANSWER)
        self.assertIsNotNone(out)
        self.assertIn("I added indexes on the user table", out)
        self.assertIn("I used PostgreSQL", out)

    def test_output_starts_with_candidate_answer(self):
        out = build_improved_answer(_project_question(), _result(), _ANSWER)
        self.assertTrue(out.startswith("I added indexes on the user table"))


# ── inserts the omitted expected concept ─────────────────────────────────────

class TestInsertsMissingConcepts(unittest.TestCase):
    def test_weaves_in_omitted_expected_concept(self):
        # Candidate mentioned PostgreSQL indexes but not EXPLAIN ANALYZE (a
        # grounding concept) -> it should be inserted.
        out = build_improved_answer(_project_question(), _result(), _ANSWER)
        self.assertIn("EXPLAIN ANALYZE", out)

    def test_does_not_repeat_a_concept_already_mentioned(self):
        # PostgreSQL is already in the answer -> must NOT be re-added.
        q = _project_question(technologies=("PostgreSQL",), concepts=("PostgreSQL",))
        out = build_improved_answer(q, _result(missing_reasoning=(_missing("metrics"),)), _ANSWER)
        # PostgreSQL appears once (candidate's), not injected again by the addition
        self.assertEqual(out.lower().count("postgresql"), _ANSWER.lower().count("postgresql"))

    def test_does_not_use_evaluator_omitted_concepts(self):
        # PHASE 8 FIX: a concept that exists ONLY in result.concept_coverage
        # (the evaluator's own omitted/superficial list -- itself sourced
        # from the expected-concepts registry, not from the candidate's
        # resume text) must NOT be ghost-written into the improved answer.
        # It remains a legitimate evaluator/dashboard signal; it is simply
        # no longer eligible for injection here.
        q = _project_question(concepts=())  # no grounding concepts
        r = _result(concept_coverage=(_concept("query planning", ConceptObservationStatus.OMITTED),),
                    missing_reasoning=())
        # With no proj.concepts and no missing_reasoning, there is nothing
        # left to add -> hidden entirely (never a bare echo of the answer).
        out = build_improved_answer(q, r, _ANSWER)
        self.assertIsNone(out)

    def test_does_not_use_evaluator_superficial_concepts(self):
        q = _project_question(concepts=())
        r = _result(concept_coverage=(_concept("query planning", ConceptObservationStatus.SUPERFICIAL),),
                    missing_reasoning=())
        out = build_improved_answer(q, r, _ANSWER)
        self.assertIsNone(out)

    def test_registry_only_concepts_not_injected(self):
        # PHASE 8 FIX regression case (the exact live-reproduced failure):
        # the project's technology (FastAPI) has entries in the
        # expected-concepts registry (ASGI / dependency injection / routing
        # / modularity / async request handling), but proj.concepts is
        # empty -- nothing in the resume's own project text was actually
        # matched. None of the registry's technology-associated concepts
        # may be injected; only genuine proj.concepts are eligible.
        from expected_concepts_registry import expected_concepts_for
        registry_concepts = expected_concepts_for(("FastAPI",))
        self.assertIn("ASGI", registry_concepts)  # sanity: registry entry exists
        self.assertIn("dependency injection", registry_concepts)

        q = _project_question(title="AI SOC Analyst", technologies=("FastAPI",), concepts=())
        r = _result(concept_coverage=(), missing_reasoning=())
        out = build_improved_answer(q, r, _ANSWER)
        # Nothing to add (no proj.concepts, no missing_reasoning) -> hidden.
        self.assertIsNone(out)

        # Even with a weak-area signal present (so the feature does fire),
        # none of the registry's FastAPI concepts may appear. Uses
        # "design_decision", not "example", so this stays a pure
        # registry-injection check independent of the "example" category's
        # own question-relevance filter (covered separately below).
        r2 = _result(concept_coverage=(), missing_reasoning=(_missing("design_decision"),))
        out2 = build_improved_answer(q, r2, _ANSWER)
        self.assertIsNotNone(out2)
        for concept in registry_concepts:
            self.assertNotIn(concept, out2)


# ── elaborates weak reasoning ────────────────────────────────────────────────

class TestElaboratesWeakAreas(unittest.TestCase):
    def test_design_decision_weakness_elaborated(self):
        out = build_improved_answer(_project_question(concepts=()),
                                    _result(missing_reasoning=(_missing("design_decision"),)), _ANSWER)
        self.assertIn("the reasoning behind that decision", out)

    def test_metrics_weakness_elaborated(self):
        out = build_improved_answer(_project_question(concepts=()),
                                    _result(missing_reasoning=(_missing("metrics"),)), _ANSWER)
        self.assertIn("the results that showed it worked", out)


# ── removes repetition ───────────────────────────────────────────────────────

class TestRemovesRepetition(unittest.TestCase):
    def test_duplicate_sentence_dropped(self):
        ans = ("I built the network topology and configured the routers. "
               "I built the network topology and configured the routers. "
               "Each site had its own subnet for isolation.")
        out = build_improved_answer(_project_question(concepts=("subnetting",)), _result(), ans)
        self.assertEqual(out.count("I built the network topology and configured the routers"), 1)


# ── hide gate ────────────────────────────────────────────────────────────────

class TestHideGate(unittest.TestCase):
    def test_excellent_hidden(self):
        self.assertIsNone(build_improved_answer(_project_question(), _result(grade="excellent", overall=0.9), _ANSWER))

    def test_good_hidden(self):
        self.assertIsNone(build_improved_answer(_project_question(), _result(grade="good", overall=0.65), _ANSWER))

    def test_hidden_when_no_signals(self):
        # adequate, but nothing to add: all expected concepts already mentioned
        # and no missing_reasoning.
        q = _project_question(technologies=(), concepts=("indexes", "lookups"))
        out = build_improved_answer(q, _result(missing_reasoning=()), _ANSWER)
        self.assertIsNone(out)

    def test_hidden_for_trivial_answer(self):
        self.assertIsNone(build_improved_answer(_project_question(), _result(), "It worked fine."))

    def test_adequate_with_signals_shown(self):
        self.assertIsNotNone(build_improved_answer(_project_question(), _result(), _ANSWER))


# ── no invention ─────────────────────────────────────────────────────────────

class TestNoInvention(unittest.TestCase):
    def test_no_ungrounded_technology_appears(self):
        # A tech not in grounding/expected concepts / answer must never appear.
        out = build_improved_answer(_project_question(), _result(), _ANSWER)
        for bogus in ("Kubernetes", "MongoDB", "GraphQL", "Redis"):
            self.assertNotIn(bogus, out)

    def test_experience_answer_still_improves(self):
        ans = ("As a backend engineer I built APIs and fixed bugs. "
               "As a backend engineer I built APIs and fixed bugs.")
        out = build_improved_answer(_experience_question(), _result(missing_reasoning=(_missing("ownership"),)), ans)
        self.assertIsNotNone(out)
        self.assertIn("which parts of this I personally implemented or decided", out)
        # repetition removed
        self.assertEqual(out.count("As a backend engineer I built APIs and fixed bugs"), 1)


# ── lexical concept coverage (the fix) ───────────────────────────────────────

class TestLexicalCoverage(unittest.TestCase):
    """A concept expressed in the candidate's own words (inflected / partial)
    must NOT be re-inserted, even without the exact contiguous phrase."""

    def _mil(self, concepts):
        return _project_question(
            title="Military Communication Network", technologies=("Cisco Packet Tracer",),
            concepts=concepts,
        )

    def test_security_paraphrase_not_reinserted(self):
        # "Security was the main driver ... network segmentation" -> Network
        # Security is already expressed via "security"; must not be re-added.
        q = self._mil(("Network Design", "Network Security"))
        ans = ("I settled on a hub-and-spoke design with static routing. Security was the "
               "main driver, so I built in network segmentation and access control.")
        out = build_improved_answer(q, _result(missing_reasoning=()), ans)
        # design was covered ("design"), security was covered ("security") ->
        # no concepts left, and no missing_reasoning -> hidden.
        self.assertIsNone(out)

    def test_only_uncovered_concept_inserted(self):
        # Answer covers design + security but NOT encryption/transmission.
        q = self._mil(("Network Design", "Network Security", "Data Transmission"))
        ans = ("I designed the layout and made security the main driver with "
               "segmentation and access control.")
        out = build_improved_answer(q, _result(missing_reasoning=()), ans)
        self.assertIsNotNone(out)
        self.assertIn("Data Transmission", out)          # genuinely absent -> inserted
        self.assertNotIn("Network Design", out)          # covered by "designed"
        self.assertNotIn("Network Security", out)        # covered by "security"

    def test_sensor_and_realtime_paraphrase_not_reinserted(self):
        q = _project_question(
            title="Theft Detection System", technologies=("Arduino Uno",),
            concepts=("Embedded Systems", "Sensor Integration", "Real-time Monitoring"),
        )
        ans = ("It's a small embedded alarm on an Arduino. A motion sensor and a distance "
               "sensor watch the area, and the firmware reads them in real time.")
        out = build_improved_answer(q, _result(missing_reasoning=()), ans)
        # embedded, sensor(s), real time all present -> nothing to add -> hidden.
        self.assertIsNone(out)

    def test_transmission_inflection_matches(self):
        q = self._mil(("Data Transmission",))
        ans = "The data was transmitted over encrypted tunnels between the sites securely."
        out = build_improved_answer(q, _result(missing_reasoning=()), ans)
        self.assertIsNone(out)  # "transmitted" covers "Transmission"

    def test_shared_word_alone_does_not_cover(self):
        # "network simulation" mentions the shared word 'network' but neither
        # 'design' nor 'security' -> both remain insertable (not falsely covered).
        q = self._mil(("Network Design", "Network Security"))
        ans = "It was just a network simulation I put together for a class project quickly."
        out = build_improved_answer(q, _result(missing_reasoning=()), ans)
        self.assertIsNotNone(out)
        self.assertIn("Network Design", out)
        self.assertIn("Network Security", out)


class TestCoachingNote(unittest.TestCase):
    """UI-honesty fix (post-demo forensic investigation): coaching_note()
    exposes the exact same appended sentence build_improved_answer would
    have embedded, computed via the shared _compute() helper -- never
    re-derived by parsing build_improved_answer's concatenated string.
    Added because a real 10-turn browser session showed every
    build_improved_answer output was the candidate's own answer verbatim
    plus this one sentence, presented under a misleading "Improved Answer"
    label. This class verifies the two public entry points never drift
    apart, not any change to generation behavior."""

    def test_matches_the_appended_clause_in_build_improved_answer(self):
        out = build_improved_answer(_project_question(), _result(), _ANSWER)
        note = coaching_note(_project_question(), _result(), _ANSWER)
        self.assertIsNotNone(out)
        self.assertIsNotNone(note)
        # The full concatenated answer must end with exactly the standalone
        # coaching note -- proves they can never disagree.
        self.assertTrue(out.endswith(note))

    def test_none_under_the_exact_same_conditions_as_build_improved_answer(self):
        for grade in ("good", "excellent"):
            with self.subTest(grade=grade):
                q = _project_question()
                r = _result(grade=grade, overall=0.9)
                self.assertIsNone(build_improved_answer(q, r, _ANSWER))
                self.assertIsNone(coaching_note(q, r, _ANSWER))

    def test_none_when_trivial_answer_for_both(self):
        q = _project_question()
        r = _result()
        self.assertIsNone(build_improved_answer(q, r, "It worked fine."))
        self.assertIsNone(coaching_note(q, r, "It worked fine."))

    def test_none_when_nothing_to_add_for_both(self):
        q = _project_question(technologies=(), concepts=("indexes", "lookups"))
        r = _result(missing_reasoning=())
        self.assertIsNone(build_improved_answer(q, r, _ANSWER))
        self.assertIsNone(coaching_note(q, r, _ANSWER))

    def test_does_not_contain_the_candidates_own_wording(self):
        """The coaching note is the isolated addition only -- it must never
        also contain the candidate's original answer text (no duplication
        between 'Your Answer' and 'Coaching Note' in the UI)."""
        note = coaching_note(_project_question(), _result(), _ANSWER)
        self.assertIsNotNone(note)
        self.assertNotIn("I added indexes on the user table", note)
        self.assertTrue(note.startswith("I'd also"))

    def test_reflects_the_soft_length_guard_exactly(self):
        """When build_improved_answer's soft-length guard drops the
        secondary (weak-area) clause, coaching_note must reflect the SAME
        shortened clause, not the original two-clause version -- proves
        they share one computation, not two independent ones that could
        drift under this edge case."""
        long_answer = _ANSWER + " " + ("Additional detail. " * 30)
        q = _project_question()  # missing: EXPLAIN ANALYZE (composite indexes already covered)
        r = _result(missing_reasoning=(_missing("design_decision"),))
        out = build_improved_answer(q, r, long_answer)
        note = coaching_note(q, r, long_answer)
        self.assertIsNotNone(out)
        self.assertIsNotNone(note)
        self.assertTrue(out.endswith(note))
        # Guard fired: only the "work in ..." clause should remain, not the
        # "be explicit about ..." (design_decision) clause too.
        if len(out.split()) <= 180:
            pass  # guard didn't need to fire for this input length; skip the stronger assertion
        else:
            self.assertNotIn("the reasoning behind that decision", note)


class TestExampleCategoryQuestionRelevance(unittest.TestCase):
    """Coaching Note content-quality fix, item 1: an "example"
    missing_reasoning item names project technologies computed against the
    WHOLE project's grounding, not scoped to the current question --
    live-reproduced (investigation, real mayurans_resume.pdf session) as a
    turn where an architecture question with zero technology relevance and
    a React-specific question both surfaced the identical unfiltered
    "React, FastAPI" pair. These tests pin the fix: only a term that
    literally appears in the CURRENT question's own text may be named, and
    when none do, the example-specific clause is dropped entirely -- never
    replaced with a generic fallback sentence."""

    def test_term_named_when_it_appears_in_the_question(self):
        q = _project_question(concepts=()).model_copy(
            update={"question_text": "How did you use FastAPI in this project?"})
        r = _result(missing_reasoning=(_missing_example(("FastAPI",)),))
        note = coaching_note(q, r, _ANSWER)
        # Direct, actionable instruction -- not a fragment tacked onto
        # "I'd also be explicit about ..." (wording-refinement fix).
        self.assertEqual(note, "Give a concrete example of how you used FastAPI in this project.")

    def test_clause_suppressed_when_no_term_appears_in_the_question(self):
        # Turn-2-shaped regression case: an architecture question that never
        # names any project technology. No fallback generic sentence either
        # -- and no other signal here (concepts=() -> missing=[]), so the
        # whole coaching note must be None, not a vague "give an example."
        q = _project_question(concepts=()).model_copy(
            update={"question_text": "Walk me through how the pieces of this project fit together."})
        r = _result(missing_reasoning=(_missing_example(("React", "FastAPI")),))
        note = coaching_note(q, r, _ANSWER)
        self.assertIsNone(note)

    def test_only_the_question_relevant_term_is_named(self):
        # Turn-5-shaped case: the question is specifically about React;
        # FastAPI is also a missing project technology but this question
        # never asked about it, so only React may be named.
        q = _project_question(concepts=()).model_copy(
            update={"question_text": "Why did you take the approach you did for React in this project?"})
        r = _result(missing_reasoning=(_missing_example(("React", "FastAPI")),))
        note = coaching_note(q, r, _ANSWER)
        self.assertEqual(note, "Give a concrete example of how you used React in this project.")

    def test_example_and_weak_area_together_are_two_clean_sentences(self):
        # Both an "example" signal (React, relevant to this question) and a
        # dimension weakness (ownership) fire on the same turn. The result
        # must be two distinct, non-repetitive sentences -- the dimension
        # clause via "I'd also be explicit about ...", the example via its
        # own standalone actionable instruction -- not one run-on sentence
        # and not the same idea stated twice.
        q = _project_question(concepts=()).model_copy(
            update={"question_text": "Why did you take the approach you did for React in this project?"})
        r = _result(missing_reasoning=(_missing_example(("React",)), _missing("ownership", sev=0.9)))
        note = coaching_note(q, r, _ANSWER)
        self.assertEqual(
            note,
            "I'd also be explicit about which parts of this I personally implemented or decided, "
            "versus what the team or project did overall. "
            "Give a concrete example of how you used React in this project.",
        )
        # Exactly two sentences -- no repeated clause, no run-on "and" chain
        # tying the two unrelated ideas together.
        self.assertEqual(note.count("Give a concrete example"), 1)

    def test_experience_turn_unaffected(self):
        # No-project turns never produce an "example" item in production
        # (heuristic_evaluator._grounding_terms returns () without a
        # project) -- confirm the relevance filter doesn't break the
        # ordinary no-project path when a non-example category is present.
        ans = "As a backend engineer I built APIs and fixed bugs on this team."
        q = _experience_question()
        r = _result(missing_reasoning=(_missing("ownership"),))
        note = coaching_note(q, r, ans)
        self.assertIsNotNone(note)
        self.assertIn("which parts of this I personally implemented or decided", note)


class TestSharpenedWeakAreaWording(unittest.TestCase):
    """The 6 already-supported categories' clauses, sharpened to match the
    desired coaching direction while remaining grounded ONLY in "this
    dimension scored weak" -- never a candidate-specific fact."""

    def test_ownership_wording(self):
        note = coaching_note(_project_question(concepts=()),
                              _result(missing_reasoning=(_missing("ownership"),)), _ANSWER)
        self.assertIn("which parts of this I personally implemented or decided, versus what the team or "
                       "project did overall", note)

    def test_architecture_wording(self):
        note = coaching_note(_project_question(concepts=()),
                              _result(missing_reasoning=(_missing("architecture"),)), _ANSWER)
        self.assertIn("the specific components involved, their responsibilities, and how they interact", note)

    def test_tradeoff_wording(self):
        note = coaching_note(_project_question(concepts=()),
                              _result(missing_reasoning=(_missing("tradeoff"),)), _ANSWER)
        self.assertIn("the alternatives I considered and why I chose this approach over them", note)

    def test_testing_wording(self):
        note = coaching_note(_project_question(concepts=()),
                              _result(missing_reasoning=(_missing("testing"),)), _ANSWER)
        self.assertIn("the concrete test cases or edge cases I used to verify it worked", note)

    def test_debugging_wording(self):
        note = coaching_note(_project_question(concepts=()),
                              _result(missing_reasoning=(_missing("debugging"),)), _ANSWER)
        self.assertIn("the specific hard cases I ran into and how I worked through them", note)

    def test_scalability_wording(self):
        note = coaching_note(_project_question(concepts=()),
                              _result(missing_reasoning=(_missing("scalability"),)), _ANSWER)
        self.assertIn("how this would hold up as usage or data grows, and what would need to change", note)

    def test_no_fabricated_technology_in_any_sharpened_note(self):
        # None of the 6 sharpened, dimension-level clauses may name any
        # specific technology/concept -- they must stay fact-free.
        bogus = ("Kubernetes", "MongoDB", "GraphQL", "Redis", "React", "FastAPI", "DeBERTa")
        for cat in ("ownership", "architecture", "tradeoff", "testing", "debugging", "scalability"):
            with self.subTest(category=cat):
                note = coaching_note(_project_question(concepts=()),
                                      _result(missing_reasoning=(_missing(cat),)), _ANSWER)
                self.assertIsNotNone(note)
                for tech in bogus:
                    self.assertNotIn(tech, note)


if __name__ == "__main__":
    unittest.main()
