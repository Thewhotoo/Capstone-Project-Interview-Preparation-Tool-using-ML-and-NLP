# Experiment 4, Track B — API-Free Rewrite Augmentation

Status: **Implemented, tested, empirically validated against the real dataset. Not yet scaled beyond a pilot-sized run.** This is the API-free alternative to the Gemini-based rewrite pipeline documented in `session_handover.md` — the two are independent and can coexist; this document covers only the new, non-LLM path.

---

## 1. Why this exists

Experiment 4's original design (rewrite generation + Gemini semantic-drift verification) is fully built, tested, and committed, but real pilot data collection has been repeatedly blocked by Gemini free-tier quota (20 requests/model/day; each rewrite attempt costs 2 calls). Per explicit direction, this track abandons the Gemini dependency for dataset construction entirely: **the final training dataset must be producible by Claude Code without depending on Gemini, OpenAI, or any other external LLM API.**

## 2. What was built

| Component | File | Role |
|---|---|---|
| Deterministic rewrite generator | `deterministic_rewrite.py` | Pure, rule-based text transforms for `concise`/`conversational`/`reflective` — regex + stdlib only, no network. |
| SBERT semantic-drift verifier | `rewrite_verifier_client.py` — `SBERTDriftVerifierClient` | Replaces the Gemini semantic-drift judge with a real (not fake/test-only) SBERT cosine-similarity check, satisfying the exact same `RewriteVerifierClient` Protocol. |
| Orchestration pipeline | `deterministic_rewrite_pipeline.py` | Mirrors `rewrite_generation_pipeline.py`'s shape; makes exactly one attempt per unit (the generator is a pure function — a retry would reproduce the identical output). |
| Run driver | `run_experiment_4_deterministic.py` | Same `select`/`generate` shape as `run_experiment_4_pilot.py`, same stratified selection (`select_pilot_sources`, imported not duplicated), pilot-sized run (40 sources × 3 styles = 120 attempts). |
| Tests | `test_deterministic_rewrite.py`, `test_deterministic_rewrite_pipeline.py` | 27 new tests, including an AST-based check that the orchestration module never imports `google.genai`. |

**Reused completely unchanged** (not duplicated, not modified): `rewrite_validation.validate_rewrite` (all 7 QA checks — an API-free rewrite is held to the identical acceptance bar a Gemini-produced one is) and `rewrite_assembler.assemble_rewritten_example`. The API-free path is held to the same quality standard, not a lowered one.

## 3. How the generator works (grounded, no fabrication)

Every transform is purely **structural**: filler-word/phrase removal, sentence-starter connectives, contractions, and a template-aware compression specific to this repository's own dataset shape (see below). None of it ever introduces a new noun, technology name, claim, or fact.

`concept_evidence` and the contradiction note are **carried forward verbatim** from the source example's own already-validated labels, never re-derived — a deliberate, documented deviation from the normal "rebuilt from the rewrite's own submitted evidence" rule (which assumes an LLM capable of reading evidence back out of freshly generated prose; a regex transform has no such capability, so it reuses evidence a human/LLM already validated for the same underlying facts, which don't change — only the surrounding prose does).

