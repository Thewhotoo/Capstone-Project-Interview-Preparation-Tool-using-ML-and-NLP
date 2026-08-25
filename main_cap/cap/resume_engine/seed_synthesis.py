"""
Interview Seed Synthesis — Milestone 4. See
docs/architecture/Milestone4_Design.md (the approved design, Sections 1-8)
and docs/architecture/ResumeIntelligenceEngine.md Section 4.5 (Cross-
Reference Pass, Stage 5 -- this module is where that stage's
`interview_seeds` responsibility lives).

Reclassified (Milestone4_Design.md Section 1-2) from "requires an LLM" to
"deterministic extraction + heuristic composition + fixed templates":
every seed is built by interpolating already-extracted evidence
(technologies, concepts, metrics, explicit comparison language) into one
of five fixed template families, never by open-ended generation. Nothing
in this module calls an LLM.

Module-boundary decision (Design doc Section 3.1, approved): this module
never imports from `resume_engine.parsers.project_parser` and never reads
any ProjectParser-internal state. It operates only on the same public
`ProjectEntry`-shaped dict every other downstream consumer (topic_pool.py,
traceability.py) already reads -- `title`, `summary`, `technologies`,
`concepts`. Any signal ProjectParser computes internally but doesn't
expose (e.g. whether an explicit "Tech:" line was present) is recomputed
independently here, accepting a small amount of duplicated computation in
exchange for Milestones 0-3 staying genuinely untouched. See
`_has_labeled_tech_line` below for the one place this tradeoff is visible:
because ProjectParser's summary field already excludes the labeled-tech
line's raw text, this recomputation will rarely fire -- an honest,
documented consequence of the boundary decision, not a bug.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from typing import Literal

from resume_engine.confidence import Confidence
from resume_engine.technology_gazetteer import TECHNOLOGIES

# ── Tunable parameters (validation-derived starting values, Design doc
#    Section 8.4/8.5 -- confirmed or adjusted by the Milestone 4 fixture
#    pass, not treated as final on paper alone) ──────────────────────────

MAX_SEEDS_PER_PROJECT = 4
TECH_PROBE_CAP = 2
INTEGRATION_PROBE_CAP = 1
CONCEPT_PROBE_CAP = 1

# Family priority order (lower = higher priority), Design doc Section 3.3:
# metric > tradeoff > tech > integration > concept.
_FAMILY_PRIORITY = {
    "metric_probe": 0,
    "tradeoff_probe": 1,
    "tech_probe": 2,
    "integration_probe": 3,
    "concept_probe": 4,
}

_TRADEOFF_WINDOW_CHARS = 100

# ── Evidence-detection regexes (recomputed independently -- see module
#    docstring; not shared with project_parser.py or dates.py) ──────────

_TECH_LABEL_PATTERN = re.compile(r"\b(?:tech(?:nolog(?:y|ies))?|stack|built with)\s*:\s*", re.IGNORECASE)

_METRIC_PATTERN = re.compile(
    r"(?:(?:reduced|increased|improved|decreased|saved|cut|boosted|grew|scaled|"
    r"sped up|lowered|raised)\D{0,20}?\d+(?:\.\d+)?\s?%)"
    r"|\d+(?:\.\d+)?\s?%"
    r"|\d+(?:\.\d+)?x\b",
    re.IGNORECASE,
)

_COMPARISON_PATTERN = re.compile(
    r"\b(?:instead of|rather than|in favor of|"
    r"chose\s+\S+\s+over|picked\s+\S+\s+over|selected\s+\S+\s+over|"
    r"migrated from\s+\S+\s+to|switched from\s+\S+\s+to)\b",
    re.IGNORECASE,
)


# ── Evidence Accounting -- debug/validation-only data model (Design doc
#    Section 8.6). NEVER referenced by interfaces.py, NEVER attached to
#    CandidateProfile, NEVER constructed unless a caller explicitly asks
#    for accounting (want_accounting=True) -- the same zero-cost-when-
#    inactive discipline PipelineTrace itself follows. ────────────────────

EvidenceKind = Literal["technology", "concept", "metric", "comparison_phrase"]


@dataclass(frozen=True)
class EvidenceItem:
    kind: EvidenceKind
    value: str


@dataclass
class UnusedEvidenceItem:
    item: EvidenceItem
    reason: str  # closed vocabulary: "below_cap:<family>" | "duplicate_of:<value>" |
    # "precondition_not_met:<family>" | "lower_priority_unselected"


@dataclass
class EvidenceAccounting:
    project_title: str
    discovered: list[EvidenceItem] = field(default_factory=list)
    consumed: dict[str, list[EvidenceItem]] = field(default_factory=dict)  # seed_text -> evidence
    unused: list[UnusedEvidenceItem] = field(default_factory=list)


@dataclass
class SeedCandidate:
    family: str
    text: str
    evidence: list[EvidenceItem]
    confidence: Confidence


@dataclass
class SeedSynthesisResult:
    seeds: list[str] = field(default_factory=list)
    seed_confidences: list[Confidence] = field(default_factory=list)
    accounting: EvidenceAccounting | None = None


# ── Evidence discovery ───────────────────────────────────────────────────


def _project_text(project: dict) -> str:
    """The only text this module ever reads -- title + summary, both
    already-extracted public ProjectEntry fields. Never reads section
    spans, body_lines, or any other ProjectParser-internal structure."""
    return f"{project.get('title', '')} {project.get('summary', '')}".strip()


def _has_labeled_tech_line(text: str) -> bool:
    """Recomputed independently (module docstring) -- honestly a weak
    signal in practice, since ProjectParser's own `summary` field already
    strips the labeled line's raw text before this module ever sees it.
    Kept because it can still fire on incidental prose phrasing (e.g. "...
    built with Redis and Docker...") even though the strong signal (an
    explicit "Tech:" line) is gone by the time evidence reaches here."""
    return bool(_TECH_LABEL_PATTERN.search(text))


def _find_metrics(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _METRIC_PATTERN.finditer(text):
        value = match.group(0).strip()
        key = value.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(value)
    return ordered


def _find_comparisons(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _COMPARISON_PATTERN.finditer(text):
        value = match.group(0).strip()
        key = value.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(value)
    return ordered


def _technology_positions(text: str, technologies: list[str]) -> list[tuple[int, str]]:
    """Every (start_index, technology) occurrence of a project's own
    already-extracted technologies inside its own text -- used only to
    judge proximity to comparison language (tradeoff-probe precondition),
    never to discover new technologies beyond what's already extracted."""
    positions: list[tuple[int, str]] = []
    for tech in technologies:
        pattern = re.compile(r"\b" + re.escape(tech) + r"\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            positions.append((match.start(), tech))
    return positions


def _nearest_two_technologies(
    text: str, comparison: str, technologies: list[str]
) -> tuple[str, str] | None:
    """Strict tradeoff-probe precondition (Design doc Section 3.5,
    guarantee 2): only fires when two DISTINCT, already-extracted
    technologies both occur within `_TRADEOFF_WINDOW_CHARS` of the
    resume's own comparison language. Returns None (precondition fails)
    otherwise -- the tradeoff-probe family simply doesn't fire, it never
    falls back to guessing."""
    match = re.search(re.escape(comparison), text, re.IGNORECASE)
    if match is None:
        return None
    center = (match.start() + match.end()) / 2

    best_per_tech: dict[str, float] = {}
    for pos, tech in _technology_positions(text, technologies):
        distance = abs(pos - center)
        if distance > _TRADEOFF_WINDOW_CHARS:
            continue
        key = tech.lower()
        if key not in best_per_tech or distance < best_per_tech[key]:
            best_per_tech[key] = distance

    if len(best_per_tech) < 2:
        return None

    ranked = sorted(best_per_tech.items(), key=lambda kv: kv[1])
    # Recover original-cased technology strings, nearest first.
    lower_to_original = {t.lower(): t for t in technologies}
    tech_a = lower_to_original[ranked[0][0]]
    tech_b = lower_to_original[ranked[1][0]]
    return tech_a, tech_b


# ── Candidate generation (one function per template family, Design doc
#    Section 3.3) ────────────────────────────────────────────────────────


def _generate_candidates(
    project: dict,
) -> tuple[list[SeedCandidate], list[EvidenceItem], dict[tuple[str, str], str]]:
    text = _project_text(project)
    technologies = list(dict.fromkeys(project.get("technologies") or []))
    concepts = list(dict.fromkeys(project.get("concepts") or []))
    metrics = _find_metrics(text)
    comparisons = _find_comparisons(text)
    had_labeled_line = _has_labeled_tech_line(text)

    discovered: list[EvidenceItem] = (
        [EvidenceItem("technology", t) for t in technologies]
        + [EvidenceItem("concept", c) for c in concepts]
        + [EvidenceItem("metric", m) for m in metrics]
        + [EvidenceItem("comparison_phrase", c) for c in comparisons]
    )

    candidates: list[SeedCandidate] = []
    early_reasons: dict[tuple[str, str], str] = {}

    # Metric-probe -- every discovered metric always becomes a candidate;
    # no family cap, since these should reach 100% utilization (Design
    # doc Section 8.6, criterion 3).
    for metric in metrics:
        candidates.append(
            SeedCandidate(
                family="metric_probe",
                text=f'You mentioned "{metric}" — how was that measured or achieved?',
                evidence=[EvidenceItem("metric", metric)],
                confidence=Confidence(
                    score=0.85, reasons=[f"+metric_pattern_matched:{metric!r}"]
                ),
            )
        )

    # Tradeoff-probe -- strict precondition (Section 3.5 guarantee 2):
    # only fires when two of the project's own technologies are found
    # near the resume's own comparison language.
    for comparison in comparisons:
        pair = _nearest_two_technologies(text, comparison, technologies)
        if pair is None:
            early_reasons[("comparison_phrase", comparison)] = "precondition_not_met:tradeoff_probe"
            continue
        tech_a, tech_b = pair
        candidates.append(
            SeedCandidate(
                family="tradeoff_probe",
                text=f'Why {tech_a} over the alternative, given you mentioned "{comparison}"?',
                evidence=[
                    EvidenceItem("technology", tech_a),
                    EvidenceItem("technology", tech_b),
                    EvidenceItem("comparison_phrase", comparison),
                ],
                confidence=Confidence(
                    score=0.8,
                    reasons=[
                        f"+comparison_language_matched:{comparison!r}",
                        f"+technologies_near_comparison:{tech_a},{tech_b}",
                    ],
                ),
            )
        )

    # Tech-probe -- one candidate per extracted technology; capped at
    # selection time (TECH_PROBE_CAP), not here, so caps and duplicates
    # are distinguishable in the accounting (Section 8.6).
    for tech in technologies:
        base = 0.75 if had_labeled_line else 0.6
        reasons = [f"+technology_extracted:{tech}"]
        reasons.append("+tech_label_line_detected" if had_labeled_line else "-tech_label_line_not_found")
        candidates.append(
            SeedCandidate(
                family="tech_probe",
                text=f"Why did you use {tech} in this project?",
                evidence=[EvidenceItem("technology", tech)],
                confidence=Confidence(score=base, reasons=reasons),
            )
        )

    # Integration-probe -- every unordered pair of extracted technologies;
    # capped at selection time.
    for tech_a, tech_b in itertools.combinations(technologies, 2):
        candidates.append(
            SeedCandidate(
                family="integration_probe",
                text=f"How did {tech_a} and {tech_b} work together in this project?",
                evidence=[EvidenceItem("technology", tech_a), EvidenceItem("technology", tech_b)],
                confidence=Confidence(
                    score=0.55, reasons=[f"+co_occurring_technologies:{tech_a},{tech_b}"]
                ),
            )
        )

    # Concept-probe -- one candidate per extracted concept; capped at
    # selection time.
    for concept in concepts:
        candidates.append(
            SeedCandidate(
                family="concept_probe",
                text=f"How did you approach {concept.lower()} in this project?",
                evidence=[EvidenceItem("concept", concept)],
                confidence=Confidence(score=0.5, reasons=[f"+concept_extracted:{concept}"]),
            )
        )

    return candidates, discovered, early_reasons


# ── Ranking, deduplication, capping, final selection (Design doc Section
#    3.3 / 8.5) ───────────────────────────────────────────────────────────


def _select(
    candidates: list[SeedCandidate],
) -> tuple[list[SeedCandidate], dict[tuple[str, str], str]]:
    """Ranks by family priority (ties broken by confidence, then original
    generation order -- Python's sort is stable), then greedily selects
    while enforcing: no evidence item reused across selected seeds (exact
    evidence-set dedup, Section 8.5 layer 1), per-family caps, and the
    overall MAX_SEEDS_PER_PROJECT cap. Returns the selected candidates and
    a reason map for every REJECTED candidate's evidence (used to build
    Evidence Accounting's `unused` list, never returned to callers who
    don't ask for accounting)."""
    ranked = sorted(candidates, key=lambda c: (_FAMILY_PRIORITY[c.family], -c.confidence.score))

    family_caps = {
        "tech_probe": TECH_PROBE_CAP,
        "integration_probe": INTEGRATION_PROBE_CAP,
        "concept_probe": CONCEPT_PROBE_CAP,
    }
    family_counts: dict[str, int] = {}
    used_evidence: set[tuple[str, str]] = set()
    selected: list[SeedCandidate] = []
    rejection_reasons: dict[tuple[str, str], str] = {}

    for candidate in ranked:
        evidence_keys = [(item.kind, item.value) for item in candidate.evidence]

        if len(selected) >= MAX_SEEDS_PER_PROJECT:
            reason = "below_cap:overall"
            for key in evidence_keys:
                rejection_reasons.setdefault(key, reason)
            continue

        overlap = [key for key in evidence_keys if key in used_evidence]
        if overlap:
            reason = f"duplicate_of:{overlap[0][1]}"
            for key in evidence_keys:
                rejection_reasons.setdefault(key, reason)
            continue

        cap = family_caps.get(candidate.family)
        if cap is not None and family_counts.get(candidate.family, 0) >= cap:
            reason = f"below_cap:{candidate.family}"
            for key in evidence_keys:
                rejection_reasons.setdefault(key, reason)
            continue

        selected.append(candidate)
        family_counts[candidate.family] = family_counts.get(candidate.family, 0) + 1
        used_evidence.update(evidence_keys)

    return selected, rejection_reasons


def _build_accounting(
    project_title: str,
    discovered: list[EvidenceItem],
    selected: list[SeedCandidate],
    early_reasons: dict[tuple[str, str], str],
    rejection_reasons: dict[tuple[str, str], str],
) -> EvidenceAccounting:
    used_keys = {(item.kind, item.value) for candidate in selected for item in candidate.evidence}
    consumed = {candidate.text: candidate.evidence for candidate in selected}

    unused: list[UnusedEvidenceItem] = []
    for item in discovered:
        key = (item.kind, item.value)
        if key in used_keys:
            continue
        reason = early_reasons.get(key) or rejection_reasons.get(key) or "lower_priority_unselected"
        unused.append(UnusedEvidenceItem(item=item, reason=reason))

    return EvidenceAccounting(
        project_title=project_title, discovered=discovered, consumed=consumed, unused=unused
    )


def synthesize_seeds(project: dict, *, want_accounting: bool = False) -> SeedSynthesisResult:
    """Public entry point: generates `interview_seeds` for one already-
    parsed `ProjectEntry`-shaped dict. Deterministic -- identical input
    always produces identical output. Never raises; a project with no
    usable evidence produces `seeds == []` (the permanent graceful-
    degradation rule, Design doc Section 3.5 guarantee 3), never a
    generic fallback seed.

    `want_accounting` gates construction of the debug-only
    EvidenceAccounting record -- False (the default) means zero extra
    work beyond generating the seeds themselves, matching the
    zero-cost-when-tracing-is-disabled philosophy used throughout this
    engine (PipelineTrace, Confidence, Observation)."""
    candidates, discovered, early_reasons = _generate_candidates(project)
    selected, rejection_reasons = _select(candidates)

    accounting = None
    if want_accounting:
        accounting = _build_accounting(
            project_title=project.get("title", ""),
            discovered=discovered,
            selected=selected,
            early_reasons=early_reasons,
            rejection_reasons=rejection_reasons,
        )

    return SeedSynthesisResult(
        seeds=[c.text for c in selected],
        seed_confidences=[c.confidence for c in selected],
        accounting=accounting,
    )
