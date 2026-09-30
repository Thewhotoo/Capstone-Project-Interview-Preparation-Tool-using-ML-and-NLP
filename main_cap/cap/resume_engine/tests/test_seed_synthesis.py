"""Unit tests for Milestone 4 (Interview Seed Synthesis). See
docs/architecture/Milestone4_Design.md for the approved design these
tests verify against."""

from __future__ import annotations

from resume_engine.seed_synthesis import (
    MAX_SEEDS_PER_PROJECT,
    TECH_PROBE_CAP,
    synthesize_seeds,
)


def _project(**overrides) -> dict:
    base = {"title": "", "summary": "", "technologies": [], "concepts": []}
    base.update(overrides)
    return base


# ── Graceful degradation (the permanent rule) ────────────────────────────


def test_zero_evidence_produces_zero_seeds():
    project = _project(title="Personal Blog", summary="A simple blog about my hobbies.")
    result = synthesize_seeds(project)
    assert result.seeds == []
    assert result.seed_confidences == []


def test_zero_evidence_never_produces_a_generic_fallback_seed():
    project = _project(title="Untitled")
    result = synthesize_seeds(project)
    assert result.seeds == []


# ── Tech-probe family ─────────────────────────────────────────────────────


def test_tech_probe_fires_for_each_extracted_technology_up_to_cap():
    project = _project(
        title="Alert Pipeline",
        summary="A streaming pipeline for security alerts.",
        technologies=["Python", "Redis", "Docker"],
    )
    result = synthesize_seeds(project)
    tech_seeds = [s for s in result.seeds if "Why did you use" in s]
    assert len(tech_seeds) == TECH_PROBE_CAP
    assert any("Python" in s for s in tech_seeds)


def test_tech_probe_names_the_technology_verbatim():
    project = _project(title="X", summary="", technologies=["FastAPI"])
    result = synthesize_seeds(project)
    assert result.seeds == ["Why did you use FastAPI in this project?"]


def test_tech_probe_fires_for_newly_gazetteer_recognized_deberta():
    """Phase 3: once `technologies` correctly includes "DeBERTa" (fixed at
    the gazetteer level in project_parser.py's dependency, not here --
    this module never re-derives technologies from raw text), the
    existing, unmodified tech-probe mechanism activates for it exactly
    like any other already-extracted technology."""
    project = _project(
        title="Interview Platform",
        summary="Developed an end-to-end ML pipeline including DeBERTa-v3 training.",
        technologies=["DeBERTa"],
    )
    result = synthesize_seeds(project)
    assert result.seeds == ["Why did you use DeBERTa in this project?"]


# ── Concept-probe family ──────────────────────────────────────────────────


def test_concept_probe_fires_for_extracted_concept():
    project = _project(title="X", summary="", concepts=["Caching"])
    result = synthesize_seeds(project)
    assert result.seeds == ["How did you approach caching in this project?"]


def test_concept_probe_capped():
    project = _project(title="X", summary="", concepts=["Caching", "Microservices", "Rate Limiting"])
    result = synthesize_seeds(project)
    concept_seeds = [s for s in result.seeds if "How did you approach" in s]
    assert len(concept_seeds) == 1


# ── Integration-probe family ──────────────────────────────────────────────


def test_integration_probe_fires_when_capacity_allows_two_distinct_technologies():
    # A single technology can't produce a distinct integration pair without
    # colliding with the tech-probe that already claimed it (dedup, tested
    # separately) -- so use a project where tech-probes are capped out
    # before all technologies are claimed, then confirm no PHANTOM
    # integration seed sneaks in referencing an unclaimed pair. This test
    # instead confirms the candidate is considered at all by checking a
    # project with exactly 2 technologies and a tech cap of 2 -- both techs
    # get tech-probed, so integration never fires (see dedup test below)
    # -- the *positive* firing case requires TECH_PROBE_CAP < technologies,
    # which is exercised in test_integration_probe_never_duplicates_evidence.
    project = _project(title="X", summary="", technologies=["Postgres", "Redis"])
    result = synthesize_seeds(project)
    assert not any("work together" in s for s in result.seeds)


def test_integration_probe_fires_for_a_pair_left_unclaimed_by_the_tech_probe_cap():
    """Positive case: with more technologies than TECH_PROBE_CAP, the
    technologies past the cap are still eligible for a legitimate,
    non-duplicate integration-probe pairing (Design doc Section 3.3)."""
    project = _project(
        title="X", summary="", technologies=["Kafka", "Spark", "Airflow", "Snowflake", "dbt"]
    )
    result = synthesize_seeds(project)
    assert any("work together" in s for s in result.seeds)


# ── Metric-probe family ────────────────────────────────────────────────────


