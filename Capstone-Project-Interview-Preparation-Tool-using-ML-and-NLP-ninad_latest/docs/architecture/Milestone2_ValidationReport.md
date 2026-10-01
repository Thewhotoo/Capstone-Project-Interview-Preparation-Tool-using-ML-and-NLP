# Milestone 2 — Validation Report

Status: **Validation pass complete. One critical bug found and fixed immediately (case-sensitivity). Several genuine findings documented, deliberately left unpatched, pending a decision on priority before Milestone 3 begins.**

Mirrors the discipline established in `Milestone1_ValidationReport.md`: run the real `HeuristicSectionDetector` across the full golden corpus (all 29 fixtures — the 22 from Milestone 1 plus 7 new ones built specifically to stress heading detection), report what actually happens, and distinguish bugs fixed immediately from genuine design trade-offs surfaced for a decision.

---

## 1. Methodology

- Added 7 new fixtures (`every_section_pdf`, `missing_sections_pdf`, `nonstandard_headers_pdf`, `ambiguous_header_pdf`, `docx_heading_styles`, `repeated_running_header_pdf`, `creative_header_sbert_pdf`), each targeting a specific tier or failure mode named in the architecture doc's Section 4.3, with hand-verified `expected_sections.json` fixtures (a new format, documented in `golden_corpus/README.md`, mirroring `expected_layout.json`'s role from Milestone 1).
- Extended `resume_engine/devtools/golden_corpus_report.py` to also run `HeuristicSectionDetector` across every fixture (not just the 7 new ones) and report section labels, confidence, and unknown-section counts.
- Extended `test_golden_corpus_extraction.py` to assert against `expected_sections.json` where present; all 7 new fixtures pass as hard regression gates, not smoke-only.

## 2. Findings

### Finding 1 (CRITICAL — confirmed bug, fixed immediately): gazetteer fuzzy matching was case-sensitive

**Observed**: ALL-CAPS headers ("CONTACT", "SKILLS", "EXPERIENCE", "EDUCATION") — one of the most common real-world resume header conventions, and exactly the pattern `_is_candidate_header_line`'s all-caps signal was built to recognize — scored as low as 13–25 (of 100) against the gazetteer's Title-Case aliases ("Contact", "Skills", ...), because `rapidfuzz`'s `token_sort_ratio` compares strings literally, case included. This forced every all-caps header through the unreliable Tier 4 embedding fallback (or straight to `"unknown"`) instead of matching confidently at Tier 2.

**Fix**: added `processor=str.lower` to the `rapidfuzz.process.extractOne` call in `_fuzzy_match_label` (`sections.py`). Confirmed via the full corpus re-run: `ats_one_column_plain`, `dense_long_ats_resume`, and `right_aligned_dates_ats` (all-caps-header ATS templates) jumped from 0.4 minimum section confidence to 0.9 with no other change.

**Why fixed immediately rather than just flagged**: this is an unambiguous correctness bug (case sensitivity in string comparison), not a design trade-off between competing valid behaviors — the same standard already applied to the `WRatio`→`token_sort_ratio` scorer fix and the `EMBEDDING_SIMILARITY_FLOOR` recalibration found earlier in this same milestone's implementation (both documented in `sections.py`'s comments directly).

### Finding 2 (MEDIUM — confirmed limitation): short ALL-CAPS body words get misread as header candidates

**Fixture**: `narrow_sidebar_ats_photo` — a Skills sidebar listing "Python", "SQL" as separate short lines.

**Observed**: `"SQL"` (short, all-caps) independently satisfies `_is_candidate_header_line`'s all-caps signal, gets run through the cascade, matches nothing confidently, and becomes its own spurious `"unknown"` section — splitting it out of the Skills content it's actually part of.

**Root cause**: the all-caps signal (added deliberately in Phase 1 to catch real ALL-CAPS section headers like "EXPERIENCE") has no way to distinguish a genuine header from a short all-caps *word* that's just normal content (an acronym: "SQL", "AWS", "API", "CI/CD"). Word count alone (`MAX_HEADER_WORDS`) doesn't help — single-word acronyms are exactly as short as single-word headers.

**Assessment**: real, not yet fixed. A plausible future direction is requiring some additional corroboration for the all-caps signal specifically (e.g. also being visually isolated by whitespace, or checked against a small stoplist of common acronyms) — not implemented here since it would be tuned against evidence this milestone's corpus doesn't yet have enough of.

### Finding 3 (MEDIUM — confirmed limitation): a name/title banner in the *main* column of a two-column layout isn't protected by the leading-block contact fold

**Fixtures**: `canva_style_two_column`, `mixed_layout_two_page`.

