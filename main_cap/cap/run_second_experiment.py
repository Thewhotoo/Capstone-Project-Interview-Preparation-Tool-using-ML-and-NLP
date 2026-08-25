"""
Second End-to-End Experiment — the research-methodology milestone following
the first end-to-end experiment (`run_first_experiment.py`, kept unmodified
as a historical artifact for comparison). Same pipeline, same existing
infrastructure, TWO methodology fixes:

  1. SPECIFICATION-LEVEL train/val/test splitting
     (`training_experimentation.split_dataset_by_group`, new function,
     additive only) instead of example-level splitting
     (`training_experimentation.split_dataset`, unchanged, still used
     elsewhere). The first experiment's benchmark drew train and test
     examples from the SAME underlying QuestionSpecifications (just
     different quality tiers) — a model could score well by recognizing
     the topic, not by generalizing. This run guarantees every example
     derived from one specification lands entirely in ONE split.

  2. POOL DIVERSITY: the generation pool is now built from FIVE candidate
     profiles spanning different technical domains
     (`experiment_candidate_profiles.all_experiment_profiles()` — backend,
     frontend, data/ML, DevOps/cloud, mobile) instead of one hardcoded
     backend-flavored profile. Same unmodified Planner/TopicPool/Question
     Realizer, run once per profile.

THIS REMAINS AN EXPERIMENT SCRIPT, NOT A NEW SUBSYSTEM. `synthetic_generation_pipeline.py`,
`coverage_strategy.py`, `dataset_manifest.py`, `model_backbone.py`,
`model_heads.py`, `model_dataset.py`, `model_evaluator.py`, `Planner`,
`TopicPool`, `QuestionRealizer` are all completely unmodified from the first
experiment. Still uses the existing `FakeGenerationClient` (real
`GeminiGenerationClient` remains blocked by the configured key's free-tier
daily quota, per session 7's finding) — dataset content is templated, not
real LLM prose; this is a methodology/diversity experiment, not a
data-quality experiment. Real generation remains a separate, still-open
follow-up once quota allows it.

ONE IMPLEMENTATION SUBTLETY handled here, not a design change: `TopicPool`
assigns specification ids ("topic_0", "topic_1", ...) starting fresh at 0
for EACH `Planner` instance, so five separate profiles produce COLLIDING
raw specification ids. The group key used for `split_dataset_by_group` is
therefore `f"profile{i}::{spec.id}"` (built here, in this script, while
iterating profiles) rather than the raw `specification.id` — no change to
`QuestionSpecification`, `TopicPool`, or any id scheme.
"""

from __future__ import annotations

import os

# Must be set before any `transformers` import touches model loading.
# Environment configuration only -- works around a reproducible upstream
# transformers 5.13.0 crash on Windows ("Windows fatal exception: access
# violation" inside core_model_loading.py's new multi-threaded
# _materialize_copy state-dict loading path) when loading the real
# pretrained microsoft/deberta-v3-base weights. Confirmed via faulthandler
# that the crash happens entirely inside AutoModel.from_pretrained, before
# any of this project's own code runs. This env var is transformers' own
# documented escape hatch for disabling that specific code path -- no
# change to model_backbone.py or any other production module.
os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")

import sys
import tempfile
import time
from collections import Counter

from conversation_memory import ConversationMemory
from coverage_strategy import CoverageUnit, plan_batch
from dataset_manifest import assemble_manifest
from experiment_candidate_profiles import all_experiment_profiles
from expected_concepts_registry import expected_concepts_for, lookup, register_expected_concepts
from generation_client import FakeGenerationClient, GeminiGenerationClient
from heuristic_evaluator import HeuristicEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import save_checkpoint_artifact
from model_dataset import build_dataloaders
from model_evaluator import TrainedEvaluator, promote_trained_model
from model_heads import train_model
from planner import ConversationState, Planner
from question_realizer import realize
from question_specification import UnitStatus
from synthetic_generation_pipeline import GenerationRejectedError, generate_training_example
from training_experimentation import (
    ExperimentConfig,
    PromotionPolicy,
    assemble_checkpoint,
    decide_promotion,
    run_benchmark,
    split_dataset_by_group,
)

