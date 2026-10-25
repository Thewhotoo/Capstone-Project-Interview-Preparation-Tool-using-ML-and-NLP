"""
Volunteer Pilot Import Path — PHASE B infra (docs/architecture/Volunteer_Pilot_Protocol.md).

Represents, validates, and (once properly staged) converts collected REAL
volunteer interview answers into the existing `TrainingExample` /
`HumanBenchmarkItem` schemas. No data collection happens here — this module
only defines the shapes and checks Phase B (recruiting/collecting real
answers) will need once it actually runs.

DESIGN CONSTRAINTS (reconciled against Volunteer_Pilot_Protocol.md, not
reinvented here):
  - Reuses `TrainingExample`/`ProvenanceSource.REAL_SESSION` as-is (protocol
    §7: "ready, no changes needed") — no parallel training-data schema.
  - `HumanBenchmarkItem.grounding_source` stays a bare string identifier
    (protocol §7's documented, deliberately-unfixed gap); the actual
    grounding TEXT for a benchmark item lives in this module's own record
    alongside it, never inside the frozen benchmark schema itself.
  - `TrainingExampleLabels.label_source` is NEVER set to "human_reviewed"
    just because a judge scored an item (protocol's "important labeling
    rule"). `RealAnswerLabelStage` below is the staged gate: a
    `LabeledVolunteerAnswer` can only become a `TrainingExample` once its
    stage is `HUMAN_REVIEWED` — `to_training_example` raises otherwise.
  - Splitting is volunteer-level, never answer-level (protocol §6):
    `group_of_by_volunteer` + `split_volunteer_answers` key every answer by
    `volunteer_id`, reusing `training_experimentation.split_dataset_by_group`
    unmodified.
  - No PII fields exist on these models AT ALL (no `name`, `email`, `phone`
    fields to accidentally populate) — the absence is structural, not a
    runtime filter. Free-text fields (`project_title`, `short_project_
    description`, `answer_text`) get a conservative regex sweep as a
    backstop, per protocol §9's "PII check" row.

Nothing in this module collects real data, calls an LLM, trains anything, or
touches the seed/rubric/validator/acceptance-threshold code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from evaluation_dimensions import CANONICAL_DIMENSIONS, EvaluationDimension
from human_benchmark import (
    HUMAN_BENCHMARK_ID_PREFIX,
    HumanAnnotation,
    HumanBenchmarkItem,
)
from question_families import ReasoningType
from question_specification import (
    Grounding,
    ProjectGrounding,
    QuestionCategory,
    QuestionSpecification,
    SourceType,
)
from rubric_judge import JudgeVerdict
from training_example import (
    ContradictionLabel,
    DimensionLabel,
    OverallLabel,
    ProvenanceSource,
    TrainingExample,
    TrainingExampleInputs,
    TrainingExampleLabels,
    TrainingExampleMetadata,
    TrainingExamplePrivacy,
    TrainingExampleProvenance,
)

# The rubric version stamped onto every human_reviewed real example's
# `labeling_guideline_version` (schema requires this to be a non-empty
# string when label_source="human_reviewed"). Bump this if the four-
# dimension rubric text (evaluation_dimensions.py) is ever revised in a way
# that would make an older annotation's guideline meaningfully different.
LABELING_GUIDELINE_VERSION = "four_dimension_rubric_v1"

_MAX_TIER = 4


# ═════════════════════════════════════════════════════════════════════════════
# 1. Representing a collected volunteer record
# ═════════════════════════════════════════════════════════════════════════════


class VolunteerAnswerRecord(BaseModel):
    """One collected (question, answer) pair from one volunteer sitting.

    Deliberately self-contained (project context is denormalized onto every
    answer row) — same convention the hand-authored seed's own JSONL rows
    already use, and it keeps per-record validation simple (no join step
    needed to check "does this record have everything it needs").

    Deliberately has NO name/email/phone/employer field of any kind — the
    absence is structural, not a runtime filter (protocol §1's "explicitly
    NOT collected" list)."""

    model_config = ConfigDict(frozen=True)

    volunteer_id: str
    session_id: str
    answer_index: int  # 0-based position within this volunteer's answers; disambiguates the group key

    project_title: str
    technologies: tuple[str, ...]
    short_project_description: str

    question_text: str
    answer_text: str
    expected_concepts: tuple[str, ...] = ()
    reasoning_type: ReasoningType

    collection_batch_id: str
    collected_at: str  # ISO8601

    @model_validator(mode="after")
    def _validate(self) -> "VolunteerAnswerRecord":
        if not re.fullmatch(r"vol_[a-zA-Z0-9]+", self.volunteer_id):
            raise ValueError(
                f"volunteer_id must look like an anonymized code (e.g. 'vol_07'), got {self.volunteer_id!r} "
                "-- never a real name"
            )
        if not self.session_id.strip():
            raise ValueError("session_id must not be empty")
        if self.answer_index < 0:
            raise ValueError("answer_index must be >= 0")
        if not self.project_title.strip():
            raise ValueError("project_title must not be empty")
        if not self.technologies:
            raise ValueError("technologies must not be empty (needed for grounding fidelity + judge context)")
        if not self.short_project_description.strip():
            raise ValueError("short_project_description must not be empty (needed to judge Grounding & Ownership)")
        if not self.question_text.strip():
            raise ValueError("question_text must not be empty")
        if not self.answer_text.strip():
            raise ValueError("answer_text must not be empty")
        if not self.collection_batch_id.strip():
            raise ValueError("collection_batch_id must not be empty")
        if not self.collected_at.strip():
            raise ValueError("collected_at must not be empty")
        return self

    @property
    def record_id(self) -> str:
        """Deterministic, stable key for this one answer -- used as the
        `split_dataset_by_group` example-id stand-in before a real
        TrainingExample (with its own uuid-based id) exists."""
        return f"{self.volunteer_id}__{self.session_id}__{self.answer_index}"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Field validation (structural, via pydantic above) + 3. privacy checks
# ═════════════════════════════════════════════════════════════════════════════

# Conservative, deterministic regex backstop -- never a semantic/NLP model,
# same "closed, explicit, conservative" discipline as dataset_filters.py's
# validator repair. This is a BACKSTOP for the manual redaction pass
# (protocol §2 step 3), never a replacement for it.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_SECRET_MARKERS: tuple[str, ...] = (
    "password", "passwd", "api_key", "apikey", "secret_key", "access_token",
    "private_key", "ssn", "social security", "credit card",
)
_NAME_INTRO_MARKERS: tuple[str, ...] = (
    "my name is", "i am ", "i'm ", "my manager", "my boss", "reach me at", "contact me at",
)


