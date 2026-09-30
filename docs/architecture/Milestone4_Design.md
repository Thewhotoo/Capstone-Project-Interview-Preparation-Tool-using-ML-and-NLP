# Milestone 4 — Interview Seed Synthesis: Design Review

Status: **Design approved (direction, template bank, LLM isolation, M3-boundary question, evaluation strategy including Evidence Coverage Accounting — all resolved). No production code written against this document yet — this update is the final addition requested before implementation; implementation itself awaits explicit go-ahead.**
Scope: reconciles the original architecture's assumption that `interview_seeds` requires genuine LLM synthesis against what Milestones 1-3 actually built, and proposes (but does not implement) the Milestone 4/5 mechanism for generating `ProjectEntry.interview_seeds: list[str]` deterministically.

Read alongside `ResumeIntelligenceEngine.md` Section 4.4 (ProjectParser), Section 10 (Milestone 4/5), Section 11 (Risks), and Section 12 Decision 3.

---

## 1. Is this still a synthesis problem, or can it now be solved deterministically?

**Reconciled position: it is narrower than originally assumed, but it is not pure extraction either. It is template instantiation over already-deterministically-extracted evidence — closer to "lightweight synthesis" than to "genuine synthesis," and closer to "heuristic composition" than to "invention."**

The original architecture doc (Section 1.3) drew the distinction as "Gemini invents a plausible interview question from a project description... A deterministic engine cannot 'invent' a question the way an LLM can." That framing is still correct about what an LLM *does*, but it overstated what the *task itself* requires. What actually makes a good interview seed is not creative invention — it's picking the most interview-worthy piece of evidence a project already contains (a named technology, a named concept, a stated metric, an explicit tradeoff) and phrasing it as a topic. Milestones 1-3 now deterministically extract exactly that evidence:

- `ProjectParser.technologies` — deterministic gazetteer/regex extraction, already available.
- `ProjectParser.concepts` — KeyBERT-proposed, gazetteer-filtered; bounded and reproducible given fixed model weights (Milestone 3's own framing), not open-ended.
- `ProjectParser.summary` — verbatim extracted text, available for regex-based metric/comparison detection.
- The discarded `had_labeled_line` signal (an explicit "Tech:"/"Stack:" line) — a strong, currently-unused precondition signal, **recomputed independently inside `seed_synthesis.py` (Section 3.1, resolved)**, not threaded out of `ProjectParser`.

So the question is no longer "can a deterministic engine invent a good interview question" (no) — it's "does generating a good interview question actually require invention" (no, not if the seed only ever names things the project's own evidence already contains). This directly extends Milestone 3's conclusion (nothing in the schema turned out to be genuinely impossible without an LLM) rather than contradicting it: `interview_seeds` was the one field that looked like an exception, and closer inspection shows it isn't one, provided the generator is restricted to *selecting and phrasing evidence*, never *inferring unstated facts*.

**Where genuine synthesis-flavored judgment remains** (and is handled by explicit, bounded rules in Section 3, not by an LLM): *which* piece of evidence is most interview-worthy, and *how much* corroboration is required before a comparative/tradeoff phrasing is allowed. Those are heuristic ranking and precondition decisions — the same kind of judgment `Confidence` scoring already makes elsewhere in the engine — not open-ended text generation.

---

## 2. Field-by-field classification

`interview_seeds` is a single field (`list[str]`), but each seed is produced by one of a small set of template families, each grounded in a specific evidence type. Classifying by template family (not by an artificial per-field breakdown, since there is only one field) is the meaningful unit:

| Template family | Evidence it consumes | Classification | Why |
|---|---|---|---|
| **Tech-probe** ("Why did you use `{tech}` in this project?" / "Walk me through how you used `{tech}`.") | `technologies[]` (deterministic gazetteer match) | **Deterministic extraction + fixed template** | The technology name is extracted deterministically; the template wraps it in fixed phrasing with zero inference. |
| **Concept-probe** ("How did you approach `{concept}` in this project?") | `concepts[]` (KeyBERT-proposed, gazetteer-filtered) | **Heuristic inference + fixed template** | KeyBERT's keyphrase proposal is a statistical (not rule-based) step, same tier Milestone 3 already assigned to concept extraction itself — the seed inherits that tier, it doesn't add a new one. |
| **Metric-probe** ("You mentioned `{metric_phrase}` — how was that measured/achieved?") | Regex-detected digit/percent/metric pattern in `summary` (the same pattern the Validation Layer, Section 8, already specifies for "no measurable outcome detected") | **Deterministic extraction + fixed template** | Pure regex match against already-extracted text; no model involved. |
| **Explicit-tradeoff-probe** ("Why `{tech_a}` over the alternative, given you mentioned {comparison phrase}?") | Regex-detected explicit comparison language ("instead of", "chose X over Y", "migrated from X to Y", "rather than") co-occurring with two gazetteer-matched technologies | **Deterministic extraction + fixed template, gated by a strict precondition** | Both the comparison language and both technology names are extracted deterministically; the template only fires when the resume *itself* states a comparison — it never infers one. See Section 3's anti-hallucination rule for why this template is intentionally rare-firing. |
| **Integration-probe** ("How did `{tech_a}` and `{tech_b}` work together in this project?") | Two co-occurring `technologies[]` entries, no comparison language required | **Heuristic composition** | Combining two already-extracted facts into one templated question is a small compositional step above pure lookup, but every noun in the output is still verbatim extracted evidence — no new claim is introduced. |
| **Generic fallback ("Tell me about this project.")** | none | **Explicitly excluded — never generated** | This is exactly the "weak/generic seed" the permanent graceful-degradation rule forbids. Not a classification tier; a rejected option. |

