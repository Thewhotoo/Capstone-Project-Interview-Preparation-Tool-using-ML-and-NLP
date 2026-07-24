"""
Third Experiment — Dataset Scaling Milestone. Validates that the Stage A
generation pipeline scales structurally to thousands of examples drawn from
a much more diverse pool (36 curated, individually realistic candidate
profiles across 12 technical domains) while preserving every existing
architectural principle unchanged.

THIS IS AN EXPERIMENT SCRIPT, NOT A NEW SUBSYSTEM. Planner, TopicPool,
QuestionRealizer, coverage_strategy, synthetic_generation_pipeline,
generation_validation's core logic, dataset_manifest, and
training_experimentation are all completely unmodified. The only production
file touched this milestone is generation_validation.py's
_KNOWN_TECHNOLOGY_VOCABULARY (additive-only, approved) -- everything else
here is new, additive orchestration.

SCOPE: generation -> DatasetManifest -> specification-level split ->
persistence. Deliberately NO training/benchmark/promotion — this milestone
is about dataset scale and diversity, not model training throughput (which
the prior research audit flagged as CPU-bound and likely to take hours at
this scale; that is out of scope here, not solved).

Uses FakeGenerationClient (deterministic, network-free) per the approved
decision to continue treating real-Gemini generation as a separate future
experiment once API quota allows it.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections import Counter

from coverage_strategy import CoverageUnit, plan_batch
from dataset_manifest import assemble_manifest
from experiment_dataset_io import save_examples_jsonl
from experiment_profile_library import all_experiment_profiles
from expected_concepts_registry import expected_concepts_for, lookup, register_expected_concepts
from generation_client import FakeGenerationClient
from synthetic_generation_pipeline import GenerationRejectedError, generate_training_example
from training_experimentation import split_dataset_by_group

BATCH_SIZE = 2500
DATASET_VERSION = "v_experiment_003_scaled_library_fake_client"

_TECHNOLOGY_CONCEPTS: dict[str, tuple[str, ...]] = {
    # Backend / full stack
    "django": ("orm", "views and urls", "middleware", "migrations"),
    "flask": ("routing", "request handling", "templating", "wsgi"),
    "postgresql": ("relational modeling", "transactions", "indexing"),
    "celery": ("task queues", "background jobs", "retries"),
    "java": ("object-oriented design", "concurrency", "jvm"),
    "spring boot": ("dependency injection", "auto-configuration", "rest controllers"),
    "kafka": ("event streaming", "partitions", "consumer groups"),
    "go": ("goroutines", "channels", "static typing"),
    "grpc": ("protocol buffers", "streaming rpc", "service contracts"),
    "redis": ("caching", "key-value storage", "expiration policies", "pub/sub"),
    "kubernetes": ("container orchestration", "deployments", "scaling", "service discovery"),
    "envoy": ("service mesh", "traffic routing", "observability"),
    "node.js": ("event loop", "asynchronous i/o", "npm ecosystem"),
    "express": ("middleware", "routing"),
    "mongodb": ("document modeling", "indexing", "aggregation pipelines"),
    # Frontend
    "react": ("component composition", "state management", "rendering", "hooks"),
    "redux": ("centralized state", "actions and reducers"),
    "typescript": ("static typing", "type inference", "interfaces"),
    "vue": ("reactive data binding", "component composition"),
    "vuex": ("centralized state management"),
    "angular": ("dependency injection", "component architecture", "change detection"),
    "module federation": ("micro-frontends", "runtime code sharing"),
    "storybook": ("component documentation", "visual testing"),
    "rxjs": ("reactive streams", "observables"),
    # Data / ML
    "scikit-learn": ("model training", "cross-validation", "feature engineering"),
    "pandas": ("dataframes", "data cleaning", "feature engineering"),
    "pytorch": ("tensors", "model training", "gradient descent", "neural network layers"),
    "hugging face": ("pretrained transformers", "fine-tuning", "tokenization"),
    "spacy": ("named entity recognition", "tokenization", "nlp pipelines"),
    "langchain": ("prompt orchestration", "retrieval chains"),
    "faiss": ("vector search", "approximate nearest neighbors"),
    "mlflow": ("experiment tracking", "model registry"),
    "scala": ("functional programming", "jvm interop"),
    "spark": ("distributed data processing", "rdds", "windowed aggregation"),
    "snowflake": ("data warehousing", "elastic compute"),
    "databricks": ("lakehouse architecture", "notebooks", "delta lake"),
    "dbt": ("data transformation", "data lineage", "testing data models"),
    # Cloud / DevOps
    "terraform": ("infrastructure as code", "state management", "resource provisioning"),
    "aws": ("cloud infrastructure", "iam", "managed services"),
    "azure": ("cloud infrastructure", "resource groups"),
    "gcp": ("cloud infrastructure", "iam", "managed services"),
    "docker": ("containerization", "images", "isolation", "deployment"),
    "github actions": ("ci/cd pipelines", "workflow automation"),
    "prometheus": ("metrics collection", "alerting rules"),
    "grafana": ("dashboards", "visualization"),
    "ansible": ("configuration management", "playbooks", "idempotent automation"),
    # Security
    "burp suite": ("web application testing", "intercepting proxies"),
    "metasploit": ("exploit development", "penetration testing"),
    "splunk": ("log correlation", "siem", "alerting"),
    "wireshark": ("packet capture", "protocol analysis"),
    "nmap": ("network scanning", "port discovery"),
    # Mobile
    "react native": ("cross-platform mobile", "native modules"),
    "kotlin": ("null safety", "coroutines", "jvm interop"),
    "jetpack compose": ("declarative ui", "state hoisting"),
    "room": ("local persistence", "sqlite abstraction"),
    "swift": ("memory management", "protocol-oriented programming", "concurrency"),
    "swiftui": ("declarative ui", "state management", "view composition"),
    "combine": ("reactive programming", "publishers and subscribers"),
    # QA
    "selenium": ("browser automation", "element locators"),
    "cypress": ("end-to-end testing", "test runners"),
    "postman": ("api testing", "request collections"),
    "jmeter": ("load testing", "performance benchmarking"),
    "gatling": ("load testing", "scenario simulation"),
    "playwright": ("cross-browser testing", "end-to-end testing"),
    # Embedded / IoT
    "arduino": ("microcontroller programming", "sensor interfacing"),
    "mqtt": ("publish-subscribe messaging", "low-bandwidth protocols"),
    "freertos": ("real-time scheduling", "task priorities"),
    "ble": ("low-energy wireless", "gatt profiles"),
    "zephyr rtos": ("real-time scheduling", "device drivers"),
    "tensorflow lite": ("model quantization", "edge inference"),
    # Blockchain
    "solidity": ("smart contracts", "gas optimization", "evm"),
    "hardhat": ("smart contract testing", "local blockchain simulation"),
    "web3.js": ("blockchain client libraries", "transaction signing"),
    "truffle": ("smart contract deployment", "migrations"),
    "ethereum": ("blockchain consensus", "smart contracts"),
    "slither": ("static analysis", "vulnerability detection"),
}


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register_experiment_expected_concepts() -> None:
    """Additive-only registry population (same pattern as sessions 7-8)."""
    for name, concepts in _TECHNOLOGY_CONCEPTS.items():
        if not lookup(name):
            register_expected_concepts(name, concepts)


def build_pool_from_profiles(profiles: tuple[dict, ...]) -> tuple[tuple[CoverageUnit, ...], dict[int, str]]:
    """Real Planner + Realizer, unmodified. Returns the combined pool plus
    an id(spec) -> profile-qualified group-key mapping (same fix session 8
    established for the specification-id collision across profiles)."""
    from conversation_memory import ConversationMemory
    from planner import ConversationState, Planner
    from question_realizer import realize
    from question_specification import UnitStatus

    units: list[CoverageUnit] = []
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
        if profile_index % 6 == 0 or profile_index == len(profiles) - 1:
            _log(f"  ...built pool through profile {profile_index + 1}/{len(profiles)}")
    return tuple(units), spec_group_key


def main() -> int:
    _log("=== STEP 1: Build the pool from 36 curated candidate profiles across 12 domains ===")
    register_experiment_expected_concepts()
    profiles = all_experiment_profiles()
    _log(f"Loaded {len(profiles)} curated profiles.")
    pool, spec_group_key = build_pool_from_profiles(profiles)
    _log(f"Built a combined pool of {len(pool)} discussion units from {len(profiles)} candidate profiles "
         f"(vs. 40 units / 5 profiles in experiment 2).")

    if not pool:
        _log("BLOCKER: no discussion units were produced -- cannot generate a dataset.")
        return 1

    _log(f"=== STEP 2: Generate {BATCH_SIZE} examples via CoverageStrategy + FakeGenerationClient ===")
    coverage_plan = plan_batch(pool, batch_size=BATCH_SIZE, batch_seed=f"experiment::{DATASET_VERSION}")
    tier_counts = Counter(t.value for t in coverage_plan.quality_tiers)
    _log(f"CoverageStrategy planned {len(coverage_plan.units)} recipes. Tier distribution: {dict(tier_counts)}")

    client = FakeGenerationClient()
    examples = []
    failures: list[tuple[str, str]] = []
    total = len(coverage_plan.units)
    t0 = time.time()
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
        except Exception as e:
            failures.append((unit.recipe_id, f"{type(e).__name__}: {e}"))
        if i % 500 == 0 or i == total:
            _log(f"  progress: {i}/{total} recipes processed ({len(examples)} accepted, {len(failures)} rejected)")

    _log(f"Generation complete in {time.time() - t0:.1f}s: {len(examples)} accepted, "
         f"{len(failures)} rejected out of {total}.")
    if not examples:
        _log("BLOCKER: zero examples were successfully generated -- cannot proceed.")
        return 1

    _log("=== STEP 3: Assemble DatasetManifest ===")
    manifest, stamped_examples = assemble_manifest(tuple(examples), dataset_version=DATASET_VERSION)
    by_id = {e.metadata.example_id: e for e in stamped_examples}

    domain_counts = Counter(p["predicted_domain"] for p in profiles)
    reasoning_counts = Counter(e.inputs.reasoning_type.value for e in stamped_examples)
    category_counts = Counter(e.inputs.specification.category.value for e in stamped_examples)
    unique_specs = len({spec_group_key[id(e.inputs.specification)] for e in stamped_examples})
    answer_word_counts = [len(e.inputs.answer_text.split()) for e in stamped_examples]

    _log("--- Dataset statistics (validated at construction by DatasetManifest/TrainingExample's own frozen validators) ---")
    _log(f"  dataset_version: {manifest.dataset_version}")
    _log(f"  total examples: {len(manifest.example_ids)}")
    _log(f"  unique underlying specifications: {unique_specs} (vs. 40 in experiment 2, 8 in experiment 1)")
    _log(f"  candidate profiles: {len(profiles)} across {len(domain_counts)} domains (vs. 5 profiles / 1-5 domains before)")
    _log(f"  tier_distribution: {dict(manifest.tier_distribution)}")
    _log(f"  label_source_distribution: {dict(manifest.label_source_distribution)}")
    _log(f"  reasoning_type distribution: {dict(reasoning_counts)}")
    _log(f"  category distribution: {dict(category_counts)}")
    _log(f"  answer word count: min={min(answer_word_counts)}, max={max(answer_word_counts)}, "
         f"avg={sum(answer_word_counts) / len(answer_word_counts):.1f}")
    _log(f"  average repetition per specification: {len(stamped_examples) / unique_specs:.1f}x "
         f"(vs. ~6.25x in experiment 2 at 120 examples / 40 specs, and would have been ~62.5x "
         f"for this batch size against experiment 2's pool)")

    _log("=== STEP 4: Specification-level split (split_dataset_by_group, unmodified since session 8) ===")
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
        _log("BLOCKER: specification overlap detected -- split_dataset_by_group has a defect.")
        return 1
    if not split.train_ids or not split.val_ids or not split.test_ids:
        _log("BLOCKER: one of train/val/test is empty.")
        return 1

    _log("=== STEP 5: Persist to JSONL (experiment_dataset_io, new this milestone) ===")
    output_path = os.path.join(tempfile.gettempdir(), f"{DATASET_VERSION}.jsonl")
    t0 = time.time()
    save_examples_jsonl(stamped_examples, output_path)
    save_elapsed = time.time() - t0
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    _log(f"Saved {len(stamped_examples)} examples to {output_path!r} in {save_elapsed:.1f}s ({file_size_mb:.2f} MB).")

    from experiment_dataset_io import load_examples_jsonl
    t0 = time.time()
    reloaded = load_examples_jsonl(output_path)
    load_elapsed = time.time() - t0
    round_trip_ok = len(reloaded) == len(stamped_examples) and all(
        a.metadata.example_id == b.metadata.example_id for a, b in zip(stamped_examples, reloaded)
    )
    _log(f"Reloaded {len(reloaded)} examples in {load_elapsed:.1f}s. Round-trip fidelity: {round_trip_ok}.")
    if not round_trip_ok:
        _log("BLOCKER: persisted dataset did not round-trip correctly.")
        return 1

    _log("=== EXPERIMENT COMPLETE (no training/benchmark/promotion this milestone, per approved scope) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
