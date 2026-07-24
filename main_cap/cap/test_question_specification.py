"""
Tests for question_specification.py — Phase 1 of ResumeDiscussion_v2.

Covers:
- Construction of QuestionSpecification / Grounding sub-models
- Immutability (frozen config actually raises on assignment)
- Grounding: exactly-one-entity validation
- source_type <-> grounding consistency validation
- Non-empty provenance field validation
- UnitLifecycleState defaults and independence from the specification
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pydantic

from question_specification import (
    QUESTION_SPECIFICATION_SCHEMA_VERSION,
    CertificationGrounding,
    ExperienceGrounding,
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    RejectedTopic,
    SourceType,
    UnitLifecycleState,
    UnitStatus,
)


def _valid_project_spec(**overrides) -> QuestionSpecification:
    defaults = dict(
        id="topic_0",
        category=QuestionCategory.PROJECT_OVERVIEW,
        text_seed=None,
        grounding=Grounding(project=ProjectGrounding(title="Widget Factory")),
        priority_boost=False,
        source_type=SourceType.PROJECT,
        source_id="Widget Factory",
        source_field="summary",
        reason="projects[title='Widget Factory'].summary/technologies",
    )
    defaults.update(overrides)
    return QuestionSpecification(**defaults)


class TestGrounding(unittest.TestCase):
    def test_project_only_is_valid(self):
        g = Grounding(project=ProjectGrounding(title="X"))
        self.assertIsNotNone(g.project)
        self.assertIsNone(g.experience)
        self.assertIsNone(g.certification)

    def test_experience_only_is_valid(self):
        g = Grounding(experience=ExperienceGrounding(role="Intern"))
        self.assertIsNotNone(g.experience)

    def test_certification_only_is_valid(self):
        g = Grounding(certification=CertificationGrounding(name="AWS"))
        self.assertIsNotNone(g.certification)

    def test_zero_entities_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            Grounding()

    def test_two_entities_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            Grounding(
                project=ProjectGrounding(title="X"),
                experience=ExperienceGrounding(role="Y"),
            )

    def test_all_three_entities_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            Grounding(
                project=ProjectGrounding(title="X"),
                experience=ExperienceGrounding(role="Y"),
                certification=CertificationGrounding(name="Z"),
            )

    def test_grounding_is_frozen(self):
        g = Grounding(project=ProjectGrounding(title="X"))
        with self.assertRaises(pydantic.ValidationError):
            g.project = ProjectGrounding(title="Y")

    def test_project_grounding_technologies_are_tuple_not_list(self):
        p = ProjectGrounding(title="X", technologies=["A", "B"])
        self.assertIsInstance(p.technologies, tuple)
        self.assertEqual(p.technologies, ("A", "B"))


class TestQuestionSpecificationConstruction(unittest.TestCase):
    def test_valid_project_spec_constructs(self):
        spec = _valid_project_spec()
        self.assertEqual(spec.id, "topic_0")
        self.assertEqual(spec.category, QuestionCategory.PROJECT_OVERVIEW)
        self.assertEqual(spec.source_type, SourceType.PROJECT)

    def test_source_type_must_match_set_grounding_entity(self):
        with self.assertRaises(pydantic.ValidationError):
            _valid_project_spec(source_type=SourceType.EXPERIENCE)

    def test_empty_id_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _valid_project_spec(id="   ")

    def test_empty_source_id_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _valid_project_spec(source_id="")

    def test_empty_source_field_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _valid_project_spec(source_field="")

    def test_empty_reason_rejected(self):
        with self.assertRaises(pydantic.ValidationError):
            _valid_project_spec(reason="")

    def test_text_seed_optional(self):
        spec = _valid_project_spec(text_seed=None)
        self.assertIsNone(spec.text_seed)
        spec2 = _valid_project_spec(text_seed="Why Redis?")
        self.assertEqual(spec2.text_seed, "Why Redis?")

    def test_experience_spec_valid(self):
        spec = QuestionSpecification(
            id="topic_1",
            category=QuestionCategory.EXPERIENCE,
            grounding=Grounding(experience=ExperienceGrounding(role="Intern", company="Acme")),
            source_type=SourceType.EXPERIENCE,
            source_id="Intern at Acme",
            source_field="description",
            reason="experience[role='Intern'].description",
        )
        self.assertEqual(spec.source_type, SourceType.EXPERIENCE)

    def test_certification_spec_valid(self):
        spec = QuestionSpecification(
            id="topic_2",
            category=QuestionCategory.CERTIFICATION,
            grounding=Grounding(certification=CertificationGrounding(name="AWS")),
            source_type=SourceType.CERTIFICATION,
            source_id="AWS",
            source_field="name",
            reason="certifications[name='AWS']",
        )
        self.assertEqual(spec.source_type, SourceType.CERTIFICATION)


class TestQuestionSpecificationImmutability(unittest.TestCase):
    """Chapter 11.4: the provenance core must be permanent once created."""

    def setUp(self):
        self.spec = _valid_project_spec()

    def test_cannot_reassign_id(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.id = "topic_999"

    def test_cannot_reassign_category(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.category = QuestionCategory.EXPERIENCE

    def test_cannot_reassign_text_seed(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.text_seed = "something else"

    def test_cannot_reassign_grounding(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.grounding = Grounding(project=ProjectGrounding(title="Other"))

    def test_cannot_reassign_source_id(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.source_id = "Something Else"

    def test_cannot_reassign_source_field(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.source_field = "other_field"

    def test_cannot_reassign_reason(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.reason = "a different reason"

    def test_cannot_reassign_priority_boost(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.priority_boost = True

    def test_cannot_reassign_source_type(self):
        with self.assertRaises(pydantic.ValidationError):
            self.spec.source_type = SourceType.EXPERIENCE

    def test_two_specs_with_same_fields_are_equal_value_objects(self):
        a = _valid_project_spec()
        b = _valid_project_spec()
        self.assertEqual(a, b)


class TestUnitLifecycleState(unittest.TestCase):
    """
    Lifecycle state is intentionally mutable and separate from the
    immutable QuestionSpecification (Chapter 11.4's closing note) — but
    (Phase 1.5, Task 2) it is no longer *directly* mutable: `status`,
    `followups_used`, and `style_used` are read-only properties. The only
    way to change them is through `TopicPool`'s hardened API (see
    test_lifecycle_hardening.py), which updates `CoverageTracker` in the
    same call — this class only tests the read-only surface and the
    underscore-prefixed internal mutators in isolation.
    """

    def test_defaults(self):
        state = UnitLifecycleState()
        self.assertEqual(state.status, UnitStatus.UNASKED)
        self.assertEqual(state.followups_used, 0)
        self.assertIsNone(state.style_used)

    def test_status_has_no_public_setter(self):
        state = UnitLifecycleState()
        with self.assertRaises(AttributeError):
            state.status = UnitStatus.ACTIVE

    def test_followups_used_has_no_public_setter(self):
        state = UnitLifecycleState()
        with self.assertRaises(AttributeError):
            state.followups_used = 1

    def test_style_used_has_no_public_setter(self):
        state = UnitLifecycleState()
        with self.assertRaises(AttributeError):
            state.style_used = "tradeoffs"

    def test_internal_mutators_change_state(self):
        """The underscore-prefixed methods exist for TopicPool's controlled
        API to call — exercised directly here just to confirm they work in
        isolation; TopicPool-level invariant tests live in
        test_lifecycle_hardening.py."""
        state = UnitLifecycleState()
        state._transition(UnitStatus.ACTIVE)
        state._increment_followups()
        state._set_style("tradeoffs")
        self.assertEqual(state.status, UnitStatus.ACTIVE)
        self.assertEqual(state.followups_used, 1)
        self.assertEqual(state.style_used, "tradeoffs")

    def test_lifecycle_mutation_never_touches_specification(self):
        spec = _valid_project_spec()
        state = UnitLifecycleState()
        state._transition(UnitStatus.COVERED)
        state._increment_followups()
        # The specification object shares no memory with the lifecycle state;
        # mutating one can never affect the other.
        self.assertEqual(spec.id, "topic_0")
        with self.assertRaises(pydantic.ValidationError):
            spec.id = "mutated"


class TestQuestionSpecificationValidation(unittest.TestCase):
    """Phase 1.5, Task 4: confirm QuestionSpecification remains immutable,
    reproducible, serializable, and versionable."""

    def test_immutable(self):
        # Restated here (in addition to TestQuestionSpecificationImmutability
        # above) as the explicit Task 4 checklist item.
        spec = _valid_project_spec()
        with self.assertRaises(pydantic.ValidationError):
            spec.source_id = "changed"

    def test_reproducible(self):
        """Identical constructor arguments always produce an identical
        (equal-by-value) specification — the property Planner determinism
        (test_planner.py) ultimately rests on."""
        a = _valid_project_spec()
        b = _valid_project_spec()
        self.assertEqual(a, b)
        self.assertEqual(hash(repr(a)), hash(repr(b)))

    def test_serializable_to_dict(self):
        spec = _valid_project_spec()
        dumped = spec.model_dump()
        self.assertEqual(dumped["id"], "topic_0")
        self.assertEqual(dumped["category"], "project_overview")
        self.assertEqual(dumped["source_type"], "project")
        self.assertIn("schema_version", dumped)

    def test_serializable_to_json_round_trip(self):
        spec = _valid_project_spec()
        json_str = spec.model_dump_json()
        restored = QuestionSpecification.model_validate_json(json_str)
        self.assertEqual(spec, restored)

    def test_serializable_dict_round_trip(self):
        spec = _valid_project_spec()
        dumped = spec.model_dump()
        restored = QuestionSpecification.model_validate(dumped)
        self.assertEqual(spec, restored)

    def test_versionable_schema_version_present_and_defaulted(self):
        spec = _valid_project_spec()
        self.assertEqual(spec.schema_version, QUESTION_SPECIFICATION_SCHEMA_VERSION)
        self.assertEqual(spec.schema_version, "v1")

    def test_versionable_schema_version_is_part_of_the_frozen_record(self):
        spec = _valid_project_spec()
        with self.assertRaises(pydantic.ValidationError):
            spec.schema_version = "v2"

    def test_versionable_a_future_version_can_be_constructed_explicitly(self):
        """A later phase migrating to a new schema version only needs to
        pass an explicit `schema_version` — the field is future-proofed to
        carry that value through serialization untouched."""
        spec = _valid_project_spec(schema_version="v2")
        self.assertEqual(spec.schema_version, "v2")
        self.assertEqual(spec.model_dump()["schema_version"], "v2")


class TestRejectedTopic(unittest.TestCase):
    def test_construction(self):
        rejected = RejectedTopic(
            topic="GraphQL federation",
            originating_project="Order Management System",
            originating_experience="",
            reason="no matching project or experience entry on this profile",
        )
        self.assertEqual(rejected.topic, "GraphQL federation")

    def test_frozen(self):
        rejected = RejectedTopic(
            topic="X", originating_project="Y", originating_experience="", reason="Z"
        )
        with self.assertRaises(Exception):
            rejected.topic = "mutated"


if __name__ == "__main__":
    unittest.main()