def pii_risk_findings(text: str) -> tuple[str, ...]:
    """Conservative regex sweep over one free-text field. Returns a tuple of
    short finding labels (empty if nothing found) -- never raises, never
    silently redacts; a human still makes the redaction call (protocol §2
    step 3), this is only the automated backstop (protocol §9's PII-check
    row)."""
    if not text:
        return ()
    lower = text.lower()
    findings = []
    if _EMAIL_RE.search(text):
        findings.append("email_like_pattern")
    if _PHONE_RE.search(text):
        findings.append("phone_like_pattern")
    for marker in _SECRET_MARKERS:
        if marker in lower:
            findings.append(f"secret_marker:{marker}")
    for marker in _NAME_INTRO_MARKERS:
        if marker in lower:
            findings.append(f"identifying_phrase:{marker!r}")
    return tuple(findings)


@dataclass(frozen=True)
class RecordValidationResult:
    """Per-record verdict: schema validity is enforced by
    `VolunteerAnswerRecord` itself (pydantic raises at construction); this
    layers the PRIVACY sweep on top, which is advisory-blocking (a record
    with findings should not be promoted until a human confirms/redacts),
    not a hard pydantic-level rejection."""

    accepted: bool
    pii_findings: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return self.accepted and not self.pii_findings


def validate_volunteer_answer_record(record: VolunteerAnswerRecord) -> RecordValidationResult:
    """Runs the privacy backstop over every free-text field on the record.
    Required-field validation already happened when `record` was
    constructed (pydantic) -- reaching this function at all means the
    schema-level checks already passed."""
    findings: list[str] = []
    for text in (record.project_title, record.short_project_description, record.answer_text):
        findings.extend(pii_risk_findings(text))
    return RecordValidationResult(accepted=True, pii_findings=tuple(findings))


# ═════════════════════════════════════════════════════════════════════════════
# Staged labeling (the "important labeling rule")
# ═════════════════════════════════════════════════════════════════════════════


class RealAnswerLabelStage(str, Enum):
    """Where a collected real answer is in the labeling pipeline (protocol
    §5/§7): real collected -> profile-blind judge -> human review/spot-check
    -> eligible for promotion. A judge-only score is NEVER sufficient to
    call an item "human_reviewed" -- that is exactly the mislabeling the
    task explicitly forbids."""

    COLLECTED = "collected"                    # no labels yet
    JUDGED_PENDING_REVIEW = "judged_pending_review"  # profile-blind judge scored it; NOT yet promotable
    HUMAN_REVIEWED = "human_reviewed"           # a human annotator's label is the final label; promotable


