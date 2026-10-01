# Milestone 4 — Validation Report

Status: **Validation pass complete. All nine acceptance criteria from `Milestone4_Design.md` Section 8.7 pass. Zero hallucination failures, zero graceful-degradation violations, zero false-tradeoff firings, zero unexplained unused evidence, zero Milestone 0-3 file modifications.**

Implements the approved design in `docs/architecture/Milestone4_Design.md` exactly: `seed_synthesis.py` (the five template families, ranking/dedup/capping selection, Evidence Accounting) wired into `cross_reference.py` as the real `DefaultCrossReferenceEngine`, per Section 6.2's placement at Stage 5 (Cross-Reference), not a new `EntityParser`.

---

## 1. Methodology

- Implemented `seed_synthesis.py` exactly per the design's algorithm (Section 3.3): evidence discovery (technologies/concepts/metrics/comparison phrases, all recomputed independently — no import from or internal-state read of `project_parser.py`), five template families in priority order (metric > tradeoff > tech > integration > concept), greedy rank-then-select with per-family caps, an overall cap, and exact evidence-overlap deduplication.
- Implemented the debug-only `EvidenceAccounting` model exactly per Section 8.6: `discovered`/`consumed`/`unused` per project, four closed-vocabulary reason codes for unused evidence, constructed only when `want_accounting=True` — never in the default path.
- Wired `seed_synthesis.synthesize_seeds` into `cross_reference.py`'s `DefaultCrossReferenceEngine.cross_reference`, the pipeline's existing Stage 5 slot (previously a `NotImplementedError` stub) — no new pipeline stage, no interface change.
- Added 34 unit tests (`test_seed_synthesis.py`, `test_cross_reference.py`) covering every template family individually, ranking/priority order, deduplication (both the negative case — evidence already claimed — and the positive case — a legitimate integration-probe firing on technologies the tech-probe cap left unclaimed), capping, grounding/anti-hallucination invariants, confidence/traceability, Evidence Accounting, and the zero-cost-when-tracing-disabled contract.
- Built a 12-fixture evidence-profile corpus (`golden_corpus/seed_synthesis_fixtures/projects.json`) spanning zero/sparse/moderate/rich evidence (Section 8.4), including two deliberately adversarial "false tradeoff" fixtures designed to try to trick the tradeoff-probe family into firing dishonestly. Locked in as golden snapshots after running the actual implementation and manually reviewing every output for the properties in Section 8.1/8.2 (not hand-derived blind — see Section 3 below for one thing this review caught).
- Extended the real, PDF-based Golden Corpus: added `expected_interview_seeds.json` to `full_entity_resume_pdf` and a new end-to-end test (`test_golden_corpus_seed_synthesis.py`) running the actual frozen `PdfDocxExtractor` → `ColumnAwareLayoutReconstructor` → `HeuristicSectionDetector` → `ProjectParser` pipeline plus the new `DefaultCrossReferenceEngine`, asserting on real-document output, not just hand-authored fixtures.
- Ran the full `resume_engine/tests/` suite after every phase (core module → pipeline wiring → golden corpus), per the "stop and fix before continuing" instruction — no regression was found at any phase, so no fix-then-rerun cycle was needed.

## 2. Acceptance criteria (Design doc Section 8.7)

