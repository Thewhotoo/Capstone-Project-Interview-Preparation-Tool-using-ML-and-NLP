"""
Interview Feedback — data-driven end-of-session feedback for the Resume Discussion.

Replaces the frontend's fixed per-grade narrative ("This was a steady
discussion...") with text derived from the actual per-turn results: how many
questions were substantively answered, which evidence dimensions were weak or
strong, and what to do about it. Deterministic, no model. It only speaks to what
the evaluator measures (relevance/completeness, depth/specificity, grounding/
ownership) and says plainly that it does not verify factual correctness.

Adapted from a teammate's `interview_feedback.py` (resumeParser_integration.md
step 6). His version read his evaluator's four canonical dimensions; ours reads
the heuristic evaluator's dimensions (which the averaged evaluator keeps), mapped:

    depth / specificity        <- technical_depth
    relevance / completeness   <- completeness
    grounding / ownership      <- ownership, resume_grounding
Each is averaged only over the answers where the evaluator reported it (it
reports only the dimensions relevant to each question type), never zero-filled.

`conversation_engine.end_conversation` adds the result as `summary["feedback"]`;
it is saved with the session and rendered by the Round 1 report.
"""

from __future__ import annotations

import math

DEPTH = "depth_specificity"
RELEVANCE = "relevance_completeness"
GROUNDING = "grounding_ownership"

# our dimension names -> evidence dimension
_SOURCE_DIMENSIONS = {
    DEPTH: ("technical_depth",),
    RELEVANCE: ("completeness",),
    GROUNDING: ("ownership", "resume_grounding"),
}

NON_SUBSTANTIVE_MAX = 0.15   # a gated non-answer scores <= 0.1 (answer_gate)
STRONG_MIN = 0.60
WEAK_DIMENSION_MAX = 0.40
STRONG_DIMENSION_MIN = 0.60

_ADVICE = {
    RELEVANCE: "Answer exactly what each question asks before adding extra — several responses drifted off the question.",
    DEPTH: "Go a level deeper: name the specific mechanism, the components, and concrete numbers, not just what the system does.",
    GROUNDING: "Speak in the first person about YOUR specific decisions and what you personally built, rather than generic \"we did X\".",
}
_STRENGTH_LABEL = {
    RELEVANCE: "answers stayed on-topic and addressed the question",
    DEPTH: "answers included concrete, specific detail",
    GROUNDING: "answers were grounded in your own work and decisions",
}
SCOPE_NOTE = (
    "This report reflects how relevant, specific, and grounded your answers were. It does not "
    "independently verify the factual correctness of individual technical claims."
)


def _evidence_scores(evaluation: dict) -> dict[str, float]:
    """This answer's score per evidence dimension (only those it reported)."""
    by_name = {d.get("name"): d.get("raw_score") for d in evaluation.get("dimensions", [])}
    out = {}
    for evidence, sources in _SOURCE_DIMENSIONS.items():
        values = [float(by_name[s]) for s in sources if isinstance(by_name.get(s), (int, float))]
        if values:
            out[evidence] = sum(values) / len(values)
    return out


def build_feedback(evaluations: list[dict], timeline: list[dict] | None = None) -> dict:
    """Headline, summary, strengths, focus areas, scope note and stats from the
    per-turn evaluation payloads (`conversation_engine._result_payload`)."""
    n = len(evaluations)
    if n == 0:
        return {"headline": "No answers were evaluated.",
                "summary": "The session ended before any answer could be assessed.",
                "strengths": [], "focus_areas": [], "scope_note": SCOPE_NOTE,
                "stats": {"questions": 0}}

    overalls = [float(e.get("overall_score", 0.0)) for e in evaluations]
    per_dimension: dict[str, list[float]] = {d: [] for d in _SOURCE_DIMENSIONS}
    for e, overall in zip(evaluations, overalls):
        # A non-answer's dimension scores are meaningless (answer_gate caps its
        # overall score but not its dimensions -- a keyword dump still "reads"
        # as grounded), so strengths/weaknesses come from real answers only.
        if overall <= NON_SUBSTANTIVE_MAX:
            continue
        for d, v in _evidence_scores(e).items():
            per_dimension[d].append(v)
    dim_means = {d: sum(v) / len(v) for d, v in per_dimension.items() if v}

    non_substantive = sum(1 for o in overalls if o <= NON_SUBSTANTIVE_MAX)
    strong = sum(1 for o in overalls if o >= STRONG_MIN)
    weak_dims = {d: m for d, m in dim_means.items() if m < WEAK_DIMENSION_MAX}
    strong_dims = {d: m for d, m in dim_means.items() if m >= STRONG_DIMENSION_MIN}
    worst_dim = min(dim_means, key=dim_means.get) if dim_means else DEPTH

    focus_areas = [{"dimension": d, "tip": _ADVICE[d]} for d in sorted(weak_dims, key=weak_dims.get)]
    strengths = [_STRENGTH_LABEL[d] for d in sorted(strong_dims, key=strong_dims.get, reverse=True)]

    if non_substantive >= math.ceil(0.6 * n):
        headline = "Most questions weren't really answered."
        summary = (
            f"You gave a non-substantive answer (an \"I don't know\", a one-liner, or off-topic text) to "
            f"{non_substantive} of {n} questions, so there isn't enough to evaluate. Pick one project from "
            f"your résumé and walk through what you personally built, the key technical decisions, and why you "
            f"made them — concrete specifics matter far more than length."
        )
    elif strong >= math.ceil(0.6 * n):
        headline = "Strong session — specific, grounded answers."
        tip = (_ADVICE[worst_dim] if dim_means.get(worst_dim, 1.0) < STRONG_DIMENSION_MIN
               else "Keep pushing for concrete numbers and trade-offs.")
        summary = (f"You answered {strong} of {n} questions with relevant, concrete detail. "
                   f"To go from good to excellent: {tip[0].lower() + tip[1:]}")
    else:
        headline = "A mixed session with clear room to go deeper."
        pieces = [f"{strong} of {n} answers were solid" if strong else "few answers landed as strong"]
        if non_substantive:
            pieces.append(f"{non_substantive} weren't substantively answered")
        advice = _ADVICE[worst_dim]
        summary = (". ".join(p[0].upper() + p[1:] for p in pieces) + ". "
                   + f"Your biggest opportunity: {advice[0].lower() + advice[1:]}")

    return {
        "headline": headline,
        "summary": summary,
        "strengths": strengths,
        "focus_areas": focus_areas,
        "scope_note": SCOPE_NOTE,
        "stats": {
            "questions": n,
            "mean_overall": round(sum(overalls) / n, 3),
            "substantively_answered": n - non_substantive,
            "non_substantive": non_substantive,
            "strong_answers": strong,
            "dimension_means": {d: round(m, 3) for d, m in dim_means.items()},
        },
    }
