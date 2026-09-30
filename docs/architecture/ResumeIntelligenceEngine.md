# Resume Intelligence Engine — Architecture & Design Review

Status: **Approved architecture — Revision 2, incorporating decisions from design review. Ready for one final read-through before Milestone 0 begins. No production code written against this document yet.**
Scope: Resume text/layout extraction → Candidate Profile JSON. Replaces `candidate_profile_generator.py`'s Gemini call.
Out of scope (unchanged by this doc): Resume Discussion (`conversation_engine.py`, `topic_pool.py`, `planner.py`), evaluation, the dashboard, the Technical Interview module. This engine's only obligation to those systems is to keep producing the same `CandidateProfile` shape they already consume.

This document is the audit + architecture deliverable for the Resume Intelligence Engine. It is organized as: (1) audit of the system being replaced, (2) the contract that must survive, (3) architecture options and the recommendation, (4) stage-by-stage design, (5) the plugin parser architecture, (6) the PipelineTrace observability system, (7) confidence scoring, (8) validation layer, (9) testing strategy, (10) milestone roadmap, (11) risks, (12) the decision log from design review. Nothing here is implemented. Stop points are marked explicitly.

**Revision note**: Revision 1 of this document was reviewed against five explicit design decisions plus a proposed developer/debug mode. All five decisions were resolved and the debug mode was approved and promoted to a first-class architectural component (Section 6). Section 12 records exactly what changed and why. Everything in Sections 1-11 below already reflects the resolved decisions — there is no separate "old" and "new" content to reconcile while reading.

---

## 1. Audit of the Current Gemini Pipeline

### 1.1 What exists today

```
Upload (PDF/DOCX/DOC/TXT)
  → app.py:371 classify_resume()
  → PDF: candidate_profile_generator.extract_text_from_pdf()  [PyMuPDF, page.get_text("text"),
         falls back to get_text("blocks") reordering if a garbled-text heuristic trips]
  → non-PDF: src.parser.extract_text()  [separate, untouched legacy extractor]
  → generate_candidate_profile(text)  [ONE Gemini 2.5 Flash call, response_schema=CandidateProfile
         (Pydantic, native structured output), temperature=0.1, retried up to 3x on transient
         errors, plus one dedicated retry if skills == []]
  → _post_process()  [fuzzy domain matching, level normalization, confidence clamp,
         technical_topics shape-gate: drop entries that don't cite exactly one origin]
  → stored in-process: _candidate_profiles[session_id] = profile   (dict, no DB, lost on restart)
  → profile_to_frontend_format(profile)  → flat dict → frontend
```

Key existing engineering facts worth preserving conceptually:
- Text is extracted first; nothing is sent to Gemini as raw bytes/multimodal. **This means a deterministic replacement only has to out-compete Gemini's *reasoning over already-extracted text*, not its document understanding** — the layout-to-text problem is already solved today by PyMuPDF, just solved leniently (no structure preserved, only reading-order text).
- The system already assumes structured-output non-determinism even with `response_schema` enforced and `temperature=0.1`: there's a 3-stage JSON-parse fallback, a truncation detector, and a full post-hoc normalization layer (`_post_process`). Gemini is not treated as a black box that "just returns the schema" — the code already distrusts it. A deterministic engine removes an entire class of failure (truncation, hallucinated JSON, non-XOR technical_topics) by construction, not by defensive parsing.
- `traceability.py` already validates *internal consistency* of Gemini's output (does a cited `originating_project` actually exist elsewhere in the same profile). It does not validate against the source resume text. This is a validation pattern worth reusing, not replacing.
- `confidence` today is Gemini's self-reported confidence in its own `predicted_domain` guess, clamped to `[0,1]`. Nothing downstream thresholds on it. This is the single biggest opportunity: today's "confidence" is decorative; the new engine's confidence must be genuinely load-bearing and explainable (Section 7).

### 1.2 Dependency map (condensed — full detail gathered via codebase audit)

| Field | Effectively required? | Consumers | Breaks how, if missing |
|---|---|---|---|
| `candidate_name` | No | frontend display | Cosmetic fallback `"Candidate"` |
| `contact_details.*` | No | frontend display only | Cosmetic |
| `skills[]` | Soft | `topic_pool` (none directly — see `technical_topics`), frontend, v1 MCQ gen | Triggers a retry in old pipeline; new engine has no retry concept, so must maximize recall here in one pass |
| `education[]` | **No downstream consumer at all** besides frontend display | — | Never becomes an interview question anywhere in the codebase today |
| `experience[].role` | **Yes, per-entry** | `topic_pool.py` skips any entry with empty `role`; v1 requires `role AND company` | Entry produces zero questions, silently |
| `experience[].company/duration/summary` | No | display, `_calculate_total_years` regex on `duration` | Degrades gracefully to `0` years |
| `projects[].title` | **Yes, per-entry** | `topic_pool.py`, `traceability.py` (exact case-insensitive match) | Whole project silently dropped from every question source |
| `projects[].summary/technologies/concepts` | No | question phrasing, grounding | Empty list/string just means fewer question variants for that project |
| `projects[].interview_seeds[]` | **Highest-value field in the whole schema** | `topic_pool.py` Priority-1 `PROJECT_DEEP_DIVE` specs, one per unique seed | If empty, that project only gets a generic overview question instead of its best question |
| `certifications[]` | No (per-item, empty strings skipped) | `topic_pool.py`, `traceability.py` | Skipped entries |
| `predicted_domain` | Soft | fallback question bank routing (`_DOMAIN_TO_DISCUSSION`, only 4 of 10 domains mapped) | Falls back to `"Software Engineer"` |
| `experience_level` | Soft | display, years-estimate fallback | Cosmetic + fallback estimate |
| `interview_blueprint.technical_topics[]` | Soft, but validated **twice** (shape-gate at generation, substance-gate — `traceability.validate_technical_topic_origin` — at planning) | `topic_pool.py` Priority-5 `SKILL_IN_CONTEXT` specs | Untraceable entries silently rejected into `self.rejected` (audit trail, never a crash) |
| `interview_blueprint.resume_verification_topics` | **Dead field** | none found anywhere | Generated by Gemini today, read by nobody |
| `interview_blueprint.starting_difficulty` | **Effectively dead** beyond its own normalization | none found beyond `_post_process` | — |
| `interview_blueprint.estimated_strengths/weaknesses` | Soft, tie-breaker only | `topic_pool.touches_weakness()` — reorders, never filters | — |
| `confidence`, `resume_summary` | No | display only | Cosmetic |

**The one hard invariant that actually breaks the product**: if `TopicPool` builds **zero** specifications at all — no project with a title, no experience with a role, no non-empty certification, no traceable technical topic — `conversation_engine.start_conversation()` returns a 400 and the session never starts. Every other field is either cosmetic or degrades a single question family, never the whole session.

**Design consequence**: the new engine's single most important correctness target is *"never produce a profile with zero usable specs for a resume that has real content."* Education, contact details, certifications, domain/level labels are all real value but are non-critical paths — they can and should ship in early milestones with looser tolerances than Experience/Project/interview-seed extraction, which must be excellent from Milestone 1 onward.

### 1.3 The exact contract to preserve

The replacement's output type is the existing Pydantic `CandidateProfile` (`candidate_profile_generator.py:183-201`), unchanged, field-for-field, including the "empty string / empty list as the missing-value sentinel, never `None`" convention every downstream consumer already relies on (no code anywhere does an `is None` check on a profile field — it's always truthiness or `.get(..., default)`). This is not a stylistic nicety — a single stray `None` where a `.get(...) or []`-guarded frontend expects `[]` would be the one class of regression that's easy to introduce and easy to miss. **The new engine must construct a `CandidateProfile` instance (or an equivalently-shaped dict) and nothing downstream should be able to tell it apart from today's Gemini output**, except by being more consistent.

`interview_seeds` deserves special design attention (Section 4.4, Section 10 Milestone 4) because it is Gemini doing real synthesis today — inventing a plausible interview question from a project description — not extraction. A deterministic engine cannot "invent" a question the way an LLM can; it has to generate seeds via templates grounded in what was actually extracted (technologies + concepts + summary), which is a different and more constrained kind of output. This is flagged as a design risk in Section 11 and has its own dedicated milestone rather than being folded into general parser work.

---

## 2. Architecture

### 2.1 The proposed pipeline shape (approved, with amendments)

**Approved exactly as proposed in design review**: preserving layout, typography, and document structure early is the foundation the rest of the engine builds on, and remains unchanged from the original proposal.

Two structural amendments, both because the current text-only extraction throws away information the new engine needs:

**Amendment 1 — Document Extraction must preserve layout metadata, not just text.** PyMuPDF's `get_text("text")` (today's approach) throws away font size, bold/weight, and bounding boxes — exactly the signals needed for reliable Section Detection. `get_text("dict")` returns spans with `bbox`, `size`, `font`, `flags` (bold/italic bit). The new engine's Document Extraction stage must retain this, producing a `DocumentModel` (list of positioned, styled text blocks), not a string. This is the single most important departure from today's code.

**Amendment 2 — Layout Reconstruction (column resolution) must run *before* Section Detection, as its own stage, not folded into extraction.** Today's `_needs_block_fallback` heuristic already hints at this problem (multi-column resumes read out of order) but only produces a flat re-ordered string. The new engine needs the column structure to survive as structure — e.g., "this resume has a narrow left sidebar (Skills, Contact, Certifications) and a wide right column (Experience, Projects)" is itself a useful signal, not just a reading-order fix.

Revised pipeline:

```
PDF / DOCX
  ↓
[1] Document Extraction        → DocumentModel (styled, positioned blocks; per-page)
  ↓
[2] Layout Reconstruction       → LinearizedDocument (columns resolved, single reading order,
                                     column provenance kept: which column each block came from)
  ↓
[3] Section Detection           → list[Section] (label, block range, confidence)
  ↓
[4] Entity Parsers (plugin-registered, per-section — no inter-dependency at this stage)
      ContactParser   EducationParser   ExperienceParser
      ProjectParser   SkillsParser      CertificationParser
  ↓
[5] Cross-Reference Pass        → resolves things no single-section parser can:
                                     - skills mentioned inline in Project/Experience bullets
                                       but not in the Skills section ("demonstrated" skills)
                                     - interview_seed synthesis (needs Project + Skills + a
                                       template bank together)
  ↓
[6] Normalization                → canonical dates, deduped/aliased technology names,
                                     unicode/whitespace cleanup, title casing
  ↓
[7] Validation                   → list[Observation] (reusable, see Section 8)
  ↓
[8] Confidence Scoring            → attaches confidence + explanation to every entity
  ↓
CandidateProfile JSON (identical shape to today's Gemini output)
```

