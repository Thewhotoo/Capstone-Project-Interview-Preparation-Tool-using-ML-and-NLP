"""
First End-to-End Experiment — validates that the full ML research track
built across sessions 1-6 (Stage A generation -> DatasetManifest ->
Training & Experimentation -> Model-Implementation -> Evaluator promotion)
actually works together on a real dataset, trained against the REAL
pretrained `microsoft/deberta-v3-base` backbone (never the tiny random-init
test backbone).

THIS IS AN EXPERIMENT SCRIPT, NOT A NEW SUBSYSTEM: every step below calls
existing, already-tested code. Nothing here defines a new class, a new
Pydantic model, or a new architectural concept. Two minimal, explicitly
flagged additions were required to make the experiment meaningful (not to
add new capability):

  1. A pool of (specification, question_text, reasoning_type) built via the
     REAL, unmodified Planner + Question Realizer (Phases 1/2) over the
     existing shared test fixture (`_planning_test_fixtures.sample_profile_dict()`)
     — this IS how Stage A's pool is meant to be produced in real use;
     nothing new.
  2. A handful of `expected_concepts_registry.register_expected_concepts`
     calls for the sample profile's own technologies (redis, flask, docker,
     sbert) — using that registry exactly as its own docstring already
     describes ("a human... adds a table entry later"), not a schema change.
     Without this, `expected_concepts_for(...)` would legitimately return
     empty for every unit on this profile (none of its technologies were
     previously registered) and the concept-observation head would never be
     exercised by this dataset.

GENERATION CLIENT (experiment configuration only — no architecture change):
a first run with the REAL `GeminiGenerationClient` hit the configured API
key's free-tier daily quota (20 requests/day/model) after only 4/50
examples — those 4 real, Gemini-generated examples are preserved as
evidence the live generation path works end-to-end (see
`experiment_log_real_gemini_partial.txt`), closing out a previously-open
item (SESSION_HANDOFF.md §6 item 7: "exercise GeminiGenerationClient
against a live Gemini call"). This run instead uses the existing, frozen,
deterministic `FakeGenerationClient` (`GENERATION_CLIENT_MODE = "fake"`
below — the ONLY thing that changed; still the same
`synthetic_generation_pipeline.generate_training_example`,
`coverage_strategy.plan_batch`, etc., completely unmodified) to validate the
REST of the pipeline (DatasetManifest, split, real `deberta-v3-base`
training, benchmarking, promotion) without waiting on quota. This is an
ENGINEERING INTEGRATION experiment — validating that the pipeline's plumbing
is correct end-to-end — not a research-quality data/model-quality
experiment; the resulting dataset's answer text is templated, not real
LLM prose. Once quota resets (or a higher API quota is available), re-run
with `GENERATION_CLIENT_MODE = "gemini"` and compare dataset quality between
the two runs.
"""

from __future__ import annotations

import os

# See run_second_experiment.py's module docstring / top-of-file comment for
# why: works around a reproducible upstream transformers 5.13.0 crash on
# Windows when loading real pretrained weights. Added defensively here too
# (this script already completed successfully once, but the crash is
# threading-timing-dependent and could recur on a future re-run).
os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")

import sys
import tempfile
import time
from collections import Counter

from _planning_test_fixtures import sample_profile_dict
from conversation_memory import ConversationMemory
from coverage_strategy import CoverageUnit, plan_batch
from dataset_manifest import assemble_manifest
from evaluation_result import ConceptObservationStatus
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
from training_example import QualityTier
from training_experimentation import (
    ExperimentConfig,
    PromotionPolicy,
    assemble_checkpoint,
    decide_promotion,
    run_benchmark,
    split_dataset,
)

BATCH_SIZE = 50
RANDOM_SEED = 42
MAX_LENGTH = 128
TRAIN_BATCH_SIZE = 4
NUM_EPOCHS = 1
LEARNING_RATE = 2e-5

# Experiment configuration only (see module docstring) -- "gemini" (real,
# rate-limited) or "fake" (deterministic, network-free, existing
# FakeGenerationClient). Everything downstream is identical either way.
GENERATION_CLIENT_MODE = os.environ.get("EXPERIMENT_GENERATION_CLIENT", "fake").strip().lower()
if GENERATION_CLIENT_MODE not in ("fake", "gemini"):
    raise ValueError(f"GENERATION_CLIENT_MODE must be 'fake' or 'gemini', got {GENERATION_CLIENT_MODE!r}")

