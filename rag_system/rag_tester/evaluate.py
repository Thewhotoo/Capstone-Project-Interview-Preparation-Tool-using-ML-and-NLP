"""
Counterfactual grading feedback.

Answers the question "what's the smallest change that would raise my score,
and by how much, exactly?" by treating compute_rubric_breakdown() as an
oracle: perturb the student's answer, re-run the REAL scoring function,
measure the REAL delta. Nothing here is LLM-guessed — every number reported
is the output of the same deterministic rubric used for the actual grade,
so a claim like "+6.2 points" is reproducible, not a plausible-sounding
LLM narrative.

Two things are deliberately NOT invented:
  1. The score delta — always measured by re-running compute_rubric_breakdown.
  2. The suggested wording — always a sentence taken verbatim from the
     reference_context that contains the missing concept, not a paraphrase.
     (If you want it paraphrased in the candidate's own voice, that's a
     separate, clearly-labeled generation step — see generate_minimal_edit_llm
     below, which is optional and never used for the score claim itself.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from evaluate import compute_rubric_breakdown, extract_weighted_concepts


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ConceptCounterfactual:
    concept: str
    weight: float
    current_hit: bool
    source_sentence: str | None      # the sentence in reference_context that contains it
    measured_delta: float            # actual overall_score delta if this concept is added
    new_overall: float               # overall_score after adding this concept alone

@dataclass
class CounterfactualReport:
    baseline_score: float
    counterfactuals: list[ConceptCounterfactual] = field(default_factory=list)
    minimal_edit_set: list[str] = field(default_factory=list)   # concepts, in order
    minimal_edit_sentences: list[str] = field(default_factory=list)
    minimal_edit_new_score: float = 0.0
    minimal_edit_delta: float = 0.0


# ---------------------------------------------------------------------------
# Locating the source sentence for a concept (grounds the suggestion in the
# actual reference text — never invented)
# ---------------------------------------------------------------------------

def find_source_sentence(concept: str, reference_context: str) -> str | None:
    """
    Return the shortest sentence in reference_context that mentions `concept`.
    Shortest, not first, so the suggested addition stays minimal.
    """
    sentences = re.split(r'(?<=[.!?])\s+', reference_context.strip())
    candidates = [s.strip() for s in sentences if concept.lower() in s.lower()]
    if not candidates:
        # fall back to partial word match for multi-word concepts
        words = concept.lower().split()
        candidates = [
            s.strip() for s in sentences
            if len(words) > 1 and all(w in s.lower() for w in words)
        ]
    if not candidates:
        return None
    return min(candidates, key=len)


# ---------------------------------------------------------------------------
# Perturbation + measurement
# ---------------------------------------------------------------------------

def perturb_with_sentence(student_answer: str, sentence: str) -> str:
    """
    Minimal perturbation: append the source sentence as a new clause.
    Appending (not rewriting) keeps the edit measurable and attributable
    to exactly one concept, which is what makes per-concept deltas valid —
    rewriting the whole answer would confound multiple effects at once.
    """
    student_answer = student_answer.strip()
    if not student_answer.endswith(('.', '!', '?')):
        student_answer += '.'
    return f"{student_answer} {sentence}"


def measure_single_concept_deltas(
    student_answer: str,
    reference_context: str,
    baseline_rubric: dict | None = None,
) -> list[ConceptCounterfactual]:
    """
    For every concept the student missed, measure the ACTUAL score delta
    from adding just that concept's source sentence, by re-running the
    real rubric function. This is O(num_missing_concepts) calls to
    compute_rubric_breakdown — fine for typical rubrics of <10 concepts,
    since each call is a couple of sentence-transformer encodes.
    """
    baseline_rubric = baseline_rubric or compute_rubric_breakdown(student_answer, reference_context)
    baseline_score = baseline_rubric["overall_score"]

    results = []
    for match in baseline_rubric["concept_matches"]:
        concept, weight, hit = match["concept"], match["weight"], match["hit"]
        source_sentence = find_source_sentence(concept, reference_context)

        if hit or source_sentence is None:
            # already covered, or we can't ground a suggestion in real text —
            # skip rather than inventing wording
            continue

        perturbed = perturb_with_sentence(student_answer, source_sentence)
        perturbed_rubric = compute_rubric_breakdown(perturbed, reference_context)
        delta = round(perturbed_rubric["overall_score"] - baseline_score, 2)

        results.append(ConceptCounterfactual(
            concept=concept,
            weight=weight,
            current_hit=hit,
            source_sentence=source_sentence,
            measured_delta=delta,
            new_overall=perturbed_rubric["overall_score"],
        ))

    # rank by measured impact, not just rubric weight — weight is a proxy,
    # the actual re-run is the ground truth
    results.sort(key=lambda c: -c.measured_delta)
    return results


# ---------------------------------------------------------------------------
# Minimal edit search: smallest set of concept-additions that closes the
# gap to a target score (or the next grade boundary)
# ---------------------------------------------------------------------------

GRADE_THRESHOLDS = [(80, 'A'), (70, 'B'), (60, 'C'), (50, 'D'), (0, 'F')]


def next_grade_threshold(current_score: float) -> float | None:
    """Smallest grade threshold strictly greater than current_score, or None if already at the top."""
    higher = [t for t, _ in GRADE_THRESHOLDS if t > current_score]
    return min(higher) if higher else None


def find_minimal_edit_set(
    student_answer: str,
    reference_context: str,
    target_score: float | None = None,
) -> CounterfactualReport:
    """
    Greedy minimal-edit search: repeatedly add the single highest-impact
    missing concept (measured, not estimated), re-measuring after each
    addition, until the target score is reached or no missing concepts
    remain. Greedy is not globally optimal but is the right tradeoff here:
    it keeps the number of compute_rubric_breakdown calls linear rather
    than combinatorial, and in practice concept contributions are close
    to additive since each edit only appends one sentence.
    """
    baseline_rubric = compute_rubric_breakdown(student_answer, reference_context)
    baseline_score = baseline_rubric["overall_score"]
    target = target_score if target_score is not None else next_grade_threshold(baseline_score)

    report = CounterfactualReport(baseline_score=baseline_score)
    report.counterfactuals = measure_single_concept_deltas(student_answer, reference_context, baseline_rubric)

    if target is None or not report.counterfactuals:
        report.minimal_edit_new_score = baseline_score
        return report

    current_answer = student_answer
    current_score = baseline_score
    remaining = list(report.counterfactuals)  # already sorted by measured delta desc

    while remaining and current_score < target:
        best = remaining.pop(0)
        current_answer = perturb_with_sentence(current_answer, best.source_sentence)
        current_rubric = compute_rubric_breakdown(current_answer, reference_context)
        new_score = current_rubric["overall_score"]

        report.minimal_edit_set.append(best.concept)
        report.minimal_edit_sentences.append(best.source_sentence)
        current_score = new_score

        # re-measure remaining concepts' deltas from the NEW baseline,
        # since adding one concept can shift semantic/clarity scores
        # enough to change which concept is now most valuable
        if remaining:
            remaining = measure_single_concept_deltas(current_answer, reference_context, current_rubric)

    report.minimal_edit_new_score = current_score
    report.minimal_edit_delta = round(current_score - baseline_score, 2)
    return report


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_counterfactual_markdown(report: CounterfactualReport) -> str:
    lines = [f"**Current score: {report.baseline_score:.1f}/100**", ""]

    if report.counterfactuals:
        lines.append("**If you had also mentioned:**")
        for c in report.counterfactuals[:5]:
            sign = "+" if c.measured_delta >= 0 else ""
            lines.append(
                f"- **{c.concept}** ({sign}{c.measured_delta:.1f} pts, "
                f"rubric weight {c.weight:.2f}) — reference says: "
                f"\"{c.source_sentence}\""
            )
        lines.append("")

    if report.minimal_edit_set:
        lines.append(
            f"**Minimal path to {report.minimal_edit_new_score:.1f}/100 "
            f"({'+' if report.minimal_edit_delta >= 0 else ''}{report.minimal_edit_delta:.1f} pts):**"
        )
        for concept, sentence in zip(report.minimal_edit_set, report.minimal_edit_sentences):
            lines.append(f"- Add a mention of **{concept}**: \"{sentence}\"")
    else:
        lines.append("_No further additions needed to reach the next grade boundary._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# OPTIONAL: paraphrase the minimal edit in the candidate's own voice.
# This is clearly separated from the score claim above — the LLM here only
# rewords, it never touches the number. If this call fails or is skipped,
# the report above is still fully valid on its own.
# ---------------------------------------------------------------------------

def generate_minimal_edit_llm(student_answer: str, report: CounterfactualReport) -> str | None:
    from generate import get_llm_response

    if not report.minimal_edit_sentences:
        return None

    facts = "\n".join(f"- {s}" for s in report.minimal_edit_sentences)
    prompt = f"""
The student wrote this answer:
{student_answer}

These facts are missing and must be added, taken verbatim from the reference:
{facts}

Rewrite the student's answer to include these facts in the student's own
phrasing where possible, but DO NOT remove or alter any factual content
from the facts list, and DO NOT add any information not present in the
facts list or the student's original answer. Return only the revised answer.
"""
    try:
        return get_llm_response(prompt)
    except Exception:
        return None