@dataclass(frozen=True)
class LabeledVolunteerAnswer:
    """One volunteer answer plus its labeling state. `judge_verdicts` is the
    profile-blind judge's independent score (always present once labeled);
    `human_annotation` is set only once a human reviewer has actually scored
    it. `stage` is derived, not caller-asserted, by `stage_for`."""

    record: VolunteerAnswerRecord
    judge_verdicts: dict[EvaluationDimension, JudgeVerdict] = field(default_factory=dict)
    human_annotation: Optional[HumanAnnotation] = None

    @property
    def stage(self) -> RealAnswerLabelStage:
        if self.human_annotation is not None:
            return RealAnswerLabelStage.HUMAN_REVIEWED
        if self.judge_verdicts:
            return RealAnswerLabelStage.JUDGED_PENDING_REVIEW
        return RealAnswerLabelStage.COLLECTED


# ═════════════════════════════════════════════════════════════════════════════
# 4. Converting to TrainingExample + 5. provenance
# ═════════════════════════════════════════════════════════════════════════════


def build_specification(record: VolunteerAnswerRecord) -> QuestionSpecification:
    """Protocol §7's exact mapping. `source_id=volunteer_id` is deliberate --
    it is what makes `split_dataset_by_group` keyed on `source_id` already
    enforce volunteer-level (never answer-level) splitting for free."""
    return QuestionSpecification(
        id=record.record_id,
        category=QuestionCategory.PROJECT_DEEP_DIVE,
        grounding=Grounding(project=ProjectGrounding(
            title=record.project_title,
            summary=record.short_project_description,
            technologies=record.technologies,
        )),
        source_type=SourceType.PROJECT,
        source_id=record.volunteer_id,
        source_field="project",
        reason=f"volunteer pilot collection ({record.collection_batch_id})",
    )


def to_training_example(labeled: LabeledVolunteerAnswer) -> TrainingExample:
    """Builds a real `TrainingExample` (`provenance.source=REAL_SESSION`,
    `synthetic=None`) from a labeled volunteer answer.

    RAISES if `labeled.stage != HUMAN_REVIEWED` -- a judge-only-scored real
    answer must never become a training example with
    `label_source="human_reviewed"` (the important labeling rule). This is
    the one and only promotion gate; there is no bypass parameter."""
    if labeled.stage is not RealAnswerLabelStage.HUMAN_REVIEWED:
        raise ValueError(
            f"cannot promote a volunteer answer to TrainingExample until it is human-reviewed "
            f"(current stage: {labeled.stage.value!r}, record_id={labeled.record.record_id!r}). "
            "A profile-blind judge score alone is not sufficient -- see "
            "docs/architecture/Volunteer_Pilot_Protocol.md §5/§7."
        )
    record = labeled.record
    annotation = labeled.human_annotation
    assert annotation is not None  # guaranteed by `stage` above

    dimension_labels = tuple(
        DimensionLabel(
            name=dl.dimension,
            score=round(dl.score / _MAX_TIER, 4),
        )
        for dl in annotation.dimension_labels
    )
    avg_tier = sum(dl.score for dl in annotation.dimension_labels) / len(annotation.dimension_labels)
    overall_score = round(avg_tier / _MAX_TIER, 4)
    grade = (
        "excellent" if overall_score >= 0.90 else
        "good" if overall_score >= 0.70 else
        "adequate" if overall_score >= 0.50 else
        "weak" if overall_score >= 0.30 else "poor"
    )

    now = datetime.now(timezone.utc).isoformat()
    return TrainingExample(
        metadata=TrainingExampleMetadata(example_id=f"real_vol_{record.record_id}", created_at=now),
        provenance=TrainingExampleProvenance(
            source=ProvenanceSource.REAL_SESSION,
            collection_batch_id=record.collection_batch_id,
            real_session_id=record.session_id,
        ),
        inputs=TrainingExampleInputs(
            specification=build_specification(record),
            question_text=record.question_text,
            reasoning_type=record.reasoning_type,
            answer_text=record.answer_text,
            expected_concepts=record.expected_concepts,
        ),
        privacy=TrainingExamplePrivacy(
            contains_pii=False,
            anonymized=True,
            anonymization_method="manual redaction + name/id decoupling (volunteer pilot protocol §2)",
        ),
        synthetic=None,
        labels=TrainingExampleLabels(
            label_source="human_reviewed",
            labeling_guideline_version=LABELING_GUIDELINE_VERSION,
            dimension_labels=dimension_labels,
            contradiction_label=ContradictionLabel(contradiction_present=False),
            overall_label=OverallLabel(
                score=overall_score, grade=grade,
                rationale=f"Human-reviewed label (annotator {annotation.annotator_id}) on a real volunteer answer.",
            ),
        ),
    )


# ═════════════════════════════════════════════════════════════════════════════
# 6. Volunteer-level grouping
# ═════════════════════════════════════════════════════════════════════════════


