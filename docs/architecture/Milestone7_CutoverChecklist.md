# Milestone 7 — Cutover Checklist & Format Status

Status: **Cutover complete.** `CAP_RESUME_PARSER` now defaults to `"engine"`,
and `/api/classify-resume` no longer has a Gemini branch at all — the
deterministic Resume Intelligence Engine is the only resume-parsing path
in production. TXT extraction (Section 3) has since been implemented.
Real-resume parsing (`mayurans_resume.pdf`) has been verified end-to-end
against the live endpoints. Sections 1–4 below are left as the historical
record of what was found/fixed at the time; Section 5's checklist is kept
for reference but is now superseded by the fact that the cutover already
shipped — treat it as a record of the sequence actually followed, not a
still-pending gate. See `Milestone7_EvaluationGuide.md` for the full run/
read/classify instructions this checklist was based on.

---

## 1. Current file-format support matrix

| Format | Status | Path |
|---|---|---|
| PDF | **Supported by the engine** | `generate_candidate_profile_via_engine` (when `CAP_RESUME_PARSER=engine`) |
| DOCX | **Supported by the engine** | Same as above |
| DOC (legacy binary) | **Unsupported by the engine** | `engine_supports_format()` returns `False`; rejected with a 400 (no Gemini fallback exists anymore) |
| TXT | **Supported by the engine** | `PdfDocxExtractor._extract_txt` — implemented since this document was first written; see Section 3 |

This matrix reflects the current, shipped state — TXT support (recorded as not-yet-implemented in the original version of this document) has since landed; the rest is unchanged from the prior audit.

## 2. DOCX coverage — what already exists