**No template family requires an LLM.** The single hardest sub-case — deciding whether a "tradeoff" framing is honest — is resolved by making that template's precondition strict enough that it simply doesn't fire without explicit textual evidence (Section 3), rather than by reaching for inference. This is the concrete mechanism that answers Question 1: the field is reclassified from "genuinely requires an LLM" to "deterministic extraction + heuristic composition," with the one previously-scary sub-case (tradeoffs) handled by refusing to guess rather than by gaining the ability to guess safely.

---

## 3. Deterministic algorithm

### 3.1 Evidence sources (all already produced by frozen Milestone 3 code — nothing here modifies `ProjectParser`)

- `ProjectEntry.technologies: list[str]` (`project_parser.py:_extract_technologies`)
- `ProjectEntry.concepts: list[str]` (`project_parser.py:_extract_concepts`)
- `ProjectEntry.summary: str` (verbatim body text, `project_parser.py`)
- **`had_labeled_line: bool`** — the same "Tech:"/"Stack:"/"Built with:" label detection `ProjectParser._extract_technologies` already performs internally (`project_parser.py:67-98`), but there it's a local variable that's silently discarded (never propagated past the tuple it's computed into). **Resolved (approved): `seed_synthesis.py` recomputes this signal independently**, via its own copy of the same small regex check, applied to the project's already-extracted `summary`/body text. `ProjectParser` is not modified, no internal field is threaded out of it, and no new field is added to `ParserResult` or the entity dict. This is a deliberate, accepted small duplication (one regex pattern, two modules) in exchange for a hard module-boundary guarantee: `seed_synthesis.py` reads only the same public shape every other Cross-Reference/downstream consumer already reads (`ProjectEntry`'s `title`/`summary`/`technologies`/`concepts`), nothing internal to M3's parser. This mirrors the existing precedent in the codebase of accepted small duplication for boundary-safety (Section 4.3 of the main doc: `sections.py`'s own line-grouping is a deliberately separate implementation from `layout.py`'s, "accepted duplication rather than a shared refactor," because M1 is frozen).

### 3.2 Combining projects, technologies, experience, and domains

- **Scope is per-project, matching the schema**: `interview_seeds` lives on `ProjectEntry`, not on `ExperienceEntry` or at the profile level, so synthesis runs once per project, using only that project's own `technologies`/`concepts`/`summary`. This mirrors `TechnicalTopic`'s existing groundedness rule (Section 2 above; every seed must trace to a single project's own evidence, never a blend across projects).
- **Experience and predicted_domain are deliberately NOT inputs to seed content** in this design. Precedent: `topic_pool.py` already keeps `PROJECT_DEEP_DIVE` (from `interview_seeds`) and experience-derived questions as separate `QuestionCategory` families with independent grounding (`project_grounding` vs. `experience_grounding`, `topic_pool.py:161-176`) — nothing today blends a project's seed with an unrelated experience entry, and introducing that blend would be new cross-entity inference the current schema and consumer code doesn't ask for. `predicted_domain` could in principle bias template *selection* (e.g. favor concept-probes over integration-probes for a "Data Science" domain), but this is deliberately out of scope for Milestone 4/5 — it's an unrequested refinement (see CLAUDE.md guidance against speculative scope) and would make seed generation depend on a soft, sometimes-wrong field (`predicted_domain` is itself only "soft," Section 1.2 of the main doc). If wanted later, it is a template-*ranking* weight, not a template-*content* change, and can be added without touching the core algorithm below.
- **Combining technologies with each other** (Integration-probe) and **technologies with explicit comparison language** (Explicit-tradeoff-probe) are the only two forms of "combination" in this design, both described in Section 2's table and both operating strictly within one project's own evidence.

### 3.3 Algorithm, precisely

```
for each ProjectEntry already produced by ProjectParser (M3, frozen):
    candidates = []

    # Metric-probe (highest priority: concrete, hardest to fabricate accidentally)
    for match in METRIC_PATTERN.finditer(summary):          # e.g. \d+%|\d+x|reduced|increased|saved \d+
        candidates.append(Seed(family="metric_probe",
                                text=f"You mentioned {match.group(0)!r} — how was that measured or achieved?",
                                evidence=[match.group(0)], confidence_base=0.85))

    # Explicit-tradeoff-probe (strict precondition: comparison language AND 2 techs)
    comparison = COMPARISON_PATTERN.search(summary)          # "instead of", "chose X over Y", "migrated from...to", "rather than"
    if comparison and len(technologies) >= 2:
        tech_a, tech_b = pick_two_nearest_to(comparison.span(), technologies)
        candidates.append(Seed(family="tradeoff_probe",
                                text=f"Why {tech_a} over the alternative, given you mentioned "
                                     f"{comparison.group(0)!r}?",
                                evidence=[tech_a, tech_b, comparison.group(0)], confidence_base=0.8))

    # Tech-probe (one per extracted technology, capped)
    for tech in technologies[:TECH_PROBE_CAP]:
        candidates.append(Seed(family="tech_probe",
                                text=f"Why did you use {tech} in this project?",
                                evidence=[tech],
                                confidence_base=0.75 if had_labeled_line else 0.6))

    # Integration-probe (co-occurring pairs, capped, only if >=2 techs and no tradeoff already covering them)
    for tech_a, tech_b in top_pairs(technologies, k=INTEGRATION_PROBE_CAP):
        candidates.append(Seed(family="integration_probe",
                                text=f"How did {tech_a} and {tech_b} work together in this project?",
                                evidence=[tech_a, tech_b], confidence_base=0.55))

    # Concept-probe (one per matched concept, capped)
    for concept in concepts[:CONCEPT_PROBE_CAP]:
        candidates.append(Seed(family="concept_probe",
                                text=f"How did you approach {concept.lower()} in this project?",
                                evidence=[concept], confidence_base=0.5))

    # Rank: metric > tradeoff > tech > integration > concept, ties broken by confidence_base desc
    # Dedup: never emit two seeds whose evidence sets share a technology/concept already used by
    #        a higher-ranked seed (prevents "Why did you use Redis?" AND "How did Redis and Kafka
    #        work together?" both firing on a thin project and crowding out variety)
    # Cap: keep top MAX_SEEDS_PER_PROJECT (proposed: 4, matching topic_pool's existing per-category
    #      restraint, e.g. technical_topics' 3-8 cap)
    # Graceful degradation: if candidates == [], interview_seeds = [] -- no fallback tier, ever.

    project.interview_seeds = [c.text for c in ranked_deduped_capped_candidates]
```

`METRIC_PATTERN` and `COMPARISON_PATTERN` are new, small, reviewable regex constants (same category of artifact as `dates.py`'s month alternation or `_TECH_LABEL_PATTERN`) — not a new gazetteer, since comparison/metric language is syntactic, not a closed vocabulary.

### 3.4 Preserving traceability

Every `Seed` carries `evidence: list[str]` — the exact extracted strings (technology names, concept names, regex match text) it was built from, in the same spirit as `TechnicalTopic.evidence` and `Confidence.reasons`. Two traceability layers, matching the architecture's existing two-tier pattern (Section 3.2 of the main doc: public schema stays thin, richer data lives on `PipelineTrace`):

1. **Public schema** — unchanged: `interview_seeds: list[str]`, exactly as today. No new field, no schema migration, no downstream consumer change (`topic_pool.py:190-207` keeps working unmodified).
2. **Internal** — each `Seed` also produces a `Confidence(score=confidence_base × section/project confidence, reasons=[...])`, attached the same way `ProjectParser` already attaches one `Confidence` per project (Section 3.2 of the main doc's `+`/`-` convention: `"+metric_pattern_matched:'40% latency reduction'"`, `"+technology_gazetteer_match:Redis"`, `"-tradeoff_precondition_not_met"` for families that didn't fire). This retains full per-seed explainability on `PipelineTrace` without touching the public `CandidateProfile` shape — consistent with how per-entity confidence already works for every other M1-3 entity today.

Because every seed's `text` is built by string-interpolating extracted evidence into a fixed template (never by asking a model to produce free text), traceability is structural, not inferred after the fact: you can always regenerate `evidence` from `text` by parsing which template fired, but the design stores `evidence` explicitly anyway so a future auditor/renderer doesn't have to reverse-engineer it.

### 3.5 Avoiding hallucinated topics

Three structural guarantees, not just conventions:

1. **Closed vocabulary in, closed vocabulary out.** Every noun phrase (`{tech}`, `{concept}`, `{metric_phrase}`, `{comparison phrase}`) that appears in a generated seed is copied verbatim from `technologies`/`concepts`/`summary` — the templates have no free-text slot filled by inference. This is the same guarantee `TechnicalTopic.evidence` already enforces for `technical_topics` (Section 2, "3.2" above), extended to `interview_seeds`.
2. **Preconditions gate synthesis-flavored templates, don't relax them.** The one template capable of implying something not literally printed (Explicit-tradeoff-probe, which frames a "why X over Y" question) only fires when the resume *itself* contains comparison language — the design does not infer a tradeoff from "the project used both Postgres and Redis" alone (that's Integration-probe's job, phrased as "how did they work together," not "why did you choose one over the other"). This directly encodes the Section 11 risk ("narrower, more predictable phrasing... a net win for determinism/traceability") as an enforced precondition, not just an accepted tradeoff.
3. **Zero-candidate paths produce zero seeds, structurally, not via a check.** There is no "if nothing else, emit a generic seed" branch anywhere in the algorithm (Section 3.3) — the permanent graceful-degradation rule (Section 10 Decision 3 of the main doc) is satisfied by the candidate list simply being empty when no precondition is met, the same way `ProjectParser` today returns `entities=[]` rather than a placeholder project when no entries cluster.

---

## 4. Comparison against the Gemini implementation

**Gains:**
- **Zero hallucination risk by construction** — every seed noun is copied from already-extracted, already-confidence-scored evidence; Gemini today can (and per the architecture audit, is trusted not to, but isn't structurally prevented from) invent a plausible-sounding technology or framing not actually in the resume.
- **Full traceability** — every seed carries `evidence`/`Confidence.reasons`, viewable on `PipelineTrace`; Gemini's seeds today carry no explanation at all.
- **Determinism** — identical resume in, identical seeds out, every run; directly enables the golden-corpus snapshot testing strategy (Section 9 of the main doc) for this field for the first time.
- **Zero marginal cost/latency, no external dependency** — consistent with the project's core motivation (Section 1.1 of the main doc).
- **Consistency with the permanent graceful-degradation rule** — sparse projects get fewer/zero seeds transparently, rather than Gemini's tendency (implicit in any LLM generation task) to always produce *something* plausible-sounding regardless of evidence thinness.

**Losses:**
- **Phrasing variety.** Templates produce structurally similar questions across many projects/candidates ("Why did you use X in this project?" recurring verbatim with only `X` changing). Gemini's phrasing is more varied and can sound more like a real interviewer improvising. This is the Section 11 risk restated, now with a concrete mitigation (multiple template families with different framings, Section 3.3) rather than a single template, which narrows but does not eliminate the gap.
- **Depth on implicit tradeoffs.** Gemini can infer an unstated design tension ("this project used both a relational DB and a cache — I bet there's a consistency story here") from world knowledge; the deterministic design deliberately refuses to do this (Section 3.5, guarantee 2) unless the resume states it explicitly. This is an intentional, accepted loss, not an oversight — the alternative (inferring tradeoffs) is exactly the hallucination risk the whole redesign exists to remove.
- **Concept vocabulary is closed.** `concept_gazetteer.py`'s ~60 entries will miss a genuinely novel or niche technical concept a project demonstrates but the gazetteer doesn't yet list; Gemini's vocabulary is effectively unbounded. Mitigated the same way as every other gazetteer in this engine (Section 11 of the main doc: "a transparent, reviewable-diff cost... versus today's opaque cost").

**Where an optional LLM enhancement would still carry real value:** none of the above losses are severe enough to justify reintroducing an LLM into the *production* path, per the project's stated goal of fully removing the Gemini dependency (Section 10 Decision 5/Milestone 7 of the main doc, and the standing constraint "prefer deterministic, explainable parsing over LLM inference whenever possible"). The one plausible, narrow case — a cosmetic *phrasing rewrite* pass that varies surface wording without touching which facts are referenced — is addressed as a strictly optional, isolated enhancement in Section 5, not built now.

---

## 5. Isolating any remaining LLM-shaped responsibility

**Recommendation: do not build this now.** No part of the core seed-synthesis algorithm (Section 3) requires an LLM, so there is nothing that must be isolated for Milestone 4/5 to ship. This section documents the one bounded case identified in Section 4 so it's designed-for rather than foreclosed, per the instruction to isolate anything that "truly still benefits" from an LLM:

- **Scope, if ever built**: a purely cosmetic *post-processing* function, `paraphrase_seeds(seeds: list[str]) -> list[str]`, called *after* Section 3's algorithm has already produced the final, evidence-grounded, capped seed list for a project.
- **Hard constraints, mirroring the existing Shadow Mode discipline (Section 2.2 of the main doc) exactly**:
  - Input and output must have the same length and the same 1:1 evidence grounding — the paraphraser may reword `"Why did you use Redis in this project?"` into `"What led you to Redis here?"`, but may never introduce a technology/concept/metric string that wasn't already in the input seed's text.
  - Never runs when the deterministic list is empty — an empty list in, empty list out; the paraphraser is never a path by which a project with zero grounded evidence acquires a seed.
  - Off by default, feature-flagged, never in the code path a real user request reaches unless explicitly enabled — same posture as Shadow Mode.
  - If it fails or is disabled, the deterministic seeds (Section 3) are what ships — never a silent fallback to fabricated content, never a hard failure of profile generation.
- **Why isolated this way**: this keeps the core parser (Sections 3-3.5) fully deterministic, explainable, and testable on its own, with the optional LLM touch confined to a single, narrow, factually-inert function that cannot affect correctness — only surface phrasing. This is the concrete mechanism requested by "isolate that responsibility so the core parser remains deterministic."

This is a documented option, not a Milestone 4/5 deliverable — building it is out of scope unless separately requested, consistent with not designing for hypothetical future requirements beyond what's needed to answer the design-review question.

---

## 6. Final Milestone 4/5 architecture and pipeline integration

### 6.1 What Milestone 4 (this design pass) delivers

Per the original roadmap's own scope for Milestone 4 (Section 10 of the main doc: "build ~10-15 real project fixtures... prototype the template bank... qualitatively evaluate seed quality... finalize template preconditions and per-seed confidence mechanism"), Milestone 4 itself remains **design + prototyping, not pipeline wiring**:

- This document (the finalized template bank: Section 2's family table, Section 3.3's algorithm, Section 3.5's anti-hallucination guarantees).
- A small standalone fixture set (10-15 projects spanning rich-evidence to sparse-evidence) and a prototype script exercising Section 3.3 against them *outside* the pipeline (e.g. a `devtools/` script, mirroring `devtools/golden_corpus_report.py`'s existing precedent of pipeline-adjacent, non-production tooling) — to qualitatively validate seed quality and confirm the graceful-degradation rule holds on genuinely sparse projects, before any of this becomes production parser code.
- No change to `pipeline.py`, `interfaces.py`, or any Milestone 0-3 file in this milestone.

### 6.2 What Milestone 5 (implementation, separately approved) would deliver

Consistent with the original roadmap (Milestone 5 = "remaining parsers + Cross-Reference Pass... interview-seed synthesis implemented per Milestone 4's finalized design"):

- A new module, `resume_engine/seed_synthesis.py` — not a new `EntityParser`. It doesn't implement the `EntityParser` protocol (Section 3.3 of the main doc) because it doesn't read `Section`/`DocumentModel` inputs; it reads already-parsed `ProjectEntry` dicts, which is exactly the Cross-Reference Pass's defined role (Section 4.5 of the main doc: "the one stage allowed to reason across sections... synthesize `interview_seeds`... since seed templates need a project's technologies *and* the shared gazetteer's concept tags together"). This confirms the seed synthesizer belongs at Stage 5, exactly where the original architecture already placed it — no new pipeline stage, no reordering.
- `pipeline.py`'s Cross-Reference stage (currently `cross_reference.py`, a stub) calls `seed_synthesis.synthesize(project_entities) -> list[list[str]]` and writes the result back onto each project dict's `interview_seeds` field, the same "annotate, don't add new top-level fields" pattern Section 4.5 already specifies for demonstrated-skills tagging.
- `Confidence`/`Observation` objects produced per Section 3.4 are retained on the relevant `StageTrace` (Cross-Reference), following the same `trace: PipelineTrace | None = None` convention every other stage already uses (Section 6.2 of the main doc) — no new observability mechanism needed.

### 6.3 Non-invasiveness to Milestones 0-3 (explicit check, since freezing is a standing constraint)

| File | Touched? |
|---|---|
| `extractor.py`, `layout.py`, `sections.py`, `document_model.py` (M1/M2) | **No.** |
| `interfaces.py` | **No** — `EntityParser` protocol unchanged; seed synthesis doesn't implement it. |
| `parsers/contact_parser.py`, `parsers/experience_parser.py` | **No.** |
| `parsers/project_parser.py` | **No (resolved, approved).** `seed_synthesis.py` independently recomputes the labeled-line signal (Section 3.1) rather than threading a new internal field through M3's parser — M3 is genuinely untouched, at the accepted cost of one small, harmless duplication. |
| `factory.py` | **Additive only** — registers the new Cross-Reference implementation where it currently raises `NotImplementedError`; no change to the three M3 parser registrations or their conformance checks. |
| `pipeline.py` | **Additive only** — the Cross-Reference stage call site already exists in the 8-stage skeleton (Milestone 0); this fills in a stub, it doesn't restructure the pipeline. |
| Golden corpus M1/M2/M3 fixtures (`expected_layout.json`, `expected_sections.json`, `expected_entities.json`) | **No** — new fixtures/expectations are additive (a new `expected_cross_reference.json` or similar), existing ones stay green. |

No frozen file's *behavior* changes. The one previously-open question (Section 3.1) is resolved: `project_parser.py` is not modified; `seed_synthesis.py` recomputes the labeled-line signal independently.

---

## 7. Summary of what's approved so far

1. **Reclassification accepted**: `interview_seeds` moves from "requires an LLM" to "deterministic extraction + heuristic composition + fixed templates" (Sections 1-2).
2. **Template bank** (Section 2 table, Section 3.3 algorithm) — five families: metric-probe, explicit-tradeoff-probe, tech-probe, integration-probe, concept-probe, ranked in that priority order, capped, deduped.
3. **Anti-hallucination guarantees** (Section 3.5) — closed-vocabulary templates, strict tradeoff precondition, structural zero-candidate-means-zero-seeds.
4. **Traceability mechanism** (Section 3.4) — public schema unchanged; per-seed `Confidence`/`evidence` retained on `PipelineTrace` only, matching the existing two-tier pattern.
5. **LLM isolation** (Section 5) — documented as a future-optional, strictly cosmetic, feature-flagged paraphrase layer; not built in Milestone 4/5.
6. **Pipeline placement** (Section 6) — new `seed_synthesis.py` module implementing the Cross-Reference stage (Stage 5, as originally designed), no new `EntityParser`.
7. **M3 module boundary** (Section 3.1, Section 6.3) — `seed_synthesis.py` recomputes any signals it needs independently; `ProjectParser` and all other Milestone 0-3 files are completely untouched, accepting a small amount of duplicated computation in exchange for a hard boundary guarantee.

No code has been written against this document. See Section 8 below for the evaluation strategy that must be satisfied before Milestone 5 implementation begins.

---

## 8. Evaluation Strategy

This section defines how seed quality is judged and what "done" means for Milestone 4, before any implementation (Milestone 5) starts. It follows the same discipline the project has applied to every prior milestone: a validation pass with concrete, checkable criteria, not a subjective "looks good" sign-off (see `Milestone1_ValidationReport.md`/`Milestone2_ValidationReport.md`/`Milestone3_ValidationReport.md` for precedent — this section is designed to produce a `Milestone4_ValidationReport.md` of the same shape once the fixture pass runs).

### 8.1 What makes a high-quality interview seed

A seed is high-quality if and only if it satisfies all of the following, each directly checkable against the `ProjectEntry` it was generated from — no subjective judgment call that can't be reduced to a rule:

1. **Grounded**: every noun phrase in the seed text (`{tech}`, `{concept}`, `{metric_phrase}`, `{comparison phrase}`) appears verbatim in that project's own `technologies`, `concepts`, or `summary`. Mechanically checkable: extract the interpolated span(s) from the rendered text and confirm substring membership in the source fields.
2. **Specific, not generic**: the seed names at least one concrete technology, concept, or metric — never a bare "Tell me about this project" / "What was your role?" style question with no named evidence. Mechanically checkable: every template in the bank (Section 3.3) has a mandatory interpolation slot; there is no template without one, so this is enforced by construction, and the check is "did a candidate ever bypass a template" (it shouldn't be possible, but the fixture pass verifies it empirically too).
3. **Answerable from the resume's own claim, not requiring the candidate to defend an unstated framing**: the tradeoff-probe family only fires when the resume itself contains comparison language (Section 3.5, guarantee 2) — checkable by confirming every emitted tradeoff-probe seed's `evidence` includes a literal comparison-pattern match, not just two co-occurring technologies.
4. **Non-redundant within a project**: no two seeds for the same project share their full evidence set (the dedup rule in Section 3.3) — checkable directly from the ranked/deduped candidate list.
5. **Proportionate to evidence depth**: a project with rich evidence (multiple technologies, a stated metric, explicit comparison language) should produce more/higher-ranked seeds than a thin project (one technology, no metrics) — checkable by confirming seed count and family mix correlate with evidence richness across the fixture set (Section 8.4), not by eyeballing any single seed in isolation.

### 8.2 Failure modes under test

Each maps to a specific fixture category in the prototyping pass (Section 6.1) and a specific automatic check:

| Failure mode | What it would look like | How the fixture pass catches it |
|---|---|---|
| **Hallucinated evidence** | A seed names a technology/concept/metric not present in the project's own `technologies`/`concepts`/`summary`. | Automatic: substring-membership check (8.1 rule 1) on every generated seed against its source project, for every fixture — a single failure here is a hard block, not a quality score deduction. |
| **Generic/fabricated fallback seed** | A project with zero extracted evidence still produces a seed like "Tell me about this project." | Automatic: assert `interview_seeds == []` for every fixture where `technologies == [] and concepts == [] and no metric/comparison match in summary` — the sparse-evidence fixtures (Section 8.4) exist specifically to exercise this path. |
| **False tradeoff framing** | A "why X over Y" seed fires when the resume never actually stated a comparison (e.g. two technologies merely co-occur). | Automatic: assert every tradeoff-probe seed's `evidence` contains a literal `COMPARISON_PATTERN` match; a fixture with two co-occurring but never-contrasted technologies must produce an integration-probe, never a tradeoff-probe, for that pair. |
| **Duplicate/near-duplicate seeds** | Two seeds effectively ask the same question with different wording (e.g. a tech-probe and an integration-probe both spotlighting the same single technology). | See Section 8.5 (dedicated duplicate-detection strategy). |
| **Evidence starvation from over-eager capping** | `MAX_SEEDS_PER_PROJECT`/per-family caps discard genuinely distinct, high-value evidence (e.g. a rich project with 3 metrics only surfaces 1 because tech-probes crowded the cap). | Manual, fixture-pass review: for the "rich evidence" fixtures specifically, confirm the ranking priority (metric > tradeoff > tech > integration > concept, Section 3.3) actually preserves the most valuable evidence under the cap, not an artifact of extraction order. |
| **Concept-probe noise** | KeyBERT/gazetteer proposes a concept only weakly related to the project, producing an off-target seed. | Inherited from Milestone 3's own concept-extraction validation (already-accepted risk tier, Section 2 table) — not re-litigated here; if it surfaces during the fixture pass, it's logged as an observation but doesn't block Milestone 4, since it's a Milestone 3 extraction-quality question, not a seed-synthesis one. |
| **Boundary violation** | Implementation accidentally imports from or mutates `project_parser.py`/`ProjectParser` internals. | Automatic: a `seed_synthesis.py`-scoped import-boundary test asserting the module's only dependency on M3 output is the public `ProjectEntry` dict shape — no import of `project_parser` internals, no reliance on parser-internal state. |

### 8.3 How the Golden Corpus validates seed quality

Extends the existing Golden Corpus mechanism (Section 9 of the main doc) rather than inventing a parallel one:

- **New fixture layer**: `expected_interview_seeds.json` per relevant golden-corpus project, added alongside the existing `expected_entities.json` (Milestone 3's gate) — same "each fixture is annotated well enough that a failure tells you what kind of resume regressed" philosophy (main doc Section "Golden Corpus philosophy").
- **Reuses existing fixtures where possible, adds new ones where the existing set doesn't cover the evidence-richness spectrum needed**: `full_entity_resume_pdf` (Milestone 3) already has multi-project, multi-technology content and becomes the primary "rich evidence" regression fixture; `single_entry_sections_pdf` covers the sparse/edge case for entry clustering already, but Milestone 4 needs its own dedicated sparse-*evidence* fixtures (a project with a title but zero technologies/concepts/metrics) — a clustering edge case and an evidence-richness edge case are different things and shouldn't be conflated onto the same fixture.
- **Snapshot assertion**: exact `interview_seeds` list per project, committed as the expected output, per the project's established golden-snapshot pattern (main doc Section 9) — a regression is a diff against a committed, human-reviewed expected list, not a heuristic quality score at test time.
- **Golden-corpus fixtures are also where 8.1's mechanical checks run in aggregate**: the fixture-pass script (Section 6.1) runs the grounding/genericity/tradeoff-precondition/dedup checks (8.1, 8.2) across every fixture project automatically, and the results (pass/fail per check per fixture) are what the eventual `Milestone4_ValidationReport.md` reports — not a manual per-seed read-through.

### 8.4 Expected seed counts per project

Derived directly from the cap/ranking design in Section 3.3, stated as explicit, testable expectations rather than a vague "a few seeds":

| Evidence profile | Expected `len(interview_seeds)` | Rationale |
|---|---|---|
| Zero evidence (no technologies, no concepts, no metric/comparison match) | **Exactly 0** | Section 3.5 guarantee 3 — the graceful-degradation rule, tested as a hard assertion, not a range. |
| Sparse (1 technology, no concepts, no metric) | **1** | Exactly one tech-probe fires; no other family has a satisfied precondition. |
| Moderate (2-3 technologies, 1 concept, no metric/comparison) | **3-4** | Tech-probes (capped) + one concept-probe + possibly one integration-probe, before the overall cap engages. |
| Rich (3+ technologies, 1+ concepts, a stated metric, explicit comparison language) | **`MAX_SEEDS_PER_PROJECT` (proposed: 4)**, always led by the metric-probe and/or tradeoff-probe per the ranking order | The cap is expected to bind here — this is the fixture category that tests capping/ranking correctness (8.2's "evidence starvation" failure mode), not just presence/absence. |

`MAX_SEEDS_PER_PROJECT = 4` and per-family caps (`TECH_PROBE_CAP`, `INTEGRATION_PROBE_CAP`, `CONCEPT_PROBE_CAP`) are proposed starting values, explicitly flagged — consistent with how `MIN_BAND_BALANCE_RATIO`/`MAX_PITCH_RATIO`/`EMBEDDING_SIMILARITY_FLOOR` were introduced in earlier milestones — as **validation-derived, tunable parameters**, to be confirmed or adjusted once the fixture pass (Section 8.3) runs against real evidence-profile examples, not treated as final on paper alone.

### 8.5 Duplicate-detection strategy

Two layers, matching the two ways a duplicate can occur:

1. **Exact evidence-set duplicates (prevented by construction, Section 3.3)**: the ranking/dedup step already refuses to emit a second seed whose evidence set overlaps a higher-ranked seed already selected (e.g. a tech-probe for `Redis` blocks a later integration-probe that would also cite `Redis`). This is not a post-hoc filter — it's part of the candidate-selection loop itself, so "duplicate" here means "shares a named entity with an already-selected seed," checked via simple set-intersection on each candidate's `evidence` list against the union of already-selected seeds' evidence, before a candidate is accepted.
2. **Near-duplicate phrasing across different evidence (caught by fixture-pass review, not a runtime algorithm)**: e.g. a tech-probe on `PostgreSQL` and a separate tech-probe on `MySQL` in the same project would pass the evidence-overlap check (different technologies) but could read as repetitive if a project happens to list many similar-role technologies. This is explicitly **not** solved by a semantic-similarity check at runtime (that would reintroduce an ML dependency into a path designed to stay simple, for a cosmetic concern) — instead, the per-family cap (`TECH_PROBE_CAP`, proposed 2) is the mitigation: even a project with 5 databases listed only ever gets 2 tech-probes, so structural repetition is bounded by the cap, not detected and removed after the fact. The fixture pass's "rich evidence" category (8.4) is where this is manually reviewed for read-worthiness, since "reads as repetitive" is a phrasing-quality judgment, not a factual-correctness one, and phrasing quality is explicitly the accepted, documented tradeoff from Section 4, not a bug to engineer around.

### 8.6 Evidence Coverage Accounting

A separate concern from Sections 8.1-8.5: those measure whether the seeds that *were* generated are correct; this measures how completely the generator used the evidence that was *available*. A generator can pass every 8.1-8.5 check (grounded, non-generic, honestly-framed, deduped) while still quietly ignoring most of a rich project's evidence — that's not a correctness bug, but it is a completeness gap worth measuring on purpose, not by accident.

**Strictly a debug/validation artifact — not a schema change.** This accounting model is never constructed in the production request path unless a trace is already active, is never attached to `CandidateProfile`, and has no public-schema footprint whatsoever. It follows the identical zero-cost-when-inactive discipline `PipelineTrace` already established (main doc Section 6.2: "When `None`... genuinely zero behavioral or performance difference"): the accounting record is built only when `seed_synthesis.py` is called with a trace object present (fixture-pass tooling, golden-corpus snapshot tests, and any future debug endpoint), never on a real user's request unless a developer has explicitly turned tracing on for that run — the same posture as every other piece of `Confidence`/`Observation` explainability data already in the engine, and the same hard boundary Shadow Mode observes for Gemini output (main doc Section 2.2): a debug-only artifact that can never leak into what a real user's profile contains.

**Data model** (internal to `seed_synthesis.py` / the validation tooling — not part of `interfaces.py`'s public dataclasses, though structurally it is a sibling of `Confidence`/`Observation` in spirit):

```python
@dataclass
class EvidenceItem:
    kind: Literal["technology", "concept", "metric", "comparison_phrase"]
    value: str                     # the exact extracted string

@dataclass
class UnusedEvidenceItem:
    item: EvidenceItem
    reason: str                    # closed vocabulary, see below

@dataclass
class EvidenceAccounting:
    project_title: str
    discovered: list[EvidenceItem]         # everything found, before any seed is built
    consumed: dict[str, list[EvidenceItem]]  # seed_text -> evidence items that seed used
    unused: list[UnusedEvidenceItem]         # discovered minus consumed, each with a reason
```

- **Evidence discovered**: the full, pre-selection inventory for the project — every gazetteer-matched technology, every gazetteer-matched concept, every `METRIC_PATTERN` match, every `COMPARISON_PATTERN` match (Section 3.3) — computed once per project, independent of which templates end up firing.
- **Evidence consumed**: the union of every candidate seed's `evidence` list (Section 3.4) that survived ranking/dedup/capping into the final `interview_seeds` output, keyed by which seed consumed it — this is the same `evidence` data Section 3.4 already produces for traceability, simply aggregated and cross-referenced against `discovered` rather than a new extraction pass.
- **Evidence intentionally left unused**: `discovered - consumed`, where every single item **must** carry one of a closed set of reason codes, not a free-text explanation:
  - `below_cap:<family>` — a valid candidate was built (e.g. a fourth tech-probe) but the family or overall cap (Section 8.4) was already full.
  - `duplicate_of:<evidence_value>` — excluded by the Section 8.5 evidence-overlap dedup rule because a higher-ranked seed already claimed it.
  - `precondition_not_met:<family>` — evidence that could only feed a template whose precondition didn't hold (e.g. a technology that only had one comparison-language partner, so tradeoff-probe's "two technologies near the comparison" precondition failed even though comparison language existed).
  - `lower_priority_unselected` — a candidate existed and was valid, but ranking (Section 3.3's family priority order) simply never reached it before the cap closed, and it doesn't fit any of the three more specific reasons above.

**Where it's produced and reported**: `seed_synthesis.py` builds one `EvidenceAccounting` record per project when tracing is active, attached to the Cross-Reference `StageTrace.metadata` under a namespaced key (e.g. `metadata["evidence_accounting"]`), following the exact mechanism Section 6.2 of the main doc already describes for any stage's optional trace data. The fixture-pass script (Section 6.1) aggregates these into a per-fixture, per-project coverage table in `Milestone4_ValidationReport.md` — reusing the report format precedent from `Milestone1_ValidationReport.md`/`Milestone2_ValidationReport.md`/`Milestone3_ValidationReport.md`, not inventing a new report shape.

**Acceptance criteria specific to evidence coverage** (checked automatically across the full fixture set, Section 8.3):

1. **No hallucinated evidence**: `consumed ⊆ discovered` for every project, every fixture — i.e. no seed's evidence item is absent from that project's own `discovered` inventory. This is the accounting-model restatement of the 8.1/8.2 grounding check, now verified via the accounting record itself rather than only via the seed text, giving two independent code paths to the same guarantee. Hard gate, zero tolerance, consistent with every other hallucination check in this document.
2. **No duplicate evidence consumption**: no single `EvidenceItem` appears in more than one seed's `consumed` entry, for any project, any fixture — the accounting-level verification of the Section 8.5 dedup rule. Hard gate.
3. **Reasonable utilization of available evidence**: utilization is measured per evidence kind, not as one blended percentage, because the ranking order (Section 3.3) makes some kinds structurally higher-priority than others:
   - **Metrics and comparison phrases** (the two highest-priority families when present): expected utilization **100%** when the corresponding precondition is met — i.e. every discovered metric produces a metric-probe, every discovered valid comparison produces a tradeoff-probe, on the rich-evidence fixtures. A shortfall here is a ranking/cap bug, not an accepted tradeoff (these families rank first specifically so they're never starved).
   - **Technologies**: expected utilization **≥ `TECH_PROBE_CAP` / len(technologies)** for projects with more technologies than the cap (i.e. utilization is expected to be partial by design once a project has more technologies than the cap allows, and every technology past the cap must resolve to a `below_cap` or `duplicate_of` reason, never an unexplained gap).
   - **Concepts**: expected utilization **≥ `CONCEPT_PROBE_CAP` / len(concepts)**, same capped-by-design logic as technologies.
   - These thresholds are proposed, validation-derived starting points (same tunable-parameter status as `MAX_SEEDS_PER_PROJECT` itself, Section 8.4) — confirmed or adjusted once the fixture pass produces real numbers, not asserted as final here.
4. **Unused evidence is fully explainable**: **100% of `unused` items carry one of the four closed-vocabulary reason codes above** — an item with no assignable reason code is itself a bug in the accounting/ranking logic (it means some evidence silently fell through a gap the algorithm doesn't know how to name), not a passable "unknown" state. This is a hard gate, deliberately stricter than the utilization percentages in point 3, because *unexplained* is a different and worse failure than *unused-but-explained*.

### 8.7 Objective acceptance criteria for Milestone 4

Milestone 4 (design + fixture prototyping, per Section 6.1's scope) is complete when **all** of the following hold, each directly verifiable, matching the pass/fail rigor of `Milestone3_ValidationReport.md`:

1. **This design document** (Sections 1-8) reviewed and approved — **done as of this update**.
2. **10-15 project fixtures** built spanning all four evidence profiles in Section 8.4 (at minimum: 2+ zero-evidence, 2+ sparse, 3+ moderate, 3+ rich, plus at least one fixture specifically constructed to exercise the false-tradeoff-framing failure mode from Section 8.2).
3. **Zero hallucination-check failures**: the 8.1/8.2 grounding check passes on 100% of generated seeds across all fixtures — this is a hard gate, not a target percentage, consistent with "never fabricate" being a permanent rule rather than a best-effort goal.
4. **Zero graceful-degradation violations**: every zero-evidence fixture produces exactly `[]`, with no exceptions.
5. **Zero false-tradeoff-framing failures**: the tradeoff-probe family never fires without a literal comparison-pattern match in `evidence`, across all fixtures.
6. **Seed counts match Section 8.4's expected ranges** for every fixture, or any deviation is explicitly justified and the table updated (not silently left inconsistent with observed behavior — same standard applied to `MIN_BAND_BALANCE_RATIO` in Milestone 1).
7. **Zero M0-3 file modifications**: a diff against the Milestone 3 freeze point touches only new files (`seed_synthesis.py` prototype, new fixtures, new devtools script, this document) — confirmed by the import-boundary check in Section 8.2.
8. **Evidence Coverage Accounting's four acceptance criteria (Section 8.6) all pass**: no hallucinated evidence, no duplicate evidence consumption, utilization thresholds met (or explicitly revised with justification), 100% of unused evidence carries a closed-vocabulary reason code.
9. **A written `Milestone4_ValidationReport.md`** summarizing all of the above — including the per-fixture evidence-coverage table from Section 8.6 — matching the precedent of every prior milestone's validation report, produced *before* Milestone 5 implementation begins.

Only once all nine criteria are met does Milestone 5 (actual pipeline wiring per Section 6.2) get proposed for separate approval — consistent with the standing "never combine multiple milestones into one implementation pass" constraint.