_VERSION_SUFFIX = "fake_client" if GENERATION_CLIENT_MODE == "fake" else "real_gemini"
DATASET_VERSION = f"v_experiment_001_{_VERSION_SUFFIX}"
MODEL_VERSION = f"deberta_v3_base_experiment_001_{_VERSION_SUFFIX}"

_CORE_GRADES = frozenset({"poor", "weak", "adequate", "good", "excellent"})


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register_experiment_expected_concepts() -> None:
    """Additive-only registry population (see module docstring, item 2)."""
    seed = {
        "redis": ("caching", "key-value storage", "expiration policies", "pub/sub"),
        "flask": ("routing", "request handling", "templating", "wsgi"),
        "docker": ("containerization", "images", "isolation", "deployment"),
        "sbert": ("semantic similarity", "sentence embeddings", "cosine similarity"),
    }
    for name, concepts in seed.items():
        if not lookup(name):
            register_expected_concepts(name, concepts)


def build_pool_from_profile() -> tuple[CoverageUnit, ...]:
    """Real Planner + Realizer, unmodified (see module docstring, item 1)."""
    profile = sample_profile_dict()
    planner = Planner(profile)
    memory = ConversationMemory()
    state = ConversationState()
    units: list[CoverageUnit] = []
    turn = 1
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

        units.append(CoverageUnit(
            specification=spec, question_text=question.question_text,
            reasoning_type=question.reasoning_type, expected_concepts=expected_concepts,
        ))
        turn += 1
    return tuple(units)


def main() -> int:
    _log("=== STEP 1: Generate the first real synthetic dataset ===")
    register_experiment_expected_concepts()
    pool = build_pool_from_profile()
    _log(f"Built a pool of {len(pool)} discussion units from the sample candidate profile (real Planner + Realizer).")
    for u in pool:
        _log(f"  - [{u.specification.category.value}] {u.reasoning_type.value}: "
             f"{u.question_text[:70]!r} (expected_concepts={u.expected_concepts})")

    if not pool:
        _log("BLOCKER: no discussion units were produced from the sample profile -- cannot generate a dataset.")
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
            # A real Gemini call can fail for reasons outside the
            # validation/rejection state machine entirely (empty/malformed
            # response, transient network/rate-limit error, etc.) --
            # generate_training_example does not catch these (by design,
            # it only retries on a VALIDATION rejection), so this script,
            # as the caller wanting partial-batch results, catches them
            # here instead of letting one flaky call abort the whole batch.
            failures.append((unit.recipe_id, f"{type(e).__name__}: {e}"))
            _log(f"  GENERATION ERROR {unit.recipe_id}: {type(e).__name__}: {e}")
        if i % 10 == 0 or i == total:
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

    _log("--- Dataset statistics (validated at construction by DatasetManifest/TrainingExample's own frozen validators) ---")
    _log(f"  dataset_version: {manifest.dataset_version}")
    _log(f"  total examples: {len(manifest.example_ids)}")
    _log(f"  tier_distribution: {dict(manifest.tier_distribution)}")
    _log(f"  label_source_distribution: {dict(manifest.label_source_distribution)}")
    _log(f"  generator_provenance (prompt_id, prompt_version): {manifest.generator_provenance}")
    _log(f"  reasoning_type distribution: {dict(reasoning_counts)}")
    _log(f"  category distribution: {dict(category_counts)}")
    _log(f"  concept_observation status distribution: {dict(concept_status_counts)}")
    _log(f"  missing_reasoning category distribution: {dict(missing_reasoning_counts)}")
    _log(f"  answer word count: min={min(answer_word_counts)}, max={max(answer_word_counts)}, "
         f"avg={sum(answer_word_counts) / len(answer_word_counts):.1f}")

    _log("=== STEP 2: Split the dataset (deterministic, existing split_dataset) ===")
    example_ids = tuple(e.metadata.example_id for e in stamped_examples)
    split = split_dataset(example_ids, split_ratios=(0.7, 0.15, 0.15), seed=f"split::{DATASET_VERSION}")
    _log(f"Split sizes: train={len(split.train_ids)}, val={len(split.val_ids)}, test={len(split.test_ids)}")
    for name, ids in (("train", split.train_ids), ("val", split.val_ids), ("test", split.test_ids)):
        tiers = Counter(by_id[i].synthetic.intended_quality_tier.value for i in ids)
        _log(f"  {name} tier distribution: {dict(tiers)}")
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

    _log(f"Loading REAL pretrained {backbone_config.hf_model_id} weights (first run downloads ~700MB)...")
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
         f"(off_topic/contradictory are excluded by design — grade_to_ordinal's own rule).")

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
    policy = PromotionPolicy()  # default: candidate must merely match-or-beat baseline QWK
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
