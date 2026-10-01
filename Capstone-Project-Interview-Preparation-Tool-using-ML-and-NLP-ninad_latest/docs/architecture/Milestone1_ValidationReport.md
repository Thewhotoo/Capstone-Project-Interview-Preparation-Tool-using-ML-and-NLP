# Milestone 1 — Validation Report

Status: **Validation pass complete. Findings #1 and #2 below are RESOLVED (2026-08) — see the addendum at the end of this document. Finding #3 remains working-as-intended (not a defect). Milestone 2 planning may now proceed.**

This is a dedicated verification pass requested after Milestone 1's initial implementation (Document Extraction + Layout Reconstruction) and its original 10-fixture golden corpus, both already committed. The goal here was specifically to stress-test the implementation against a much more diverse set of real-world resume template shapes *before* building anything on top of it in Milestone 2 (Section Detection) — and to report findings honestly rather than quietly patching them out of the results.

**This document is preserved as originally written** (Sections 1-4 below describe the pre-fix state and the investigation that led to it) — the addendum at the end records what changed and why, rather than editing the findings out of history.

---

## 1. Methodology

- Added 12 new golden-corpus fixtures (bringing the corpus to 22) emulating real-world resume template families: ATS-plain, Canva, Overleaf/LaTeX academic, Google Docs export, academic CV, icon-heavy contact headers, a narrow-sidebar edge case, a mixed single/two-column multi-page document, a dense long resume, a minimal/sparse resume, inline right-aligned dates, and a 3-column DOCX table.
- Every fixture is synthetic (no real candidate data), built with `pymupdf`/`python-docx`, and documented in its own `metadata.json` per the existing golden-corpus format (`resume_engine/tests/golden_corpus/README.md`).
- Built a new dev-tool script, `resume_engine/devtools/golden_corpus_report.py`, that runs the real `PdfDocxExtractor` + `ColumnAwareLayoutReconstructor` across every fixture in the corpus (all 22, not just the new 12) and reports, per fixture: characters extracted, span count, hyperlink count, page count, layout mode, layout confidence, and a same-line-column-split diagnostic count — then flags low-confidence, ambiguous, and sparse results automatically.
- **This script is diagnostic tooling for this validation pass, not a new permanent regression gate.** The permanent gate remains `resume_engine/tests/test_golden_corpus_extraction.py`, which now also smoke-tests (extraction + layout must not crash) all 12 new fixtures; only the original 10 fixtures carry hand-verified `expected_layout.json` hard assertions, since several of the new fixtures' "correct" outcomes are exactly what's in question below.
- No changes were made to `extractor.py` or `layout.py`'s actual logic during this pass — every finding below reflects the Milestone 1 code as committed.

Full per-fixture output:

```
fixture_id                       style            type   chars  spans links pages layout_mode     conf  same_y  result
------------------------------------------------------------------------------------------------------------------------
academic_cv_multipage            academic_cv      pdf      333     11     0     2 single_column   0.95       0  OK
ats_one_column_plain             ats_plain        pdf      377     10     0     1 single_column   0.95       0  OK
canva_docx_table_photo_sidebar   canva            docx     206      6     0     1 ambiguous       0.35       0  FLAGGED
canva_style_two_column           canva            pdf      355     15     0     1 two_column       0.8       6  OK
corrupt_or_password_docx         -                docx      --     --    --    -- --                --      --  EXTRACTION_FAILURE (expected)
corrupt_pdf                      -                pdf       --     --    --    -- --                --      --  EXTRACTION_FAILURE (expected)
dense_long_ats_resume            ats_plain        pdf     1122     26     0     1 single_column   0.95       0  OK
docx_plain_paragraphs            -                docx     306      7     0     1 single_column   0.95       0  OK
docx_table_sidebar                -               docx     286      7     0     1 two_column       0.6       3  FLAGGED
google_docs_export               google_docs      docx     239      7     0     1 single_column   0.95       0  OK
hyperlinked_contact_icons_pdf    -                pdf       96      4     2     1 single_column   0.95       0  FLAGGED
icon_heavy_contact_header        icon_heavy       pdf       89      7     5     1 ambiguous       0.35       0  FLAGGED
minimalist_sparse_one_page       ats_plain        pdf      102      3     0     1 single_column   0.95       0  FLAGGED
mixed_layout_two_page            ats_plain        pdf      287     12     0     2 two_column       0.7       5  OK
narrow_sidebar_ats_photo         ats_narrow_sidebar pdf      918     23     0     1 ambiguous       0.35       0  FLAGGED
nested_bullets_pdf               -                pdf      201      7     0     1 single_column   0.95       0  OK
overleaf_latex_academic          latex_academic   pdf      397     10     0     1 single_column   0.95       0  OK
ragged_single_column_pdf         -                pdf      473     11     0     1 single_column   0.95       0  OK
right_aligned_dates_ats          ats_plain        pdf      284     11     0     1 two_column       0.6       3  FLAGGED
scanned_image_only_pdf           -                pdf       --     --    --    -- --                --      --  EXTRACTION_FAILURE (expected)
single_column_pdf                -                pdf      336      8     0     1 single_column   0.95       0  OK
two_column_sidebar_pdf           -                pdf      343     15     0     1 two_column       0.8       7  OK

Flagged fixtures:
  - canva_docx_table_photo_sidebar: LOW_CONFIDENCE layout (0.35, mode=ambiguous); AMBIGUOUS layout classification
  - docx_table_sidebar: LOW_CONFIDENCE layout (0.60, mode=two_column)
  - hyperlinked_contact_icons_pdf: SPARSE extraction (96 chars)
  - icon_heavy_contact_header: LOW_CONFIDENCE layout (0.35, mode=ambiguous); AMBIGUOUS layout classification; SPARSE extraction (89 chars)
  - minimalist_sparse_one_page: SPARSE extraction (102 chars)
  - narrow_sidebar_ats_photo: LOW_CONFIDENCE layout (0.35, mode=ambiguous); AMBIGUOUS layout classification
  - right_aligned_dates_ats: LOW_CONFIDENCE layout (0.60, mode=two_column)

Total fixtures: 22, flagged: 7
```

Run it yourself from `main_cap/cap/`: `python -m resume_engine.devtools.golden_corpus_report`

---

## 2. Findings, ranked by severity

### Finding 1 (HIGH — confirmed defect): inline right-aligned dates get pulled into a phantom second column, corrupting reading order

**Fixture**: `right_aligned_dates_ats` — a single-column ATS resume with the (extremely common) real-world pattern of printing the date range right-aligned on the *same visual line* as the role/company text.

**Observed**: classified `two_column` (confidence 0.60). Inspecting the actual output span order:

```
col=0 'Jordan Example'
col=0 'EXPERIENCE'
col=0 'Acme Corp, Senior Engineer'
col=0 'Led migration of the billing platform to microservices.'
col=0 'Beta Inc, Software Engineer'
col=0 'Built the customer-facing analytics dashboard.'
col=0 'Gamma LLC, Junior Engineer'
col=0 'Maintained the internal reporting toolchain.'
col=1 '2021 - Present'
col=1 '2018 - 2021'
col=1 '2016 - 2018'
```

All three dates are pulled out of their job entries and dumped at the very end of the document, disconnected from the roles they belong to. This is not merely a mislabeled confidence score — it actively corrupts the linearized reading order. A downstream `ExperienceParser` (Milestone 3) expecting a date-range line adjacent to its role/company line would find no dates at all in the right place and three orphaned date strings at the end of the document.

**Root cause**: `layout.py`'s column classification runs directly on each individual `TextSpan`'s `x0`, not on pre-merged visual lines. Two `insert_text` calls at the same y-position (role/company at `x0=72`, date at `x0=450`) become two separate spans with very different `x0` values. With three job entries, the three date spans corroborate each other into a legitimate-looking second "column" (clears `MIN_CORROBORATING_LINES=3`, clears `MIN_BAND_BALANCE_RATIO` at 3/8≈0.375, and the two bands' y-ranges fully overlap since they're literally the same rows) — the exact same geometric signature a real two-column sidebar produces.

**Assessment**: this is likely **the single most consequential finding in this validation pass**, since inline right-aligned dates are one of the most common resume formatting conventions in the real world, not an edge case. Not patched, per instruction — flagged for a design decision before Milestone 2.