def group_of_by_volunteer(records: list[VolunteerAnswerRecord]) -> dict[str, str]:
    """`record_id -> volunteer_id`, the input `split_dataset_by_group` needs
    to guarantee every answer from the same volunteer lands in the same
    split (protocol §6's hard rule)."""
    return {r.record_id: r.volunteer_id for r in records}


def split_volunteer_answers(
    records: list[VolunteerAnswerRecord],
    split_ratios: tuple[float, float, float] = (0.8, 0.2, 0.0),
    seed: str = "volunteer_pilot_v1",
):
    """Volunteer-level (never answer-level) train/val split, reusing
    `training_experimentation.split_dataset_by_group` unmodified.
    Default ratios have a 0.0 test share -- per protocol §6, the frozen
    human benchmark (held-out VOLUNTEERS, see below) is this stratum's held-
    out signal; a separate answer-level test split would just fragment an
    already-small pool for no benefit."""
    from training_experimentation import split_dataset_by_group

    group_of = group_of_by_volunteer(records)
    record_ids = tuple(group_of.keys())
    return split_dataset_by_group(record_ids, group_of, split_ratios, seed)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Frozen benchmark path
# ═════════════════════════════════════════════════════════════════════════════


def partition_benchmark_volunteers(
    all_volunteer_ids: list[str],
    held_out_volunteer_ids: list[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Splits the full volunteer roster into (benchmark_ids, trainval_ids).
    `held_out_volunteer_ids` is caller-supplied (a deliberate roster
    decision -- e.g. the first 8-12 recruited -- not algorithmically
    inferred), so this function's only job is to validate the partition is
    total and disjoint, which is where a silent bug would otherwise hide."""
    all_set = set(all_volunteer_ids)
    held_out_set = set(held_out_volunteer_ids)
    unknown = held_out_set - all_set
    if unknown:
        raise ValueError(f"held_out_volunteer_ids contains ids not in all_volunteer_ids: {sorted(unknown)}")
    trainval_ids = tuple(v for v in all_volunteer_ids if v not in held_out_set)
    return tuple(held_out_volunteer_ids), trainval_ids


def assert_no_volunteer_split_leakage(
    benchmark_volunteer_ids: tuple[str, ...],
    trainval_group_of: dict[str, str],
) -> None:
    """Hard guard mirroring `human_benchmark.assert_disjoint_from_training`'s
    discipline, but at the VOLUNTEER level (protocol §6's specific concern):
    fails loudly if any volunteer assigned to the frozen benchmark also
    appears as a group-key value among the train/val records."""
    trainval_volunteer_ids = set(trainval_group_of.values())
    overlap = set(benchmark_volunteer_ids) & trainval_volunteer_ids
    if overlap:
        raise ValueError(
            f"volunteer(s) {sorted(overlap)} appear in BOTH the frozen benchmark and train/val -- "
            "a volunteer must never have answers in both (Volunteer_Pilot_Protocol.md §6)"
        )


def benchmark_grounding_text(record: VolunteerAnswerRecord) -> str:
    """The grounding TEXT for a benchmark-bound record, kept in the pilot's
    own storage alongside (never inside) the frozen `HumanBenchmarkItem` --
    protocol §7's documented workaround for `grounding_source` being a bare
    identifier on that frozen schema. Same flattening convention as
    `model_backbone.grounding_to_text` (title + summary + technologies)."""
    parts = [record.project_title, record.short_project_description, *record.technologies]
    return " ".join(p for p in parts if p).strip()


def to_human_benchmark_item(labeled: LabeledVolunteerAnswer) -> HumanBenchmarkItem:
    """Builds a `HumanBenchmarkItem` for a benchmark-bound volunteer answer.

    RAISES if `labeled.stage != HUMAN_REVIEWED` -- exactly the same
    promotion gate as `to_training_example`; the frozen benchmark's
    `final_labels` must come from human annotation/adjudication, never
    copied from the judge (protocol §5, point 4)."""
    if labeled.stage is not RealAnswerLabelStage.HUMAN_REVIEWED:
        raise ValueError(
            f"cannot promote a volunteer answer to HumanBenchmarkItem until it is human-reviewed "
            f"(current stage: {labeled.stage.value!r}, record_id={labeled.record.record_id!r})."
        )
    record = labeled.record
    annotation = labeled.human_annotation
    assert annotation is not None

    return HumanBenchmarkItem(
        item_id=f"{HUMAN_BENCHMARK_ID_PREFIX}vol_{record.record_id}",
        question_text=record.question_text,
        answer_text=record.answer_text,
        grounding_source=record.volunteer_id,
        category=QuestionCategory.PROJECT_DEEP_DIVE.value,
        reasoning_type=record.reasoning_type.value,
        expected_concepts=record.expected_concepts,
        annotations=(annotation,),
        final_labels=annotation.dimension_labels,
    )
