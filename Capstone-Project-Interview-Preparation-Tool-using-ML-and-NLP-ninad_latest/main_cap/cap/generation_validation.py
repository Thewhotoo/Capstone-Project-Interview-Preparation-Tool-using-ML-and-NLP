"""
Generation Validation — Stage A Synthetic Dataset Generation Pipeline
(Synthetic Dataset Generation Promptbook RFC, Section 9 — APPROVED AND
FROZEN).

Automatic quality-assurance gate a raw `GenerationOutput` must pass before
it is eligible to become a `TrainingExample`. Every rejection condition
named in Promptbook Section 9 is implemented here as its own check;
`validate_generation` combines them into one verdict. This module never
repairs an output — see Implementation requirement 10 ("failed generations
should be rejected and regenerated rather than partially repaired"); a
failing check always means the whole attempt is discarded, never patched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from evaluation_result import ConceptObservationStatus, MissingReasoningCategory
from generation_client import GenerationOutput
from generation_recipe import GenerationRecipe

_MIN_ANSWER_WORDS = 3

# A small, open, growable vocabulary of well-known technology names this
# check watches for — same registry-style extensibility already used by
# expected_concepts_registry.py. Deliberately NOT exhaustive: this is a
# heuristic proxy for the "hallucinated technology" failure mode (Promptbook
# Section 9), not a claim of complete coverage. New names are added here as
# new string entries, never as a schema change.
_KNOWN_TECHNOLOGY_VOCABULARY: tuple[str, ...] = (
    "django", "flask", "fastapi", "express", "node.js", "nodejs", "spring",
    "mongodb", "postgresql", "postgres", "mysql", "sqlite", "redis", "kafka",
    "rabbitmq", "react", "angular", "vue", "docker", "kubernetes", "aws",
    "azure", "gcp", "tensorflow", "pytorch", "graphql", "grpc", "langchain",
    "langgraph", "elasticsearch", "nginx", "terraform", "jenkins",
    # Additive expansion (research-scaling milestone) for the domains added
    # to the experiment profile library — mobile, cybersecurity, DevOps/SRE,
    # data engineering, AI/ML, embedded/IoT, blockchain, QA. Still not
    # exhaustive, same heuristic-proxy discipline as above.
    "swift", "swiftui", "kotlin", "jetpack compose", "combine",
    "ansible", "prometheus", "grafana", "github actions",
    "spark", "airflow", "databricks", "snowflake", "dbt",
    "scikit-learn", "hugging face", "spacy", "mlflow", "faiss",
    "solidity", "hardhat", "truffle", "web3.js", "ethereum", "slither",
    "mqtt", "freertos", "zephyr rtos",
    "selenium", "cypress", "playwright", "jmeter", "gatling",
    "burp suite", "metasploit", "splunk", "wireshark", "nmap",
)

# Small, local marker sets for the reasoning-mismatch check (Promptbook
# Section 9). Deliberately duplicated rather than imported from
# heuristic_evaluator.py — that module is Evaluation Engine internals this
# pipeline must stay independent from (same "deliberate independence"
# rationale heuristic_evaluator.py itself documents relative to
# discussion_engine.py).
_CATEGORY_MARKERS: dict[str, tuple[str, ...]] = {
    MissingReasoningCategory.TRADEOFF: ("versus", "vs.", "instead of", "alternative", "trade-off", "tradeoff", "compared to"),
    MissingReasoningCategory.ARCHITECTURE: ("architecture", "component", "layer", "service", "module", "structure"),
    MissingReasoningCategory.DEBUGGING: ("bug", "issue", "broke", "fixed", "resolved", "debug", "root cause"),
    MissingReasoningCategory.TESTING: ("test", "tested", "testing", "verified", "unit test", "integration test"),
    MissingReasoningCategory.SCALABILITY: ("scale", "scaling", "load", "throughput", "concurrent"),
    MissingReasoningCategory.OWNERSHIP: ("i designed", "i built", "i implemented", "i led", "i was responsible"),
}

_MAJOR_SEVERITY_THRESHOLD = 0.67


@dataclass(frozen=True)
class ValidationVerdict:
    """Whether a `GenerationOutput` may proceed to
    `training_example_assembler.py`, and why not if it may not. Routing
    (reject vs. regenerate) is the pipeline's job, not this module's — this
    module only detects, never retries."""

    accepted: bool
    rejection_reasons: tuple[str, ...] = ()


def _grounding_technologies(recipe: GenerationRecipe) -> frozenset[str]:
    project = recipe.specification.grounding.project
    if project is None:
        return frozenset()
    return frozenset(t.lower() for t in project.technologies)


def _contains_term(text_lower: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text_lower) is not None


def check_malformed_output(output: GenerationOutput) -> tuple[str, ...]:
    """Non-parseable/empty output (Promptbook Section 9)."""
    reasons = []
    if not output.answer_text.strip():
        reasons.append("malformed_output: answer_text is empty")
    elif len(output.answer_text.split()) < _MIN_ANSWER_WORDS:
        reasons.append("malformed_output: answer_text is implausibly short")
    return tuple(reasons)


def check_hallucinated_technology(output: GenerationOutput, recipe: GenerationRecipe) -> tuple[str, ...]:
    """Hallucinated technologies / invented grounding (Promptbook Section
    7/9) — any known-vocabulary technology name in the answer that is not
    present in the grounding's own technology list."""
    grounded = _grounding_technologies(recipe)
    answer_lower = output.answer_text.lower()
    hallucinated = [
        name for name in _KNOWN_TECHNOLOGY_VOCABULARY
        if name not in grounded and _contains_term(answer_lower, name)
    ]
    if hallucinated:
        return (f"hallucinated_technology: mentions {', '.join(hallucinated)} not present in grounding",)
    return ()