BATCH_SIZE = 120
RANDOM_SEED = 42
MAX_LENGTH = 128
TRAIN_BATCH_SIZE = 4
NUM_EPOCHS = 1
LEARNING_RATE = 2e-5

GENERATION_CLIENT_MODE = os.environ.get("EXPERIMENT_GENERATION_CLIENT", "fake").strip().lower()
if GENERATION_CLIENT_MODE not in ("fake", "gemini"):
    raise ValueError(f"GENERATION_CLIENT_MODE must be 'fake' or 'gemini', got {GENERATION_CLIENT_MODE!r}")

_VERSION_SUFFIX = "fake_client" if GENERATION_CLIENT_MODE == "fake" else "real_gemini"
DATASET_VERSION = f"v_experiment_002_multi_profile_{_VERSION_SUFFIX}"
MODEL_VERSION = f"deberta_v3_base_experiment_002_multi_profile_{_VERSION_SUFFIX}"

_CORE_GRADES = frozenset({"poor", "weak", "adequate", "good", "excellent"})


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register_experiment_expected_concepts() -> None:
    """Additive-only registry population — same pattern session 7 already
    used, extended with the new profiles' technologies."""
    seed = {
        "redis": ("caching", "key-value storage", "expiration policies", "pub/sub"),
        "flask": ("routing", "request handling", "templating", "wsgi"),
        "docker": ("containerization", "images", "isolation", "deployment"),
        "sbert": ("semantic similarity", "sentence embeddings", "cosine similarity"),
        "react": ("component composition", "state management", "rendering", "hooks"),
        "typescript": ("static typing", "type inference", "interfaces"),
        "jest": ("unit testing", "mocking", "test coverage"),
        "webpack": ("bundling", "code splitting", "build configuration"),
        "pandas": ("dataframes", "data cleaning", "feature engineering"),
        "scikit-learn": ("model training", "cross-validation", "feature engineering"),
        "pytorch": ("tensors", "model training", "gradient descent", "neural network layers"),
        "terraform": ("infrastructure as code", "state management", "resource provisioning"),
        "kubernetes": ("container orchestration", "deployments", "scaling", "service discovery"),
        "github actions": ("ci/cd pipelines", "workflow automation"),
        "swift": ("memory management", "protocol-oriented programming", "concurrency"),
        "swiftui": ("declarative ui", "state management", "view composition"),
        "combine": ("reactive programming", "publishers and subscribers"),
    }
    for name, concepts in seed.items():
        if not lookup(name):
            register_expected_concepts(name, concepts)


def build_pool_from_profiles(profiles: tuple[dict, ...]) -> tuple[tuple[CoverageUnit, ...], dict[str, str]]:
    """Real Planner + Realizer, unmodified, run once per profile. Returns
    the combined pool plus a specification.id -> globally-unique group-key
    mapping (see module docstring's "ONE IMPLEMENTATION SUBTLETY")."""
    units: list[CoverageUnit] = []
    # Keyed by id(spec) -- the specification OBJECT's Python identity, not
    # its `.id` string field. `spec.id` (e.g. "topic_0") is assigned by
    # TopicPool starting fresh at 0 for EACH Planner instance, so it
    # collides across the 5 profiles; the object reference itself does not
    # (each Planner constructs brand-new QuestionSpecification instances)
    # and survives unchanged all the way through
    # BatchUnit/GenerationRecipe/TrainingExample.inputs.specification
    # (Pydantic does not copy an already-valid nested model instance by
    # default), so it's a safe, purely-script-level way to recover which
    # profile a generated example came from.
    spec_group_key: dict[int, str] = {}
    for profile_index, profile in enumerate(profiles):
        planner = Planner(profile)
        memory = ConversationMemory()
        state = ConversationState()
        turn = 1
        profile_unit_count = 0
        while True:
            spec = planner.plan_next(state)
            if spec is None:
                break
            question, variant_idx = realize(spec, memory, turn)
            memory.record_turn(question, variant_idx)
            planner.advance(spec.id, UnitStatus.COVERED)
            state = ConversationState(last_category=spec.category)

            if spec.grounding.project is not None:
                names = (spec.grounding.project.title, *spec.grounding.project.technologies, *spec.grounding.project.concepts)
            elif spec.grounding.experience is not None:
                names = (spec.grounding.experience.company,)
            else:
                names = (spec.grounding.certification.name,)
            expected_concepts = expected_concepts_for(names)

            spec_group_key[id(spec)] = f"profile{profile_index}::{spec.id}"
            units.append(CoverageUnit(
                specification=spec, question_text=question.question_text,
                reasoning_type=question.reasoning_type, expected_concepts=expected_concepts,
            ))
            turn += 1
            profile_unit_count += 1
        _log(f"  profile {profile_index} ({profile.get('predicted_domain', profile.get('candidate_name'))!r}): "
             f"{profile_unit_count} units, {len(planner.rejected)} rejected")
    return tuple(units), spec_group_key


