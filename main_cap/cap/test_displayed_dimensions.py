"""Only the four canonical attributes are surfaced per turn; overall_score is unchanged."""

from types import SimpleNamespace as NS

from conversation_engine import DISPLAYED_DIMENSIONS, _result_payload


def _dim(name, score):
    return NS(name=name, raw_score=score, confidence=0.8, contributes_to_overall=True)


def _claim(claim, dimension):
    return NS(claim=claim, dimension=dimension, evidence="e")


def test_only_displayed_dimensions_are_rendered():
    names = ["technical_accuracy", "technical_depth", "communication", "completeness",
             "architecture", "ownership", "debugging", "resume_grounding", "authenticity"]
    result = NS(
        overall_score=0.7, grade="good", confidence=0.8, confidence_rationale="x", reasoning="x",
        dimensions=tuple(_dim(n, 0.6) for n in names),
        strengths=(_claim("Strong communication.", "communication"), _claim("Strong ownership.", "ownership")),
        weaknesses=(_claim("Weak testing.", "testing"),),
        missing_reasoning=(), concept_coverage=(), suggested_improvements=(), recommended_topics=(),
        contradiction_detected=False,
    )
    payload = _result_payload(result)
    assert {d["name"] for d in payload["dimensions"]} == DISPLAYED_DIMENSIONS
    assert payload["strengths"] == ["Strong ownership."]
    assert payload["weaknesses"] == []
    assert payload["overall_score"] == 0.7