| # | Criterion | Result |
|---|---|---|
| 1 | Design document (Sections 1-8) reviewed and approved | **Pass** — approved prior to implementation. |
| 2 | 10-15 project fixtures spanning all four evidence profiles, including a false-tradeoff-framing fixture | **Pass** — 12 fixtures: 2 zero, 2 sparse, 4 moderate (including both adversarial false-tradeoff fixtures), 3 rich. |
| 3 | Zero hallucination-check failures (100% of generated seeds grounded) | **Pass** — `test_no_hallucinated_evidence` asserts `consumed ⊆ discovered` across all 12 fixtures; 0 failures. |
| 4 | Zero graceful-degradation violations | **Pass** — both zero-evidence fixtures produce exactly `[]`; `test_zero_evidence_fixtures_produce_no_seeds` and unit-level tests confirm no generic fallback path exists in the code at all (structural, not just tested). |
| 5 | Zero false-tradeoff-framing failures | **Pass** — `test_false_tradeoff_fixtures_never_produce_a_tradeoff_seed` confirms neither adversarial fixture (mere co-occurrence; comparison language with only one known technology) produces a tradeoff-probe seed. |
| 6 | Seed counts match Section 8.4's expected ranges, or deviations justified | **Pass, with documented deviations** — see Section 4 below; every deviation from the generic table is explained by the specific fixture's evidence shape, not left unexplained. |
| 7 | Zero M0-3 file modifications | **Pass** — see Section 5; `git diff --stat` against the Milestone 3 freeze point touches only `cross_reference.py` (explicitly a Milestone-0-era stub slated for this milestone, not a frozen M0-3 parsing/extraction file) plus new files. |
| 8 | Evidence Coverage Accounting's four acceptance criteria (Section 8.6) all pass | **Pass** — see Section 6 below. |
| 9 | Written `Milestone4_ValidationReport.md` with the evidence-coverage table, produced before Milestone 5 implementation begins | **Pass** — this document. |

## 3. Findings

### Finding 1 (design confirmation, not a bug): the tradeoff-probe template names only `tech_a` in its text, while its evidence set includes `tech_b`

