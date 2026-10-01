from resume_engine.confidence import Confidence
from resume_engine.interfaces import ParserResult
from resume_engine.validation import DefaultValidationEngine, Observation


def _result(*entities, observations=None) -> ParserResult:
    return ParserResult(
        entities=list(entities),
        confidences=[Confidence(score=0.8, reasons=["+x"]) for _ in entities],
        observations=list(observations or []),
    )


def test_validate_collects_observations_already_embedded_by_earlier_stages():
    embedded = Observation(severity="notice", category="missing_technologies", message="m", entity_ref="projects[0]")
    parser_results = {"projects": _result({"title": "X", "summary": "", "technologies": []}, observations=[embedded])}
    observations = DefaultValidationEngine().validate(parser_results)
    assert embedded in observations


def test_missing_linkedin_rule_fires_when_contact_present_without_linkedin():
    contact = {"candidate_name": "X", "email": "x@test.invalid", "phone": "", "linkedin": "", "location": ""}
    parser_results = {"contact": _result(contact)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert any(o.category == "missing_linkedin" for o in observations)


def test_missing_linkedin_rule_does_not_fire_when_linkedin_present():
    contact = {"candidate_name": "X", "email": "", "phone": "", "linkedin": "linkedin.com/in/x", "location": ""}
    parser_results = {"contact": _result(contact)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "missing_linkedin" for o in observations)


def test_missing_linkedin_rule_does_not_fire_when_no_contact_entity():
    parser_results = {"contact": _result()}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "missing_linkedin" for o in observations)


def test_no_measurable_outcome_rule_fires_when_summary_has_no_metric():
    project = {"title": "X", "summary": "Built a caching layer.", "technologies": ["Redis"]}
    parser_results = {"projects": _result(project)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert any(o.category == "no_measurable_outcome" for o in observations)


def test_no_measurable_outcome_rule_does_not_fire_when_summary_has_a_metric():
    project = {"title": "X", "summary": "Reduced latency by 40%.", "technologies": ["Redis"]}
    parser_results = {"projects": _result(project)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "no_measurable_outcome" for o in observations)


def test_no_measurable_outcome_rule_skips_projects_with_empty_summary():
    """An empty summary is a different, already-covered issue (parser-
    level missing_technologies/empty-section observations) -- this rule
    only judges summaries that exist but lack a metric."""
    project = {"title": "X", "summary": "", "technologies": []}
    parser_results = {"projects": _result(project)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "no_measurable_outcome" for o in observations)


def test_empty_experience_summary_rule_fires():
    experience = {"company": "Acme", "role": "Engineer", "duration": "2021 - 2022", "summary": ""}
    parser_results = {"experience": _result(experience)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert any(o.category == "empty_experience_summary" for o in observations)


def test_inconsistent_dates_rule_fires_when_end_precedes_start():
    experience = {"company": "Acme", "role": "Engineer", "duration": "2022 - 2020", "summary": "Did things."}
    parser_results = {"experience": _result(experience)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert any(o.category == "inconsistent_dates" and o.severity == "warning" for o in observations)


def test_inconsistent_dates_rule_does_not_fire_for_a_normal_range():
    experience = {"company": "Acme", "role": "Engineer", "duration": "2020 - 2022", "summary": "Did things."}
    parser_results = {"experience": _result(experience)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "inconsistent_dates" for o in observations)


def test_inconsistent_dates_rule_does_not_fire_for_an_ongoing_role():
    experience = {"company": "Acme", "role": "Engineer", "duration": "2020 - Present", "summary": "Did things."}
    parser_results = {"experience": _result(experience)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "inconsistent_dates" for o in observations)


def test_inconsistent_dates_rule_does_not_fire_for_unparseable_duration():
    experience = {"company": "Acme", "role": "Engineer", "duration": "sometime", "summary": "Did things."}
    parser_results = {"experience": _result(experience)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert not any(o.category == "inconsistent_dates" for o in observations)


def test_validate_is_deterministic_and_never_raises_on_empty_input():
    assert DefaultValidationEngine().validate({}) == []


def test_validate_never_gates_and_returns_a_plain_list():
    """Non-goal, per the architecture doc: validation observes, it never
    blocks profile generation -- confirmed here structurally: validate()
    always returns (never raises) regardless of how many rules fire."""
    project = {"title": "", "summary": "", "technologies": []}
    experience = {"company": "", "role": "", "duration": "2022 - 2020", "summary": ""}
    contact = {"candidate_name": "", "email": "", "phone": "", "linkedin": "", "location": ""}
    parser_results = {"projects": _result(project), "experience": _result(experience), "contact": _result(contact)}
    observations = DefaultValidationEngine().validate(parser_results)
    assert isinstance(observations, list)
    assert len(observations) >= 3
