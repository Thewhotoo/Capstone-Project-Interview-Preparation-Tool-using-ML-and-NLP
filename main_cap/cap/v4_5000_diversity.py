"""
V4 5000-Example Dataset -- Diversity Monitor (local, NO LLM).

Reads the RAW Claude-authored batch records (not the converted
TrainingExamples) and reports frequency distributions plus SOFT steering
WARNINGS when any facet becomes disproportionately dominant. These are
steering signals for FUTURE batches -- never rejection rules, and this module
NEVER modifies or discards any accepted example (per the dataset's rules; the
early drift audit is exactly what this operationalizes).

Facets tracked: question opening patterns, declared question_form, intent,
reasoning_type, QuestionCategory, technology frequency, project_family,
humanization style, humanized share, overall tier distribution, per-dimension
tier distribution, examples-per-group.

Thresholds are soft, documented constants. A warning means "steer future
batches away from this," not "this example is invalid."
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

_CANONICAL_KEYS = ("technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership")


@dataclass(frozen=True)
class DiversityThresholds:
    max_single_technology_share: float = 0.22      # any one tech > 22% of tech mentions
    max_question_opening_share: float = 0.15       # any one 3-word opener > 15% of questions
    max_reasoning_type_share: float = 0.40         # any one reasoning_type > 40%
    max_category_share: float = 0.75               # any one QuestionCategory > 75%
    max_project_family_share: float = 0.30         # any one project family > 30%
    max_question_form_share: float = 0.20          # any one question_form > 20%
    max_humanization_style_share: float = 0.45     # any one humanized style > 45% of humanized
    humanized_share_low: float = 0.15              # humanized share of authored below this
    humanized_share_high: float = 0.35             # ... or above this
    tier_share_low: float = 0.05                   # any overall tier below this
    tier_share_high: float = 0.45                  # ... or above this


def _overall_tier_from_dims(dims: dict[str, int]) -> int:
    score = sum(dims[k] / 4.0 for k in _CANONICAL_KEYS) / len(_CANONICAL_KEYS)
    if score >= 0.80:
        return 4
    if score >= 0.60:
        return 3
    if score >= 0.40:
        return 2
    if score >= 0.25:
        return 1
    return 0


def _opening(question: str, n: int = 3) -> str:
    words = re.findall(r"[a-zA-Z']+", (question or "").lower())
    return " ".join(words[:n])


@dataclass
class DiversityReport:
    authored_count: int = 0
    frequencies: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def analyze(records: list[dict], thresholds: DiversityThresholds = DiversityThresholds()) -> DiversityReport:
    """`records` = raw authored batch dicts (as read from batch_*.jsonl)."""
    n = len(records)
    rep = DiversityReport(authored_count=n)
    if n == 0:
        return rep

    tech = Counter(t for r in records for t in r.get("grounding", {}).get("technologies", []))
    openings = Counter(_opening(r.get("question", "")) for r in records)
    qforms = Counter(r.get("question_form", "") for r in records if r.get("question_form"))
    intents = Counter(r.get("intent", "") for r in records if r.get("intent"))
    reasoning = Counter(r.get("reasoning_type", "") for r in records)
    categories = Counter(r.get("category", "") for r in records)
    families = Counter(r.get("project_family", "") for r in records if r.get("project_family"))
    humanized = [r for r in records if r.get("humanized")]
    hum_styles = Counter(r.get("humanization_style", "") for r in humanized if r.get("humanization_style"))
    tier_counts = Counter(_overall_tier_from_dims(r["dimensions"]) for r in records)
    perdim = {k: Counter() for k in _CANONICAL_KEYS}
    for r in records:
        for k in _CANONICAL_KEYS:
            perdim[k][r["dimensions"][k]] += 1
    groups = Counter(r.get("group_id", "") for r in records)
    per_group = list(groups.values())

    rep.frequencies = {
        "technology": dict(tech.most_common()),
        "question_opening_trigram": dict(openings.most_common(15)),
        "question_form": dict(qforms.most_common()),
        "intent": dict(intents.most_common()),
        "reasoning_type": dict(reasoning.most_common()),
        "category": dict(categories.most_common()),
        "project_family": dict(families.most_common()),
        "humanization_style": dict(hum_styles.most_common()),
        "overall_tier": {t: tier_counts.get(t, 0) for t in range(5)},
        "per_dimension_tier": {k: {t: perdim[k].get(t, 0) for t in range(5)} for k in _CANONICAL_KEYS},
        "unique_groups": len(groups),
        "unique_questions": len({(r.get("question") or "").strip().casefold() for r in records}),
        "examples_per_group_max": max(per_group) if per_group else 0,
        "examples_per_group_mean": round(sum(per_group) / len(per_group), 2) if per_group else 0,
        "humanized_count": len(humanized),
        "humanized_share_of_authored": round(len(humanized) / n, 3),
    }

    w = rep.warnings
    tech_total = sum(tech.values()) or 1
    for name, c in tech.most_common(1):
        if c / tech_total > thresholds.max_single_technology_share:
            w.append(f"technology '{name}' is {c/tech_total:.0%} of tech mentions (> {thresholds.max_single_technology_share:.0%}) -- steer future batches to other tech families")
    for op, c in openings.most_common(1):
        if c / n > thresholds.max_question_opening_share:
            w.append(f"question opening '{op}...' is {c/n:.0%} of questions (> {thresholds.max_question_opening_share:.0%}) -- vary question forms")
    for rt, c in reasoning.most_common(1):
        if c / n > thresholds.max_reasoning_type_share:
            w.append(f"reasoning_type '{rt}' is {c/n:.0%} (> {thresholds.max_reasoning_type_share:.0%}) -- diversify reasoning types")
    for cat, c in categories.most_common(1):
        if c / n > thresholds.max_category_share:
            w.append(f"category '{cat}' is {c/n:.0%} (> {thresholds.max_category_share:.0%}) -- add other categories")
    if families:
        for fam, c in families.most_common(1):
            if c / n > thresholds.max_project_family_share:
                w.append(f"project_family '{fam}' is {c/n:.0%} (> {thresholds.max_project_family_share:.0%}) -- diversify project families")
    if qforms:
        for qf, c in qforms.most_common(1):
            if c / n > thresholds.max_question_form_share:
                w.append(f"question_form '{qf}' is {c/n:.0%} (> {thresholds.max_question_form_share:.0%}) -- spread across more forms")
    if hum_styles:
        hs_total = sum(hum_styles.values()) or 1
        for hs, c in hum_styles.most_common(1):
            if c / hs_total > thresholds.max_humanization_style_share:
                w.append(f"humanization_style '{hs}' is {c/hs_total:.0%} of humanized (> {thresholds.max_humanization_style_share:.0%}) -- vary humanized styles")
    hum_share = len(humanized) / n
    if hum_share < thresholds.humanized_share_low:
        w.append(f"humanized share {hum_share:.0%} below target band (~15-30%) -- add humanized examples")
    elif hum_share > thresholds.humanized_share_high:
        w.append(f"humanized share {hum_share:.0%} above target band (~15-30%) -- ease off humanized examples")
    for t in range(5):
        share = tier_counts.get(t, 0) / n
        if share < thresholds.tier_share_low:
            w.append(f"overall tier {t} is only {share:.0%} of authored (< {thresholds.tier_share_low:.0%}) -- author more tier-{t} examples")
        elif share > thresholds.tier_share_high:
            w.append(f"overall tier {t} is {share:.0%} of authored (> {thresholds.tier_share_high:.0%}) -- ease off tier-{t}")

    return rep
