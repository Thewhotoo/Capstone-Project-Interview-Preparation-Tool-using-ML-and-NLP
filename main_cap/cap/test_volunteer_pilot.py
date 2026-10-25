"""Tests for the PHASE B volunteer-pilot import path (volunteer_pilot.py).

No real volunteer data, no LLM calls -- fully mocked/synthetic test fixtures
standing in for what a real collected record would look like.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evaluation_dimensions import CANONICAL_DIMENSIONS, EvaluationDimension
from human_benchmark import HumanAnnotation, HumanDimensionLabel
from question_families import ReasoningType
from rubric_judge import JudgeVerdict
from training_example import ProvenanceSource
from volunteer_pilot import (
    LABELING_GUIDELINE_VERSION,
    LabeledVolunteerAnswer,
    RealAnswerLabelStage,
    VolunteerAnswerRecord,
    assert_no_volunteer_split_leakage,
    benchmark_grounding_text,
    build_specification,
    group_of_by_volunteer,
    partition_benchmark_volunteers,
    pii_risk_findings,
    split_volunteer_answers,
    to_human_benchmark_item,
    to_training_example,
    validate_volunteer_answer_record,
)


def _record(**overrides) -> VolunteerAnswerRecord:
    defaults = dict(
        volunteer_id="vol_01",
        session_id="sess_1",
        answer_index=0,
        project_title="Recipe sharing app",
        technologies=("Flask", "SQLite"),
        short_project_description="A small app where users share recipes and rate each other's.",
        question_text="What does your project actually do?",
        answer_text="It lets users post recipes and other users can rate and comment on them.",
        expected_concepts=(),
        reasoning_type=ReasoningType.EXPLANATION,
        collection_batch_id="volunteer_pilot_test",
        collected_at="2026-09-06T00:00:00+00:00",
    )
    defaults.update(overrides)
    return VolunteerAnswerRecord(**defaults)


def _judge_verdicts() -> dict:
    return {
        dim: JudgeVerdict(dimension=dim.value, score=3, rationale="test", judge_version="test-judge-v1")
        for dim in CANONICAL_DIMENSIONS
    }


def _human_annotation() -> HumanAnnotation:
    return HumanAnnotation(
        annotator_id="annotator_1",
        rubric_version=LABELING_GUIDELINE_VERSION,
        dimension_labels=tuple(
            HumanDimensionLabel(dimension=dim.value, score=3) for dim in CANONICAL_DIMENSIONS
        ),
    )


# ── 1. Representing a collected record ───────────────────────────────────────

def test_valid_record_constructs():
    r = _record()
    assert r.volunteer_id == "vol_01"
    assert r.record_id == "vol_01__sess_1__0"


def test_record_id_disambiguates_multiple_answers_same_session():
    r0 = _record(answer_index=0)
    r1 = _record(answer_index=1)
    assert r0.record_id != r1.record_id


def test_no_pii_fields_exist_on_the_schema():
    # Structural guarantee: these are simply not valid constructor kwargs.
    fields = set(VolunteerAnswerRecord.model_fields.keys())
    for forbidden in ("name", "full_name", "email", "phone", "employer"):
        assert forbidden not in fields


# ── 2. Required-field validation ─────────────────────────────────────────────

@pytest.mark.parametrize("field,bad_value", [
    ("volunteer_id", "John Smith"),       # must look like vol_XXX, never a name
    ("volunteer_id", ""),
    ("project_title", ""),
    ("technologies", ()),
    ("short_project_description", ""),
    ("question_text", ""),
    ("answer_text", ""),
    ("collection_batch_id", ""),
    ("collected_at", ""),
])
def test_required_fields_rejected_when_missing_or_invalid(field, bad_value):
    with pytest.raises(ValidationError):
        _record(**{field: bad_value})


def test_answer_index_must_be_non_negative():
    with pytest.raises(ValidationError):
        _record(answer_index=-1)


def test_volunteer_answer_record_is_frozen():
    r = _record()
    with pytest.raises(ValidationError):
        r.answer_text = "changed"


# ── 3. Privacy / PII checks ──────────────────────────────────────────────────

def test_pii_findings_empty_for_clean_text():
    assert pii_risk_findings("We used Redis for caching.") == ()


def test_pii_findings_catches_email():
    assert "email_like_pattern" in pii_risk_findings("reach me at volunteer@example.com")


def test_pii_findings_catches_phone_like_pattern():
    assert "phone_like_pattern" in pii_risk_findings("call me at 555-123-4567")


def test_pii_findings_catches_secret_markers():
    findings = pii_risk_findings("I hardcoded the API_KEY in the config by mistake.")
    assert any(f.startswith("secret_marker:") for f in findings)


def test_pii_findings_catches_identifying_phrase():
    findings = pii_risk_findings("My manager told me to fix it.")
    assert any(f.startswith("identifying_phrase:") for f in findings)


def test_validate_record_flags_pii_across_all_free_text_fields():
    r = _record(answer_text="Email me at leaker@example.com if you have questions.")
    result = validate_volunteer_answer_record(r)
    assert result.accepted  # schema-valid
    assert not result.clean  # but privacy-flagged
    assert "email_like_pattern" in result.pii_findings


def test_validate_record_clean_when_no_pii():
    result = validate_volunteer_answer_record(_record())
    assert result.clean


# ── Staged labeling ("important labeling rule") ──────────────────────────────

def test_freshly_collected_record_has_collected_stage():
    labeled = LabeledVolunteerAnswer(record=_record())
    assert labeled.stage is RealAnswerLabelStage.COLLECTED


def test_judge_only_scored_record_is_pending_review_not_human_reviewed():
    labeled = LabeledVolunteerAnswer(record=_record(), judge_verdicts=_judge_verdicts())
    assert labeled.stage is RealAnswerLabelStage.JUDGED_PENDING_REVIEW
    assert labeled.stage is not RealAnswerLabelStage.HUMAN_REVIEWED


def test_human_annotated_record_is_human_reviewed():
    labeled = LabeledVolunteerAnswer(
        record=_record(), judge_verdicts=_judge_verdicts(), human_annotation=_human_annotation(),
    )
    assert labeled.stage is RealAnswerLabelStage.HUMAN_REVIEWED


def test_to_training_example_rejects_judge_only_labels():
    """The core guardrail the task calls out explicitly: a judge-only score
    must NEVER produce a label_source='human_reviewed' TrainingExample."""
    labeled = LabeledVolunteerAnswer(record=_record(), judge_verdicts=_judge_verdicts())
    with pytest.raises(ValueError, match="human-reviewed"):
        to_training_example(labeled)


def test_to_training_example_rejects_completely_unlabeled_record():
    labeled = LabeledVolunteerAnswer(record=_record())
    with pytest.raises(ValueError, match="human-reviewed"):
        to_training_example(labeled)


def test_to_human_benchmark_item_rejects_judge_only_labels():
    labeled = LabeledVolunteerAnswer(record=_record(), judge_verdicts=_judge_verdicts())
    with pytest.raises(ValueError, match="human-reviewed"):
        to_human_benchmark_item(labeled)


# ── 4/5. Conversion + provenance ─────────────────────────────────────────────

def test_build_specification_uses_volunteer_id_as_source_id():
    spec = build_specification(_record(volunteer_id="vol_42"))
    assert spec.source_id == "vol_42"
    assert spec.grounding.project.title == "Recipe sharing app"
    assert spec.grounding.project.technologies == ("Flask", "SQLite")


def test_to_training_example_has_real_session_provenance():
    labeled = LabeledVolunteerAnswer(
        record=_record(), judge_verdicts=_judge_verdicts(), human_annotation=_human_annotation(),
    )
    ex = to_training_example(labeled)
    assert ex.provenance.source is ProvenanceSource.REAL_SESSION
    assert ex.provenance.real_session_id == "sess_1"
    assert ex.synthetic is None
    assert ex.labels.label_source == "human_reviewed"
    assert ex.labels.labeling_guideline_version == LABELING_GUIDELINE_VERSION


def test_to_training_example_dimension_labels_match_human_annotation():
    labeled = LabeledVolunteerAnswer(
        record=_record(), judge_verdicts=_judge_verdicts(), human_annotation=_human_annotation(),
    )
    ex = to_training_example(labeled)
    by_name = {dl.name: dl.score for dl in ex.labels.dimension_labels}
    for dim in CANONICAL_DIMENSIONS:
        assert by_name[dim.value] == pytest.approx(3 / 4)


def test_real_examples_are_distinguishable_from_synthetic():
    labeled = LabeledVolunteerAnswer(
        record=_record(), judge_verdicts=_judge_verdicts(), human_annotation=_human_annotation(),
    )
    ex = to_training_example(labeled)
    # A synthetic example always has ProvenanceSource.SYNTHETIC + non-None
    # `synthetic` metadata (enforced by TrainingExample's own validator); a
    # real one is the structural opposite -- this is the "remain
    # distinguishable" requirement, checked directly.
    assert ex.provenance.source is ProvenanceSource.REAL_SESSION
    assert ex.synthetic is None


# ── 6. Volunteer-level grouping ──────────────────────────────────────────────

def test_group_of_by_volunteer_maps_record_id_to_volunteer():
    records = [_record(volunteer_id="vol_01", answer_index=0), _record(volunteer_id="vol_01", answer_index=1)]
    group_of = group_of_by_volunteer(records)
    assert len(group_of) == 2
    assert set(group_of.values()) == {"vol_01"}


def test_split_keeps_same_volunteers_answers_together():
    records = []
    for v in range(6):
        for i in range(4):
            records.append(_record(volunteer_id=f"vol_{v:02d}", session_id="s1", answer_index=i))
    split = split_volunteer_answers(records, split_ratios=(0.7, 0.3, 0.0))
    group_of = group_of_by_volunteer(records)

    def volunteers_in(ids):
        return {group_of[i] for i in ids}

    train_vols = volunteers_in(split.train_ids)
    val_vols = volunteers_in(split.val_ids)
    assert not (train_vols & val_vols), "no volunteer should span both train and val"
    # every record from a given volunteer lands in exactly one split
    for v in {r.volunteer_id for r in records}:
        rec_ids = {r.record_id for r in records if r.volunteer_id == v}
        assert rec_ids <= set(split.train_ids) or rec_ids <= set(split.val_ids)


# ── 7. Frozen benchmark path ──────────────────────────────────────────────────

def test_partition_benchmark_volunteers_is_disjoint_and_total():
    all_ids = [f"vol_{i:02d}" for i in range(10)]
    held_out = all_ids[:3]
    bench, trainval = partition_benchmark_volunteers(all_ids, held_out)
    assert set(bench) == set(held_out)
    assert set(trainval) == set(all_ids) - set(held_out)
    assert set(bench).isdisjoint(trainval)


def test_partition_benchmark_volunteers_rejects_unknown_id():
    with pytest.raises(ValueError):
        partition_benchmark_volunteers(["vol_01", "vol_02"], ["vol_99"])


def test_assert_no_volunteer_split_leakage_passes_when_disjoint():
    bench = ("vol_01", "vol_02")
    trainval_group_of = {"vol_03__s1__0": "vol_03", "vol_04__s1__0": "vol_04"}
    assert_no_volunteer_split_leakage(bench, trainval_group_of)  # no raise


def test_assert_no_volunteer_split_leakage_catches_a_volunteer_in_both():
    bench = ("vol_01", "vol_02")
    trainval_group_of = {"vol_02__s1__0": "vol_02", "vol_03__s1__0": "vol_03"}
    with pytest.raises(ValueError, match="vol_02"):
        assert_no_volunteer_split_leakage(bench, trainval_group_of)


def test_to_human_benchmark_item_from_human_reviewed_answer():
    labeled = LabeledVolunteerAnswer(
        record=_record(volunteer_id="vol_09"), judge_verdicts=_judge_verdicts(),
        human_annotation=_human_annotation(),
    )
    item = to_human_benchmark_item(labeled)
    assert item.item_id.startswith("hb_")
    assert item.grounding_source == "vol_09"
    assert len(item.final_labels) == 4
    assert item.annotations[0].annotator_id == "annotator_1"


def test_benchmark_grounding_text_includes_project_context():
    text = benchmark_grounding_text(_record())
    assert "Recipe sharing app" in text
    assert "Flask" in text


def test_human_benchmark_item_never_built_from_judge_labels_alone():
    """Structural proof that a HumanBenchmarkItem's final_labels always come
    from the HumanAnnotation, never the judge -- even when both are present
    and happen to differ."""
    # judge says everything is a 1; human annotator says everything is a 4
    judge = {
        dim: JudgeVerdict(dimension=dim.value, score=1, rationale="test", judge_version="test-judge-v1")
        for dim in CANONICAL_DIMENSIONS
    }
    human = HumanAnnotation(
        annotator_id="annotator_2", rubric_version=LABELING_GUIDELINE_VERSION,
        dimension_labels=tuple(HumanDimensionLabel(dimension=dim.value, score=4) for dim in CANONICAL_DIMENSIONS),
    )
    labeled = LabeledVolunteerAnswer(record=_record(), judge_verdicts=judge, human_annotation=human)
    item = to_human_benchmark_item(labeled)
    assert all(dl.score == 4 for dl in item.final_labels)  # human, not judge (1)
