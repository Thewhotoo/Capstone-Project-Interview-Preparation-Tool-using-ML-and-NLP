# 05 — Resume Intelligence Engine (`main_cap/cap/resume_engine/`)

Owner: Mayuran. Deterministic, local, no LLM. Replaced a single Gemini call (Milestone 7 cutover).
Design docs: `docs/architecture/ResumeIntelligenceEngine.md`, `Milestone{1..7}_*.md`, `Milestone4_Design.md` (seed synthesis).
Entry: `candidate_profile_generator.generate_candidate_profile_via_engine(path)` = `factory.default_pipeline().run(path, fmt)` → `candidate_profile_mapper.map_to_candidate_profile(annotated)` → `CandidateProfile.model_dump()`.
Called from `resume_store.parse_resume` at upload (signup, `/api/resumes`, `/api/classify-resume`). Formats: `.pdf .docx .txt` (no `.doc`). `ExtractionFailure` → user-facing `ResumeUploadError`.

## Structure
- `interfaces.py` — Protocols for every stage + `ParserResult(entities, confidences, observations)`, `EntityParser`, conformance check.
- `pipeline.py` — `ResumePipeline.run`: depends only on interfaces; `_timed` records `StageTrace` when a `PipelineTrace` is passed.
- `factory.py` — composition root (only place importing concrete stages); `default_parser_registry()` registers 6 parsers with a shape-conformance check.
- `registry.py` — `ParserRegistry.run_all(sections_by_label, doc)`.

## The 8 stages
| # | Stage | Module | Notes |
|---|---|---|---|
| 1 | Document extraction | `extractor.py` `PdfDocxExtractor` | PyMuPDF dict spans (font, size, bold, bbox) + hyperlinks; python-docx runs/styles/tables; TXT. → `DocumentModel(spans, body_font_size, hyperlinks, extraction_quality, layout_mode…)` (`document_model.py`) |
| 2 | Layout | `layout.py` `ColumnAwareLayoutReconstructor` | gap-analysis k∈{1,2} columns per page with corroboration signals (line count, balance, pitch, y-overlap); 3+ columns unsupported |
| 3 | Section detection | `sections.py` `HeuristicSectionDetector` | header candidates (≤6 words, font ≥1.05×body, bold/caps/DOCX heading style) → label cascade: exact/gazetteer (`section_gazetteer.py`) → rapidfuzz (≥85 confident, <55 reject) → SBERT embedding (≥.55). Pre-first-header block = contact; contact regex safety net; running-header removal |
| — | (pipeline) | `pipeline.py` | `_absorb_repeated_unknown_entries` (2+ consecutive "unknown" after projects/experience = entry sub-headers), `_group_sections_by_label` |
| 4 | Entity parsing | `parsers/*.py` | contact, experience, projects, education, skills, certifications; `_entry_clustering.py` shared bold-header clustering |
| 5 | Cross-reference | `cross_reference.py` | interview-seed synthesis (`seed_synthesis.py`) + demonstrated-skill tagging |
| 6 | Normalization | `normalization.py` | NFKC/whitespace, date separators, technology canonicalization/dedupe |
| 7 | Validation | `validation.py` | collects Observations (missing linkedin, no measurable outcome, empty summary, inconsistent dates…); never gates |
| 8 | Confidence | `confidence.py` | `Confidence(score, reasons["+x","-y"])`, `AnnotatedCandidateProfile(parser_results, observations, overall_confidence)` |

Parsers (key behaviours):
- `contact_parser.py`: name/email/phone/linkedin/location; uses hyperlinks (icon-only LinkedIn).
- `experience_parser.py`: role/company/duration/summary; `role` matters most (topic_pool needs role or company). Handles two-line headers, institution-marker fallback (role="").
- `project_parser.py`: title (must be exact — `traceability.find_project_by_title` matches on it), summary, technologies (technology_gazetteer + "Tech:" lines), concepts via KeyBERT (SBERT backbone, lazy).
- `education_parser.py`, `skills_parser.py` (split on delimiters, gazetteer-normalised, unknown tokens kept), `certification_parser.py` (also sweeps skills/summary for stray certs; substring matching).
- Gazetteers (plain data): technology, concept, section, degree, institution, job_title, location, domain, certification. `technology_gazetteer.TECHNOLOGIES` is also used by Round 1 evaluation and the fact checker.

## Seed synthesis (`seed_synthesis.py`)
Fixed template families, priority metric > tradeoff > tech > integration > concept; `MAX_SEEDS_PER_PROJECT = 4`, `TECH_PROBE_CAP = 2`, `INTEGRATION_PROBE_CAP = 1`, `CONCEPT_PROBE_CAP = 1`. Evidence regexes: metrics ("reduced … 40%", "3x"), comparisons ("instead of", "chose X over", "migrated from X to"). Seeds are full question sentences → become `PROJECT_DEEP_DIVE` specs (`text_seed_is_sentence=True`).

## Mapper (`candidate_profile_mapper.py`)
Builds fields with no upstream producer: `predicted_domain` (`classify_domain` over domain_gazetteer), `experience_level` (Beginner/Intermediate/Advanced from durations), `interview_blueprint.technical_topics` (gazetteer tech/concept matches per project/experience with `originating_project/experience` + evidence), `estimated_strengths/weaknesses` (weaknesses from observations), `starting_difficulty`, `resume_summary`. Validated by constructing the pydantic `CandidateProfile`.

## CandidateProfile schema (`candidate_profile_generator.py:58-201`)
`candidate_name, contact_details{email,phone,linkedin,location}, skills[str], education[{degree,major,institution,graduation_year}], experience[{company,role,duration,summary}], projects[{title,summary,technologies[],concepts[],interview_seeds[]}], certifications[str], predicted_domain, experience_level, confidence, interview_blueprint{resume_verification_topics, technical_topics[{topic, originating_project, originating_experience, evidence}], starting_difficulty, estimated_strengths, estimated_weaknesses}, resume_summary`.
`profile_to_frontend_format(profile)` flattens it for the UI (`name, email, phone, predicted_domain, discussion_domain, skills, experience{years,level}, education, projects, certifications, focus_topics, resume_summary, experience_detail`).
The rest of `candidate_profile_generator.py` (~900 lines) is the legacy Gemini parser — only reachable via `CAP_RESUME_PARSER=gemini`, which `app.py` does not consult. Treat as dead/dev-only.

## Tests & benchmarks
- `resume_engine/tests/` (~511 tests, run separately), `golden_corpus/<case>/` with `resume.pdf|docx` + `metadata.json` + optional `expected_{sections,layout,entities,interview_seeds}.json` (cases: two-column, Canva, Overleaf, scanned, corrupt, running headers, icon headers, …).
- `parser_tests/resumes/001-010.pdf` (real PII).
- `benchmarks/parser/score_parser.py` field-level F1 vs gold (`gold_templates.json` + private real gold). Baseline 2026-10-23: projects F1 .91, tech .81, skills .90, education .57, experience .53 (real resumes).

## Known limits
3+ columns / ruled tables; company↔role swaps; school-level education dropped; inline cert lists merged; `graduation_year` = first year found; mapper years ignore "Present"; no publications/awards labels; `ProjectParser` still emits `-interview_seeds_not_implemented_until_milestone_5` reason; `DocumentModel.source_format` Literal lacks "txt"; `PipelineTrace.to_html()` unimplemented.
