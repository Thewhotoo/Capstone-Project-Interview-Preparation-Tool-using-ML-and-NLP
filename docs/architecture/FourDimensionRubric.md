# Four-Dimension Evaluation Rubric

**Status:** Step 1 (schema definition only). Canonical source: `main_cap/cap/evaluation_dimensions.py`.

This document is the developer-facing rubric for the **four, and only four**,
dimensions on which a resume-grounded interview answer is judged going forward.
It replaces the legacy 12-dimension taxonomy (`reasoning_dimension_relevance.py`)
as the *target* schema. Step 1 defines the schema and rubric only — it does
**not** wire these into the DeBERTa model, the dataset, or any evaluator. That
(context-in-input, relabel, retrain) is later, separate work.

## Why four, and why new keys

The legacy 12 dimensions are highly overlapping, three of them were never
labeled in the deployed dataset, and their "always-relevant" four
(accuracy / communication / completeness / resume_grounding) are not the four
we actually want. The canonical four are defined here with **new, distinct
keys** (not a rename) and explicit non-overlap boundaries so they stay
independent and separately learnable.

Scoring is ordinal **0–4** (poor / weak / adequate / good / excellent),
matching the backbone's existing CORAL formulation.

| # | Display name | Key | One-line focus |
|---|---|---|---|
| 1 | Technical Correctness | `technical_correctness` | Are the technical claims **true**? |
| 2 | Depth & Specificity | `depth_specificity` | Are the mechanisms/details **concrete**, not verbose? |
| 3 | Relevance & Completeness | `relevance_completeness` | Did they **answer what was asked**, fully? |
| 4 | Grounding & Ownership | `grounding_ownership` | Is it **their real project**, understood first-hand? |

The full per-tier text and the evidence-up / evidence-down lists live in code
(`RUBRICS` in `evaluation_dimensions.py`) so there is a single source of truth;
this doc summarizes and explains the boundaries.

## 1. Technical Correctness — `technical_correctness`
Truth of the technical content only. **Do not** reward fluency, verbosity, or
confidence; a terse correct answer scores high, a long confident wrong answer
scores low.
- **0** fundamentally wrong · **1** mostly incorrect · **2** mixed, notable error · **3** largely correct, minor imprecision · **4** fully correct incl. nuance.
- **Up:** accurate mechanisms, correct terminology, sound cause→effect.
- **Down:** misconceptions, misused terms, self-contradiction.

## 2. Depth & Specificity — `depth_specificity`
Concreteness of the *how/why* — named components, real decisions, numbers,
trade-off reasoning. **Length ≠ depth.**
- **0** buzzwords only · **1** vague, no mechanism · **2** some specifics · **3** concrete mechanism · **4** deep + quantitative + alternatives/edge cases.
- **Up:** named components, metrics, specific decisions + reasons.
- **Down:** generic phrasing, padding, hand-waving over the probed part.

## 3. Relevance & Completeness — `relevance_completeness`
Did the answer address the **specific** question and cover its important parts
/ expected concepts — independent of correctness or depth.
- **0** off-topic · **1** barely relevant · **2** partial · **3** answers with minor gaps · **4** fully answers every part + expected concepts.
- **Up:** addressing the asked focus, covering each sub-part/expected concept.
- **Down:** answering a different question, ignoring parts, omitting expected concepts, unrelated padding.

## 4. Grounding & Ownership — `grounding_ownership`
Two linked signals: (a) is the answer tied to the candidate's **actual
resume/project context**, and (b) does it show **first-hand understanding and
personal contribution** — versus a generic textbook answer, an unsupported
claim, or credit that contradicts the resume.
- **0** ungrounded/contradictory (textbook or conflicts with resume) · **1** mostly generic, vague "we" · **2** some grounding, thin ownership · **3** grounded with personal involvement · **4** strongly grounded + owned, consistent with resume.
- **Up:** actual project specifics, first-person concrete contribution, consistency with grounding.
- **Down:** generic textbook answer, unsupported/inflated claims, collective "we" with no role, contradicting the resume.

## Keeping the four distinct (non-overlap)
Each rubric in code carries an explicit `must_not_overlap_with` entry for the
other three. The load-bearing separations:

- **Correct but vague** → high Correctness, low Depth.
- **Detailed but irrelevant** → high Depth, low Relevance.
- **On-topic but wrong** → high Relevance, low Correctness.
- **Correct textbook recital of their "project"** → high Correctness/Depth, low Grounding & Ownership.
- **Confident but unsupported** → low Correctness and/or low Grounding & Ownership, regardless of fluency.

## Applicability
The rubric is written to work across all resume-grounded question intents:
architecture, implementation details, technology choices, debugging,
trade-offs, testing, scalability, security, ownership, and challenges/failures.

## Legacy compatibility
`LEGACY_DIMENSION_MAP` in `evaluation_dimensions.py` groups each of the legacy
12 dimensions under exactly one canonical dimension (a partition), so later
aggregation/relabel code can translate old signal into the four **without**
importing or editing the frozen legacy module. A unit test
(`test_evaluation_dimensions.py`) checks this stays in sync with the real
legacy set.

Mapping:
- **Technical Correctness** ← technical_accuracy
- **Depth & Specificity** ← technical_depth, architecture, tradeoffs, debugging, testing, scalability
- **Relevance & Completeness** ← completeness, communication
- **Grounding & Ownership** ← resume_grounding, ownership, authenticity