def check_concept_count(output: GenerationOutput, recipe: GenerationRecipe) -> tuple[str, ...]:
    """Incorrect concept count (Promptbook Section 9): every
    demonstrated/superficial target must have exactly one evidence entry;
    every omitted target must have none, and must not appear in the answer."""
    reasons = []
    evidence_by_concept = {e.concept.strip().lower(): e for e in output.concept_evidence}
    answer_lower = output.answer_text.lower()

    for target in recipe.concept_targets:
        key = target.concept.strip().lower()
        entry = evidence_by_concept.get(key)
        if target.status in (ConceptObservationStatus.DEMONSTRATED, ConceptObservationStatus.SUPERFICIAL):
            if entry is None or not entry.evidence.strip():
                reasons.append(f"concept_count_mismatch: no evidence supplied for {target.concept!r} (target={target.status.value})")
        else:  # OMITTED
            if entry is not None:
                reasons.append(f"concept_count_mismatch: evidence supplied for {target.concept!r}, which was targeted OMITTED")
            elif _contains_term(answer_lower, key):
                reasons.append(f"concept_count_mismatch: {target.concept!r} appears in the answer despite being targeted OMITTED")
    return tuple(reasons)


def check_reasoning_mismatch(output: GenerationOutput, recipe: GenerationRecipe) -> tuple[str, ...]:
    """Reasoning mismatch (Promptbook Section 9) — a MAJOR-severity,
    present=True target whose category markers are nonetheless strongly
    present in the answer suggests the recipe wasn't actually followed."""
    reasons = []
    answer_lower = output.answer_text.lower()
    for target in recipe.reasoning_targets:
        if not target.present or target.severity < _MAJOR_SEVERITY_THRESHOLD:
            continue
        markers = _CATEGORY_MARKERS.get(target.category)
        if not markers:
            continue
        hits = sum(1 for m in markers if m in answer_lower)
        if hits >= 2:
            reasons.append(
                f"reasoning_mismatch: category {target.category!r} was targeted major-severity-missing, "
                f"but the answer strongly addresses it ({hits} markers found)"
            )
    return tuple(reasons)


def check_contradiction_consistency(output: GenerationOutput, recipe: GenerationRecipe) -> tuple[str, ...]:
    """The contradiction note must be present iff the recipe intended a
    contradiction (Promptbook Section 8's one-contradiction discipline)."""
    has_note = bool(output.contradiction_note.strip())
    if recipe.is_contradictory and not has_note:
        return ("reasoning_mismatch: recipe targeted a contradiction but no contradiction_note was supplied",)
    if not recipe.is_contradictory and has_note:
        return ("reasoning_mismatch: a contradiction_note was supplied but the recipe did not target one",)
    return ()


def validate_generation(output: GenerationOutput, recipe: GenerationRecipe) -> ValidationVerdict:
    """Run every automatic QA check and combine into one verdict. Off-topic
    recipes skip the concept/reasoning-mismatch checks entirely — those
    targets don't exist for an off-topic recipe (Promptbook Section 2's
    override), so there is nothing to conform to."""
    reasons: list[str] = []
    reasons.extend(check_malformed_output(output))
    reasons.extend(check_hallucinated_technology(output, recipe))
    if not recipe.is_off_topic:
        reasons.extend(check_concept_count(output, recipe))
        reasons.extend(check_reasoning_mismatch(output, recipe))
    reasons.extend(check_contradiction_consistency(output, recipe))
    return ValidationVerdict(accepted=not reasons, rejection_reasons=tuple(reasons))
