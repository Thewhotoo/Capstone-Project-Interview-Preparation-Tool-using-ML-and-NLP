# Volunteer Pilot Protocol — Real Human Interview-Answer Collection (Design Phase)

**Status: DESIGN ONLY. Nothing in this document has been implemented.** No seed
records, judged labels, rubric, validator, or acceptance thresholds were
touched to produce it. No volunteers have been recruited, no data collected.

**Context:** the public real-data feasibility research (prior session)
concluded that genuine Category-B data (real interview answers grounded in
the *candidate's own* resume/project) is essentially unavailable publicly at
useful scale, while TechQA (IBM) is a small, cleanly-licensed Category-A
supplement. This document designs the internal volunteer pilot that is the
only realistic path to real Category-B data.

---

## 1. Collection protocol — what a volunteer actually provides

The guiding question for every field below was: **is this needed to score
the four dimensions, or is it just "nice to have resume realism"?** Anything
in the second bucket is cut.

### Per-volunteer, collected ONCE
| Field | Purpose | Notes |
|---|---|---|
| `volunteer_id` | Anonymized, generated at intake (e.g. `vol_07`), never the person's name | The only "identity" we retain a mapping for, and only until anonymization is finalized (see §2) |
| `project_title` | Grounding context (maps to `ProjectGrounding.title`) | A short real or lightly-genericized title ("Inventory sync service", not "Acme Corp's proprietary SKU-Sync™") |
| `technologies` | Grounding context (maps to `ProjectGrounding.technologies`) | Short list, e.g. `["Django", "Postgres", "Redis"]` — needed for the grounding-fidelity check and for the judge's context |
| `short_project_description` | Grounding context (maps to `ProjectGrounding.summary`) | 2–4 sentences: what the project *does*, no more. This is what makes the later answers gradeable on Grounding & Ownership — **without this, we cannot tell a grounded answer from a generic one at labeling time** |
| `role/contribution` (optional) | Same purpose, folds into `summary` or a short separate line | Only collect if the volunteer offers it naturally; do not force a formal "my responsibilities were..." section — that reads as resume text, not interview text |

**Explicitly NOT collected:** full resume, employer name (unless the volunteer
volunteers it and it isn't sensitive), job title/dates, team names, internal
system names beyond what's needed to talk about the tech, any credentials.
The project description is a *substitute* for a resume, not a resume excerpt
— it should be written by the volunteer in their own words for this pilot,
not copy-pasted from an actual CV.

### Per-answer, collected for each question a volunteer answers
| Field | Purpose |
|---|---|
| `question_text` | The literal question asked (selected per §3) |
| `answer_text` | The volunteer's natural, typed answer — no length minimum/maximum enforced, no coaching |
| `expected_concepts` (optional, usually empty) | Only set if the question template names one (see §3); otherwise left empty, same convention the seed already uses |
| `collection_batch_id` | e.g. `volunteer_pilot_2026q4` — identifies this whole collection round |
| `session_id` | Which sitting this answer came from (a volunteer might answer in one sitting or two) — distinct from `volunteer_id` so we can tell "same person, different day" apart if that ever matters, but both roll up to the same `volunteer_id` for splitting purposes |
| `collected_at` | ISO8601 timestamp |

**Explicitly NOT collected per-answer:** no "how confident are you in this
answer" self-rating, no "what score do you think this deserves" — this is
exactly the target-quality leakage the task instructs against. Volunteers are
never told what dimension or tier their answer maps to.

### What we deliberately do NOT collect at all
Names, phone numbers, email addresses (a throwaway "volunteer #N" code is
assigned at intake instead — see §2 for how the name↔code mapping itself is
handled), employer-sensitive information, proprietary/confidential code
snippets pasted verbatim, secrets/credentials, or any personal identifier
beyond the anonymized `volunteer_id`.

---

## 2. Consent and privacy

**This is not legal advice — a supervisor/IRB-equivalent (if your program has
one) or your project supervisor should review the consent text before any
volunteer is approached.** What follows is a practical draft suitable for a
college project, not a substitute for that review.

### Consent form — required content
1. **Explicit opt-in.** A single unambiguous checkbox/signature: "I agree to
   participate." No pre-checked boxes, no participation-by-default.
2. **Purpose statement**, plainly worded: *"Your answers will be used to
   develop and evaluate an AI model that scores mock-interview answers. They
   may become part of a training dataset or a fixed evaluation benchmark for
   this model. This is a student/research project, not a hiring evaluation."*
3. **What is collected** — list the exact fields from §1, so the volunteer
   sees the whole footprint before agreeing, not just a vague summary.
4. **How it's anonymized** — see the process below; state plainly that the
   name↔`volunteer_id` mapping will be deleted after a stated point.
5. **How it's stored** — where the files live (e.g. a private, non-public
   repo location — **never** the committed/public seed files), who has
   access (the project team only), and for how long.
6. **Whether anonymized excerpts may be retained for model development** —
   this must be its own explicit yes/no the volunteer can decline
   independently of overall participation, if you want to offer that
   granularity; simplest version is to make it part of the single consent
   (retain anonymized data indefinitely for this project's purposes) and say
   so plainly rather than bundling silently.
7. **Withdrawal process and its real limit** — state clearly: *"You may
   withdraw and have your raw answers deleted any time before anonymization
   is finalized on [date/event]. After that point, your data has been
   stripped of any link back to your identity and can no longer be located
   or removed individually."* This is an honest limitation, not a legal
   trick — say it in those words.
8. **Voluntary participation** — no course credit, grade, or any other
   dependency should be tied to participating; state this if it could
   otherwise be misread as compulsory (e.g. classmates in the same course).
9. **Not a real interview** — explicit line: *"This is not an evaluation of
   you, your skills, or your job-readiness. There is no pass/fail. Answer
   naturally as if in a real interview, but nothing about this affects you
   professionally."*

### Anonymization process
1. At intake, generate `volunteer_id` (e.g. `vol_01`…`vol_40`) and record the
   name↔id mapping in a **single, access-restricted file, never committed to
   the repo**, held only by the collector(s).
2. All collected fields (project context + answers) are stored keyed by
   `volunteer_id` only — the collection instrument itself should never ask
   for a name in the same record as the answers.
3. Before any data is merged into the training/benchmark artifacts, do a
   manual pass over `project_title`/`summary`/`answer_text` for accidental
   identifying leakage (a company name mentioned mid-answer, a teammate's
   name, etc.) and redact/genericize.
4. Once redaction is confirmed and the volunteer's withdrawal window has
   passed, **delete the name↔id mapping file**. This is the "irreversible
   anonymization" point referenced in the withdrawal clause above.

### What NOT to collect (repeated for the consent form itself)
The consent form should also state, as a *reassurance* to volunteers, the
explicit list of things we will never ask for: names in the answer records,
phone/email, current employer's confidential material, actual secrets/keys,
or proprietary code — this makes informed consent easier and reduces the
chance someone pastes something they shouldn't.

---

## 3. Question design — 20 reusable templates

Fifteen to twenty-five was the ask; twenty gives clean coverage without
padding. Each is written as a **template** with a `{project}` slot so it can
be grounded in the volunteer's actual project, per the instruction to prefer
project-grounded phrasing over generic textbook questions.

| # | Intent | Template |
|---|---|---|
| 1 | Basic understanding / overview | "What does {project} actually do?" |
| 2 | Architecture | "Walk me through the high-level architecture of {project}." |
| 3 | Implementation | "How did you implement [the core feature] in {project}?" |
| 4 | Technical decision | "Why did {project} use [technology X] instead of [alternative Y]?" |
| 5 | Trade-off | "What trade-off did you make in [a specific design choice] in {project}?" |
| 6 | Debugging/problem solving | "Describe a bug you had to track down in {project}." |
| 7 | Failure | "Tell me about a time {project} broke or failed in production/testing." |
| 8 | Testing | "How did you test {project} (or the part you built)?" |
| 9 | Performance | "How did you improve performance in {project}?" |
| 10 | Scalability | "How would {project} handle significantly more load/users/data?" |
| 11 | Security | "What security considerations did you account for in {project}?" |
| 12 | Edge cases | "What edge case did you have to handle in {project}?" |
| 13 | Alternative approaches | "What other approach did you consider for [a specific part] of {project}, and why didn't you use it?" |
| 14 | Ownership | "What part of {project} did you personally build or own?" |
| 15 | Challenge | "What was the hardest part of building {project}?" |
| 16 | Improvement/future work | "What would you improve about {project} if you had more time?" |
| 17 | Concept explanation | "Explain [a key concept/technology you used] and how it applies in {project}." |
| 18 | Decision-making (multi-option) | "How did you decide between [option A] and [option B] for {project}?" |
| 19 | Reflection | "Looking back, what would you do differently in {project}?" |
| 20 | Depth probe (follow-up style) | "Can you go deeper on how [X] actually works under the hood in {project}?" |

The `[bracketed]` slots are filled in *live*, during a short intake
conversation with the volunteer about their project — not left as literal
placeholders. This is the single place a human (the collector) does light,
unavoidable customization; it is NOT the volunteer shaping their own
question difficulty.

### Selecting 3–5 per volunteer
- Always include **one overview/basic-understanding question** (#1 or #2) —
  gives a natural, low-pressure opener and produces good Relevance/Depth
  contrast material on its own.
- Deliberately mix **at least one "explain/how" question** (implementation,
  architecture, concept) with **at least one "why/trade-off" question**
  (technical decision, trade-off, alternatives) and **at least one
  "narrative" question** (failure, challenge, debugging) — this is what
  produces the natural divergence the four dimensions need (see §4), without
  telling the volunteer to aim for any particular outcome.
- Rotate which template numbers are used across volunteers (a simple
  round-robin or the same deterministic-seed-based selection style already
  used for `coherent_profile` in `dimension_profiles.py`) so the question set
  as a whole doesn't over-sample "ownership" questions and under-sample
  "performance" questions, or vice versa.
- Cap at 5 per volunteer — beyond that, fatigue sets in and answers start
  reading as rushed/lower-effort in a way that isn't representative of a
  real interview.

---

## 4. Four-dimension coverage mapping

| Question type | Primarily exercises | Why |
|---|---|---|
| Overview, concept explanation, architecture | Relevance & Completeness, Depth & Specificity | Tests whether the volunteer actually addresses what was asked and how concretely |
| Technical decision, trade-off, alternatives, decision-making | Technical Correctness, Depth & Specificity | These require an actual technical claim to be right or wrong about, and reward/punish shallow reasoning distinctly |
| Debugging, failure, challenge, edge cases | Grounding & Ownership, Depth & Specificity | Naturally elicit first-person narrative ("I found," "I noticed") when genuine, and expose vague hand-waving when not |
| Ownership, reflection | Grounding & Ownership specifically | Most direct probe — but also most likely to trigger the exact "unsupported ownership claim" pattern the seed's hard case I already models, which is fine — that's a real, useful natural case, not something to filter out |
| Performance, scalability, security, testing | Technical Correctness, Depth & Specificity | Domain-general enough that answers range naturally from correct-and-deep to correct-and-shallow to subtly wrong |

**On natural divergence (not engineered):** the protocol does not instruct
volunteers toward any of the eight listed divergent patterns (technically
correct but shallow, strong ownership but technically weak, etc.). Those
patterns emerge on their own from real human variance — some volunteers will
genuinely misremember a mechanism (technically incorrect), some will answer a
challenge question with real specificity but minimal grounding language if
they're not naturally reflective writers, some will over-hedge on a
trade-off question they didn't personally decide. The role of the *question
mix* (§3's requirement to include multiple intents per volunteer) is only to
maximize the chance that natural divergence shows up across the ~100–200
collected answers as a whole — not to force any individual answer into a
category.

---

## 5. Labeling protocol

Same profile-blind discipline as the seed, using the existing,
already-audited machinery — **no new labeling infrastructure needed.**

**The judge sees exactly:** `question_text`, grounding text (built from
`project_title` + `technologies` + `short_project_description` via
`model_backbone.grounding_to_text`, identical to how the seed's judging was
built), `expected_concepts` (usually empty), `answer_text`, and the rubric
(`rubric_judge.build_judge_prompt`) — **verified by source inspection in the
prior session to reference none of the following.**

**The judge must NOT see:** any notion of "this is a real human answer" vs.
synthetic (the prompt-building function structurally cannot leak this — it
only takes question/grounding/concepts/answer), no target/intended quality,
no volunteer identity, no `source_type`/provenance metadata of any kind.

### Recommended annotation design
1. **Every collected answer** gets an independent Claude/profile-blind
   judging pass (`judge_all_dimensions`), exactly as the seed's — this is
   the baseline label source for every item.
2. **A meaningful subset gets human annotation too** — recommend **all
   items destined for the frozen human benchmark** (see §6) plus **a random
   ~20–25% of the training-bound items**, human-labeled by at least one
   annotator using the same rubric, structurally via `HumanAnnotation` (which
   already requires exactly the four canonical dimensions, per-annotator).
3. **Compute agreement** between the judge's score and the human
   annotator's score per dimension (reuse `rubric_judge.compute_agreement`'s
   `|judged - target| <= tolerance` pattern, but here "target" is the human
   label, not a generation-intent profile — same mechanism, different
   semantic role). Report per-dimension agreement rates and mean absolute
   delta, same shape as the seed's `target_vs_judge_agreement` diagnostic.
4. **Do not replace human annotation with LLM judging** for anything
   destined for the frozen benchmark: a `HumanBenchmarkItem`'s `final_labels`
   must come from `HumanAnnotation`/adjudication, never copied from the
   judge. The judge's score on a benchmark item is useful *only* as the
   comparison point for agreement metrics — it is never itself the
   benchmark's ground truth. This mirrors the frozen module's own comment:
   *"the authoritative, frozen, held-out evaluation set... never used for
   training or hyperparameter tuning"* and, by the same logic, never
   labeled solely by the thing it's meant to evaluate.

---

## 6. Human benchmark vs. training data — volunteer-level, not answer-level split

**Hard rule, stated explicitly because it's easy to get backwards: split by
`volunteer_id`, never by individual answer.** A volunteer who contributes 4
answers must have all 4 in the same bucket (train, val, or the frozen
benchmark) — never 2 in training and 2 in the benchmark. This is the same
`split_dataset_by_group` discipline the seed already uses (grouping by
`source_id`), just with `volunteer_id` as the group key instead of a project
name, since here the leakage risk is a *person's* writing style/vocabulary
leaking across splits, not just a project's content.

### Recommended allocation (out of 20–40 volunteers, 60–200 answers)
- **Frozen human benchmark: 8–12 volunteers held out completely** (never
  contribute to training or validation at all). At ~3–5 answers each, that's
  roughly **30–50 answers** — comfortably inside the `human_benchmark.py`
  design target of "~150-300 real answers" once combined with a later,
  larger collection round; this pilot alone won't fill the benchmark, and
  that's fine — it's a down payment, not the whole thing.
- **Remaining 12–28 volunteers → training/validation**, split by
  `split_dataset_by_group` at roughly 80/20 train/val (no test split needed
  here — the frozen benchmark *is* the held-out test signal for this
  stratum; a separate real-data "test" split would just fragment an already
  small pool for no benefit).

### Why hold out entire volunteers, not just a fraction of answers
A model that's seen 3 of a volunteer's 5 answers has effectively seen that
person's vocabulary, project, and writing tics — evaluating on their
remaining 2 answers would overstate generalization exactly the way the
existing `split_dataset_by_group` docstring already warns about for
synthetic data ("an example-level split can let a model succeed by
recognizing the topic rather than generalizing"). The risk is worse for real
human data, where writing style is a much stronger, more idiosyncratic
signal than anything in the synthetic seed.

---

## 7. Existing schema integration — inspected, mostly ready, one real gap found

### Real training-data path: ready, no changes needed
A volunteer answer destined for training/validation maps cleanly onto the
existing `TrainingExample` schema:

| Field | Value |
|---|---|
| `provenance.source` | `ProvenanceSource.REAL_SESSION` |
| `provenance.real_session_id` | the answer's `session_id` (required by the schema's own validator when source=real_session) |
| `provenance.collection_batch_id` | `"volunteer_pilot_2026q4"` (or similar) |
| `synthetic` | `None` (schema requires this — real examples carry no synthetic-generation metadata) |
| `inputs.specification` | `QuestionSpecification(id=..., category=QuestionCategory.PROJECT_DEEP_DIVE, grounding=Grounding(project=ProjectGrounding(title=project_title, summary=short_project_description, technologies=tuple(technologies))), source_type=SourceType.PROJECT, source_id=volunteer_id, source_field="project", reason="volunteer_pilot_2026q4 collection")` |
| `inputs.question_text` / `answer_text` / `expected_concepts` | direct copy from the collected record |
| `inputs.reasoning_type` | inferred from which of the 20 question templates was used (each template maps to one `ReasoningType`, e.g. template #6 (debugging) → `ReasoningType.DEBUGGING`) |
| `privacy.contains_pii` | `False` once the anonymization pass (§2) is confirmed; `anonymized=True`, `anonymization_method="manual redaction + name/id decoupling"` |
| `labels.dimension_labels` | from the judge (and human annotation where available) |

**Using `volunteer_id` as `source_id`** is the correct group key for
`split_dataset_by_group` — it naturally enforces the volunteer-level
(not answer-level) split from §6, for free, with zero new code.

### One real gap found: `HumanBenchmarkItem.grounding_source` is a bare string
`human_benchmark.py`'s `HumanBenchmarkItem` (inspected directly) stores
`grounding_source: str` — just an identifier, not a structured
title/technologies/summary. That's fine for *tracking* which project a
benchmark item traces back to, but it means the actual grounding **text**
needed to build the judge's/annotator's context (`grounding_to_text`) has
nowhere to live on the frozen benchmark record itself.

**This does not block the pilot** — the grounding text can be looked up
from the same volunteer-collection record that feeds the training path (kept
alongside the benchmark items in the pilot's own storage, not inside
`HumanBenchmarkItem`), since annotation happens before an item is frozen into
the benchmark. But it is a genuine, documented limitation: **if
`HumanBenchmarkItem` is ever consumed standalone (without the original
collection record nearby), there's no field to reconstruct the grounding
context from.** Per your instruction, I have not changed the schema to fix
this — flagging it as a finding for whoever populates the benchmark for real
to decide whether a future additive field (e.g. `grounding_text: str`) is
worth adding at that point.

### Label-source subtlety (also just a finding, not a change)
`TrainingExampleLabels.label_source` is a closed enum:
`{"synthetic_ground_truth", "human_reviewed"}`. A volunteer's real answer,
labeled only by the profile-blind LLM judge (no human review yet), doesn't
cleanly fit either — it isn't synthetic-generated, and it hasn't been
`human_reviewed`. **Recommended resolution, no schema change:** an
LLM-judge-only-labeled real answer should **not yet become a `TrainingExample`
at all** — it stays in an interim, pilot-internal holding area until either
(a) a human annotator reviews it and its labels can honestly be marked
`"human_reviewed"`, or (b) the project later decides that judge-only real
labels are an acceptable third category, at which point that's a real schema
change to propose explicitly, not sneak in via mislabeling. This keeps the
existing schema's guarantees honest rather than stretching an enum value to
mean something it doesn't say.

---

## 8. Real vs. synthetic mixture — recalculated from actual pilot numbers, not a target percentage

Working backward from what's actually achievable, for a **1,500–2,500-example
target**:

| Stratum | Source | Approx. count | Approx. % of 2,000 (midpoint) |
|---|---|---|---|
| Hand-authored seed (existing) | This project | 100 (fixed) | ~5% |
| Volunteer real data (training+val portion only, benchmark held out separately) | This pilot | ~30–120 (12–28 volunteers × 3–5 answers, minus whatever's excluded by quality filtering) | **~1.5–6%** |
| TechQA (Category-A public, if adopted) | IBM, CDLA-Permissive | a few dozen to ~100, capped deliberately narrow per the prior research's own recommendation (documentation-style answers, not interview reasoning — should stay a minority supplement, not scaled to fill a large fraction) | ~2–5% |
| Deterministic synthetic rewrites/augmentation | `deterministic_rewrite_pipeline.py`, expanding the judged hand-authored seed | the remainder | ~85–90% |

**This lands real data (volunteer + TechQA combined) at roughly 3–11% of the
final dataset, not 20–30%.** That's a direct, honest consequence of (a) how
small a "college-project-scale" volunteer pilot actually is relative to
1,500–2,500 examples, and (b) the deliberate decision not to force TechQA
beyond a small supplement given its domain/format mismatch. Forcing 20–30%
would mean either recruiting an unrealistic number of volunteers or diluting
quality by overweighting TechQA far past what its format actually supports —
neither is worth doing just to hit a round number.

### Strata that must stay separate (never silently merged)
1. **Hand-authored seed** (`provenance.source=SYNTHETIC`, but hand-authored —
   already tracked via `synthetic.generator_model="claude_code_hand_authored"`)
2. **Volunteer real data** (`provenance.source=REAL_SESSION`)
3. **TechQA / other licensed public real data** (`provenance.source=REAL_SESSION`
   also, but a distinct `collection_batch_id` e.g. `"techqa_v1"` — real, but
   NOT a volunteer, and NOT resume-grounded, so it should also be excluded
   from any Grounding & Ownership—specific analysis/reporting)
4. **Deterministic synthetic rewrites** (`provenance.source=SYNTHETIC`,
   `synthetic.rewritten_from_example_id` set — already a distinct,
   schema-tracked sub-case)

Acceptance/reporting should break results out **per stratum**, not just in
aggregate — exactly the same principle already applied to hard-case
coverage and tier distributions in `dataset_acceptance.py`.

### Volunteer answers must NOT feed the deterministic rewrite pipeline
Explicitly called out because it's an easy mistake: the rewrite pipeline's
existing precedent (Experiment 4) applies to *synthetic* examples, whose
labels the rewrite process is designed to carry forward unchanged (style
rewrites "never change claims/content"). Real volunteers' consent covers
*their own answer* being used for training/evaluation — it does not
automatically cover generating derivative paraphrases of their real,
personal words at scale. Unless a future consent form explicitly asks and
gets a "yes" to derivative augmentation, volunteer answers stay a rewrite-free
stratum, permanently.

---

## 9. Acceptance and quality gates for the real-data stratum

The synthetic seed's acceptance gate (`dataset_acceptance.evaluate_dataset`)
is not simply reused — several of its checks don't make sense for a
30–120-item, single-collection-round real stratum, and a few new ones matter
that don't apply to hand-authored data at all. Below, each threshold's
number is derived from the pilot's own stated target scale (§ headers
reference back to the task's 20–40 volunteers / 3–5 answers / 60–200 total),
not invented independently.

| Check | Threshold | Why this number |
|---|---|---|
| Minimum volunteers | ≥ 15 | Below the stated 20–40 target range's floor minus a small buffer for attrition/withdrawal; fewer than this and source diversity (below) can't be met either |
| Minimum answers per contributing volunteer | ≥ 2 (target 3–5) | Below 2, a "volunteer" contributes too little to support even a same-person train/val boundary meaningfully; 2 is the practical floor, not the target |
| Source diversity (distinct volunteers) | Same logic as the seed's `min_distinct_sources`, but scaled to *this stratum's own size* — e.g. require distinct-volunteer-count ≥ 60% of total answers ÷ 5 (the max answers/volunteer) | Directly mirrors the seed's already-established principle (a `PILOT_SEED_V1_ACCEPTANCE_CONFIG`-style stratum-specific threshold, not the synthetic-dataset's production default) — must be sized to this stratum, never copy the 100-example seed's or the eventual 1,500–2,500 set's numbers wholesale |
| No duplicate answers | Exact-duplicate check (`dataset_filters.exact_qa_duplicate_indices`) at 0 tolerance | Reused as-is — this check's logic doesn't depend on data being synthetic |
| Near-duplicate check | Production SBERT path (`dataset_filters.near_duplicate_pairs`, threshold 0.92) — reused as-is | Same reasoning; real answers can coincidentally converge in phrasing too (e.g. two volunteers both got the idempotent-billing question) |
| Leakage-free splitting | `split_dataset_by_group` keyed on `volunteer_id`, verified via the same no-cross-split-leakage check pattern already in `dataset_acceptance.py` | Directly reused mechanism, per §6 |
| PII check | Manual redaction pass (§2) PLUS an automated regex sweep for obvious leakage patterns (email-like strings, phone-number-like digit runs, "my manager [Name]"-style constructs) before any merge | Automated as a backstop, not a replacement for the manual pass — real free-text answers are exactly where PII slips in unnoticed |
| Provenance completeness | Every item has `volunteer_id`/`session_id`/`collection_batch_id`/`collected_at` populated | Structural — the schema already requires `real_session_id` when `source=REAL_SESSION`; this just confirms the pilot's own bookkeeping matches before promotion |
| Grounding-context completeness | Every item's `project_title` + `technologies` + `short_project_description` non-empty | Without this, Grounding & Ownership can't be meaningfully judged at all — this is the real-data equivalent of the seed's implicit assumption that every record has a grounding |
| Human/judge agreement | Report mean absolute delta + per-dimension agreement rate (same shape as `target_vs_judge_agreement`, but human-label-vs-judge here, not target-profile-vs-judge) — **no pass/fail threshold recommended yet**, only reporting, since we don't have a prior baseline for how well the judge tracks *human* labels (only how well it tracks generation *intent*, which is a different question) | Forcing a threshold before we've observed even one round of real human/judge agreement would be exactly the kind of arbitrary number the task warned against |
| Distribution across the four dimensions | Diagnostic only (like the seed's tier histogram) — report, don't gate | At only 60–200 answers, insisting on full 0–4 coverage on all four dimensions the way the seed's design deliberately engineered would be unrealistic and would pressure volunteers/collectors toward cherry-picking, which defeats the entire point of natural data |
| Natural-language diversity | Diagnostic: vocabulary/length variance report, not a hard gate | Real answers are naturally diverse by construction; a hard threshold here risks penalizing legitimately terse-but-correct volunteers |

---

## 10. End-to-end collection workflow

```
1. Volunteer recruited (classmates/teammates/other volunteers)
        ↓
2. Consent (§2) — explicit opt-in, reviewed by supervisor before first use
        ↓
3. Intake conversation: volunteer_id assigned; project_title,
   technologies, short_project_description collected
        ↓
4. Collector selects 3-5 question templates (§3) for this volunteer,
   fills in the {project}/[bracketed] slots from the intake conversation
        ↓
5. Volunteer answers naturally (written, no time pressure beyond
   "answer like you would in a real interview"; no coaching on length/depth)
        ↓
6. Manual PII/identifying-detail redaction pass on project context + answers
        ↓
7. Storage: keyed by volunteer_id/session_id only, in a private
   (non-public, non-committed) location -- name<->id mapping kept separately
        ↓
8. Profile-blind labeling: judge sees question+grounding+concepts+answer
   only (§5) -- run for every collected item
        ↓
9. Human spot-check / full annotation on the subset destined for the
   frozen benchmark + ~20-25% of the rest (§5)
        ↓
10. Quality filtering against §9's checks (dedup, near-dup, PII sweep,
    provenance/grounding completeness)
        ↓
11. Volunteer-level (not answer-level) split into: frozen benchmark
    (8-12 volunteers, fully held out) / train+val (remaining volunteers,
    ~80/20 by split_dataset_by_group)
        ↓
12. Merge into the overall dataset as a clearly-tagged, separate stratum
    (never silently combined with synthetic/hand-authored rows -- §8)
```

This is deliberately lightweight: steps 3–6 can realistically run as one
20–30 minute session per volunteer (intake conversation + written answers),
and steps 8–12 are scripted/batch work the team does afterward, not
per-volunteer overhead.

---

## 11. Final recommendation — phased plan (not yet executed)

- **PHASE A — protocol/design**: this document. *(This phase's output.)*
- **PHASE B — volunteer collection**: recruit 20–40 volunteers, run intake +
  answer collection per §10 steps 1–6.
- **PHASE C — annotation**: profile-blind judging on all items + human
  annotation on the benchmark-bound subset and a ~20–25% training-bound
  sample, per §5.
- **PHASE D — quality control**: run §9's checks; redaction/PII sweep;
  resolve any judge/human disagreements destined for the benchmark via
  adjudication (`AdjudicationStatus`).
- **PHASE E — dataset integration**: map surviving items into
  `TrainingExample` (training/val-bound, `human_reviewed` labels only per
  §7's resolution) and `HumanBenchmarkItem` (benchmark-bound, frozen).
- **PHASE F — final mixed-dataset construction**: combine the four strata
  from §8 with per-stratum reporting through `dataset_acceptance.py`-style
  gating (extended, not replacing, the existing gate).
- **PHASE G — DeBERTa retraining**: out of scope for this document and for
  the entire workstream to date — unchanged, later, not started.

**None of phases B–G have been executed. This document is Phase A's
complete output.**

---

## Summary answers

**VOLUNTEER PILOT SIZE:** 20–40 volunteers × 3–5 answers each (60–200
answers total), consistent with the task's own target range — no reason
found in this design pass to deviate from it in either direction.

**REAL-DATA TARGET:** ~3–11% of the eventual 1,500–2,500-example dataset
(volunteer pilot + TechQA combined) — not 20–30%. See §8 for the
stratum-by-stratum arithmetic.

**PUBLIC DATA:** Yes, include TechQA, but only as a small supplement (a few
dozen to ~100 examples, ~2–5% of the final dataset) for Technical
Correctness signal — not scaled up further given its documentation-style
format and narrow enterprise-support domain, and not a substitute for
Grounding & Ownership data, which it cannot provide.

**FROZEN HUMAN BENCHMARK:** 8–12 fully-held-out volunteers (~30–50 answers)
from this pilot alone — a down payment toward `human_benchmark.py`'s stated
~150–300-answer target, not the whole thing; later collection rounds would
need to add more held-out volunteers to reach that target.

**SCHEMA READY:** **YES** for the training-data path (`TrainingExample` +
`ProvenanceSource.REAL_SESSION` map cleanly, no changes needed). **PARTIAL**
for the benchmark path (`HumanBenchmarkItem.grounding_source` is a bare
identifier with nowhere to store the actual grounding text — workable for
this pilot by keeping that text in the pilot's own collection records
alongside the benchmark items, but worth a future additive field if the
benchmark is ever consumed standalone). No schema changes made this session.

**COLLECTION PROTOCOL READY:** **YES** — §§1–4 (what to collect, consent,
questions, dimension mapping) are complete and executable as written,
pending the supervisor's review of the consent text specifically (§2).

**NEXT ACTION:** Get the consent form (§2) reviewed by your university/project
supervisor. That review is the one genuine blocker before Phase B
(recruiting the first volunteer) can start — everything else in this design
is ready to execute as soon as that's cleared.