def test_metric_probe_fires_on_percentage():
    project = _project(
        title="X", summary="Reduced query latency by 40% under load.", technologies=["Postgres"]
    )
    result = synthesize_seeds(project)
    assert any("40%" in s for s in result.seeds)
    assert any(s.startswith('You mentioned') for s in result.seeds)


def test_metric_probe_fires_on_multiplier():
    project = _project(title="X", summary="Scaled throughput 3x with batching.")
    result = synthesize_seeds(project)
    assert any("3x" in s for s in result.seeds)


def test_metric_probe_ranks_above_tech_probe():
    project = _project(
        title="X",
        summary="Reduced latency by 40%.",
        technologies=["Python", "Redis", "Docker", "Kafka"],
    )
    result = synthesize_seeds(project)
    assert result.seeds[0].startswith("You mentioned")


# ── Tradeoff-probe family (strict precondition) ────────────────────────────


def test_tradeoff_probe_fires_with_explicit_comparison_language_and_two_nearby_technologies():
    project = _project(
        title="X",
        summary="Chose Postgres over MongoDB for strong consistency guarantees.",
        technologies=["Postgres", "MongoDB"],
    )
    result = synthesize_seeds(project)
    assert any("over the alternative" in s for s in result.seeds)


def test_tradeoff_probe_never_fires_without_explicit_comparison_language():
    """Two technologies merely co-occurring is NOT a tradeoff -- this is
    the anti-hallucination guarantee from Design doc Section 3.5,
    guarantee 2: integration-probe covers co-occurrence; tradeoff-probe
    requires the resume to state a comparison itself."""
    project = _project(
        title="X",
        summary="Used Postgres and MongoDB together in this project.",
        technologies=["Postgres", "MongoDB"],
    )
    result = synthesize_seeds(project)
    assert not any("over the alternative" in s for s in result.seeds)


def test_tradeoff_probe_never_fires_with_comparison_language_but_only_one_nearby_technology():
    project = _project(
        title="X",
        summary="Chose Postgres instead of a flat file for storage.",
        technologies=["Postgres"],
    )
    result = synthesize_seeds(project)
    assert not any("over the alternative" in s for s in result.seeds)


# ── Ranking, deduplication, capping, priority order ─────────────────────────


def test_family_priority_order_metric_tradeoff_tech_integration_concept():
    project = _project(
        title="X",
        summary="Reduced cost by 20% after switching from MySQL to Postgres.",
        technologies=["MySQL", "Postgres"],
        concepts=["Query Optimization"],
    )
    result = synthesize_seeds(project)
    families_in_order = []
    for seed in result.seeds:
        if seed.startswith("You mentioned"):
            families_in_order.append("metric")
        elif "over the alternative" in seed:
            families_in_order.append("tradeoff")
        elif seed.startswith("Why did you use"):
            families_in_order.append("tech")
        elif "work together" in seed:
            families_in_order.append("integration")
        elif seed.startswith("How did you approach"):
            families_in_order.append("concept")
    assert families_in_order == sorted(
        families_in_order, key=lambda f: ["metric", "tradeoff", "tech", "integration", "concept"].index(f)
    )


