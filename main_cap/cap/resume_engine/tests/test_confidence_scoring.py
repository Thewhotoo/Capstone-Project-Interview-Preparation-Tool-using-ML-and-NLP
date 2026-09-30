from resume_engine.confidence import Confidence, DefaultConfidenceEngine
from resume_engine.interfaces import ParserResult


def _result(*scores: float) -> ParserResult:
    return ParserResult(
        entities=[{"x": i} for i in range(len(scores))],
        confidences=[Confidence(score=s, reasons=["+x"]) for s in scores],
        observations=[],
    )


def test_overall_confidence_is_the_flat_mean_of_every_entity_score():
    parser_results = {
        "contact": _result(0.8),
        "projects": _result(0.9, 0.7),
    }
    profile = DefaultConfidenceEngine().score(parser_results, observations=[])
    # mean(0.8, 0.9, 0.7) == 0.8
    assert profile.overall_confidence.score == 0.8


def test_overall_confidence_reasons_name_every_contributing_parser():
    parser_results = {"contact": _result(0.8), "projects": _result(0.9)}
    profile = DefaultConfidenceEngine().score(parser_results, observations=[])
    reasons = profile.overall_confidence.reasons
    assert any("contact" in r and "1 entities" in r for r in reasons)
    assert any("projects" in r and "1 entities" in r for r in reasons)


def test_parser_with_zero_entities_gets_a_negative_reason_not_penalized_in_the_score():
    parser_results = {"contact": _result(0.8), "education": _result()}
    profile = DefaultConfidenceEngine().score(parser_results, observations=[])
    assert profile.overall_confidence.score == 0.8  # education's absence doesn't drag the mean down
    assert any("education" in r and r.startswith("-") for r in profile.overall_confidence.reasons)


def test_zero_entities_everywhere_produces_zero_confidence_with_explicit_reason():
    parser_results = {"contact": _result(), "projects": _result()}
    profile = DefaultConfidenceEngine().score(parser_results, observations=[])
    assert profile.overall_confidence.score == 0.0
    assert "-no_entities_found_in_any_parser" in profile.overall_confidence.reasons


def test_confidence_reasons_are_never_empty():
    """Mirrors check_parser_conformance's "confidence must always be
    explainable" rule -- not enforced by a shared function for
    ConfidenceEngine, but held to the same standard by construction."""
    profile = DefaultConfidenceEngine().score({}, observations=[])
    assert profile.overall_confidence.reasons


def test_annotated_profile_carries_through_parser_results_and_observations_unchanged():
    from resume_engine.validation import Observation

    parser_results = {"contact": _result(0.8)}
    obs = [Observation(severity="notice", category="x", message="m", entity_ref="contact")]
    profile = DefaultConfidenceEngine().score(parser_results, observations=obs)
    assert profile.parser_results is parser_results
    assert profile.observations == obs
