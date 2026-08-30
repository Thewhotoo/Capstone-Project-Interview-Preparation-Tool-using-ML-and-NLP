# Resume Intelligence Engine — Real-World Evaluation Guide

Status: **Guidance document, not an architecture change. No production code involved.** Prepares the human-run evaluation that gates flipping `CAP_RESUME_PARSER`'s default from `gemini` to `engine` (Milestone 7, Phase 4). See `Milestone7_ValidationReport.md` Section 5 for why this step was deliberately not run automatically.

---

## 1. Audit of the Shadow Mode tooling that exists today

Two modules, both in `resume_engine/devtools/` (developer/QA tooling only — neither is importable from `app.py`, per the architecture doc's Section 2.2 hard constraints):

**`shadow_mode.py`**
- `run_shadow_comparison(resume_file_path: str, resume_text: str) -> ShadowComparisonResult` — runs Gemini (`generate_candidate_profile`, text-based) and the engine (`generate_candidate_profile_via_engine`, file-based) on the same resume and returns a structured comparison.
- `compare_profiles(gemini_profile, engine_profile) -> list[Discrepancy]` — the pure diff function (no API calls), type-aware per field:
  - Scalars (`candidate_name`, `predicted_domain`, `experience_level`, `confidence`, `resume_summary`): direct equality.
  - Flat string lists (`skills`, `certifications`): order-independent set diff.
  - Structured entity lists (`education` by institution, `experience` by role, `projects` by title): matched by a natural key, then diffed field-by-field.
  - `contact_details`, `interview_blueprint`: whole-object equality (kept unsummarized deliberately — these are exactly where genuine synthesis differences are most interesting to see in full).
- Every `Discrepancy` carries a `category`: `missing_in_engine`, `missing_in_gemini`, `different_value`, or `count_mismatch` — **never** a verdict on which side is correct. `ShadowComparisonResult.category_counts()` gives the per-resume tally.

**`shadow_mode_batch.py`**
- `run_batch_shadow_comparison(resume_dir: str) -> dict[filename, ShadowComparisonResult | Exception]` — runs the above over every `.pdf`/`.docx` file in a directory (non-recursive; `.doc`/`.txt` are silently skipped — the engine has no extractor for them). One resume's failure (corrupt file, extraction error) is captured as an `Exception` value, never aborts the batch.
- `aggregate_category_counts(results) -> dict[str, int]` — batch-wide category totals.
- `write_report(results, report_path)` — a human-reviewable JSON file: a `summary` block (batch totals) plus one entry per resume (`category_counts` + the full `discrepancies` list, or `{"error": "..."}`).
- A CLI entry point (`main()`), runnable as `python -m resume_engine.devtools.shadow_mode_batch`.

Both modules are fully implemented and unit-tested (26 tests total, `test_shadow_mode.py` + `test_shadow_mode_batch.py`) — but every test mocks Gemini's response. **Nothing in the current test suite constitutes a real-world comparison.** That's the gap this evaluation closes.

## 2. How to run it

**Prerequisites:**
- `GEMINI_API_KEY` set in `main_cap/cap/.env` (same variable `app.py` already requires for the live Gemini path — no new setup if you've used the app before).
- A directory of real or realistic resume files, `.pdf`/`.docx` only (see Section 3 for composition).
- Run from `main_cap/cap` (so `resume_engine`, `candidate_profile_generator`, and `src.parser` are all importable):

```bash
cd main_cap/cap
python -m resume_engine.devtools.shadow_mode_batch --dir path/to/resumes --report shadow_report.json
```

**What happens:** for every resume, Gemini is called for real (this costs API quota/money and takes time — budget roughly one Gemini call per resume, same cost as a real upload today) and the engine runs locally. Progress isn't streamed per-file today; for a first run, start with a small subset (5-10 resumes) to confirm the setup works before committing the full corpus.

**Reading the output** (`shadow_report.json`):
1. Start with `summary` — the batch-wide category totals. This is your first signal: is `missing_in_engine` dominant (engine under-extracting), `missing_in_gemini` dominant (engine finding things Gemini didn't — could be good), or roughly balanced (mostly phrasing/classification differences)?
2. Drill into `resumes["<filename>"].discrepancies` for any resume whose category counts look like outliers vs. the rest of the batch — that's where a real problem (not a phrasing quirk) is most likely to surface.
3. Any `{"error": "..."}` entry means the engine (or the batch runner's own extraction step) failed outright on that file — always worth opening manually to see why, since it's a candidate critical failure (Section 5).

I can't run this myself in this environment (no `GEMINI_API_KEY`, and I won't call a paid external API without you explicitly asking me to on a specific occasion) — but once you have `shadow_report.json`, paste it (or a summary/excerpt) back to me and I'll help interpret it against the criteria below.

## 3. Recommended evaluation corpus

**Size**: 40-60 resumes for a decision you can act on with reasonable confidence. Fewer than ~30 risks a single unlucky/lucky category dominating the read; more than ~60 has fast-diminishing returns for the cost, unless the first pass surfaces something ambiguous worth a larger confirming batch.

**Composition** (a rough split for 50; adjust proportionally for a different total):

| Category | Count | Why it matters |
|---|---|---|
| Students / new grads (projects-heavy, thin experience) | 8 | Stresses `ProjectParser`/interview-seed synthesis on sparse-but-real evidence; tests graceful degradation isn't over-triggering. |
| Experienced engineers (5+ roles, dense resumes) | 8 | Stresses entry-clustering, multi-entry sections, `experience_level`/domain inference at the "Advanced" end. |
| Sparse / single-project resumes | 5 | Directly exercises the permanent graceful-degradation rule (Milestone 4) — the resume-level equivalent of the seed-synthesis fixture corpus. |
| Academic / research CVs (publications, teaching) | 5 | A **known, already-documented** Section Detection coverage gap (Milestone 2 Finding 4: the 7-label canonical set doesn't cover publications/teaching/awards) — expect this category to show real gaps; the question is how bad, not whether. |
| ATS-plain (single column, no styling) | 8 | The engine's best-case format; should show the fewest discrepancies here — a useful baseline. |
| Highly designed (two-column, sidebars, icons, Canva-style) | 8 | Stresses Layout Reconstruction + Section Detection's harder cases; several are already-documented residual limitations (Milestone 1/2 findings) — expect to see them, not be surprised by them. |
| Non-software domains (marketing, finance, healthcare, etc.) | 5 | Tests `domain_gazetteer.py`'s breadth beyond the software-heavy fixtures every other milestone's testing has focused on. |
| DOCX (mixed into the above, not a separate bucket) | ~30% of total | Exercises the DOCX-specific extraction path, not just PDF. |

Use real resumes with consent, or anonymized/synthetic-but-realistic ones — never commit real candidate PII anywhere durable (matches the golden corpus's own standing rule). `shadow_report.json` will contain real extracted contact info if real resumes are used — treat it as sensitive, don't commit it to the repo.

## 4. Acceptance criteria

Objective, checkable against `shadow_report.json` — not a vibe check:

1. **Zero critical failures** (Section 5) across the whole corpus. This is a hard gate — even one occurrence should block the flip until understood.
2. **Zero regressions** (Section 5) affecting more than ~2 resumes in the batch, and no single regression pattern recurring on more than ~20% of the corpus. A pattern above that threshold means a real, fixable gap (e.g., gazetteer coverage), not a resume-specific edge case.
3. **Contact extraction (email/phone) matches or exceeds Gemini's** on ATS-plain and designed resumes alike — this is the category where the engine's deterministic regex approach should be at least as reliable as an LLM transcribing from flattened text; any systematic gap here is worth investigating regardless of size.
4. **Every engine-produced profile survives the real `TopicPool` non-empty**, i.e. `len(pool.specifications) > 0` and `pool.rejected == []` when constructed from the engine's output for every resume that has genuine project/experience content (reuse the exact check `test_candidate_profile_mapper.py`'s schema-compatibility test already runs, just against real data now instead of one synthetic fixture).
5. **No fabricated content anywhere** — every `interview_seed`, `technical_topic`, `technology`, or `concept` the engine produces must be traceable to literal text in that resume. This should be structurally guaranteed by the architecture (Milestones 3/4's grounding guarantees), so this criterion is really "confirm the guarantee held in practice," not a soft target.
6. `predicted_domain`/`experience_level` agreement rate with Gemini is **informational only, not a gate** — neither system is ground truth, and both are, at best, reasonable guesses on ambiguous resumes. Track it, don't block on it.

## 5. How to classify each difference

Every `Discrepancy` in the report falls into one of these four buckets. None of them are pre-assigned by the tooling — that's a deliberate design choice (Section 1) — so this is the human judgment call the evaluation exists to make.

### Expected improvements (the engine doing something genuinely better)
- More reliable, byte-for-byte reproducible contact info (email/phone regex vs. LLM transcription).
- LinkedIn/GitHub captured from a hyperlinked icon with no visible URL text — a real gap in Gemini's flattened-text input the engine's `DocumentModel.hyperlinks` closes (documented since Milestone 1).
- Full determinism itself: identical input always produces identical output, which Gemini cannot guarantee even at `temperature=0.1`.
- `duplicate_technologies_merged`/`skill_not_demonstrated` observations — signals Gemini's pipeline never produced at all.
- Any case where Gemini's `interview_seeds`/`technical_topics` reference something not actually in the resume (a hallucination) and the engine's version doesn't — this would be the most important improvement to confirm, not just note.

### Acceptable differences (not wrong, no action needed)
- `interview_seeds`/`technical_topics` phrasing (fixed templates vs. LLM prose) — the explicitly accepted, documented tradeoff from Milestone 4's design review.
- `resume_summary` reading more mechanical/templated than Gemini's fluent paragraph — same tradeoff, different field.
- `projects[].summary` being verbatim-extracted rather than abstractively paraphrased (documented since Milestone 3).
- `predicted_domain`/`experience_level` differing on a genuinely ambiguous resume (both are guesses; disagreement isn't evidence either is wrong).
- Missing an unusual/niche skill or technology term not yet in a gazetteer — a real, expected, low-urgency coverage gap (the same "transparent, reviewable-diff maintenance cost" every gazetteer in this engine accepts by design).
- Missing publication/teaching/award entries on academic CVs — the already-documented Section Detection coverage gap, not a new finding.

### Regressions (real, worth fixing before or shortly after cutover — not necessarily launch-blocking alone)
- Systematically fewer projects/experience entries than Gemini on **common, well-formed** resume templates (not edge cases already known to be hard).
- Contact info missed on a clearly-formatted, non-adversarial resume.
- Near-zero `interview_seeds` on a project that obviously has rich evidence (multiple technologies, a stated metric) — would point to `seed_synthesis.py`'s caps/thresholds needing retuning, not a design flaw.
- Any `missing_in_engine` pattern recurring on more than ~20-25% of the corpus for the same field — systematic, not incidental.

### Critical failures (block the flip until resolved)
- An unhandled exception on a normal (non-corrupt, non-scanned) resume — should never happen; if it does, it's a real bug, not a documented limitation.
- Zero projects **and** zero experience entries extracted from a resume that clearly has substantial content — the one hard product invariant (an empty `TopicPool` breaks the interview session entirely).
- Any confirmed fabricated/hallucinated value anywhere in engine output — this would contradict the architecture's central guarantee and should be treated as the single most serious possible finding, however rare.

## 6. Next steps

1. Assemble the corpus per Section 3 (or a reasonable approximation of it — the split is a guide, not a strict requirement).
2. Run the batch command in Section 2. Start small (5-10 resumes) to confirm the setup, then run the full batch.
3. Send me `shadow_report.json` (or the `summary` block plus any resume whose discrepancies look like outliers) and I'll help classify the results against Section 5 and check them against Section 4's acceptance criteria.
4. Once we're both satisfied the criteria are met, flipping the default is a one-line change (`candidate_profile_generator.get_active_parser_backend`'s fallback value) — I'll make that change only after this review, not before.

No code was written or modified as part of this document.