### Finding 2 (MEDIUM — confirmed limitation): a genuine two-column resume with a short sidebar is misclassified as "ambiguous"

**Fixture**: `narrow_sidebar_ats_photo` — a real two-column layout (3-line Skills sidebar, 20-line Experience main column).

**Observed**: classified `ambiguous` (confidence 0.35) instead of `two_column`. Reading order itself stays intact for this one (the ambiguous path preserves natural document order rather than attempting a wrong split), but the layout signal itself is wrong, and any later stage or product feature that reads `layout_mode`/`layout_confidence` (e.g. a future confidence-tempering step) would be misinformed.

**Root cause**: `MIN_BAND_BALANCE_RATIO=0.25` in `layout.py`, added specifically to guard against the *opposite* failure mode (a handful of stray right-aligned fragments — see Finding 1 — being misread as a real column). A real sidebar with only 3 lines against a 20-line main column has a balance ratio of 0.15, below the guard's threshold. **The same numeric fix that would loosen this guard would make Finding 1 worse** — they are in direct tension, and a real fix needs a better signal than raw line-count balance (e.g. corroborating a candidate sidebar via a recognized header keyword like "Skills"/"Contact", which doesn't exist until Section Detection in Milestone 2).

**Assessment**: real, but lower-severity than Finding 1 — reading order isn't corrupted, only the mode/confidence label is wrong.

### Finding 3 (LOW — working as intended, included for completeness): 3+ column layouts degrade safely

**Fixture**: `canva_docx_table_photo_sidebar` — a 3-column DOCX table (photo cell, skills sidebar, main column).

**Observed**: classified `ambiguous` (confidence 0.35), not force-guessed into an incorrect two-column split. Reading order happens to stay correct because DOCX table extraction already visits cells in column-major order.

**Assessment**: this is the architecture doc's Section 4.2 non-goal (3+ columns) degrading exactly as designed — "detected and flagged... rather than mis-parsed silently." Not a defect. Included in this report because it was one of the fixtures deliberately built to probe this exact non-goal, and it's worth confirming in writing that it behaves as intended rather than assuming so.

### Non-findings worth noting explicitly

