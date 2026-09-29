"""
Interview Feedback — data-driven, honest end-of-session feedback.

Replaces the frontend's fixed narrative templates (e.g. "This was a steady
discussion... a few technical claims didn't hold up") with feedback DERIVED from
the actual per-turn evaluation signals: how many questions were substantively
answered, which evidence dimensions were weak/strong, and what to do about it.

Deterministic and model-free (no LLM, no API — consistent with this project's
constraints). HONEST BY DESIGN: it only speaks to what the evaluator can
actually measure — relevance, specificity/depth, and résumé-grounding/ownership
of the answers — and it explicitly does NOT claim to have verified the factual
correctness of technical claims (there is no per-question answer key for
experiential résumé questions; see resume_evidence_evaluator / correctness_nli_scorer).

Consumes the same per-turn payloads `conversation_engine._result_payload`
already produces (overall_score, grade, dimensions[{name, raw_score}]); adds a
single `feedback` block to `end_conversation`'s summary. No evaluation logic and
no scoring changes here — pure summarization of results already computed.
"""

from __future__ import annotations

import math

_TECH = "technical_correctness"
_DEPTH = "depth_specificity"
_RELV = "relevance_completeness"
_GRND = "grounding_ownership"

# Actionable guidance per evidence dimension (what to DO), not a canned verdict.
_ADVICE = {
    _RELV: "Answer exactly what each question asks before adding extra — several responses drifted off the question.",
    _DEPTH: "Go a level deeper: name the specific mechanism, the components, and concrete numbers, not just what the system does.",
    _GRND: "Speak in the first person about YOUR specific decisions and what you personally built, rather than generic \"we did X\".",
}
_STRENGTH_LABEL = {
    _RELV: "answers stayed on-topic and addressed the question",
    _DEPTH: "answers included concrete, specific detail",
    _GRND: "answers were grounded in your own work and decisions",
}
_SCOPE_NOTE = (
    "This report reflects how relevant, specific, and grounded your answers were. It does not "
    "independently verify the factual correctness of individual technical claims."
)


def _dim(ev: dict, name: str) -> float:
    for d in ev.get("dimensions", []):
        if d.get("name") == name:
            return float(d.get("raw_score", 0.0))
    return 0.0


def build_feedback(evaluations: list[dict], timeline: list[dict] | None = None) -> dict:
    """Build an honest, data-driven feedback block from the per-turn evaluation
    payloads. Returns a dict the UI can render directly (headline, summary,
    strengths, focus_areas, scope_note, stats)."""
    n = len(evaluations)
    if n == 0:
        return {"headline": "No answers were evaluated.",
                "summary": "The session ended before any answer could be assessed.",
                "strengths": [], "focus_areas": [], "scope_note": _SCOPE_NOTE,
                "stats": {"questions": 0}}

    overalls = [float(e.get("overall_score", 0.0)) for e in evaluations]
    mean_overall = sum(overalls) / n
    dim_means = {d: sum(_dim(e, d) for e in evaluations) / n for d in (_DEPTH, _RELV, _GRND)}

    non_substantive = sum(1 for o in overalls if o <= 0.15)   # gated non-answers / degenerate
    strong = sum(1 for o in overalls if o >= 0.60)
    weak_dims = {d: m for d, m in dim_means.items() if m < 0.40}
    strong_dims = {d: m for d, m in dim_means.items() if m >= 0.60}
    # dominant weakness = the lowest-scoring evidence dimension (correctness excluded — unverified)
    worst_dim = min(dim_means, key=dim_means.get)

    focus_areas = [{"dimension": d, "tip": _ADVICE[d]} for d in sorted(weak_dims, key=weak_dims.get)]
    strengths = [_STRENGTH_LABEL[d] for d in sorted(strong_dims, key=strong_dims.get, reverse=True)]

    # ── headline + summary, chosen from the ACTUAL data ──
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
        tip = _ADVICE[worst_dim] if dim_means[worst_dim] < 0.6 else "Keep pushing for concrete numbers and trade-offs."
        summary = (
            f"You answered {strong} of {n} questions with relevant, concrete detail. To go from good to "
            f"excellent: {tip.lower()}"
        )
    else:
        headline = "A mixed session with clear room to go deeper."
        pieces = [f"{strong} of {n} answers were solid" if strong else "few answers landed as strong"]
        if non_substantive:
            pieces.append(f"{non_substantive} weren't substantively answered")
        summary = (
            ". ".join(p.capitalize() for p in pieces) + ". "
            + f"Your biggest opportunity: {_ADVICE[worst_dim].lower()}"
        )

    return {
        "headline": headline,
        "summary": summary,
        "strengths": strengths,
        "focus_areas": focus_areas,
        "scope_note": _SCOPE_NOTE,
        "stats": {
            "questions": n,
            "mean_overall": round(mean_overall, 3),
            "substantively_answered": n - non_substantive,
            "non_substantive": non_substantive,
            "strong_answers": strong,
            "dimension_means": {d: round(m, 3) for d, m in dim_means.items()},
        },
    }