Every stage above is wrapped by the `PipelineTrace` mechanism (Section 6) — this is not drawn as a separate pipeline stage because it isn't one; it's an optional observer attached to each of the eight stages above, never a ninth stage with its own position in the data flow.

Stage [5] is the one real structural addition beyond the original sketch, and it exists because two of the schema's most valuable fields — "skills demonstrated in projects" (today only surfaced in a diff computed at *discussion* time, `discussion_engine.py:1203-1207`, not in the profile itself) and `interview_seeds` — genuinely require more than one section's data at once. Keeping every other parser strictly single-section-scoped is what keeps the architecture modular and testable; Stage 5 is the one place cross-section reasoning is allowed to live, so it doesn't leak into the others.

Stage [4] is now explicitly a **plugin registry**, not six hardcoded function calls — see Section 5.

### 2.2 Why not other architectures

**Rejected: single monolithic regex/NLP pass over raw text (today's non-Gemini alternative most people reach for first).** Loses positional/style information immediately, so section boundaries become a pure string-matching guess with no font-size or whitespace corroboration. This is strictly worse than what PyMuPDF already gives for free via `get_text("dict")`, so there's no reason to throw that information away before parsing.

**Rejected: full ML-model pipeline (fine-tuned resume-specific NER/token-classification model, e.g. train a BERT sequence-tagger over section/entity labels).** This is the "increasingly complex heuristics" direction the requirements explicitly warn against, inverted — it would replace one opaque non-deterministic dependency (Gemini) with another (a trained tagger with its own failure modes, its own retraining burden, and non-trivial labeled-data requirements the project doesn't currently have — there is no existing resume-parsing training set in this repo, unlike the evaluator models which do have one). **Where the codebase already has trained local models available (`sentence-transformers`, already in `requirements.txt` and already used by the ResumeDiscussion evaluators) they are used surgically, not as the backbone** — see Section 4 for the specific places this is justified (fuzzy technology/skill matching, semantic section-header matching as a *fallback*, and location corroboration — all closed-set or nearest-neighbor comparisons, never open-ended extraction).

**Rejected: table-based / rule-engine-only with zero statistical components.** Purely deterministic string/regex matching is the right *default*, but a few sub-problems (which of two lines is "Company" vs "Role" when order varies; whether "React Native" and "React" should be treated as distinct skills) are genuinely fuzzy-matching problems where a small embedding model measurably outperforms a fixed edit-distance threshold, at zero marginal API cost and full local determinism (same model weights, same output, every time — this is the sense in which "deterministic" is used throughout this document: no network call, no sampling, reproducible given the same input and the same pinned model version).

**Approved position: a deterministic core (regex, gazetteers, layout heuristics, `dateutil` parsing) doing the large majority of the work, with SBERT embeddings — already a project dependency, and now the engine's *only* statistical/ML component after design review — used only for well-scoped fuzzy-matching and disambiguation sub-tasks where they measurably help, never for structural decisions like section boundaries or entity existence.** This matches the project's own precedent: `ResumeDiscussion_v2.md` NFR3 already commits to "deterministic where it matters... controlled randomness for tie-breaking... is acceptable and documented" for the discussion engine. This document adopts the identical philosophy for parsing, and design review further narrowed the ML surface area to SBERT alone (Section 10, Decision 4) rather than SBERT plus spaCy.

**Gemini as a temporary Shadow Mode QA tool — resolved, with hard constraints (Decision 2).** The requirement is to *permanently* remove the Gemini dependency, and the design below does that — Gemini is not called anywhere in the production/runtime path of the recommended architecture. Design review approved keeping a temporary Gemini codepath alive **only** as **Shadow Mode**, a Milestone 0 development/QA tool, under the following hard constraints, which apply for the entire lifetime of Shadow Mode and must be enforced in code, not just convention:

- Shadow Mode runs **only** in developer/test tooling (the comparison harness), never in any code path reachable from a real user request.
- Gemini's output in Shadow Mode may be used to: compare against the new engine's output field-by-field, flag fields the new engine produced nothing for, and speed up building golden-corpus expected-output fixtures.
- Gemini's output in Shadow Mode must **never**: auto-fill a missing field in the deterministic engine's output, overwrite or merge into any deterministic parser result, or be treated as ground truth without a human explicitly reviewing and accepting the specific discrepancy into a golden fixture.
- There is no code path, feature flag, or fallback condition anywhere in the design in which Gemini's output reaches a real `CandidateProfile` returned to a real user. If the deterministic engine fails or produces a low-confidence profile, the correct behavior is to surface that honestly (low confidence, validation observations, or a typed extraction failure) — never to silently substitute Gemini's answer.
- Shadow Mode, the harness that runs it, and the Gemini call it depends on are explicitly temporary development infrastructure, documented as such in code (module-level docstring stating removal is required at Milestone 7, not optional cleanup), and physically deleted — not merely disabled — at Milestone 7 (Section 10).

---

## 3. Data Structures

### 3.1 Document & Section Model (engine-internal — never seen by downstream consumers)

```python
@dataclass
class TextSpan:
    text: str
    bbox: tuple[float, float, float, float]   # x0, y0, x1, y1
    font_size: float
    is_bold: bool
    page_num: int
    column_index: int              # set by Layout Reconstruction

@dataclass
class DocumentModel:
    spans: list[TextSpan]
    hyperlinks: list[tuple[str, tuple[float,float,float,float], int]]  # (url, bbox, page)
    page_count: int
    source_format: Literal["pdf", "docx"]

@dataclass
class Section:
    label: str                      # canonical: "experience", "projects", "education", ...
    raw_header_text: str             # what was actually printed, e.g. "Professional Experience"
    spans: list[TextSpan]            # the spans belonging to this section
    header_confidence: float
    header_match_reason: str         # explainability: "alias_gazetteer_exact" | "font_heuristic" | "embedding_fallback:0.83"
```

### 3.2 Confidence & Validation Model

```python
@dataclass
class Confidence:
    score: float                     # 0.0-1.0
    reasons: list[str]               # explainable, sign-prefixed for renderer consistency:
                                      #   "+" = a positive signal that fired
                                      #   "-" = a checked signal that was absent/failed
                                      # e.g. ["+found_in_explicit_skills_section",
                                      #       "+also_referenced_in_project:'AI SOC Analyst'",
                                      #       "-no_measurable_outcome_detected"]

@dataclass
class Observation:                   # Validation layer output — see Section 8
    severity: Literal["info", "notice", "warning"]
    category: str                    # e.g. "missing_technologies", "unverified_skill"
    message: str                     # human-readable, e.g. "Project 'X' has no technologies listed."
    entity_ref: str                  # e.g. "projects[2]"
```

The `+`/`-` prefix convention on `Confidence.reasons` (new in this revision) exists specifically so every renderer — console, HTML, JSON — can format a confidence explanation identically without re-deriving which signals were positive vs. negative, e.g.:

```
Project "AI SOC Analyst"
Confidence: 0.91
  ✓ Detected inside Projects section
  ✓ Technology list found
  ✓ Strong title match (formatting-corroborated)
  ⚠ Missing measurable outcome
```

This is a direct rendering of `Confidence.reasons` — `+`-prefixed entries render as `✓`, `-`-prefixed entries render as `⚠` — no separate "explanation" data structure is needed; the confidence score and its explanation are always the same object, which is the guarantee requested in design review ("confidence should always be explainable").

`Confidence` is attached per-entity in an internal `AnnotatedCandidateProfile` (mirrors `CandidateProfile` 1:1 but every list item and the profile itself also carries a `Confidence`). The **public** `CandidateProfile` returned to the rest of the app keeps today's single top-level `confidence: float` field unchanged (nothing downstream reads per-entity confidence today), but the richer per-entity scores and explanations are computed, retained on the `PipelineTrace` (Section 6), and exposed via a new read-only endpoint for the (separately valuable, per your Validation Layer note) future "resume feedback" product feature. This is the concrete mechanism for "confidence should be meaningful and explainable" without silently changing the schema shape downstream code depends on.

### 3.3 Parser Plugin Model

See Section 5 for the full design; the core types are introduced here since they're part of the same data-structure layer:

```python
@dataclass
class ParserResult:
    entities: list[Any]              # e.g. list[ExperienceEntry], list[ProjectEntry]
    confidences: list[Confidence]    # one per entity, same order
    observations: list[Observation]  # validation-relevant findings raised during parsing itself

class EntityParser(Protocol):
    entity_name: str                 # "experience", "projects", "education", "skills",
                                      # "certifications", "contact"
    required_sections: list[str]     # canonical Section labels this parser reads

    def parse(
        self,
        sections: dict[str, Section],
        doc: DocumentModel,
        trace: "PipelineTrace | None" = None,
    ) -> ParserResult: ...
```

### 3.4 PipelineTrace Model

See Section 6 for full design and rationale; core types:

```python
@dataclass
class StageTrace:
    stage_name: str
    input_summary: Any
    output_summary: Any
    metadata: dict[str, Any]
    warnings: list[Observation]
    confidences: list[Confidence]
    started_at: float
    duration_ms: float

@dataclass
class PipelineTrace:
    document_id: str
    stages: list[StageTrace]
    total_duration_ms: float

    def to_json(self) -> str: ...
    def to_html(self) -> str: ...
    def to_console(self) -> str: ...
```

---

## 4. Stage-by-Stage Design

### 4.1 Document Extraction

- **Purpose**: turn a PDF/DOCX file into a `DocumentModel` — styled, positioned text, plus hyperlinks (many resumes hyperlink "LinkedIn" or a GitHub icon glyph rather than printing the URL as visible text; `page.get_links()` in PyMuPDF and `docx` hyperlink relationships both expose this and today's pipeline drops it entirely).
- **Inputs**: file path, detected format.
- **Outputs**: `DocumentModel`.
- **Libraries**: `pymupdf` (already a dependency) via `page.get_text("dict")` for PDF spans + `page.get_links()` for hyperlinks; `python-docx` (already a dependency) for DOCX — python-docx exposes paragraph-level runs with `.bold`, `.font.size`, and paragraph style name (`Heading 1` etc., which is a strong, high-confidence section-header signal DOCX gives essentially for free and PDF does not).
- **Algorithm**: for PDF, flatten `dict`-mode spans into `TextSpan`s, keep font size distribution per document (needed for Section Detection's "is this bigger than body text" relative test, since absolute font size varies by template). For DOCX, map paragraph style names to a header-confidence boost.
- **Failure modes**: scanned/image-only PDF → zero spans extracted. **OCR is explicitly out of scope for the core milestones** (see Section 10, Milestone 8+) — the engine should detect this case (near-zero extracted characters, same `< 50 char` floor the current code already uses at `app.py:412-413`) and return a clear, typed `ExtractionFailure` result rather than a degraded guess, exactly as today's `ValueError` at `candidate_profile_generator.py:258-262` does. Password-protected/corrupt files: caught, typed error, no partial profile returned.
- **Confidence**: not entity-level here; this stage instead emits a document-level `extraction_quality` signal (chars extracted, span count, whether block-fallback logic fired) that later stages read to temper their own confidence — a page that only yielded 40 short garbled spans should make every downstream entity less confident, not just fail silently.
- **Timing**: this stage's `duration_ms` is the first datapoint in every `PipelineTrace` (Section 6) and the natural baseline for "is this resume unusually slow to process" regression detection, since it scales with page count and PDF complexity independent of anything the rest of the engine does.
- **Testing**: golden corpus of real (anonymized/synthetic) resumes per format, asserting span counts and hyperlink extraction against hand-verified fixtures; a corrupted-file and an image-only-PDF fixture, asserting the typed failure path.

### 4.2 Layout Reconstruction

- **Purpose**: resolve single-column vs. multi-column layouts into one correct reading order, without discarding which column each block came from.
- **Inputs**: `DocumentModel`.
- **Outputs**: `DocumentModel` with `column_index` populated and spans reordered into `(column_index, y, x)` reading order.
- **Algorithm**: cluster span x0-coordinates per page (k-means with k∈{1,2}, or simpler: gap analysis — sort distinct left-edges, find the largest horizontal gap; if it exceeds a page-width-relative threshold and is corroborated by a vertical band of spans on both sides, treat as a real column boundary rather than a stray indented bullet). This is intentionally simple clustering, not a learned layout model — two-column resumes are the dominant real-world alternative to single-column and a k∈{1,2} decision with a clear geometric rule is both explainable and testable, matching the "95% of realistic resumes, not 100% of all resumes" mandate. Three-or-more-column resumes and complex table-based layouts (e.g. an Experience section laid out as an actual table with ruled cells) are explicitly a non-goal for the initial milestones — detected and flagged (`extraction_quality` degraded, entity confidences lowered) rather than mis-parsed silently.
- **Failure modes**: a false-positive column split (e.g. a resume with a single ragged-right paragraph misread as two columns, or — found during Milestone 1 validation, see the implementation note below — inline right-aligned metadata such as a date printed on the same visual line as a role/company). Mitigated by requiring the gap to be corroborated across multiple consecutive lines, not a single line, before committing to a two-column read, **and** by the row-pitch-continuity check described below, which is what actually distinguishes a genuine second column from an occasional same-line companion value.
- **Confidence**: contributes to `extraction_quality`; a `layout_mode: "single_column" | "two_column" | "ambiguous"` tag with its own confidence is retained on the `DocumentModel` for diagnostics.
- **Testing**: fixtures for single-column, true two-column (sidebar + main), the false-positive case (ragged single column), inline right-aligned dates, and a short-but-genuine sidebar — assert reading order matches hand-verified expected order.

**Implementation note, post-Milestone-1 validation (see `docs/architecture/Milestone1_ValidationReport.md` and Section 12, decision entry below)**: the initial implementation's corroboration guard used **line-count balance** between the two candidate bands (`min(left_lines, right_lines) / max(...)`) as a proxy for "is this a genuine column." A dedicated validation pass against a diverse golden corpus found this proxy is wrong in both directions on real templates: it accepts inline right-aligned dates as a fake second column (three date fragments corroborate each other into a passing "band," even though each one is just a trailing value on an otherwise single-column row), and it rejects a real, short, genuinely two-column sidebar (a 3-line Skills sidebar next to a 20-line Experience column fails a naive count-balance check despite being completely legitimate).

The root problem: line count and balance describe *how much* content a candidate band has, not *how it's distributed over the page*. The property that actually distinguishes a real column from an occasional same-line companion value is **row-pitch continuity** — whether the band's own rows are spaced at roughly the same cadence as the rest of the page (a real, continuously-flowing column) or spaced much further apart than the surrounding text (a value that only shows up attached to specific rows of the other column, with "gaps" on every row that doesn't have one). Concretely: a right-aligned date appears once per job entry, while the entry's role line and its description line both live in the "main" band — so the date band's own row-to-row spacing is roughly double the main band's, a direct, measurable signature that generalizes across templates. A real short sidebar has no such gap: its own rows are single-spaced, same as the main column's.

A **row-pitch-continuity ratio** was added as a new corroboration signal: each candidate band's internal pitch is the median gap between its own consecutive row y-positions (median, not mean, so one larger paragraph-break gap doesn't distort an otherwise single-spaced band); the signal passes only if `max(left_pitch, right_pitch) / min(left_pitch, right_pitch)` stays under a threshold (`1.5`), i.e. neither band's rows are meaningfully sparser than the other's. This fixed both validation findings simultaneously, because they were the same underlying bug (the wrong proxy signal), not two independent problems in tension.

**Revision (same investigation, reconsidered per explicit direction)**: the balance-ratio guard was initially *replaced outright* by the pitch-continuity check. On review, the decision was reversed: balance ratio is **retained**, not dropped, because the case for its complete removal wasn't established against a corpus large enough to justify it (~22 fixtures) — dropping a corroborating signal requires evidence it contributes nothing at scale, not just that a stronger signal was found for the two known findings. `layout.py`'s corroboration step is now a small set of independent, named `CorroborationSignal`s (line count, balance, pitch continuity, y-overlap) combined by one explicit policy function (currently: all must pass) — a structure chosen specifically so a future *semantic* signal (e.g. "this candidate band's text looks date/label-heavy vs. prose," once Section Detection or content classification exists to support it) can be added as one more function in the list, without redesigning the combination logic. This is the concrete extension point for combining geometric and semantic evidence later.

`MIN_BAND_BALANCE_RATIO` was recalibrated (0.25 → 0.1) using the validation data directly: every genuine two-column fixture observed sits at ≥0.375 balance; the one known genuine short-sidebar case sits at 0.15; the one known false positive (inline right-aligned dates) sits at 0.375 too — meaning balance ratio, at any threshold, never actually distinguished that false positive; pitch continuity is what catches it. 0.1 sits with deliberate margin below the single observed 0.15 data point, not tuned tightly to it. **Both `MIN_BAND_BALANCE_RATIO` and `MAX_PITCH_RATIO` are explicitly documented in `layout.py` as validation-derived, tunable parameters, not intrinsic properties of resume geometry** — their current values reflect what a 22-fixture corpus has shown so far, and either may move if a larger corpus shows otherwise. `MIN_CORROBORATING_LINES` (still ≥3 per band) and the y-overlap guard are unchanged and remain genuinely complementary signals within the same list — line count still guards against 1–2-line coincidences a pitch ratio can't safely judge from so little data, and y-overlap still separately confirms the two bands actually run in parallel down the page (e.g. ruling out a real column vs. an unrelated footer) rather than merely both being present somewhere on it.

**Known residual limitation, accepted rather than solved here**: a resume where *every single line* carries trailing right-aligned content at the same pitch as the surrounding text (no interspersed description-only lines at all) would still pass the pitch check and be misclassified as two-column, since pitch alone can't distinguish "real column" from "metadata present on literally every row" — disambiguating that would require content-aware reasoning, which belongs to Section Detection (Milestone 2), not this purely geometric stage (it's exactly the kind of case the semantic-signal extension point above is meant to eventually address). This is rarer in practice than the interspersed pattern this fix targets (most resumes have more body/bullet lines than header lines) and is recorded as a known gap rather than claimed to be solved (see Section 11).

### 4.3 Section Detection

- **Purpose**: partition the linearized document into labeled `Section`s.
- **Inputs**: linearized `DocumentModel`.
- **Outputs**: `list[Section]`.
- **Algorithm, in priority order (first confident match wins, cascading only on low confidence — this cascade itself is the explainability trail stored in `header_match_reason`)**:
  1. **DOCX style-name match** (DOCX only): paragraph style is `Heading*` → near-certain header (`confidence≈0.98`).
  2. **Alias gazetteer, exact/near-exact**: a curated list of section-name aliases per canonical section (`EXPERIENCE`: "Experience", "Work Experience", "Professional Experience", "Employment History"; `PROJECTS`: "Projects", "Personal Projects", "Selected Projects"; etc. — extend similarly for Education, Skills, Certifications, Summary/Objective, Contact). Matched via `rapidfuzz` (pinned dependency, Section 10 Decision 4) against a line that is otherwise a plausible header (short, standalone line, larger/bolder than the surrounding body-text font-size mode computed in 4.1). `confidence` scaled by match ratio.
  3. **Font/whitespace heuristic without a gazetteer hit**: a short standalone line noticeably larger/bolder than body text, followed by denser text, is treated as an *unlabeled* section header — assigned the canonical label whose gazetteer it comes *closest* to via the same fuzzy match, but flagged with a lower confidence and an explicit `Observation` ("unknown or ambiguous section: 'Career Highlights'") per the user's own example. This is exactly the deterministic-but-honest behavior the spec asks for: don't silently misfile it, don't crash, surface it.
  4. **Embedding fallback** (last resort, only if 2 and 3 both produce low confidence): SBERT sentence embedding of the candidate header line against the canonical section names, cosine similarity. This is the one place a local ML model participates in a structural decision, justified because it is a bounded, closed-set classification (6-8 canonical labels) rather than open-ended extraction, and because it's the fallback of last resort behind two deterministic checks, not the primary mechanism.
  - **Contact/Header** is the special case: it is (almost always) the untitled block before the first detected section, plus anything containing an email/phone/URL pattern regardless of section, so it does not depend on a header label at all — see 4.4.
- **Failure modes**: missing sections (candidate simply has no Education section) → that canonical section is absent from the list entirely, and downstream parsers correctly produce an empty list (matches the schema default, matches "no crash" requirement). Section-order doesn't matter — the detector doesn't assume Contact-then-Summary-then-Experience-then-...; it labels whatever it finds wherever it is, which directly satisfies "resumes with unusual ordering."
- **Confidence**: per-`Section.header_confidence`, plus the match-reason string for explainability, as shown in 3.1.
- **Testing**: the largest fixture corpus in the whole project — real-shaped resumes (anonymized/synthetic) covering: all-standard-headers, nonstandard-but-common headers ("Employment History" instead of "Experience"), a genuinely unknown/ambiguous header, and a resume missing 2-3 sections entirely. Assert both the correct label *and* the correct confidence tier (high/medium/low) and match_reason, not just the label — the explainability contract needs its own tests, not just the classification accuracy.

**Implementation note, post-Milestone-2 build and validation (see `docs/architecture/Milestone2_ValidationReport.md` and Section 12 below)**: implemented largely as designed above, with a few adaptations grounded in what Milestone 1 actually produces and one critical bug found and fixed during validation.

- **Canonical label set**: `contact`, `summary`, `experience`, `projects`, `education`, `skills`, `certifications`, `unknown` — `summary` was added beyond the six entity-parser labels since `CandidateProfile.resume_summary` already exists as a schema field, even though no dedicated `SummaryParser` exists yet (Milestone 3).
- **Line grouping is page/column-aware**, not just y-proximity: `sections.py` groups the already-linearized `DocumentModel.spans` into visual lines, but never merges across a `page_num` or `column_index` change. This is a small, deliberately separate implementation from `layout.py`'s own per-band line grouping — Milestone 1 is frozen, so this is accepted duplication rather than a shared refactor.
- **Tiers 2/3 are one fuzzy-match call with a graduated confidence**, not two separate matching passes — behaviorally identical to the documented cascade, simpler to implement and reason about.
- **Scorer choice matters more than the design doc anticipated**: `rapidfuzz`'s default `WRatio` scorer badly over-matches short header-like phrases sharing one common word with an alias (e.g. "Volunteer Work Abroad" scored 85.5 — confidently, wrongly — against "Work History"). Switched to `token_sort_ratio` (order-independent whole-phrase similarity), which doesn't exhibit this failure mode.
- **Critical bug found and fixed during validation**: the fuzzy matcher was case-sensitive, so ALL-CAPS headers ("CONTACT", "SKILLS") — one of the most common real-world header conventions — scored as low as 13-25 against the Title-Case gazetteer, forcing them through the unreliable embedding fallback instead of matching confidently. Fixed with `processor=str.lower`. See the validation report for the full writeup; this was treated as an unambiguous correctness bug and fixed immediately, not held for a design discussion, the same standard applied to two smaller calibration fixes found in the same pass (the fuzzy-match scorer above, and `EMBEDDING_SIMILARITY_FLOOR` raised from 0.5 to 0.55 after a false match was observed just above the original floor).
- **The contact special case's "fold into contact" rule is position-based** (before the first *real* section in document order), which correctly handles a name banner at the very start of a document but does **not** help a name/title banner placed in the *main* column of a two-column layout, since column-major reading order means the sidebar's real sections are read first — Findings 2 and 3 in the validation report. Not fixed in this milestone; flagged as one underlying gap (no way to say "this looks like a header but isn't really a boundary here" beyond the single leading-block rule) that a future pass could address for both cases at once.
- **The 7-label canonical set doesn't cover every real section type** (publications, teaching, awards — common in academic CVs specifically) — Tier 3/4 correctly assign the *closest* available label at low confidence rather than crashing or misfiling silently, which is working as designed, but is a real coverage gap, not a solved problem (Finding 4).
- **`repeated_running_header_pdf`'s known limitation** (a repeated per-page header/footer, occurring after a real section has started, fragments that section's cross-page continuation into a spurious `"unknown"` entry) was anticipated as a risk before implementation and confirmed exactly as expected during validation — the most consequential open finding from this milestone, since it's a common real template pattern with a genuine (if contained) reading-order-adjacent effect, not merely a mislabeled confidence score.

### 4.4 Entity Parsers (Contact, Experience, Project, Education, Skills, Certification)

All six are independent implementations of the `EntityParser` interface (Section 5) — no shared state between them beyond the read-only `dict[str, Section]` and `DocumentModel` they're given, so they're independently unit-testable and (implementation detail, not architectural requirement) trivially parallelizable.

**ContactParser**
- Input: the pre-first-section block, plus a full-document regex sweep for email/phone/URL patterns as a safety net (contact info is occasionally placed in a footer or sidebar picked up as its own "section").
- Algorithm: `email` — standard RFC-5322-lite regex. `phone` — **deterministic regex-shape validation only (no external dependency)**: extract digit-heavy candidate substrings, normalize by stripping formatting characters, and classify confidence by shape — a substring that matches a well-formed pattern (optional `+country`, area code grouping, 10-15 total digits, plausible separator placement) scores higher than a bare undifferentiated digit run of the right length. This is a deliberate scope reduction from full numbering-plan validation (Section 10, Decision 4): `contact_details.phone` has no downstream functional consumer today (Section 1.2), so shape-level confidence is the right amount of rigor for a display-only field, and it avoids a dependency whose only payoff would be a marginal confidence-tier improvement on a cosmetic field. `linkedin`/`github` — URL regex over both visible text *and* the `DocumentModel.hyperlinks` extracted in 4.1 (catches "LinkedIn" rendered as a hyperlinked icon with no visible URL — a real gap in today's Gemini pipeline too, since it only ever sees flattened text). `location` — gazetteer of city/state/country names (a static data file, the primary and default-sufficient mechanism) with an **SBERT nearest-neighbor fallback** as a secondary corroborating signal only, never the sole source: embed the candidate location line and compare against embeddings of the gazetteer's own entries, surfacing a fuzzy match (e.g. an unusual abbreviation or formatting the literal gazetteer lookup missed) without introducing a second NLP stack or model download beyond SBERT, which the engine already depends on for Section Detection's Tier 4 fallback (4.3) and the gazetteer fuzzy-matching used elsewhere (4.4 Project/Skills parsers). This directly reflects Decision 4: SBERT absorbs the one piece of genuine semantic-matching value spaCy would have added, without a second dependency.
- Confidence: email gets a real regex-shape validity signal; phone gets the shape-tier described above; location/linkedin get gazetteer-hit vs. SBERT-corroboration-only tiers.

**ExperienceParser**
- Within the Experience section, cluster spans into per-entry blocks using a repeating structural signal: a bold/larger line (role and/or company) followed by a date-range-shaped line (regex: `MMM YYYY – MMM YYYY|Present`, `dateutil.parser` for flexible date-string parsing, pinned dependency per Decision 4), followed by bullet-marked or paragraph body text until the next such header line or the section end.
- Role vs. Company disambiguation (order varies across templates, e.g. "Senior Engineer, Acme Corp" vs. "Acme Corp — Senior Engineer"): maintained job-title gazetteer (a static curated list, extendable) — whichever half of the header line matches the gazetteer is `role`; the other is `company`. If neither matches, lower-confidence heuristic default (first segment = role, matching the more common convention) with the ambiguity itself recorded in `Confidence.reasons` (e.g. `"-role_not_gazetteer_matched"`).
- `duration` stored both as the original string (schema compatibility) and, internally, as parsed start/end for `_calculate_total_years`-equivalent math to run on structured dates instead of the current best-effort regex reparse.
- `summary`: remaining bullet/paragraph text, cleaned in Normalization (4.6).
- Nested bullets (a sub-bullet under a top-level bullet — common for "responsibilities" vs. "achievements" split): flattened into `summary` in reading order; not modeled as a separate structure, since nothing downstream consumes bullet hierarchy today and inventing that distinction would be exactly the kind of un-asked-for complexity the requirements warn against.
- Confidence per entry: high when both role (gazetteer-matched) and a parseable date range are present; medium if only one; low (and an `Observation`) if an entry has no parseable dates at all ("Inconsistent dates" — the user's own validation example).

**ProjectParser**
- Structurally identical entry-clustering approach to Experience (header line + body), but the header line is a free-text title (no gazetteer to match against, since project names are arbitrary) — title confidence is instead driven by formatting corroboration (bold/larger font = high confidence it's a real title vs. accidentally splitting a paragraph).
- `technologies`: two sources merged — (a) an explicit "Tech:"/"Stack:"/"Built with:" labeled line within the entry (regex-detected label, high confidence), and (b) inline gazetteer matches of known technology names against the entry's full text (a curated, extensible technology/tool gazetteer — this is the single most valuable piece of static data to invest in early, since it also powers Skills parsing and the cross-reference pass). Deduped in Normalization.
- `concepts`: derived, not directly printed on resumes — a curated concept gazetteer (e.g. "distributed systems", "authentication", "CI/CD") matched against entry text via keyword/keyphrase matching (`keybert`, pinned dependency per Decision 4, already used elsewhere in the codebase for exactly this kind of keyphrase extraction) rather than a fixed regex list, since concepts are the field most likely to appear as varied natural-language phrasing rather than a fixed vocabulary.
- `interview_seeds`: **has its own dedicated design milestone, not resolved inline in this section** — see Section 10, Milestone 4, and the permanent graceful-degradation principle it establishes (a project with insufficient extracted evidence gets fewer or zero seeds, never a fabricated one).
- Confidence: high when title (formatting-corroborated) + at least one technology are present; the `interview_seeds` list itself carries a per-seed confidence tied to how many template preconditions were satisfied, per the design produced in Milestone 4.

**EducationParser**
- Degree gazetteer (BS/B.S./Bachelor of Science/BSc, MS/M.S./Master of Science, PhD, etc. — a small, closed, well-known vocabulary, one of the easiest sub-problems in the whole engine) + institution (gazetteer of common university names as a confidence booster, but *not* required — an unrecognized institution name is still accepted, just at lower confidence, since a closed-world institution list would be actively wrong for a global user base) + `graduation_year` (4-digit year regex, corroborated by proximity to a degree line).
- Given this field has **zero downstream functional consumers today** (Section 1.2), it is correctly a lower-effort, lower-risk milestone — good display quality is the actual bar, not perfect recall.

**SkillsParser**
- Primary source: an explicit Skills section, split on common delimiters (comma, pipe, bullet, newline), each token normalized against the technology/tool gazetteer shared with the Project Parser (same gazetteer, single source of truth — this sharing is why SkillsParser and ProjectParser, while independently run, must agree on one canonical gazetteer module rather than each maintaining its own list, which would drift).
- Secondary source (feeds the Cross-Reference pass, not this parser directly): skills mentioned only inside Project/Experience bullets, never listed explicitly — today invisible to the profile entirely; the new engine can genuinely do better than Gemini here specifically because gazetteer-matching against full document text is a search problem, not a synthesis problem, and doesn't require re-reading with fresh "creativity" the way an LLM would.
- Confidence: high for skills present in an explicit Skills section; noted separately (in `Confidence.reasons`, not a separate schema field) whether a skill is *also* demonstrated in a project — this is the mechanism for the "skills listed but never demonstrated" validation observation (Section 8).

**CertificationParser**
- Simplest parser: explicit Certifications section, one gazetteer-normalized entry per line/bullet (e.g. "AWS Certified Solutions Architect", "PMP", "CKA" — canonical name variants collapsed, matching the schema's `list[str]` shape exactly, no behavior change needed for `topic_pool.py`'s existing `isinstance(cert, dict)` defensive branch, which becomes permanently dead code but is safe to leave alone since it's harmless).
- Also scans Skills/Summary sections for stray certification mentions not under a dedicated heading (some resumes only have one line: "AWS Certified, 2023" with no separate section) via the same gazetteer.

**Implementation note, post-Milestone-3 build and validation (see `docs/architecture/Milestone3_ValidationReport.md` and Section 12 below)**: `ContactParser`/`ExperienceParser`/`ProjectParser` (the three Milestone 3 parsers; Education/Skills/Certification remain Milestone 5) are implemented largely as designed above, with the following adaptations:

- **Shared utilities, new this milestone**: `technology_gazetteer.py`, `job_title_gazetteer.py`, `concept_gazetteer.py`, `location_gazetteer.py` (plain data files, matching `section_gazetteer.py`'s Milestone 2 precedent), a shared `parsers/_entry_clustering.py` (header-line-plus-body clustering, used by both `ExperienceParser` and `ProjectParser` — a deliberate local reimplementation, not an import from `sections.py`/`layout.py`, both frozen), and `dates.py` (a `python-dateutil` wrapper shared by `ExperienceParser` now and `EducationParser` in Milestone 5).
- **A real Milestone 2/pipeline interaction bug was found and fixed**: `HeuristicSectionDetector` has no concept of "entry" -- a bold/larger line *inside* a section (a job's "Company, Role" line, a project's title line) is structurally indistinguishable to it from a genuine new section boundary, and usually doesn't confidently match any canonical label, landing in `"unknown"`. Two consecutive such lines correctly following the same real section were being permanently split off as separate stray `"unknown"` sections instead of staying part of `experience`/`projects` -- confirmed to zero out `ProjectParser`'s output entirely on a realistic two-project resume during Milestone 3's own testing. Fixed in `pipeline.py` (`_absorb_repeated_unknown_entries`, called before `_group_sections_by_label`), not in `sections.py` itself: 2+ consecutive `"unknown"` Sections immediately following a real section, with no other real section in between, are absorbed into it. A single, isolated `"unknown"` (Milestone 2's own validated `ambiguous_header_pdf` case, e.g. "Languages") is untouched -- verified as a direct regression test before this fix was accepted. **Documented residual limitation**: a section with exactly one entry still fragments, since one data point can't be distinguished from a genuine one-off ambiguous section by geometry alone (`single_entry_sections_pdf` golden-corpus fixture demonstrates this deliberately, not hidden).
- **A `dates.py` regex bug was found and fixed**: matching `[A-Za-z]{3,9}` as a generic "month-like word" false-matched the last word of a role title directly followed by a start year on the same line (e.g. "Senior Engineer 2021 - Present" matched "Engineer 2021" as if "Engineer" were a month), corrupting both the extracted date and the role/company split downstream. Fixed with an explicit month-name alternation, not a generic word-length class -- a new module (`dates.py`, this milestone), not a change to any frozen file.
- **`ProjectParser`'s confidence formula omits the architecture doc's fourth term** (interview-seed template precondition satisfied, +0.2) entirely, since `interview_seeds` doesn't exist until Milestone 5 -- M3's `ProjectParser` confidence tops out around 0.8, not 1.0, documented in the confidence reasons themselves (`"-interview_seeds_not_implemented_until_milestone_5"`), not silently patched to look complete.
- **`projects[].summary` is verbatim extraction, not abstractive summarization** -- a deliberate, documented behavior difference from today's Gemini pipeline (which paraphrases into "a concise 2-3 sentence summary"). Functionally sufficient for `topic_pool.py`'s grounding use, which doesn't require abstraction.
- **`factory.py`'s conformance-checking gap (flagged in the Milestone 3 plan) was closed**: `default_parser_registry()` now registers the three real parsers with `check_parser_conformance` active, using a deliberately empty sample (`sample_sections={}`) so the check exercises each parser's fast "missing section" path rather than eagerly loading `ProjectParser`'s KeyBERT/SBERT models on every call to this function -- conformance checking's scope is verifying the `ParserResult` shape contract, not extraction correctness (that's the dedicated test suite), so a trivial sample is sufficient and avoids a real, otherwise-recurring performance cost.

### 4.5 Cross-Reference Pass

- **Purpose**: the one stage allowed to reason across sections. Two responsibilities: (a) tag which Skills-section entries are also evidenced in Projects/Experience text (demonstrated vs. merely listed — directly powers a validation observation and is a genuinely richer signal than today's profile carries at all), and (b) synthesize `interview_seeds` per the mechanism designed in Milestone 4, since seed templates need a project's technologies *and* the shared gazetteer's concept tags together.
- **Inputs**: all parsed entities (the `ParserResult`s produced by every registered `EntityParser`).
- **Outputs**: annotations merged back onto the Skills and Project entities (no new top-level schema fields — stays within the existing contract).
- **Failure modes**: none new — worst case, no cross-references found, fields stay as the single-section parsers left them.

### 4.6 Normalization

- Unicode (`unicodedata.normalize("NFKC", ...)`) and whitespace cleanup on every string field (resumes routinely contain smart quotes, non-breaking spaces, stray control characters from PDF extraction — today silently passed through to Gemini and back).
- Date canonicalization via `dateutil`, producing both the display string and internal start/end for computation.
- Technology/skill de-aliasing (e.g. "JS" / "Javascript" / "JavaScript" → one canonical form) via the shared gazetteer's alias map, plus de-duplication (case-insensitive) — directly implements the "duplicate technologies" validation example by making duplicates structurally impossible to reach the profile in the first place, with the *dedup event itself* logged as an `Observation` (`info` severity: "merged duplicate technology entries: 'JS', 'Javascript'") rather than silently invisible, per the explainability principle running through this whole design.
- Title-casing / trimming for names, companies, institutions — careful not to mangle intentionally-stylized casing (e.g. "iOS", "eBay") — handled via a small exception list, not blind `.title()`.

### 4.7 Validation Layer

See Section 8 (own section, since the user explicitly wants it treated as a reusable, separable subsystem).

### 4.8 Confidence Scoring

See Section 7.

---

## 5. Plugin Parser Architecture

**Approved as a new architectural requirement.** Rather than Stage [4] being six hardcoded function calls the orchestrator invokes by name, every entity parser implements the common `EntityParser` protocol defined in Section 3.3, and the orchestrator holds a registry it iterates over generically:

```python
class ParserRegistry:
    def register(self, parser: EntityParser) -> None: ...
    def run_all(
        self, sections: dict[str, Section], doc: DocumentModel, trace: PipelineTrace | None
    ) -> dict[str, ParserResult]:
        # for each registered parser: look up its required_sections, call .parse(),
        # merge results keyed by entity_name, recording a StageTrace per parser if trace is set
        ...
```

**Why this is the right structural choice, not just a style preference:**

- **Direct precedent already exists in this codebase.** `evaluator_registry.py` implements exactly this pattern for pluggable evaluators in the Resume Discussion / evaluation subsystem — registerable implementations of a common interface, looked up generically by the orchestrator rather than hardcoded. Adopting the same pattern here is consistency with an established, working precedent, not a new idea being introduced to the project.
- **Extensibility without orchestrator changes.** Adding a future parser (e.g. a `PublicationsParser` or `AwardsParser`, if the schema ever grows) means writing one new class and registering it — the pipeline orchestrator, Stage [4]'s call site, and every other parser are untouched. This is the concrete mechanism behind "future parser additions much easier."
- **Testability.** Each parser is tested against the `EntityParser` protocol in complete isolation — a test only needs to construct `Section` fixtures and call `.parse()` directly, with no dependency on the orchestrator, the registry, or any other parser. This is already true of the six parsers as designed in Section 4.4; the registry formalizes it as an enforced interface rather than an informal convention.
- **`required_sections` is a declared, inspectable contract**, not implicit knowledge buried in each parser's implementation — the registry (or a future dev-mode listing) can print "ExperienceParser requires: experience" without reading the parser's source, which is itself a small explainability win in the same spirit as the rest of this document.

**Cost of this decision**: essentially zero beyond what Section 4.4 already specified — the six parsers were already designed as independent, section-scoped units with no shared state; formalizing them behind a `Protocol` and a registry is a thin structural wrapper, not a redesign of any parser's internal logic.

---

## 6. PipelineTrace — Observability Architecture

**Approved and promoted to a first-class architectural component**, not an optional debugging add-on bolted on after the fact.

### 6.1 Principle: one object, multiple renderers

There is exactly one underlying data structure — `PipelineTrace` (Section 3.4) — and every observability surface (JSON output, HTML report, console output, golden-snapshot tests) is a **renderer of that same object**, never an independently maintained system:

```
                         PipelineTrace
                              │
        ┌──────────┬──────────┼──────────┬──────────────┐
        ▼          ▼          ▼          ▼              ▼
  to_json()   to_html()  to_console()  golden-snapshot   (future renderers,
                                        test comparison    e.g. a metrics
                                                            exporter)
```

This directly answers the architecture question raised in design review ("dedicated debug pipeline vs. logging vs. artifacts vs. HTML vs. JSON — or something better"): the better approach is that these are not competing options to choose between, they are four thin views of one object. Building a second, separately-maintained debug pipeline was explicitly rejected — it would double maintenance and risk the classic failure mode where the debug view silently drifts from what actually happened in production.

### 6.2 How it attaches to the pipeline without touching production behavior

Every stage function and every `EntityParser.parse()` implementation accepts an optional `trace: PipelineTrace | None = None` parameter, defaulting to `None`. When `None` (the production default), no `StageTrace` is constructed, no timing call is made, and no extra data is retained — genuinely zero behavioral or performance difference from a pipeline with no tracing concept at all. When a caller (a test, a CLI tool, or a developer session) passes a real `PipelineTrace`, each stage appends its own `StageTrace` before returning. This is the same span-if-sampled pattern used by production tracing systems (e.g. OpenTelemetry), scoped down to a single local pipeline run.

Because every stage already produces the ingredients a `StageTrace` needs — `Confidence` objects with explanations (Section 3.2), `Observation`s (Section 3.2), `header_match_reason` strings (Section 3.1), `extraction_quality`/`layout_mode` metadata (Section 4.1-4.2) — building the trace mechanism does not require inventing new explainability data anywhere in the engine. It requires collecting data every stage was already going to produce, into one place, per run. This is the direct payoff of having designed explainability into every stage's contract from Section 3 onward, rather than adding it as an afterthought.

### 6.3 Timing (new requirement, incorporated)

Every `StageTrace` carries `started_at` and `duration_ms`, populated whenever a trace is active. `PipelineTrace.total_duration_ms` is the sum across all stages plus orchestration overhead. Concretely, a full trace run against one resume yields a breakdown such as:

```
Document Extraction:      42ms
Layout Reconstruction:     6ms
Section Detection:        18ms
ContactParser:              3ms
ExperienceParser:          11ms
ProjectParser:              9ms
EducationParser:            2ms
SkillsParser:                4ms
CertificationParser:        1ms
Cross-Reference Pass:      14ms
Normalization:               5ms
Validation:                   7ms
Confidence Scoring:           4ms
──────────────────────────────
Total:                     126ms
```

Because Section 5's registry already invokes each parser individually, per-parser timing (not just "all parsers combined") falls out of the plugin architecture for free — each `EntityParser.parse()` call is its own traced stage. This granularity is what makes the timing data useful for regression detection: a future change that makes `ProjectParser` slower is visible as a specific line moving, not a vague total-time increase with no attribution.

### 6.4 Confidence explanation rendering

Per Section 3.2's `+`/`-` prefix convention, every renderer formats a `Confidence` identically:

```
Project "AI SOC Analyst"
Confidence: 0.91
  ✓ Detected inside Projects section
  ✓ Technology list found
  ✓ Strong title match (formatting-corroborated)
  ⚠ Missing measurable outcome
```

`to_console()` prints this literally; `to_html()` renders the same data as styled checkmark/warning rows; `to_json()` preserves the raw `reasons` list for programmatic diffing (e.g. golden-snapshot tests asserting the exact reason set, not just the score).

### 6.5 Integration with the testing strategy

Golden-file tests (Section 9) snapshot the **entire trace**, not only the final `CandidateProfile` JSON. This means a regression test failure reports *which stage* diverged from the committed snapshot — e.g. "Section Detection's confidence for the Projects header dropped from 0.95 to 0.71" — rather than only "the final profile doesn't match," which would require manually bisecting the pipeline by hand to find the cause. This is a material upgrade to the testing strategy that exists specifically because the trace mechanism was designed in from the start rather than added later.

### 6.6 Implementation cost and timing of the build

**Cost**: modest and cross-cutting rather than deep. Every stage function and every `EntityParser` implementation needs one additional optional parameter and a handful of lines to populate a `StageTrace` when tracing is active. The `PipelineTrace`/`StageTrace` dataclasses themselves (Section 3.4) are a small, one-time investment. The `to_console()`/`to_json()` renderers are close to trivial given the data is already structured; `to_html()` is a genuinely separate, larger piece of work (an actual template/rendering layer) and is treated as deferrable.

**When to build it**: the `trace` parameter and the `StageTrace`/`PipelineTrace` data model are **baked into every stage starting at Milestone 1** — this is the one piece of this design where retrofitting later is materially more expensive than building it in from the start, for the identical reason `DocumentModel` (Decision 1) had to be right from Milestone 1: adding an optional parameter to a function signature that doesn't yet exist is free; adding it across five milestones' worth of already-written, already-tested stage code later is a real, avoidable rework cost. The `to_console()` and `to_json()` renderers should exist by Milestone 2 (as soon as there's a two-stage pipeline worth inspecting) since they double as the golden-snapshot testing mechanism from Section 9 onward. `to_html()` is explicitly deferred to after Milestone 3, once there's a complete-enough pipeline that a visual report is worth the build cost rather than showing mostly empty stages.

This is reflected in the milestone roadmap (Section 10): Milestone 1 explicitly includes "bake in the `trace` parameter across all stage signatures" as a deliverable, not a follow-up task.

---

## 7. Confidence Scoring Framework

**Principle**: every confidence score must be reconstructable from a documented, weighted combination of concrete signals — never a single arbitrary number, and never itself the output of an opaque model. This mirrors `ResumeDiscussion_v2.md` NFR4's explainability requirement for evaluation scores; the new engine adopts the identical bar for parsing confidence, and design review has strengthened this further: a confidence score without its accompanying `+`/`-` explanation list (Section 3.2) is treated as an incomplete implementation of any given parser, not an acceptable minimal version.

**Mechanism**: each stage that emits an entity computes its `Confidence.score` as a documented weighted sum of independent boolean/graded signals specific to that entity type, and always populates `Confidence.reasons` with sign-prefixed, human-readable names of the signals that fired or failed. Concretely, for example:

- **Project confidence** = weighted combination of: title formatting-corroborated (bold/larger font) [+0.4], at least one technology extracted [+0.25], at least one interview-seed template precondition satisfied [+0.2], section-header confidence itself [+0.15 × section confidence]. A project named via a plain unformatted line with no technologies scores low and *says why* (`"-title_not_formatting_corroborated"`, `"-no_technologies_extracted"`) rather than returning an unexplained `0.4`. This is exactly the worked example from design review: `["+detected_inside_projects_section", "+technology_list_found", "+strong_title_match", "-missing_measurable_outcome"]` → `0.91`.
- **Skill confidence** = high (e.g. 0.9+) if found in an explicit Skills section via exact/near-exact gazetteer match; reduced if only found via inline text-mention (no explicit listing); boosted further (documented, additive, capped at 1.0) if also demonstrated in a project (from the Cross-Reference pass).
- **Experience confidence** = role gazetteer-matched [+0.4] + parseable date range [+0.3] + non-empty summary [+0.2] + section-header confidence contribution [+0.1 × section confidence].
- **Education confidence** = degree gazetteer-matched [+0.5] + parseable graduation year [+0.25] + institution present (gazetteer match or not) [+0.25, gazetteer match earns the full amount, an unrecognized-but-present institution earns half].

These specific weights are a starting proposal, not a claim of correctness — they should be tuned against the golden-corpus test suite (Section 9) once real fixtures exist, and every weight change is a one-line, reviewable diff in a single documented module, which is the entire point of choosing an additive, inspectable formula over a learned scoring model.

**Where this differs from today**: today's `confidence: float` is Gemini's self-assessment of one field (`predicted_domain`) and nothing else is scored at all. The new engine scores every entity, every score carries its own explanation by construction (Section 3.2, Section 6.4), and (new capability, not present today) they can genuinely gate behavior later — e.g., a future milestone could choose to only surface a project's `interview_seeds` to the discussion planner if the project's own confidence clears a threshold, which is not possible today because there is no per-entity signal to threshold on.

---

## 8. Validation Layer

Designed explicitly as its own module (`resume_validation.py` or similar), consuming a finished `AnnotatedCandidateProfile` and producing `list[Observation]` — **structurally decoupled from the parsers themselves**, so it can be reused later as a standalone "resume feedback" product feature (per your explicit note) without dragging in any parsing internals, and so a future rule can be added without touching a single parser.

Rule categories (each rule = one small, independently testable function taking the profile and returning zero or more `Observation`s):

- **Completeness**: project has no technologies listed; experience entry has an empty summary; missing GitHub/LinkedIn in contact details; no measurable achievements in a project (no digit/percent/metric pattern found in its summary).
- **Consistency**: inconsistent or unparseable dates (an experience/education entry whose date range didn't survive `dateutil` parsing, or where end-date precedes start-date); duplicate technologies (surfaced as an `info` observation even though Normalization already de-duplicates them, so the fact that a duplicate *existed* in the source resume is still visible — dedup fixes the data, the observation preserves the signal that the original resume was inconsistent).
- **Cross-reference (needs Section 4.5's output)**: skills listed in the Skills section but never demonstrated in any project or experience bullet ("Skills listed but never demonstrated").
- **Structural**: unknown/ambiguous section header (surfaced directly from Section Detection's tier-3/4 matches, Section 4.3); a section detected but empty after entity parsing (e.g. a "Projects" header found with no parseable project entries beneath it — likely a parser gap or a genuinely header-only section, worth surfacing either way).

Each `Observation` carries `severity` (`info`/`notice`/`warning` — deliberately *not* "error", since these are quality observations about the resume, never parsing failures per the user's explicit framing), a `category` slug (stable, for future filtering/aggregation when this becomes its own feature), a human-readable `message`, and an `entity_ref` pointing back to the specific profile entry.

**Non-goal for this layer**: it does not gate or block profile generation. A resume that trips ten validation observations still produces a complete, usable `CandidateProfile` — validation output is informational, stored alongside the profile (and retained on the `PipelineTrace`, Section 6), not merged into the public schema, to avoid another downstream-compatibility surface, and simply unused by the current product until a future feature consumes it.

---

## 9. Testing Strategy

- **Golden corpus**: a curated set of real-shaped (synthetic/anonymized, to avoid shipping real candidate PII into the test suite) resumes covering: single-column, two-column, DOCX, PDF, a resume with every canonical section, a resume missing several sections, a resume with nonstandard section names, a resume with an ambiguous/unknown section, a resume with nested bullets, a resume with hyperlinked (not visible-text) contact links, a scanned/image-only PDF (asserts the typed failure path, not a parse attempt). This corpus is the primary regression gate — every milestone below expands it.
- **Unit tests per parser**: each `EntityParser` implementation tested in isolation against hand-authored `Section` fixtures (bypassing earlier stages), calling `.parse()` directly per Section 5's testability argument, asserting both the extracted values *and* the confidence score/explanation — an entity extracted "correctly" but with an unexplained or wrong confidence is still a test failure, since explainability is a first-class requirement here, not a bonus.
- **Golden-file end-to-end trace tests**: full pipeline against each golden-corpus resume, run with a `PipelineTrace` active, asserting the entire trace (Section 6.5) — not just the final `CandidateProfile` JSON — matches a committed expected-output fixture exactly (a snapshot-test pattern). This is what makes the engine's determinism a *tested property*, not just a design intention: the same input file must byte-for-byte reproduce the same trace across runs and across machines, and a failure localizes to the specific stage that changed.
- **Schema-compatibility test**: construct profiles from the new engine and run them through the *existing* `topic_pool.py`/`traceability.py`/`profile_to_frontend_format` code paths unmodified, asserting no exception and a non-empty `TopicPool` — this is the direct regression test for the one hard invariant identified in Section 1.2.
- **Property-based tests** (via `hypothesis`, a small dev-only dependency) for Normalization specifically — e.g. "de-aliasing is idempotent," "no output field is ever `None`" — since normalization bugs (a stray `None` slipping through) are exactly the class of regression most likely to silently break a downstream `.get()`/truthiness check.
- **Shadow Mode comparison harness** (Milestone 0 tool, not a permanent test, subject to the hard constraints in Section 2.2): run both the legacy Gemini pipeline and the new engine on the same golden corpus, diff the two `CandidateProfile`s field-by-field, and use systematic disagreements — reviewed by a human, never auto-applied — to find real gaps before the Gemini path is ever removed.

---

## 10. Milestone Roadmap

Each milestone is runnable and demoable on its own; none requires the next to already exist to show value. Revised from the original proposal to give `interview_seeds` its own dedicated milestone (Decision 3) and add a canary phase before Gemini's final removal (Decision 5).

**Milestone 0 — Audit & Harness**
- Deliverables: this design doc; the Shadow Mode comparison harness, built to the hard constraints in Section 2.2 (comparison-only, human-reviewed, never auto-applied); the golden resume corpus (initial ~15-20 fixtures) with hand-verified expected `CandidateProfile` JSON for each.
- Success criteria: harness runs both pipelines on the corpus and produces a field-level diff report for human review; no code path exists by which Shadow Mode output could reach a production response.
- Integration points: none — purely additive tooling, zero risk to the running app.

**Milestone 1 — Document Extraction + Layout Reconstruction + Trace Foundation**
- Deliverables: `DocumentModel`, PDF span/hyperlink extraction, DOCX paragraph/style extraction, column resolution; the `PipelineTrace`/`StageTrace` data model (Section 6) and the `trace: PipelineTrace | None = None` convention baked into both of this milestone's stage functions, establishing the pattern every later stage follows.
- Success criteria: on the golden corpus, correct reading order and correct hyperlink capture, measured against hand-verified fixtures; scanned-PDF fixture correctly produces the typed failure path; running either stage with a trace active produces a correctly-timed, correctly-populated `StageTrace`.
- Testing: Section 9's per-stage unit tests for this stage only.
- Integration points: none yet — not wired into `app.py`.

**Milestone 2 — Section Detection + Trace Renderers (JSON, console)**
- Deliverables: the 4-tier cascade (Section 4.3), the alias gazetteer data file, unknown-section handling; `PipelineTrace.to_json()` and `.to_console()`, which immediately double as the golden-snapshot testing mechanism from this milestone onward.
- Success criteria: correct section labels + tier/confidence on the full golden corpus, including the deliberately-hard fixtures (nonstandard names, missing sections, one genuinely ambiguous header); golden-snapshot tests using `to_json()` are in place and passing.
- Integration points: none yet.

**Milestone 3 — Plugin Registry + Core Entity Parsers: Contact, Experience, Project**
- Deliverables: the `EntityParser` protocol and `ParserRegistry` (Section 5); the three parsers whose fields are load-bearing per the Section 1.2 dependency map (`role`, `title`, and the evidence `interview_seeds` will depend on in Milestone 4).
- Success criteria: schema-compatibility test (Section 9) passes — a `TopicPool` built from these profiles is non-empty on every golden-corpus resume that has real experience/project content. This is the milestone where the "does the product still work" bar is actually cleared.
- Integration points: still Shadow Mode only; not yet wired to replace the live Gemini call.

**Milestone 4 — Interview Seed Synthesis: Dedicated Design Pass**
- Deliverables: **kept as its own standalone milestone, not folded into parser or cross-reference work**, per Decision 3. Scope: build ~10-15 real project fixtures spanning "rich evidence" (metrics, multiple technologies, clear trade-offs) to "sparse evidence" (a one-line project with no technologies); prototype the template bank from Section 4.4 against them; qualitatively evaluate seed quality and variety before committing to production parser code; finalize the template preconditions and the per-seed confidence mechanism.
- Success criteria: a reviewed template bank design, validated against the fixture set, with the graceful-degradation rule (Section 4.4, Section 10 note below) demonstrably holding: sparse-evidence fixtures produce zero or few seeds, never a fabricated or generic one.
- **Permanent design rule established here, not just a one-time decision**: if high-quality interview seeds cannot be generated from real extracted evidence, the engine produces no seeds for that project rather than a weak or generic one. This rule is binding on all future changes to seed synthesis, not only its initial implementation.
- Integration points: still Shadow Mode; this milestone's output (the template bank design) feeds the Cross-Reference Pass implementation in Milestone 5.

**Milestone 5 — Remaining Entity Parsers (Education, Skills, Certification) + Cross-Reference Pass**
- Deliverables: the three lower-criticality parsers (registered into the same `ParserRegistry` from Milestone 3), the shared technology/gazetteer data module, the Cross-Reference pass (demonstrated-skills tagging, and interview-seed synthesis implemented per Milestone 4's finalized design).
- Success criteria: full field-for-field parity or improvement vs. the Shadow Mode Gemini comparison on the golden corpus.
- Integration points: still Shadow Mode.

**Milestone 6 — Normalization, Confidence Scoring, Validation Layer, HTML Trace Renderer**
- Deliverables: Sections 7 and 8 in full, the unicode/date/dedup normalization pass, and `PipelineTrace.to_html()` (Section 6.6 — deferred until there's a complete pipeline worth visualizing, which this milestone now provides).
- Success criteria: golden-file end-to-end trace snapshot tests (Section 9) pass and are committed as the permanent regression suite; validation observations hand-verified against each golden-corpus resume's known issues; an HTML trace report is viewable end-to-end for at least one golden-corpus resume.
- Integration points: still Shadow Mode.

**Milestone 7 — Cutover, with a Canary Phase**
- Deliverables: swap `generate_candidate_profile()`'s implementation to call the new engine instead of Gemini, behind a feature flag. Cutover proceeds in the following explicit sequence, not a single flip:
  1. **New engine live, Gemini running in comparison-only mode** — the new engine's output is what's actually returned to users; Gemini is still called in parallel (or against a recent sample of real uploads) purely to produce a comparison diff, exactly as in Shadow Mode, but now against real production traffic rather than only the golden corpus.
  2. **Developer review** — comparison diffs from the canary period are reviewed for systematic gaps the golden corpus didn't surface (real resumes are more varied than any fixture set).
  3. **Delete Gemini** — once the canary period's diffs show no unresolved systematic gap, the Gemini call, the `GEMINI_API_KEY` dependency for this feature, Shadow Mode's harness, and the retry/truncation/JSON-fallback machinery in `candidate_profile_generator.py` that existed solely to compensate for LLM non-determinism are all removed in a deliberate follow-up change — not the same change that started the canary phase.
- Success criteria: full existing test suite (`test_candidate_profile_generator.py` and all downstream tests) green against the new engine; canary-period comparison diffs reviewed with no unresolved systematic gap; a manual end-to-end smoke test through the real upload → discussion → dashboard flow.
- Integration points: `app.py:416`, `candidate_profile_generator.py` (becomes the new engine's home, or is renamed — naming/module-boundary decision deferred to implementation time).
- Risk gate: at no point does Gemini's output influence what a real user receives, including during the canary phase — canary Gemini calls are comparison-only, per the Section 2.2 constraints, which apply through this milestone's entire duration, not only through Milestone 0.

**Milestone 8+ (explicitly out of scope unless requested later)**: OCR fallback for scanned PDFs (`pytesseract`+`pdf2image`, both new, heavier dependencies requiring a system-level Tesseract/poppler install — a real deployment-complexity cost, correctly deferred); the standalone Resume Validation product feature UI; per-entity confidence-gated behavior in the discussion planner; a `PipelineTrace` metrics-exporter renderer (Section 6.1) if production-time profiling ever becomes a stated need.

---

## 11. Risks

- **`interview_seeds` quality is the single biggest open risk**, which is exactly why it now has its own dedicated milestone (Milestone 4) rather than being folded into general parser work. A template-based approach will produce narrower, more predictable phrasing than an LLM's — likely a net win for determinism/traceability but a real reduction in *phrasing variety* per project. The permanent graceful-degradation rule (Milestone 4) is the chosen mitigation for the worse failure mode (a fabricated or generic seed) at the accepted cost of the milder one (fewer seeds on sparse projects).
- **Gazetteer maintenance burden.** Technology names, job titles, and section aliases all live in curated static data files that will need periodic updates as new tech/title vocabulary emerges (e.g. a brand-new framework name). This is a real, ongoing cost — but it is a transparent, reviewable-diff cost (add a line to a data file) versus today's opaque cost (hope Gemini's training data stays current), which is the trade-off this whole redesign is choosing to make.
- **Two-column/layout edge cases beyond the k∈{1,2} model.** Complex table-based resumes or 3+-column layouts are explicitly a non-goal (Section 4.2) — the risk is scope creep pressure to keep chasing them. Mitigation: the `extraction_quality` signal and Validation Layer's "ambiguous section" observations exist precisely so these resumes fail *visibly and gracefully* (lower confidence, flagged observations) rather than needing to be silently handled correctly.
- **Row-pitch continuity (Section 4.2's post-validation fix) has one known residual gap**: a resume where every single line carries trailing right-aligned content at the same pitch as the rest of the page (no interspersed description-only lines) would still be misread as two-column, since the check is purely geometric and can't distinguish "real column" from "metadata on literally every row" without content-aware reasoning. Accepted as rarer in practice than the pattern the fix targets; revisit only if real-world validation data (or Milestone 2's Section Detection, once it exists) shows this matters.
- **Coverage will genuinely regress on some fraction of real-world resumes** relative to Gemini's very high general-purpose flexibility — this is the accepted, explicit trade-off in your own requirements (95% extremely well vs. 100% fragile), not an oversight. Milestone 7's canary phase (Decision 5) exists specifically to surface this with real usage data before Gemini is deleted, rather than relying on golden-corpus performance alone.
- **Removing spaCy narrows the engine's semantic-matching surface to SBERT alone** (Decision 4) — location-corroboration and section-header fallback both now depend on one model family rather than two independent ones. This is an accepted simplification, not a free lunch: if SBERT's nearest-neighbor location corroboration proves measurably weaker than NER-based corroboration would have been, that's a data point to revisit, not a foreclosed decision — but it is not expected to matter much given location is a low-criticality, display-only field (Section 1.2).
- **Dropping `phonenumbers` means phone confidence is shape-based, not numbering-plan-validated.** Accepted because `contact_details.phone` has no downstream functional consumer today (Section 1.2) — revisit only if a future feature makes phone validity functionally load-bearing, not before.
- **Shadow Mode discipline is a process risk, not a technical one.** The hard constraints in Section 2.2 are enforceable in code (no reachable path from user requests to the Gemini call after Milestone 0) but the "never treat Gemini output as ground truth without human review" constraint is a human-process discipline, not something the type system enforces. Worth a lightweight code-review checklist item during Milestones 0-7 rather than assuming the constraint self-enforces.
- **Remaining dependencies are modest**: `rapidfuzz`/`dateutil`/`keybert` (pinned explicitly, previously transitive), `hypothesis` (dev-only). No new dependency requires a system-level binary install for the in-scope milestones (OCR, which would, is explicitly deferred to Milestone 8+). This is a smaller dependency footprint than Revision 1 of this document proposed, per Decision 4.
- **Section Detection's leading-block contact fold is position-based, not layout-aware** (Milestone 2 validation, `Milestone2_ValidationReport.md` Findings 2-3): it correctly catches a name banner at the very start of a document, but not one placed in the main column of a two-column layout, since column-major reading order means the sidebar's real sections are read first. The same underlying gap also causes a short ALL-CAPS body word (e.g. "SQL" in a skills list) to occasionally be misread as its own header-like line. Accepted as a real, documented gap rather than solved preemptively — a future generalization (requiring corroboration from what follows a candidate header before committing to a new section) is the likely fix direction, addressing both alongside `repeated_running_header_pdf`'s known limitation, but is not designed or implemented without a dedicated pass.
- **The Section Detection canonical label set (7 labels) doesn't cover every real section type** (publications, teaching, awards, common in academic CVs) -- Tier 3/4 assign the closest available label at low confidence rather than crashing, which is correct behavior, but is a real coverage gap. A future gazetteer/label-set expansion is a scope decision, not made unilaterally during Milestone 2.
- **A section with exactly one entry still fragments** (Milestone 3's `pipeline._absorb_repeated_unknown_entries` fix, Section 4.4): the fix's repetition-based signal (2+ consecutive `"unknown"` sections following a real one) can't fire on a single data point, so a resume with e.g. only one job or one project sees that entry's title line split off as a stray `"unknown"` section, and the parser sees an empty section. Same underlying gap as the two Section Detection risks above (no way to say "this looks like a header but isn't a real boundary" without content-aware signals) -- deliberately demonstrated, not hidden, via the `single_entry_sections_pdf` golden-corpus fixture. A future generalized fix (Milestone 5+, once content-aware corroboration is feasible) could address all of these together.

---

## 12. Decision Log — Design Review Resolutions

This section records what design review changed, for anyone reading this document later who wants to know *why* it looks the way it does rather than re-deriving it.

| # | Decision | Resolution | Where reflected |
|---|---|---|---|
| 1 | Styled `DocumentModel` + Layout Reconstruction as its own stage | **Approved exactly as proposed.** No change. | Section 2.1 |
| 2 | Shadow Mode Gemini as a QA tool | **Approved with hard constraints**: comparison-only, never auto-fills/overwrites/falls back, every discrepancy requires human review, explicitly documented as temporary, physically deleted by Milestone 7 (was "Milestone 6" before the milestone renumbering below). | Section 2.2, Section 9, Section 10 (M0, M7) |
| 3 | `interview_seeds` synthesis approach | **Approved as a dedicated design pass**, kept as its own standalone milestone rather than folded into another. Graceful degradation (no seeds rather than weak/generic ones) established as a **permanent** rule, not a one-time implementation choice. | Section 4.4, Section 10 (Milestone 4), Section 11 |
| 4 | Dependencies | **Simplified.** Keep `rapidfuzz`, `python-dateutil`, `keybert` (pinned). **Removed**: `spaCy` (SBERT absorbs its semantic-matching role via nearest-neighbor location corroboration and the existing Section Detection embedding fallback) and `phonenumbers` (replaced with deterministic regex-shape validation, justified by phone being a display-only field with no downstream functional consumer). | Section 2.2, Section 4.4 (ContactParser), Section 11 |
| 5 | Milestone sequencing | **Approved with an addition.** Kept the shadow-mode-through-implementation shape, but Milestone 7 (cutover) now proceeds through an explicit canary phase — new engine live with Gemini in comparison-only mode, developer review of real-traffic diffs, then a deliberate follow-up change to delete Gemini — rather than a single instant flip. | Section 10 (Milestone 7) |
| — | Developer/debug mode (`PipelineTrace`) | **Approved and promoted to a first-class architectural component.** One `PipelineTrace` object with `to_json()`/`to_html()`/`to_console()` as renderers of the same underlying data — not separate systems. Timing captured per stage (and per parser, via the plugin registry). Confidence explanations use a `+`/`-` sign convention so every renderer formats them identically. The `trace` parameter is baked into every stage signature starting at Milestone 1; renderers land progressively (JSON/console at Milestone 2, HTML at Milestone 6) as the pipeline becomes substantial enough to be worth visualizing. | Section 3.2, Section 3.3, Section 3.4, Section 6 (new), Section 9, Section 10 |
| — | Plugin parser architecture | **Approved as a new architectural requirement.** All six entity parsers implement a common `EntityParser` protocol, registered into a `ParserRegistry` the orchestrator iterates over generically — mirroring the existing `evaluator_registry.py` precedent already in this codebase. | Section 3.3, Section 5 (new) |
| 6 | Layout Reconstruction's column-corroboration guard (post-Milestone-1 validation) | **Row-pitch continuity added; balance ratio kept, not replaced (amended after initial implementation).** The initial line-count balance-ratio guard was found, via a dedicated validation pass against a diverse golden corpus (`docs/architecture/Milestone1_ValidationReport.md`), to accept inline right-aligned dates as a false second column *and* reject genuine short sidebars — the same underlying bug (line count is the wrong proxy for "is this a real column"), not two unrelated problems in tension. A row-pitch-continuity ratio (does each candidate band's own row spacing match the other band's) was added and fixed both findings with one principled signal. The first implementation of this fix *replaced* the balance-ratio guard outright; on explicit direction this was reversed — balance ratio is retained (recalibrated: 0.25 → 0.1, using the validation data directly) since removing a corroborating signal needs evidence it contributes nothing at a scale larger than 22 fixtures, which hadn't been established. The corroboration step is now a named, listed set of independent signals combined by one explicit policy function, specifically to leave a clean extension point for a future semantic signal (e.g. date/label-heavy text detection) to be added alongside the geometric ones without a redesign. Both `MIN_BAND_BALANCE_RATIO` and `MAX_PITCH_RATIO` are documented as validation-derived, tunable parameters, not architectural constants. One residual limitation accepted, not solved (Section 11). | Section 4.2, Section 11 |
| 7 | Section Detection's interface bridge, gazetteer scorer, and a critical case-sensitivity bug (Milestone 2 build + validation) | **List/dict bridged in the pipeline, not the interfaces; two calibration fixes and one bug fixed immediately.** A real gap was found before implementation: `SectionDetector.detect()` returns `list[Section]` but `ParserRunner.run_all()` expects `dict[str, Section]` — resolved by a small `pipeline.py` grouping step (`_group_sections_by_label`), which is also the entire mechanism for cross-page/column continuation, rather than changing either interface. During implementation, `rapidfuzz`'s default `WRatio` scorer was found to over-match short phrases sharing one common word with a gazetteer alias, and was replaced with `token_sort_ratio`. During validation (`docs/architecture/Milestone2_ValidationReport.md`), a critical bug was found and fixed immediately (not held for design discussion, since it was an unambiguous correctness bug, not a trade-off): gazetteer fuzzy matching was case-sensitive, so ALL-CAPS headers — one of the most common real-world conventions — scored near-zero against the gazetteer, fixed with `processor=str.lower`. `EMBEDDING_SIMILARITY_FLOOR` was also raised (0.5 → 0.55) after a false match was observed just above the original floor. Three genuine, unfixed findings were documented rather than patched: the contact leading-block fold is position- not layout-aware (misses a main-column name banner in two-column templates, and a short ALL-CAPS body acronym can be misread as a header); the 7-label canonical set doesn't cover publications/teaching/awards; and the anticipated running-header-fragments-continuation risk was confirmed exactly as predicted before implementation. | Section 4.3, Section 11 |
| 8 | Section Detection fragments multi-entry sections -- found and fixed during Milestone 3 (Entity Parsing) build | **Fixed at the pipeline merge layer (`pipeline._absorb_repeated_unknown_entries`), not in `sections.py`.** While testing the real `ProjectParser` end-to-end, a realistic two-project resume produced zero entities. Root cause: `HeuristicSectionDetector` has no concept of "entry" -- a bold/larger line inside a section (a job's "Company, Role" line, a project's title line) is structurally indistinguishable to it from a genuine new section boundary, and usually lands in `"unknown"`. Investigated whether a purely geometric fix at the Section Detection layer existed (indentation, confidence tier) and confirmed neither distinguishes this from Milestone 2's own validated `ambiguous_header_pdf` case ("Languages," a genuine one-off ambiguous section) -- a blanket "unknown never starts a new section" rule would have fixed the fragmentation bug but broken that already-approved fixture. Resolved instead with a repetition-based signal: 2+ consecutive `"unknown"` sections immediately following a real section, with no other real section in between, are absorbed into it; a single isolated `"unknown"` is untouched. Verified against `ambiguous_header_pdf` as a direct regression test before the fix was accepted. **Documented residual limitation**: a section with exactly one entry still fragments (Section 11), demonstrated deliberately via a new `single_entry_sections_pdf` golden-corpus fixture rather than hidden. | Section 4.4, Section 11 |

---

## 13. Final Review Point

No production code has been written against this document. All five original design decisions plus the developer/debug mode proposal have been resolved (Section 12) and incorporated into Sections 1-11 above. There are no known open architectural questions remaining.

This is the point to do one last full read-through before Milestone 0 begins. Specific things worth a final visual confirmation, since they're new or changed in this revision rather than carried over unchanged:

1. Section 2.2's Shadow Mode constraints — are these strict enough, or does anything else need to be explicitly forbidden before Milestone 0's harness is built?
2. Section 5's `EntityParser`/`ParserRegistry` design — does mirroring `evaluator_registry.py`'s pattern match your expectations for how this should feel to extend later?
3. Section 6's `PipelineTrace` design — confirm the "one object, multiple renderers" shape and the Milestone 1 (hook) / Milestone 2 (JSON+console) / Milestone 6 (HTML) staging matches what you had in mind.
4. Section 10's renumbered milestone sequence (0 through 8+, with Milestone 4 now dedicated to `interview_seeds` and Milestone 7 carrying the canary phase) — confirm this ordering before it becomes the actual execution plan.

Once you confirm the above, the next step is Milestone 0 — still no production code, but the first actual deliverables (the golden corpus and the Shadow Mode harness) would begin.
