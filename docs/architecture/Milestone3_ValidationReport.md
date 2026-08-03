# Milestone 3 — Validation Report

Status: **Validation pass complete. One critical cross-milestone bug found and fixed (with explicit design review and approval before the fix, not a quick patch), two smaller bugs found and fixed immediately as unambiguous correctness issues, one residual limitation documented and deliberately left unsolved.**

Mirrors the discipline established in `Milestone1_ValidationReport.md`/`Milestone2_ValidationReport.md`: build the real parsers (`ContactParser`, `ExperienceParser`, `ProjectParser`), test them end-to-end against realistic content (not just hand-built unit fixtures), and report what actually happens.

---

## 1. Methodology

- Built `ContactParser`, `ExperienceParser`, `ProjectParser` per the approved Milestone 3 plan, with unit tests for each against hand-built `Section`/`DocumentModel` fixtures (the same style Milestones 1-2 used).
- Additionally, and this is what surfaced the milestone's main finding: tested each parser **end-to-end** through the real `PdfDocxExtractor` → `ColumnAwareLayoutReconstructor` → `HeuristicSectionDetector` pipeline against realistic multi-entry resume content — something the unit tests alone, using hand-constructed `Section` objects, could not have caught, since they bypass real Section Detection entirely.
- Added 2 new golden-corpus fixtures (`full_entity_resume_pdf`, `single_entry_sections_pdf`) with `expected_entities.json`, extending the format Milestones 1-2 established.
- Extended `resume_engine/devtools/golden_corpus_report.py` with entity-parsing counts across the full 31-fixture corpus (not just the 2 new ones), auto-flagging any section detected but yielding zero parsed entries.

## 2. Findings

### Finding 1 (CRITICAL — confirmed cross-milestone bug, fixed with a full design review): Section Detection fragments multi-entry sections

**Observed**: `ProjectParser`, run end-to-end against a realistic two-project resume, returned **zero entities**. Investigation traced this to `HeuristicSectionDetector` (Milestone 2): its structural header pre-filter fires on bold/large lines *inside* a section (a project's title line, a job's "Company, Role" line) exactly as readily as on true section boundaries, since it has no concept of "entry." Verified this affects both `ProjectParser` and `ExperienceParser`, and that whether it "accidentally" self-heals depends entirely on whether the entry-header text happens to resolve back to the same canonical label via Section Detection's Tier 4 embedding fallback (e.g. "Acme Corp, Senior Engineer" coincidentally embeds close to "experience"; "Widget Factory, Product Designer" — equally realistic — does not, and gets permanently lost).

**Why this wasn't caught during Milestone 2's own validation**: every Milestone 2 fixture had bold text only at true section boundaries; none exercised a bold line *inside* a section's body, because that's an Entity Parsing (Milestone 3) concept Section Detection's own test corpus had no reason to include.

**Process**: this was treated as requiring the same rigor as the Milestone 1/2 architectural fixes — stopped mid-implementation, investigated whether a purely geometric fix existed at the Section Detection layer (it doesn't: neither indentation nor confidence tier distinguishes a genuine one-off ambiguous section from a repeating entry sub-header), presented the finding and three options to the user, got explicit direction to design a proper fix, wrote up the design (repetition as the discriminating signal, verified against Milestone 2's own `ambiguous_header_pdf` fixture before proposing it), and only implemented after approval.

**Fix**: `pipeline._absorb_repeated_unknown_entries`, called before the existing `_group_sections_by_label` — 2+ consecutive `"unknown"` sections immediately following a real section, with no other real section in between, are absorbed into it. `sections.py` itself is untouched.

**Result**: `full_entity_resume_pdf` (2 experience entries, 2 project entries) now parses all 4 entries correctly. `ambiguous_header_pdf`'s "Languages" (a single, isolated `"unknown"`) is unaffected — confirmed via a direct regression test.

**Documented residual limitation, not claimed solved**: a section with exactly one entry still fragments (`single_entry_sections_pdf`, deliberately included in the corpus to demonstrate this rather than hide it) — one data point can't be distinguished from a genuine standalone ambiguous section by geometry alone.

### Finding 2 (HIGH — confirmed bug, fixed immediately): date regex false-matched a role title's last word as a month

**Observed**: `"Senior Engineer 2021 - Present"` parsed as date range `"Engineer 2021 - Present"` — `dates.py`'s regex used a generic `[A-Za-z]{3,9}` class for "month-like word," which matched *any* word directly followed by a year, not just real month names. This corrupted both the extracted date (start date lost) and the role/company split (the corrupted "match" text, when stripped from the header line, left the wrong remainder to split on).

**Fix**: replaced the generic word-length class with an explicit month-name alternation (`Jan(?:uary)?|Feb...`). Fixed immediately as an unambiguous correctness bug — the same standard already applied to comparable findings in Milestones 1 and 2.

### Finding 3 (MEDIUM — confirmed, expected, not a defect): job-title gazetteer coverage gaps produce reasonable-but-imperfect role/company splits

**Observed**: `"Widget Factory, Product Designer"` — where "Product Designer" isn't in `job_title_gazetteer.py`'s curated list — falls through to the documented fallback ("first segment = role"), producing `role="Widget Factory"`, `company="Product Designer"` (swapped). Not a bug: this is the exact, designed fallback behavior for a gazetteer miss, and gazetteer coverage is an accepted, ongoing maintenance cost per the architecture doc's own risk register (Section 11). Noted here for completeness, not flagged as an action item.

## 3. What this means for Milestone 5

Finding 1's residual limitation (single-entry sections) is the same underlying gap as two Milestone 2 findings already on record (the contact leading-block fold being position- not layout-aware, and short ALL-CAPS body words being misread as headers) — all three stem from Section Detection having no way to say "this looks like a header but isn't really a boundary here" without content-aware corroboration. A future generalized fix, once a later stage has content-aware signals available, could plausibly address all three at once. Not designed or attempted here.

## 4. Files added in this validation pass

- `resume_engine/tests/golden_corpus/{full_entity_resume_pdf, single_entry_sections_pdf}/` — 2 new fixtures with `metadata.json` + `expected_entities.json`.
- `resume_engine/devtools/golden_corpus_report.py` — extended with entity-parsing output.
- `resume_engine/tests/test_golden_corpus_extraction.py` — extended to check `expected_entities.json`.
- `resume_engine/tests/golden_corpus/README.md` — documents `expected_entities.json`.
- `pipeline.py` — `_absorb_repeated_unknown_entries` (Finding 1's fix).
- `dates.py` — the month-name regex fix (Finding 2), part of this milestone's own new code, not a change to a prior milestone.
- This document.

No changes to `extractor.py`, `layout.py`, `sections.py`, `document_model.py`, `interfaces.py`, `registry.py`, or any file outside `resume_engine/` and this report.