- **`docx_table_sidebar`** (from the original Milestone 1 corpus) was auto-flagged by the report tool for "low confidence" (0.60, `two_column`) — but this is its documented, hand-verified **correct** outcome (`expected_layout.json` asserts exactly this and passes in the permanent test suite). Same confidence value as Finding 1's genuinely wrong result. **This is a useful confirmation of the architecture doc's own principle that confidence is a signal for review, not a verdict of correctness by itself** — a 0.6 score means "just barely corroborated," and it can be just-barely-corroborated-and-right or just-barely-corroborated-and-wrong. Nothing to fix here; noted for calibration awareness going into Milestone 6 (Confidence Scoring).
- **Hyperlink capture was correct in every fixture tested**, including the 5-icon `icon_heavy_contact_header` case where layout classification itself went sideways (`ambiguous`, 0.35). Hyperlink capture is independent of column geometry and held up even when layout didn't. This is a genuine strength, not just an absence of a problem.
- **`minimalist_sparse_one_page` and `hyperlinked_contact_icons_pdf`** were auto-flagged as "sparse" (under the report script's 150-char threshold) but both are legitimate, valid resumes by design (102 and 96 chars respectively, both comfortably above the real `MIN_EXTRACTED_CHARS=50` floor). These are false positives of the *report script's* arbitrary threshold, not defects in the extractor — noted so the flag isn't mistaken for a real issue.
- **The report's own automated "same-line column split" diagnostic (`same_y` column) cannot by itself distinguish a genuine defect from normal two-column content.** `canva_style_two_column`, `mixed_layout_two_page`, and `two_column_sidebar_pdf` all show non-zero same-line-split counts (5-7) purely because a sidebar row and a main-column row legitimately render at the same height — completely normal and correct for a two-column layout. Only cross-referencing against each fixture's *documented expected outcome* (not the raw metric) separates Finding 1's genuine defect from this normal pattern. This limitation of the diagnostic tool itself is recorded here rather than silently relying on a metric that oversells its own precision.

---

## 3. What this means for Milestone 2

Per instruction, **nothing above has been patched**. Two things need a decision before Section Detection is built on top of this foundation:

1. **Finding 1 (inline right-aligned dates)** actively corrupts reading order for a very common real-world pattern and most likely needs a real fix (not just a threshold tweak) before Section Detection, since Section Detection's font/whitespace heuristics (Section 4.3) will inherit whatever reading order Layout Reconstruction hands it. The likely direction — grouping same-line spans into one unit before column classification runs, rather than classifying at the raw span level — is a design change to `layout.py`'s algorithm, not a constant tweak, and should go through the same "design before code" discipline as the original Milestone 1 plan.
2. **Finding 2 (narrow sidebar)** is real but lower-severity, and as noted, its "obvious" fix (loosen the balance ratio) directly conflicts with the guard that prevents Finding 1 from being even more common. A durable fix likely wants a smarter corroborating signal, which may be more natural to add once Section Detection exists (Milestone 2) than in Layout Reconstruction alone.

Recommendation: resolve at least Finding 1 — and ideally reconsider the balance-ratio guard in light of Finding 2 — before starting Milestone 2, since Section Detection's correctness depends directly on Layout Reconstruction's reading order. This is a recommendation, not an action taken; no code changes have been made based on it.

---

## 4. Files added in this validation pass

- `resume_engine/tests/golden_corpus/{ats_one_column_plain, canva_style_two_column, overleaf_latex_academic, google_docs_export, academic_cv_multipage, icon_heavy_contact_header, narrow_sidebar_ats_photo, mixed_layout_two_page, dense_long_ats_resume, minimalist_sparse_one_page, right_aligned_dates_ats, canva_docx_table_photo_sidebar}/` — 12 new fixtures, each with `metadata.json` (extended with an optional `template_style` field) documenting its purpose and, where applicable, its confirmed finding.
- `resume_engine/devtools/golden_corpus_report.py` — the validation-pass report script (dev tooling, not a pytest test).
- `resume_engine/tests/test_golden_corpus_extraction.py` — extended to smoke-test fixtures without an `expected_layout.json` (the new 12) rather than requiring one, since several of their "correct" answers are exactly what's under review above.
- This document.

No changes to `extractor.py`, `layout.py`, `pipeline.py`, `document_model.py`, `requirements.txt`, `factory.py`, `interfaces.py`, or any file outside `resume_engine/` and this report.

---

## 5. Addendum (2026-08) — Findings #1 and #2 resolved

Per explicit instruction, Finding #1 was investigated from first principles rather than patched with a threshold tweak. The full design writeup lives in `docs/architecture/ResumeIntelligenceEngine.md` Section 4.2 (implementation note) and Section 12 (Decision Log, entry 6); this addendum records only the outcome and the validation evidence.

**Root cause, restated precisely**: none of the original guards (gap size, line count, line-count balance, y-overlap) measured whether a candidate band actually flowed as its own continuous stream of content down the page, versus only appearing as an occasional companion value attached to some of the other band's rows. Line count and balance ratio are proxies for "how much content," not "how continuously it's distributed" — and both Finding #1 (dates: same line count as a real column, but sparse) and Finding #2 (short sidebar: same line count as a fake column, but dense) were symptoms of relying on that wrong proxy. **They were one bug, not two.**

**Fix**: `layout.py`'s `MIN_BAND_BALANCE_RATIO` guard (line-count ratio) was removed and replaced with a row-pitch-continuity check — the median gap between a band's own consecutive row y-positions, compared between the two candidate bands. A genuine column's rows are spaced at roughly the same cadence as the other column's; a value riding along on only some rows (like a date printed once per job entry, while the surrounding band also has a description line per entry) has a measurably larger internal gap. `MIN_CORROBORATING_LINES` and the y-overlap guard are unchanged — they check different things and remain valid.

**Result, re-running the identical validation methodology (`resume_engine/devtools/golden_corpus_report.py`) against all 22 fixtures**:

| Fixture | Before | After |
|---|---|---|
| `right_aligned_dates_ats` | `two_column` (0.60) — **defect**: dates dislocated to end of document | `ambiguous` (0.35) — reading order confirmed correct, dates stay adjacent to their job entries |
| `narrow_sidebar_ats_photo` | `ambiguous` (0.35) — **defect**: real sidebar misclassified | `two_column` (0.60) — correctly recognized, correct column assignment confirmed |
| All other 20 fixtures | — | **numerically identical** to the original report in Section 1 — zero regressions |

Both fixtures were upgraded from smoke-only to permanent hard-assertion regression fixtures (`expected_layout.json` added to each, including an `expected_span_order_contains` check on `right_aligned_dates_ats` that directly locks in the dates-stay-adjacent-to-their-entries behavior). Two new unit tests were added to `test_layout.py` reproducing each finding's exact geometry. Full suite: 84/84 passing.

**Residual limitation, unchanged from the original design discussion**: a resume where literally every line carries trailing right-aligned content at matching pitch (no interspersed description-only lines) would still be misread as two-column — this needs content-aware reasoning that belongs to Section Detection, not this geometric stage. Recorded in the architecture doc (Section 11) as an accepted gap, not a regression introduced by this fix.

Finding #3 (3-column DOCX table degrading to `ambiguous`) was not a defect and required no change.

---

## 6. Addendum 2 (2026-08) — balance ratio retained, not replaced; extension point added

The initial fix in Section 5 above *replaced* the balance-ratio guard outright with row-pitch continuity. On review, this was reconsidered: dropping a corroborating signal (balance ratio) requires evidence it contributes nothing, not just that a better signal was found for the two specific findings this pass investigated. 22 fixtures isn't that evidence.

**Empirical check before recalibrating**: every candidate split in the corpus that reaches the balance-check stage was instrumented directly:

```
canva_style_two_column   page0: left=8  right=7  balance=0.875
docx_table_sidebar       page0: left=3  right=3  balance=1.000
mixed_layout_two_page    page1: left=5  right=5  balance=1.000
narrow_sidebar_ats_photo page0: left=3  right=20 balance=0.150   <- should ACCEPT (real sidebar)
right_aligned_dates_ats  page0: left=8  right=3  balance=0.375   <- should REJECT (fake column)
two_column_sidebar_pdf   page0: left=8  right=7  balance=0.875
```

Worth stating plainly: **the original `MIN_BAND_BALANCE_RATIO=0.25` never actually blocked the dates false positive** — 0.375 clears 0.25 comfortably. Balance ratio's presence or absence made no difference to Finding #1; pitch continuity was always the signal that had to catch it. This is exactly the kind of evidence the "prove zero value" bar asks for, but on its own, across only 22 fixtures, it doesn't meet it — so balance ratio stays active rather than being removed on the strength of one corpus.

**Change made**: `layout.py`'s corroboration step was restructured from a chain of early-return checks into a small set of independent, named `CorroborationSignal`s (line count, balance, pitch continuity, y-overlap) combined by one explicit policy function (`_evaluate_corroboration`, currently: all must pass). `MIN_BAND_BALANCE_RATIO` was recalibrated from `0.25` to `0.1` — chosen with deliberate margin below the one observed real short-sidebar case (0.15), not tuned tightly to it. Both `MIN_BAND_BALANCE_RATIO` and `MAX_PITCH_RATIO` are now explicitly documented in `layout.py` and the architecture doc (Section 4.2) as **validation-derived, tunable parameters** — not intrinsic properties of resume geometry — with the specific observed data points recorded alongside each constant.

This restructuring is also the concrete **extension point for future semantic corroboration**: a signal like "this candidate band's text looks date/label-heavy rather than prose" (once Section Detection or content classification exists to support it) is one more function appended to `layout.py`'s `CORROBORATION_SIGNALS` list — no change needed to `_classify_page` or the combination policy to add one.

**Re-verified against the full 22-fixture corpus**: every row is numerically identical to Section 5's post-pitch-fix results (`right_aligned_dates_ats` still `ambiguous` 0.35, `narrow_sidebar_ats_photo` still `two_column` 0.60, everything else unchanged) — confirming the restructuring changed *how* the decision is made and documented, not *what* it decides. One new unit test was added (`test_balance_ratio_still_rejects_extreme_imbalance_even_with_matching_pitch`) constructing a case with matching pitch but balance below 0.1, confirming it's still rejected — proof balance ratio is a real, active gate, not a vestigial one. Full suite: 85/85 passing.

**Milestone 2 (Section Detection) planning may now begin**, per the condition set at the top of this report.