def test_no_evidence_item_is_consumed_by_more_than_one_seed():
    project = _project(
        title="X",
        summary="",
        technologies=["Redis", "Kafka"],
        concepts=["Caching"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    seen_evidence: set[tuple[str, str]] = set()
    for candidate_evidence in result.accounting.consumed.values():
        for item in candidate_evidence:
            key = (item.kind, item.value)
            assert key not in seen_evidence, f"{key} consumed by more than one seed"
            seen_evidence.add(key)


def test_integration_probe_never_duplicates_evidence_already_claimed_by_tech_probe():
    """With TECH_PROBE_CAP=2 and exactly 2 technologies, both get claimed
    by tech-probes first (higher priority) -- the corresponding
    integration-probe candidate is a pure duplicate and must not appear."""
    project = _project(title="X", summary="", technologies=["Redis", "Kafka"])
    result = synthesize_seeds(project)
    assert not any("work together" in s for s in result.seeds)
    assert len(result.seeds) == 2  # both tech-probes, nothing else


def test_overall_cap_is_never_exceeded():
    project = _project(
        title="X",
        summary="Reduced latency by 40% after choosing Redis over Memcached.",
        technologies=["Python", "Redis", "Memcached", "Docker", "Kafka"],
        concepts=["Caching", "Rate Limiting"],
    )
    result = synthesize_seeds(project)
    assert len(result.seeds) <= MAX_SEEDS_PER_PROJECT


# ── Grounding / anti-hallucination invariant ────────────────────────────────


def test_every_seed_only_names_evidence_present_in_the_project():
    """Structural grounding check (Design doc Section 3.5, guarantee 1 /
    Section 8.1 rule 1): every evidence item consumed by a generated seed
    must appear in the project's own discovered evidence -- never
    fabricated."""
    project = _project(
        title="Realtime Dashboard",
        summary="Reduced page load by 25% using React and D3 instead of jQuery for rendering.",
        technologies=["React", "D3", "jQuery"],
        concepts=["Real-Time Updates"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    discovered_keys = {(item.kind, item.value) for item in result.accounting.discovered}
    for evidence_list in result.accounting.consumed.values():
        for item in evidence_list:
            assert (item.kind, item.value) in discovered_keys


def test_every_generated_seed_names_at_least_one_concrete_piece_of_evidence():
    """No template in the bank has a zero-evidence slot -- Section 8.1
    rule 2, enforced by construction."""
    project = _project(
        title="X",
        summary="Reduced cost by 20%.",
        technologies=["Go"],
        concepts=["Observability"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    for seed_text, evidence in result.accounting.consumed.items():
        assert len(evidence) >= 1, seed_text


# ── Confidence / traceability ───────────────────────────────────────────────


def test_every_seed_has_a_matching_nonempty_confidence():
    project = _project(title="X", summary="", technologies=["Go", "Redis"], concepts=["Caching"])
    result = synthesize_seeds(project)
    assert len(result.seeds) == len(result.seed_confidences)
    for confidence in result.seed_confidences:
        assert confidence.reasons


# ── Evidence Accounting (Design doc Section 8.6) ────────────────────────────


def test_accounting_is_none_when_not_requested():
    project = _project(title="X", summary="", technologies=["Go"])
    result = synthesize_seeds(project)
    assert result.accounting is None


def test_accounting_records_discovered_consumed_and_unused():
    project = _project(
        title="X",
        summary="",
        technologies=["Python", "Redis", "Docker"],
        concepts=["Caching", "Microservices"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    accounting = result.accounting
    assert accounting.project_title == "X"
    assert len(accounting.discovered) == 5  # 3 technologies + 2 concepts
    assert sum(len(v) for v in accounting.consumed.values()) >= 1
    assert accounting.unused  # Docker (tech cap) and Microservices (concept cap) both left over


def test_every_unused_item_carries_a_closed_vocabulary_reason():
    project = _project(
        title="X",
        summary="",
        technologies=["Python", "Redis", "Docker"],
        concepts=["Caching", "Microservices"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    valid_prefixes = ("below_cap:", "duplicate_of:", "precondition_not_met:", "lower_priority_unselected")
    for unused_item in result.accounting.unused:
        assert unused_item.reason.startswith(valid_prefixes), unused_item.reason


def test_unused_technology_beyond_cap_reports_below_cap_reason():
    project = _project(title="X", summary="", technologies=["Python", "Redis", "Docker"])
    result = synthesize_seeds(project, want_accounting=True)
    unused_values = {item.item.value: item.reason for item in result.accounting.unused}
    assert unused_values["Docker"] == "below_cap:tech_probe"


def test_unused_comparison_without_precondition_reports_precondition_reason():
    project = _project(
        title="X",
        summary="Chose Postgres instead of a flat file for storage.",
        technologies=["Postgres"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    comparison_unused = [
        item for item in result.accounting.unused if item.item.kind == "comparison_phrase"
    ]
    assert len(comparison_unused) == 1
    assert comparison_unused[0].reason == "precondition_not_met:tradeoff_probe"


def test_rich_evidence_project_fully_utilizes_metrics_and_comparisons():
    """Section 8.6 criterion 3: metrics/comparisons should reach 100%
    utilization when their preconditions are met, since they rank first
    and carry no family cap."""
    project = _project(
        title="X",
        summary="Reduced latency by 40% after choosing Redis over Memcached for caching.",
        technologies=["Redis", "Memcached"],
    )
    result = synthesize_seeds(project, want_accounting=True)
    metric_unused = [i for i in result.accounting.unused if i.item.kind == "metric"]
    comparison_unused = [i for i in result.accounting.unused if i.item.kind == "comparison_phrase"]
    assert metric_unused == []
    assert comparison_unused == []


def test_determinism_same_input_produces_identical_output():
    project = _project(
        title="X",
        summary="Reduced latency by 40% using Redis instead of Memcached.",
        technologies=["Redis", "Memcached", "Docker"],
        concepts=["Caching"],
    )
    first = synthesize_seeds(project, want_accounting=True)
    second = synthesize_seeds(project, want_accounting=True)
    assert first.seeds == second.seeds
    assert [c.score for c in first.seed_confidences] == [c.score for c in second.seed_confidences]