def main() -> int:
    _log("=== STEP 1: Generate a diversified synthetic dataset (5 candidate profiles) ===")
    register_experiment_expected_concepts()
    profiles = all_experiment_profiles()
    pool, spec_group_key = build_pool_from_profiles(profiles)
    _log(f"Built a combined pool of {len(pool)} discussion units from {len(profiles)} candidate profiles.")

    if not pool:
        _log("BLOCKER: no discussion units were produced from the profiles -- cannot generate a dataset.")
        return 1

    coverage_plan = plan_batch(pool, batch_size=BATCH_SIZE, batch_seed=f"experiment::{DATASET_VERSION}")
    tier_counts = Counter(t.value for t in coverage_plan.quality_tiers)
    _log(f"CoverageStrategy planned {len(coverage_plan.units)} recipes. Tier distribution: {dict(tier_counts)}")

    if GENERATION_CLIENT_MODE == "fake":
        client = FakeGenerationClient()
        _log("Using FakeGenerationClient (deterministic, network-free) -- see module docstring for why.")
    else:
        client = GeminiGenerationClient()
        _log("Using the REAL GeminiGenerationClient -- live API calls, subject to quota.")

    examples = []
    failures: list[tuple[str, str]] = []
    total = len(coverage_plan.units)
    for i, (unit, tier) in enumerate(zip(coverage_plan.units, coverage_plan.quality_tiers), start=1):
        try:
            outcome = generate_training_example(
                recipe_id=unit.recipe_id, specification=unit.specification, question_text=unit.question_text,
                reasoning_type=unit.reasoning_type, expected_concepts=unit.expected_concepts,
                quality_tier=tier, client=client, generation_batch_id=DATASET_VERSION,
            )
            examples.append(outcome.example)
        except GenerationRejectedError as e:
            failures.append((unit.recipe_id, str(e)))
            _log(f"  REJECTED {unit.recipe_id}: {e}")
        except Exception as e:
            failures.append((unit.recipe_id, f"{type(e).__name__}: {e}"))
            _log(f"  GENERATION ERROR {unit.recipe_id}: {type(e).__name__}: {e}")
        if i % 20 == 0 or i == total:
            _log(f"  progress: {i}/{total} recipes processed ({len(examples)} accepted, {len(failures)} rejected)")

    _log(f"Generation complete: {len(examples)} accepted, {len(failures)} rejected out of {total}.")
    if not examples:
        _log("BLOCKER: zero examples were successfully generated -- cannot proceed.")
        return 1

    _log("Assembling DatasetManifest...")
    manifest, stamped_examples = assemble_manifest(tuple(examples), dataset_version=DATASET_VERSION)
    by_id = {e.metadata.example_id: e for e in stamped_examples}

    reasoning_counts = Counter(e.inputs.reasoning_type.value for e in stamped_examples)
    category_counts = Counter(e.inputs.specification.category.value for e in stamped_examples)
    concept_status_counts = Counter(
        c.status.value for e in stamped_examples for c in e.labels.concept_labels
    )
    missing_reasoning_counts = Counter(
        m.category for e in stamped_examples for m in e.labels.missing_reasoning_labels
    )
    answer_word_counts = [len(e.inputs.answer_text.split()) for e in stamped_examples]
    # NOTE: raw specification.id (e.g. "topic_0") collides across profiles
    # by TopicPool design -- use the profile-qualified group key (see
    # build_pool_from_profiles) for an accurate unique-specification count.
    unique_specs = len({spec_group_key[id(e.inputs.specification)] for e in stamped_examples})
    # profile diversity: which of the 5 source_ids (project/experience/cert
    # names) each example traces back to, as a proxy for domain spread.
    source_counts = Counter(e.inputs.specification.source_id for e in stamped_examples)

    _log("--- Dataset statistics (validated at construction by DatasetManifest/TrainingExample's own frozen validators) ---")
    _log(f"  dataset_version: {manifest.dataset_version}")
    _log(f"  total examples: {len(manifest.example_ids)}")
    _log(f"  unique underlying specifications: {unique_specs}")
    _log(f"  tier_distribution: {dict(manifest.tier_distribution)}")
    _log(f"  label_source_distribution: {dict(manifest.label_source_distribution)}")
    _log(f"  generator_provenance (prompt_id, prompt_version): {manifest.generator_provenance}")
    _log(f"  reasoning_type distribution: {dict(reasoning_counts)}")
    _log(f"  category distribution: {dict(category_counts)}")
    _log(f"  source_id (topic) distribution: {dict(source_counts)}")
    _log(f"  concept_observation status distribution: {dict(concept_status_counts)}")
    _log(f"  missing_reasoning category distribution: {dict(missing_reasoning_counts)}")
    _log(f"  answer word count: min={min(answer_word_counts)}, max={max(answer_word_counts)}, "
         f"avg={sum(answer_word_counts) / len(answer_word_counts):.1f}")

    _log("=== STEP 2: Specification-level split (new split_dataset_by_group) ===")
    example_ids = tuple(e.metadata.example_id for e in stamped_examples)
    group_of = {
        example_id: spec_group_key[id(by_id[example_id].inputs.specification)]
        for example_id in example_ids
    }
    split = split_dataset_by_group(example_ids, group_of, split_ratios=(0.7, 0.15, 0.15), seed=f"split::{DATASET_VERSION}")
    _log(f"Split sizes: train={len(split.train_ids)}, val={len(split.val_ids)}, test={len(split.test_ids)}")

    train_specs = {group_of[i] for i in split.train_ids}
    val_specs = {group_of[i] for i in split.val_ids}
    test_specs = {group_of[i] for i in split.test_ids}
    _log(f"Unique specifications per split: train={len(train_specs)}, val={len(val_specs)}, test={len(test_specs)}")
    overlap = (train_specs & val_specs) | (train_specs & test_specs) | (val_specs & test_specs)
    _log(f"Specification overlap across splits: {len(overlap)} (must be 0 for a valid held-out split)")
    if overlap:
        _log("BLOCKER: specification overlap detected across splits -- split_dataset_by_group has a defect.")
        return 1

    for name, ids in (("train", split.train_ids), ("val", split.val_ids), ("test", split.test_ids)):
        tiers = Counter(by_id[i].synthetic.intended_quality_tier.value for i in ids)
        sources = Counter(by_id[i].inputs.specification.source_id for i in ids)
        _log(f"  {name} tier distribution: {dict(tiers)}")
        _log(f"  {name} topic (source_id) distribution: {dict(sources)}")
    if not split.train_ids or not split.val_ids or not split.test_ids:
        _log("BLOCKER: one of train/val/test is empty -- cannot proceed with training/benchmarking as designed.")
        return 1

    _log("=== STEP 3: Train the REAL pretrained microsoft/deberta-v3-base backbone ===")
    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=MAX_LENGTH)
    _log(f"Loading real tokenizer for {backbone_config.hf_model_id} (first run downloads it)...")
    tokenizer = build_tokenizer(backbone_config)

    train_loader, val_loader, test_loader = build_dataloaders(
        stamped_examples, split, tokenizer, backbone_config, batch_size=TRAIN_BATCH_SIZE, seed=RANDOM_SEED,
    )
    _log(f"Dataloaders built: train_batches={len(train_loader)}, val_batches={len(val_loader)}, "
         f"test_batches={len(test_loader)} (train shuffle seeded with RANDOM_SEED={RANDOM_SEED})")

    _log(f"Loading REAL pretrained {backbone_config.hf_model_id} weights...")
    t0 = time.time()
    model = train_model(
        train_loader, val_loader, backbone_config,
        num_epochs=NUM_EPOCHS, learning_rate=LEARNING_RATE, random_seed=RANDOM_SEED,
    )
    _log(f"Training complete in {time.time() - t0:.1f}s ({NUM_EPOCHS} epoch(s), "
         f"lr={LEARNING_RATE}, batch_size={TRAIN_BATCH_SIZE}, max_length={MAX_LENGTH}).")

    checkpoint_path = os.path.join(tempfile.gettempdir(), f"{MODEL_VERSION}.pt")
    save_checkpoint_artifact(model, checkpoint_path)
    experiment_config = ExperimentConfig(
        backbone_name=backbone_config.hf_model_id, random_seed=RANDOM_SEED, dataset_version=DATASET_VERSION,
        parameters={
            "num_epochs": NUM_EPOCHS, "learning_rate": LEARNING_RATE,
            "batch_size": TRAIN_BATCH_SIZE, "max_length": MAX_LENGTH, "pooling": backbone_config.pooling,
            "split_method": "specification_level_group_holdout", "num_profiles": len(profiles),
        },
    )
    checkpoint = assemble_checkpoint(model_version=MODEL_VERSION, experiment_config=experiment_config, artifact_uri=checkpoint_path)
    _log(f"Checkpoint saved: model_version={checkpoint.model_version!r} -> artifact_uri={checkpoint.artifact_uri!r}")

    _log("=== STEP 4: Benchmark against HeuristicEvaluator (existing run_benchmark) ===")
    trained_evaluator = TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)
    baseline = HeuristicEvaluator()

    test_examples = tuple(by_id[i] for i in split.test_ids)
    core_test_examples = tuple(e for e in test_examples if e.labels.overall_label.grade in _CORE_GRADES)
    _log(f"Benchmark set: {len(core_test_examples)}/{len(test_examples)} test examples have a core ordinal grade "
         f"(off_topic/contradictory are excluded by design — grade_to_ordinal's own rule). "
         f"Drawn from {len(test_specs)} specifications NEVER seen in training.")

    if not core_test_examples:
        _log("BLOCKER: no core-grade examples in the test split -- cannot benchmark.")
        return 1

    t0 = time.time()
    benchmark = run_benchmark(trained_evaluator, baseline, core_test_examples, dataset_version=DATASET_VERSION)
    _log(f"Benchmark complete in {time.time() - t0:.1f}s.")
    _log(f"  candidate: {benchmark.candidate_evaluator_name} v{benchmark.candidate_evaluator_version} "
         f"-> QWK={benchmark.candidate_qwk:.4f}")
    _log(f"  baseline:  {benchmark.baseline_evaluator_name} v{benchmark.baseline_evaluator_version} "
         f"-> QWK={benchmark.baseline_qwk:.4f}")
    _log(f"  example_count={benchmark.example_count}, dataset_version={benchmark.dataset_version}")

    _log("=== STEP 5: Promotion decision (existing decide_promotion / PromotionPolicy) ===")
    policy = PromotionPolicy()
    decision = decide_promotion(checkpoint, benchmark, policy)
    _log(f"approved={decision.approved}")
    _log(f"rationale: {decision.rationale}")

    if decision.approved:
        promote_trained_model(checkpoint, decision, trained_evaluator, make_active=True)
        _log(f"Promoted and registered as the active evaluator: {trained_evaluator.name}")
    else:
        _log("NOT promoted -- registration skipped, per the existing (unmodified) promotion policy.")

    _log("=== EXPERIMENT COMPLETE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