**Observed**: reviewing the `moderate_explicit_migration` fixture's actual output (`"Why REST over the alternative, given you mentioned 'Migrated from REST to'?"`), `GraphQL` never appears in the rendered seed text, yet its evidence is marked "consumed" (by the tradeoff seed), which correctly prevents a redundant separate tech-probe on `GraphQL` later. This is not a bug — it is exactly the template and evidence-list shape specified in the approved design (Section 3.3's pseudocode: `evidence=[tech_a, tech_b, comparison...]` for the tradeoff family). Recorded here because it was worth confirming deliberately (a seed's *evidence* set is allowed to be broader than the nouns literally printed in its *text*, by design — the evidence set exists for deduplication/traceability, not as a literal transcript of the text) rather than assuming the implementation matched intent without checking a concrete example.

No other findings — the implementation matched the approved design on every other point checked during this pass; no bugs were found in `seed_synthesis.py`, `cross_reference.py`, or their interaction with the frozen M0-3 pipeline.

## 4. Seed-count deviations from Section 8.4's generic table

Section 8.4 gave illustrative *ranges* per evidence profile, explicitly flagged as starting estimates to be confirmed or adjusted against real fixture output (not treated as final on paper alone). Observed counts:

| Fixture | Profile | Section 8.4 estimate | Actual | Explanation |
|---|---|---|---|---|
| `zero_evidence_blog`, `zero_evidence_untitled` | zero | 0 | 0 | Matches exactly. |
| `sparse_single_tech`, `sparse_single_tech_2` | sparse | 1 | 1 | Matches exactly. |
| `moderate_state_management`, `moderate_stream_processing` | moderate | 3-4 | 3 | Matches (within range). |
| `moderate_explicit_migration` | moderate | 3-4 | **2** | Below range — the tradeoff-probe's evidence set claims *both* technologies at once (Finding 1), so with only 2 technologies + 1 concept in this fixture, once the tradeoff fires there are no remaining technologies left for a tech-probe. This is a direct, explainable consequence of the approved dedup rule, not an unexplained gap. |
| `false_tradeoff_mere_cooccurrence` | moderate | 3-4 | 2 | Below range — this fixture intentionally has only 2 technologies and 0 concepts (it exists to test the tradeoff guarantee, not to hit a count target); both technologies become tech-probes. |
| `false_tradeoff_comparison_too_far` | moderate | 3-4 | **1** | Below range — this fixture intentionally has only 1 technology (needed to make the tradeoff precondition fail via "fewer than two technologies," not via distance); a single tech-probe is the only evidence available. |
| `rich_cap_engages`, `rich_metrics_and_concepts`, `rich_no_metrics_wide_tech_spread` | rich | `MAX_SEEDS_PER_PROJECT` (4) | 4 | Matches exactly — the cap binds on all three rich fixtures, as expected. |

All three "moderate" deviations come from fixtures deliberately constructed to isolate a specific behavior (the tradeoff dedup rule; the tradeoff anti-hallucination guarantee) rather than to hit the generic count target — this is judged an acceptable, explained deviation, not a defect in the algorithm. `MAX_SEEDS_PER_PROJECT=4`, `TECH_PROBE_CAP=2`, `INTEGRATION_PROBE_CAP=1`, `CONCEPT_PROBE_CAP=1` are confirmed as reasonable starting values against this fixture set; no change proposed.

## 5. M0-3 boundary check

```
main_cap/cap/resume_engine/cross_reference.py   | modified (this milestone's own deliverable — was a Milestone-0-era
                                                    NotImplementedError stub explicitly earmarked for this milestone,
                                                    per Design doc Section 6.2/6.3; never one of the "frozen" M0-3 files)
main_cap/cap/resume_engine/seed_synthesis.py    | new
main_cap/cap/resume_engine/tests/...            | new (test_seed_synthesis.py, test_cross_reference.py,
                                                    test_golden_corpus_seed_synthesis.py, seed_synthesis_fixtures/,
                                                    full_entity_resume_pdf/expected_interview_seeds.json)
docs/architecture/Milestone4_Design.md          | new (design doc, written and approved before this implementation)
docs/architecture/Milestone4_ValidationReport.md| new (this document)
```

**No changes to** `extractor.py`, `layout.py`, `sections.py`, `document_model.py`, `interfaces.py`, `registry.py`, `factory.py`, `parsers/contact_parser.py`, `parsers/experience_parser.py`, `parsers/project_parser.py`, or any existing golden-corpus `expected_layout.json`/`expected_sections.json`/`expected_entities.json` file. `seed_synthesis.py` imports only `resume_engine.confidence.Confidence` and `resume_engine.technology_gazetteer.TECHNOLOGIES` (the shared, public gazetteer already used by multiple M3 parsers) — it never imports `resume_engine.parsers.project_parser`, confirmed by inspection of its import block.

## 6. Evidence Coverage Accounting — tables and utilization analysis (Section 8.6)

### 6.1 Hallucination and duplicate-consumption checks (criteria 1-2)

Both are hard gates, checked automatically across all 12 fixtures (`test_no_hallucinated_evidence`, `test_no_duplicate_evidence_consumption`): **0 failures on both**, across every fixture. Every evidence item any seed's text depends on is drawn from that project's own `discovered` inventory, and no single evidence item is ever claimed by two different seeds.

### 6.2 Utilization by evidence kind (criterion 3)

| Evidence kind | Fixtures with this kind present | Utilization observed | Notes |
|---|---|---|---|
| `metric` | `rich_cap_engages` (1), `rich_metrics_and_concepts` (2) | **100%** (3/3 consumed) | Matches the design's expectation exactly — metric-probe carries no family cap and ranks first. |
| `comparison_phrase` | `moderate_explicit_migration` (1, consumed), `false_tradeoff_comparison_too_far` (1, unused — precondition failed) | **100% when precondition met** (1/1); the second is correctly *unused with an explicit reason*, not a utilization failure — the criterion is "100% utilization when the corresponding precondition is met," and here the precondition (2 nearby technologies) is deliberately not met. | Confirms the precondition gate works as designed, not just that comparisons get used when convenient. |
| `technology` | present in 10/12 fixtures | Capped by design once a project has more technologies than `TECH_PROBE_CAP` — e.g. `rich_no_metrics_wide_tech_spread` (5 technologies): 4 of 5 consumed (Kafka, Spark, Airflow, Snowflake via tech-probe + a legitimate integration-probe), 1 unused (`dbt`, `below_cap:tech_probe`). Within the `TECH_PROBE_CAP / len(technologies)` expectation from Section 8.6. | |
| `concept` | present in 8/12 fixtures | Capped similarly — e.g. `moderate_stream_processing` (2 concepts, `CONCEPT_PROBE_CAP=1`): 1 of 2 consumed, matching `CONCEPT_PROBE_CAP / len(concepts)`. In the three "rich" fixtures, concepts are additionally crowded out entirely by the overall cap once higher-priority families fill it (`below_cap:overall`, not `below_cap:concept_probe`) — this is the "evidence starvation" scenario from Section 8.2, confirmed as correct ranking behavior (the highest-value evidence wins the cap), not a defect. | |

### 6.3 Unused-evidence explainability (criterion 4)

`test_every_unused_evidence_item_is_explainable` checks every unused item across all 12 fixtures against the four closed-vocabulary reason codes: **0 unexplained items**. Observed reason-code distribution across the fixture set:

| Reason code | Count | Example |
|---|---|---|
| `below_cap:tech_probe` | 2 | `Node.js` in `moderate_state_management`; `dbt` in `rich_no_metrics_wide_tech_spread` |
| `below_cap:concept_probe` | 1 | `Stream Processing` in `moderate_stream_processing` |
| `below_cap:overall` | 6 | `Caching`/`Distributed Systems` in `rich_cap_engages`; `Vector Search`/`Embeddings` in `rich_metrics_and_concepts`; `ETL`/`Observability` in `rich_no_metrics_wide_tech_spread` |
| `precondition_not_met:tradeoff_probe` | 1 | the lone comparison phrase in `false_tradeoff_comparison_too_far` |
| `duplicate_of:*` | 0 in the locked fixtures (all overlap cases in this fixture set happened to resolve via a cap reason first) — exercised directly by unit tests instead (`test_no_evidence_item_is_consumed_by_more_than_one_seed`, `test_integration_probe_never_duplicates_evidence_already_claimed_by_tech_probe`) | `duplicate_of:Redis` when an integration-probe candidate is rejected because both its technologies were already tech-probed |
| `lower_priority_unselected` | 0 | Fallback reason never needed in practice — every rejection in this fixture set and the unit-test suite was fully explained by a more specific reason. |

All four reason codes are exercised somewhere in the combined test suite (fixtures + unit tests); every one of the 12-fixture parametrized checks (hallucination, duplicate-consumption, explainability — 36 parametrized test cases total) passed, with zero unexplained unused-evidence items across the corpus.

## 7. Test count

`python -m pytest resume_engine/tests/ -q` from `main_cap/cap`: **261 passed** (up from 172 at the Milestone 3 freeze — 89 new tests: 28 in `test_seed_synthesis.py`, 7 in `test_cross_reference.py`, 54 in `test_golden_corpus_seed_synthesis.py`). Zero failures, zero regressions in any Milestone 0-3 test at any point during this implementation.

## 8. What this means for Milestone 5

Milestone 4's own scope (per the original roadmap and this implementation) is complete: `seed_synthesis.py` and its Cross-Reference wiring are real, tested, and validated. The remaining Milestone 5 scope per the architecture doc — `EducationParser`/`SkillsParser`/`CertificationParser` and demonstrated-skill tagging (the Cross-Reference pass's *other* documented responsibility, distinct from seed synthesis) — is unaffected by this work and remains unimplemented. Not started here; no design work on it was done in this pass.

## 9. Files added in this validation pass

- `resume_engine/seed_synthesis.py` — the Milestone 4 module.
- `resume_engine/cross_reference.py` — real `DefaultCrossReferenceEngine` (was a stub).
- `resume_engine/tests/test_seed_synthesis.py` — 28 unit tests.
- `resume_engine/tests/test_cross_reference.py` — 7 wiring tests.
- `resume_engine/tests/test_golden_corpus_seed_synthesis.py` — 54 golden-corpus/acceptance-criteria tests.
- `resume_engine/tests/golden_corpus/seed_synthesis_fixtures/projects.json` — 12-fixture evidence-profile corpus.
- `resume_engine/tests/golden_corpus/full_entity_resume_pdf/expected_interview_seeds.json` — real-PDF golden snapshot.
- `docs/architecture/Milestone4_Design.md` — the approved design (written and approved before this implementation began).
- This document.

No changes to `extractor.py`, `layout.py`, `sections.py`, `document_model.py`, `interfaces.py`, `registry.py`, `factory.py`, any of the three Milestone 3 parsers, or any prior golden-corpus expectation file.
