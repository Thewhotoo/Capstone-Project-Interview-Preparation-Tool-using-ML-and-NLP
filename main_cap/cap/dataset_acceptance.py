"""
Dataset Acceptance Gate — Step 3 infra (reusable quality report).

Runs the Step-3 acceptance checks over a set of accepted `LabeledExample`s and
their group-aware `DatasetSplit`, producing a structured report. Intended to
be run BEFORE any training. It computes 12 checks; hard checks contribute to
an overall pass/fail, while the four-dimension correlation is reported as a
DIAGNOSTIC only (never a hard failure) — hard-case coverage and the actual
tier distributions are the stronger independence evidence.

Operates on already-generated examples; it neither generates nor trains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from dataset_filters import (
    duplicate_answer_counts,
    find_banned_phrases,
    hallucinated_technologies,
    questions_over_cap,
)
from dimension_profiles import HARD_CASES
from evaluation_dimensions import CANONICAL_DIMENSIONS, NUM_TIERS

_MAX_TIER = NUM_TIERS - 1


@dataclass(frozen=True)
class AcceptanceConfig:
    answer_per_question_cap: int = 8
    min_distinct_sources: int = 20
    min_hard_case_coverage: int = 1     # min examples per hard case to "cover" it
    max_duplicate_answer_rate: float = 0.02
    max_exact_answer_dup_rate: float = 0.02


# PILOT CONFIG (seed_v1 forensic analysis): the default `min_distinct_sources`
# above (20) is calibrated for the eventual 1,500-2,500-example dataset, not
# the 100-example hand-authored seed pilot, which was deliberately built on
# 12 projects (7-9 examples each). Running the default config against the
# 100-example seed produced a `grounding_source_diversity` failure that
# reflected this size mismatch, not a seed-quality problem (confirmed: the
# pipeline's own tests already override `min_distinct_sources` for small
# batches rather than rely on the production default). This named constant
# makes that distinction explicit in the acceptance/reporting path instead of
# silently overriding the default inline — the PRODUCTION default above is
# untouched and stays the threshold for the eventual full-scale dataset.
PILOT_SEED_V1_ACCEPTANCE_CONFIG = AcceptanceConfig(min_distinct_sources=12)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: Optional[bool]   # True/False for hard checks; None for diagnostics
    value: object = None
    detail: str = ""


@dataclass(frozen=True)
class AcceptanceReport:
    results: tuple[CheckResult, ...] = field(default_factory=tuple)

    @property
    def hard_checks(self) -> tuple[CheckResult, ...]:
        return tuple(r for r in self.results if r.passed is not None)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.hard_checks)

    def get(self, name: str) -> Optional[CheckResult]:
        return next((r for r in self.results if r.name == name), None)


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


def evaluate_dataset(labeled, split, config: AcceptanceConfig = AcceptanceConfig()) -> AcceptanceReport:
    """`labeled`: an iterable of LabeledExample (only accepted ones are used).
    `split`: the DatasetSplit produced by `split_labeled`. Returns an
    AcceptanceReport; inspect `.passed` for the hard-check verdict and the
    individual `CheckResult`s (including the correlation diagnostic)."""
    accepted = [le for le in labeled if le.accepted and le.example is not None]
    examples = [le.example for le in accepted]
    results: list[CheckResult] = []

    id_to_split = {}
    for sid in split.train_ids:
        id_to_split[sid] = "train"
    for sid in split.val_ids:
        id_to_split[sid] = "val"
    for sid in split.test_ids:
        id_to_split[sid] = "test"

    def _norm(s: str) -> str:
        return " ".join((s or "").split()).casefold()

    # 1. no cross-split leakage (answers / questions / source_id)
    def _leak(key_fn, label) -> CheckResult:
        by_key_splits: dict[str, set] = {}
        for ex in examples:
            sid = ex.metadata.example_id
            spl = id_to_split.get(sid)
            if spl is None:
                continue
            k = key_fn(ex)
            by_key_splits.setdefault(k, set()).add(spl)
        leaked = [k for k, spls in by_key_splits.items() if len(spls) > 1]
        return CheckResult(
            name=f"no_cross_split_leakage_{label}", passed=(len(leaked) == 0),
            value=len(leaked), detail=(f"{len(leaked)} {label}(s) span >1 split" if leaked else "clean"),
        )

    results.append(_leak(lambda e: _norm(e.inputs.answer_text), "answers"))
    results.append(_leak(lambda e: _norm(e.inputs.question_text), "questions"))
    results.append(_leak(lambda e: e.inputs.specification.source_id, "source_ids"))

    # 2. no banned quality phrases in any answer
    banned_hits = sum(1 for ex in examples if find_banned_phrases(ex.inputs.answer_text))
    results.append(CheckResult(
        name="no_banned_quality_phrases", passed=(banned_hits == 0),
        value=banned_hits, detail=f"{banned_hits} answers contain a banned self-describing phrase",
    ))

    # 3. every example has all four canonical dimension labels
    required = {d.value for d in CANONICAL_DIMENSIONS}
    missing_four = sum(
        1 for ex in examples if {d.name for d in ex.labels.dimension_labels} != required
    )
    results.append(CheckResult(
        name="all_four_dimensions_present", passed=(missing_four == 0),
        value=missing_four, detail=f"{missing_four} examples missing one of the four canonical labels",
    ))

    # 4. tier distribution per dimension (diagnostic)
    tier_dist: dict[str, dict[int, int]] = {d.value: {t: 0 for t in range(NUM_TIERS)} for d in CANONICAL_DIMENSIONS}
    for ex in examples:
        for dl in ex.labels.dimension_labels:
            if dl.name in tier_dist:
                tier_dist[dl.name][round(dl.score * _MAX_TIER)] += 1
    results.append(CheckResult(name="tier_distribution_per_dimension", passed=None, value=tier_dist))

    # 5. hard-case coverage
    profile_counts: dict[str, int] = {}
    for le in accepted:
        profile_counts[le.profile_id] = profile_counts.get(le.profile_id, 0) + 1
    covered = [k for k in HARD_CASES if profile_counts.get(k, 0) >= config.min_hard_case_coverage]
    results.append(CheckResult(
        name="hard_case_coverage", passed=(len(covered) == len(HARD_CASES)),
        value={"covered": sorted(covered), "counts": profile_counts},
        detail=f"{len(covered)}/{len(HARD_CASES)} hard cases covered",
    ))

    # 6. category coverage (diagnostic)
    categories = {}
    for ex in examples:
        c = ex.inputs.specification.category.value
        categories[c] = categories.get(c, 0) + 1
    results.append(CheckResult(name="category_coverage", passed=None, value=categories))

    # 7. reasoning-type coverage (diagnostic)
    reasoning = {}
    for ex in examples:
        r = ex.inputs.reasoning_type.value
        reasoning[r] = reasoning.get(r, 0) + 1
    results.append(CheckResult(name="reasoning_type_coverage", passed=None, value=reasoning))

    # 8. grounding/source diversity
    sources = {ex.inputs.specification.source_id for ex in examples}
    results.append(CheckResult(
        name="grounding_source_diversity", passed=(len(sources) >= config.min_distinct_sources),
        value=len(sources), detail=f"{len(sources)} distinct sources (min {config.min_distinct_sources})",
    ))

    # 9. answer-per-question limits
    pairs = [(ex.inputs.question_text, ex.inputs.answer_text) for ex in examples]
    over = questions_over_cap(pairs, config.answer_per_question_cap)
    results.append(CheckResult(
        name="answer_per_question_cap", passed=(len(over) == 0),
        value=len(over), detail=f"{len(over)} questions exceed cap {config.answer_per_question_cap}",
    ))

    # 10. duplicate rates (exact duplicate answers)
    answers = [ex.inputs.answer_text for ex in examples]
    dup_counts = duplicate_answer_counts(answers)
    dup_extra = sum(c - 1 for c in dup_counts.values())
    dup_rate = (dup_extra / len(answers)) if answers else 0.0
    results.append(CheckResult(
        name="duplicate_answer_rate", passed=(dup_rate <= config.max_exact_answer_dup_rate),
        value=round(dup_rate, 4), detail=f"{dup_extra} duplicate answers ({dup_rate:.1%})",
    ))

    # 11. generation-target vs judge agreement (diagnostic + hard on availability)
    agreements = [le.agreement for le in accepted if le.agreement is not None]
    if agreements:
        mean_max_delta = sum(a.max_delta for a in agreements) / len(agreements)
        all_ok = all(a.all_acceptable for a in agreements)
        results.append(CheckResult(
            name="target_vs_judge_agreement", passed=all_ok,
            value=round(mean_max_delta, 3),
            detail=("all accepted examples within tolerance" if all_ok else "some accepted examples exceed tolerance"),
        ))
    else:
        results.append(CheckResult(name="target_vs_judge_agreement", passed=None, value=None,
                                   detail="no agreement records available"))

    # 12. grounding fidelity (hallucinated technologies)
    halluc = 0
    for ex in examples:
        project = ex.inputs.specification.grounding.project
        allowed = project.technologies if project is not None else ()
        if hallucinated_technologies(ex.inputs.answer_text, allowed):
            halluc += 1
    results.append(CheckResult(
        name="grounding_fidelity", passed=(halluc == 0),
        value=halluc, detail=f"{halluc} answers mention out-of-grounding technologies",
    ))

    # DIAGNOSTIC: four-dimension correlation (NEVER a hard failure)
    scores_by_dim: dict[str, list[float]] = {d.value: [] for d in CANONICAL_DIMENSIONS}
    for ex in examples:
        by_name = {dl.name: dl.score for dl in ex.labels.dimension_labels}
        if all(d.value in by_name for d in CANONICAL_DIMENSIONS):
            for d in CANONICAL_DIMENSIONS:
                scores_by_dim[d.value].append(by_name[d.value])
    correlations: dict[str, Optional[float]] = {}
    dims = [d.value for d in CANONICAL_DIMENSIONS]
    abs_vals = []
    for i in range(len(dims)):
        for j in range(i + 1, len(dims)):
            r = _pearson(scores_by_dim[dims[i]], scores_by_dim[dims[j]])
            correlations[f"{dims[i]}|{dims[j]}"] = None if r is None else round(r, 3)
            if r is not None:
                abs_vals.append(abs(r))
    mean_abs = round(sum(abs_vals) / len(abs_vals), 3) if abs_vals else None
    results.append(CheckResult(
        name="four_dimension_correlation_DIAGNOSTIC", passed=None,
        value={"mean_abs_pairwise": mean_abs, "pairwise": correlations},
        detail="diagnostic only — not a hard acceptance criterion",
    ))

    return AcceptanceReport(results=tuple(results))