**Observed**: the contact special case's "fold an unrecognized header into contact before the first real section" rule (Section 4, milestone plan) only helps at the very *start* of the linearized document. In a two-column template where the sidebar (read first, column-major) starts immediately with a real section ("Skills"), `found_real_section` flips to `True` before the reader ever reaches the main column's name banner — so when that banner is reached, it's treated as appearing *after* a real section and becomes its own spurious `"unknown"` entry instead of folding into contact.

**Assessment**: real, not yet fixed. This is a natural consequence of the leading-block rule being defined in terms of *document position* rather than *visual position* — column-major linearization (correct and frozen, per Milestone 1) means "first in reading order" and "visually at the top of the page" aren't always the same line. Worth reconsidering alongside Finding 2 in a future pass, since both are instances of the same underlying question ("is this candidate header actually structural, or should it fold into something else").

### Finding 4 (LOW — confirmed gap, not a bug): the 7-label canonical set doesn't cover every real section type

**Fixtures**: `academic_cv_multipage`, `overleaf_latex_academic` (both from the Milestone 1 corpus, exercised by Section Detection for the first time here).

**Observed**: "Publications" fuzzy-matches `education` at 67 (Tier 3, low confidence) via shared vocabulary with "Academic History"/"Academic Background"; "Teaching" falls through to Tier 4 and matches `education` at 0.72 similarity; "Awards" scores too low everywhere and correctly becomes `"unknown"`.

**Assessment**: not a bug — the gazetteer (`section_gazetteer.py`) simply has no canonical label for publications/teaching/awards content, which is genuinely common in academic CVs specifically. Tier 3/4 doing their designed job (assign the *closest* available label at low confidence) is working as intended; the low confidence score is the honest signal that the assignment is a stretch. A candidate future addition (a `publications` or `awards` canonical label) is a gazetteer/label-set expansion decision, not made unilaterally here.

### Finding 5 (already documented, reconfirmed): `repeated_running_header_pdf`'s known limitation

Unchanged from the milestone plan's Risk #2, written before implementation and confirmed exactly as anticipated: a repeated running header on page 2 (after a real section already started) fragments the Experience section's continuation into a spurious `"unknown"` entry. See `repeated_running_header_pdf/metadata.json` for full detail — this is the most consequential open finding from this pass, since running headers/footers are a common real template pattern and the effect (splitting entity content across two Section buckets) would concretely hurt Milestone 3's `ExperienceParser`.

## 3. What this means for Milestone 3

Findings 2, 3, and 5 all stem from the same underlying gap: **the current design has no way to say "this line is header-shaped but isn't really a section boundary here" beyond the single, position-based leading-block rule.** A more general fix (e.g., requiring a short header-like line to be corroborated by what follows it — real body content of a *different* apparent type — before committing to a new section) would likely address Findings 2, 3, and 5 together, the same way row-pitch continuity addressed two seemingly separate Layout Reconstruction findings at once. That generalization is not designed or implemented here — flagged as the natural next investigation, not started without approval.

Finding 4 is a scope/coverage decision (expand the gazetteer/label set), independent of the others.

None of Findings 2–5 corrupt content the way Milestone 1's Finding 1 did (dates dislocated from their entries) — worst case here is an extra low-confidence `"unknown"` bucket that a future Validation Layer (Milestone 6) or a human reviewing low-confidence sections would immediately spot, not silent data loss. Recommendation: proceed to Milestone 3 with these findings recorded, revisit the generalized fix if `ExperienceParser`'s own validation surfaces them as a practical blocker.

## 4. Files added in this validation pass

- `resume_engine/tests/golden_corpus/{every_section_pdf, missing_sections_pdf, nonstandard_headers_pdf, ambiguous_header_pdf, docx_heading_styles, repeated_running_header_pdf, creative_header_sbert_pdf}/` — 7 new fixtures with `metadata.json` + `expected_sections.json`.
- `resume_engine/devtools/golden_corpus_report.py` — extended with section-detection output (not a new script).
- `resume_engine/tests/test_golden_corpus_extraction.py` — extended to check `expected_sections.json` where present.
- `resume_engine/tests/golden_corpus/README.md` — documents the new `expected_sections.json` format.
- `sections.py` — the case-sensitivity fix (Finding 1) and the earlier-in-milestone `WRatio`→`token_sort_ratio` and `EMBEDDING_SIMILARITY_FLOOR` fixes, all documented inline.
- This document.

No changes to `extractor.py`, `layout.py`, `pipeline_trace.py`, `document_model.py`, `interfaces.py`, `factory.py`, or any file outside `resume_engine/` and these two docs.