**Key finding from inspecting the real corpus**: `v_experiment_3_relabeled_dimensions` (Experiment 1/2's output) was itself generated entirely via `generation_client.FakeGenerationClient` — a deterministic template, never real Gemini prose (`generate(prompt)` builds `"I used {concept} — {detail}."` per concept, `detail` ∈ {"demonstrated with concrete functional detail", "mentioned briefly"}). This is not new information introduced this session, but it matters directly here: the highest-leverage `concise` transform for THIS corpus is recognizing and compressing that exact template shape — merging N parallel "I used X — detail." sentences sharing a detail into one "I used X, Y, and Z — detail." sentence, preserving every technology name and qualifier level exactly while removing the repeated boilerplate. Sentences that don't match the shape (a genuinely free-form answer) pass through untouched.

## 4. Empirical result (pilot-scale, same 40×3 stratification as the Gemini pilot)

Run twice — an initial version, then one round of targeted, evidence-based tuning after inspecting real rejection reasons (not before):

| Run | Accept rate | Accepted / Attempted |
|---|---|---|
| Initial | 45.8% | 55 / 120 |
| After 2 small fixes (see below) | **61.7%** | **74 / 120** |

Both runs completed in under a minute, with **zero external API calls**.

**The two fixes**, both evidence-based (found by inspecting real rejection reasons, not guessed in advance):
1. Applied the boilerplate detail-phrase shortening ("demonstrated with concrete functional detail" → "in depth") to **all three styles**, not just `concise` — on this templated corpus, `conversational`/`reflective` had almost nothing else to lexically vary, which was tripping the near-duplicate ceiling.
2. Gated the `reflective` closing sentence on the source answer having ≥8 words — appending a closer to a very short answer was pushing the length ratio outside its band and, for short answers, diluting SBERT similarity below the drift floor.

**Remaining rejection pattern** (documented, not yet fixed): `concise` is disproportionately rejected by the SBERT drift check (21/74 attempts) on richly-evidenced (many-concept) source examples — aggressive multi-concept compression can legitimately drop cosine similarity below the drift floor (0.70) even with zero information loss, a known false-positive risk of embedding similarity on paraphrase/compression, not a correctness bug. A further, more conservative compression strategy (e.g. capping how many concepts get merged into one sentence) could likely raise this further; not attempted yet, in the interest of reporting a working result rather than continuing to tune before checking in.

**Manual spot-check** (3 accepted examples, one per style, same source): all three preserved every concept, correct qualifier level, coherent English, genuinely different surface phrasing from the source and from each other.

## 5. Provenance (Track B requirement)

- **Data source**: exclusively this repository's own existing, already-labeled dataset (`v_experiment_3_relabeled_dimensions`, `artifacts/experiment_3_relabeled/dataset.jsonl`) — no external data fetched, nothing scraped. No separate license/attribution applies beyond what `experiment_3_reproducibility/` already documents for that dataset's own provenance.
- **Generation method tag**: every accepted example's `synthetic.generation_prompt_id` is `"deterministic_rewrite"` / `synthetic.generator_model` is `"deterministic-rule-based-v1"` — deliberately distinct from the Gemini path's `"rewrite_promptbook"` id, so the two generation methods are independently traceable in the dataset forever (append-only versioning discipline already established for this pipeline).
- **Train/val/test separation**: unchanged mechanism — every rewrite's split placement is a direct lookup against its source's already-existing split side (train-only for this pilot, matching the Gemini pilot's own scope), never a recomputed grouping. Val/test remain untouched by any augmentation.
- **Leakage**: a rewrite of a train-split source is itself train-split by construction; nothing crosses into val/test.
- **Reproducibility**: the generator is a pure, deterministic function (no `random` module) — the same source dataset always produces the identical accepted/rejected outcome. Re-running `run_experiment_4_deterministic.py generate` regenerates byte-identical results.
- **Colab handoff**: output lands in the same `TrainingExample`/`DatasetSplit` shapes and the same `experiment_dataset_io.py` JSON/JSONL mechanism every other experiment already uses — no new export step needed to hand this off to Google Colab for DeBERTa training.

## 6. Explicitly not done yet (by instruction — awaiting direction)

- **Not scaled beyond the 40×3 pilot.** Artifacts live in `artifacts/experiment_4_deterministic/` (gitignored, same convention as every other experiment's local artifacts).
- The `concise`-style drift-rejection pattern above is diagnosed but not further tuned.
- The other 5 style tags `rewrite_prompt_controllers.py` defines (`verbose`, `interview_like`, `highly_structured`, `confident`, `cautious`) remain LLM-only — `deterministic_rewrite.py` intentionally implements only the 3 the pilot uses.
- No decision yet on whether/how to combine this track's output with the (separately blocked) Gemini track's eventual output, or whether Track B alone is sufficient for the next DeBERTa retraining round.
