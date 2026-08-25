# Golden Corpus

The regression benchmark suite for the Resume Intelligence Engine. See
`docs/architecture/ResumeIntelligenceEngine.md` Section 9 (Testing
Strategy).

This corpus is a **benchmark suite, not just a folder of sample resumes**
— every fixture is annotated well enough that a test failure tells you
*what kind* of resume regressed, not just that something did.

No fixtures existed as of Milestone 0. Milestone 1 added the first ten,
scoped to Document Extraction + Layout Reconstruction. Milestone 2 added
seven more, scoped to Section Detection (content-heavy fixtures exercising
the 4-tier heading cascade). This document defines the format every
fixture must follow, so the corpus grows consistently rather than being
retrofitted with metadata later.

## Fixture layout

```
golden_corpus/
  <fixture_id>/
    resume.pdf | resume.docx     # the input file
    metadata.json                 # required — see schema below
    expected_layout.json          # added in Milestone 1 (see below) — the Extraction +
                                     Layout Reconstruction regression gate, until the
                                     heavier snapshot files below exist
    expected_sections.json        # added in Milestone 2 (see below) — the Section
                                     Detection regression gate
    expected_profile.json         # hand-verified expected CandidateProfile JSON (Milestone 3+)
    expected_trace.json           # added from Milestone 6 onward (full PipelineTrace snapshot)
    notes.md                       # optional — free-text context metadata.json can't capture
```

### `expected_layout.json` (Milestone 1)

`expected_profile.json`/`expected_trace.json` don't exist until later
milestones (there's no `CandidateProfile` or full trace to snapshot yet),
so each Milestone-1-era fixture that exercises real content gets this
lighter, hand-verified file instead — the actual regression gate for
`test_golden_corpus_extraction.py`:

```json
{
  "layout_mode": "two_column",
  "layout_confidence_min": 0.6,
  "span_count_min": 12,
  "hyperlink_count": 0
}
```

Two fixtures don't get this file at all — a fixture whose `metadata.json`
sets `"expects_extraction_failure": true` (a corrupt file, a
scanned/image-only PDF) asserts that `PdfDocxExtractor.extract()` raises
`ExtractionFailure`, not a layout result. Two optional keys exist for
fixtures where the *order* of extraction matters: `extraction_notes_contains`
(a string expected somewhere in `DocumentModel.extraction_quality.notes`)
and `expected_span_order_contains` (a list of span texts expected to appear
in that relative order, not necessarily contiguous).

### `expected_sections.json` (Milestone 2)

The Section Detection regression gate, in the same spirit as
`expected_layout.json`:

```json
{
  "expected_labels_in_order": ["contact", "experience", "education"],
  "min_confidence_by_label": {"experience": 0.85, "education": 0.85},
  "max_confidence_by_label": {"skills": 0.5},
  "reason_must_contain": {"experience": "docx_style_match"},
  "labels_must_be_absent": ["projects", "certifications"]
}
```

Only `expected_labels_in_order` is required — it's checked against the
exact ordered list of labels `HeuristicSectionDetector.detect()` returns
(before the pipeline's list→dict merge, so a label detected twice, e.g.
across a page break, appears twice here). The other keys are optional,
per-label assertions. A fixture can have `expected_layout.json`,
`expected_sections.json`, `expected_entities.json`, any combination, or
none (validation-pass fixtures with none are smoke-tested only — see
`test_golden_corpus_extraction.py`).

### `expected_entities.json` (Milestone 3)

The Entity Parsing regression gate, checked against `sections` AFTER
`pipeline.py`'s section-merge/absorption logic runs (i.e. what
`ContactParser`/`ExperienceParser`/`ProjectParser` actually receive, not
`HeuristicSectionDetector`'s raw per-header-hit list):

```json
{
  "contact": {
    "entity_count": 1,
    "expected_fields": {"candidate_name": "Jordan Example", "email": "jordan.example@test.invalid"}
  },
  "experience": {
    "entity_count": 2,
    "expected_roles": ["Senior Engineer", "Software Engineer"],
    "expected_companies": ["Acme Corp", "Beta Inc"]
  },
  "projects": {
    "entity_count": 2,
    "expected_titles": ["AI SOC Analyst", "Task Tracker"],
    "technologies_contains": {"AI SOC Analyst": ["Python", "Redis", "Docker"]}
  }
}
```

Each of `contact`/`experience`/`projects` is independently optional --
include only the parsers a given fixture is meant to exercise.
`entity_count` is the only required key per included parser; the rest are
optional, more specific assertions. A fixture whose `entity_count` is
deliberately `0` (e.g. `single_entry_sections_pdf`) is asserting a known,
documented limitation, not a defect -- see that fixture's `metadata.json`.

## `metadata.json` schema

```json
{
  "fixture_id": "two_column_sidebar_pdf",
  "layout_type": "two_column",
  "document_type": "pdf",
  "synthetic_or_real": "synthetic",
  "difficulty": "medium",
  "known_edge_cases": [
    "narrow left sidebar with Skills/Contact/Certifications",
    "wide right column with Experience/Projects"
  ],
  "notes": "Regression fixture for the k=2 column-clustering gap-analysis heuristic (architecture doc Section 4.2).",
  "added_in_milestone": 1
}
```

| Field | Values | Purpose |
|---|---|---|
| `fixture_id` | matches the directory name | stable identifier for referencing this fixture in test names/CI output |
| `layout_type` | `single_column` \| `two_column` \| `ambiguous` | which Layout Reconstruction path this fixture exercises |
| `document_type` | `pdf` \| `docx` | which Document Extraction path this fixture exercises |
| `template_style` | free-text slug, e.g. `ats_plain`, `canva`, `latex_academic` | optional; the real-world resume template family this fixture emulates (introduced in the Milestone 1 validation pass) |
| `synthetic_or_real` | `synthetic` \| `anonymized` | **never `real`** — no real candidate PII is ever committed to this corpus; `anonymized` means real-resume-*derived* but with every identifying detail replaced |
| `difficulty` | `easy` \| `medium` \| `hard` | how much of the cascade/heuristic machinery this fixture is expected to stress |
| `known_edge_cases` | list of short strings | the specific thing(s) this fixture exists to catch a regression in |
| `notes` | free text | anything `known_edge_cases` doesn't capture cleanly |
| `added_in_milestone` | integer | which milestone introduced this fixture, for tracing corpus growth over time |
| `expects_extraction_failure` | `true` \| omitted | optional, Milestone 1+; when `true`, the fixture has no `expected_layout.json` and the test instead asserts `PdfDocxExtractor.extract()` raises `ExtractionFailure` |

## Conventions

- Use obviously-fake names, emails, and phone numbers in every fixture (e.g. `jordan.example@test.invalid`) — never real personal data, even in `anonymized` fixtures.
- One fixture should exist to stress exactly the case its `known_edge_cases` describes — prefer several small, sharply-scoped fixtures over one resume trying to cover everything.
- `expected_profile.json` (and, from Milestone 6, `expected_trace.json`) is the actual regression gate (Section 9's golden-file tests) — `metadata.json` exists to make a failure *interpretable*, not to be asserted against directly.
- The initial ~15-20 fixture corpus (Milestone 0's own remaining deliverable per the architecture doc's roadmap) should cover, at minimum: single-column PDF, two-column PDF (sidebar + main), DOCX, a resume with every canonical section, a resume missing several sections, nonstandard section names, one genuinely ambiguous/unknown section header, nested bullets, hyperlinked (not visible-text) contact links, and a scanned/image-only PDF (exercises the typed extraction-failure path, not a parse attempt).