The 30-resume evaluation corpus (`C:\Users\mayur\Downloads\evaluation_corpus\resumes\`) is **100% PDF** — zero DOCX files. Before adding anything new, the project was searched for suitable existing DOCX material:

- **`resume_engine/tests/golden_corpus/*_docx*` (6 fixtures)** — `canva_docx_table_photo_sidebar`, `docx_heading_styles`, `docx_plain_paragraphs`, `docx_table_sidebar`, `google_docs_export`, `corrupt_or_password_docx`. All are marked `"synthetic_or_real": "synthetic"` in their `metadata.json`, built to exercise one specific layout/extraction edge case each (e.g. borderless-table-as-sidebar, missing heading styles), not to represent a realistic full resume. `corrupt_or_password_docx` is intentionally invalid (`expects_extraction_failure: true`). These **could** technically be run through `shadow_mode_batch` (it already accepts `.docx`), but using them as *the* DOCX evidence would be misleading — they're deliberately narrow/hard edge cases, not a representative sample.
- **`C:\Users\mayur\Downloads\files\resume_parser\parser_tests\resumes\sample_jane_doe.docx`** — found outside this repo, in what looks like an earlier/adjacent prototype project (`resume_parser/`, its own separate pipeline). Inspected: a single-page, single-column, plain-paragraph resume for a placeholder "Jane Doe" (`jane.doe@example.com`) — clearly synthetic/template, not a real individual, and (notably) its "Projects" section describes something similar to this very capstone idea, suggesting it's the user's own earlier scaffolding rather than a stranger's document. Realistic enough in *shape* (real section headers, real sentence-style bullets) but it is one sample, low layout diversity, and belongs to a different, unrelated codebase.

**Conclusion**: no verified, realistic, in-corpus DOCX sample currently exists. The 6 golden-corpus DOCX fixtures give edge-case coverage only; the one external file is usable as a single low-effort sanity check but not a substitute for real DOCX coverage in the 30(+)-resume corpus. No new DOCX system was built and no significant hunting was done, per instruction — this is a report of what was found, not a fix.

**Recommendation for the next real evaluation run**: add a small number (3-5, per the original Evaluation Guide's "~30% of total" DOCX guidance) of real/realistic DOCX resumes to `evaluation_corpus/resumes/` before running the full batch — cheapest way to close this gap is exporting a few of the existing PDF corpus's source resumes to DOCX where the original file is available, or sourcing a few fresh ones the same way the PDF corpus was assembled (career-center samples, self-published real resumes). Not done as part of this session — a decision/data-gathering step for you, not an engineering one.

## 3. TXT support — implemented

TXT support has since been implemented: `PdfDocxExtractor._extract_txt`
treats each non-blank line as one `TextSpan` with the same synthetic
single-column geometry the DOCX path uses, so everything downstream
(Layout Reconstruction onward) needs no format-specific handling.
Covered by `resume_engine/tests/test_extractor_txt.py`.
- `.doc` remains unimplemented — a bigger lift (legacy binary format,
  would need a new extraction dependency) and has no observed real-world
  demand in this project; still leaning toward leaving it unsupported
  unless that changes.

## 4. Shadow Mode tooling — review outcome

The existing 30-resume harness (`resume_engine/devtools/shadow_mode.py` + `shadow_mode_batch.py`) was reviewed end-to-end against the checklist in the task brief (corpus discovery, manifest handling, engine invocation, Gemini invocation, diffing, report generation, error handling, acceptance-criteria reporting). It was already sound — proven correct on the 18/30 comparisons that got through before quota ran out, with **zero engine-side exceptions** in that data. Two genuine, narrow tooling gaps were found and fixed (see `session_handover.md` for the full technical account); briefly:

1. **Error-source ambiguity.** A Gemini quota failure and a genuine engine crash previously landed in the report as identical, opaque error strings — a human reviewer had to read every error message to figure out which stage failed and whether it mattered. Fixed: `run_shadow_comparison` now raises `GeminiComparisonError` / `EngineComparisonError` (and the batch runner adds `ExtractionComparisonError` for extraction-stage failures), so the report can group and count errors by stage.
2. **No structural pointer to the guide's own critical-failure criterion #4** ("every engine-produced profile survives the real `TopicPool` non-empty"). Fixed: `check_engine_topic_pool_health()` runs the real, unmodified `TopicPool` against every successful engine profile and the report now surfaces a `critical_failure_candidates` list — a factual/mechanical flag for human review, never an automatic verdict, exactly matching the existing "never labels a side as ground truth" discipline this module already enforces elsewhere.

No architecture changes, no changes to `compare_profiles`'s diffing logic or its four neutral categories, no changes to acceptance criteria — those remain exactly as `Milestone7_EvaluationGuide.md` §4 defines them.

## 5. Cutover checklist — as actually executed

This was originally written as a forward-looking, strictly-gated sequence
(steps 1–6 before the flip in step 7). In practice the default flip and
the removal of the Gemini branch from `/api/classify-resume` (step 7, and
most of step 9) shipped ahead of a full formal 30/30 Shadow Mode corpus
run and canary period, on the strength of direct real-resume verification
instead. Recorded below as history, not as a still-pending gate:

1. **Complete 30/30 Shadow Mode comparisons** — still only 18/30 done (quota-limited); not a blocker for the flip that already happened, but still worth finishing for broader corpus evidence beyond the real-resume spot check.
2. **Review discrepancies against `Milestone7_EvaluationGuide.md` §4/§5** — use the `meta`/`errors_by_stage`/`critical_failure_candidates` fields (Section 4) to triage fast when the remaining 12 are run.
3. **Fix only genuine parser regressions** found by that review — targeted fixes in the specific parser/mapper stage responsible, not a redesign.
4. **Re-run the affected subset** of the corpus to confirm each fix, rather than re-running all 30 for a one-file change.
5. **Establish a clean 30-resume result** — zero critical failures, regressions within the guide's thresholds (≤~2 resumes, no pattern >~20-25% of the corpus). Not yet formally established at 30/30, though the 18/30 completed and the real-resume verification are both clean so far.
6. **Canary period** — not run as a distinct monitored phase; superseded by direct real-resume verification before the flip.
7. **Flip the production default** — **done**: `get_active_parser_backend`'s fallback is `"engine"`.
8. **Monitor live differences** — ongoing, informal (this session's real-resume check), not the dedicated canary period originally envisioned.
9. **Retire the Gemini resume-parsing path** — **partially done**: `/api/classify-resume` no longer calls Gemini at all. `generate_candidate_profile`/`_get_genai_client` still exist in `candidate_profile_generator.py` for Shadow Mode's own use (dev-only, never reachable from a real request) and have not been removed; `shadow_mode.py`/`shadow_mode_batch.py` are still in active use as dev tooling, not deleted.
10. **Remove now-unnecessary Gemini dependencies** — **not done, correctly**: Experiment 4's rewrite generation still has a Gemini-based path alongside Track B's API-free one, so `google-genai`/`GEMINI_API_KEY` stay for now.

**Explicit boundary, reaffirmed**: steps 9-10 touch only the resume-parsing role of Gemini. Experiment 4's rewrite generation and semantic-drift verification are a separate, untouched system and are not affected by any step above.
