# 08 — Slide RAG pipeline & question bank (`rag_system/rag_tester/`)

Owner: Ninad. **Offline only** — the app just reads `question_bank/*.json`. Run commands from `rag_system/rag_tester`.
Not in git: `sources/<subject>/*.pdf` (faculty slides, ~5,800 slides), `knowledge_base_v2/`, caches (`.slide_cache/ .vision_cache/ .qbank_cache/ .enrich_cache/`), per-subject `*_report.md`.
Hardware used: RTX 5050 8 GB, CUDA 13. Ollama `qwen3:8b` Q4_K_M (~45 tok/s).

## Pipeline (`slide_rag/`)
| Stage | Module | What |
|---|---|---|
| 1 extract | `extract.py` | PyMuPDF layout-aware per slide: title (largest top line), body bullets, code (monospace), tables (`find_tables`), running header/footer removal, diagram-label noise kept aside; RapidOCR for picture-only slides (optional). Cached per PDF hash + extractor version |
| 2 classify | `classify.py` | types deck_title/contents/admin/quiz/divider/image_only/image_heavy/content…; drops keep a `dropped` reason; quiz slides → `quiz.json`; flags `needs_vision` |
| 3 vision | `vision.py` | Qwen3-VL-2B (bf16, GPU) reads diagrams/tables/formulas; only run on CN so far; retrieval aid, NOT evidence |
| 4 sections | `sections.py` | merge "(contd.)", stem-sharing titles, worked-problem solutions into sections (`SECTION_MAX_WORDS`) |
| 6 index | `index.py` | children (slide + section-opening) with breadcrumb headers → FAISS (MiniLM) + BM25 (`text_utils.tokenize` both sides) |
| retrieve | `retrieve.py` | dense+BM25 min-max mix (`alpha`), roll up to section, rerank top with `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| 8 report | `report.py` | per-subject diagnostics |
| build | `build.py` | `python -m slide_rag.build [--subject dbms]` → `knowledge_base_v2/<subject>/{slides,sections,children}.json, index.faiss, bm25.pkl, manifest.json, report.*` |
| eval | `retrieval_eval.py` + `eval/gold_<subject>.json` | section/slide hit@k, MRR (gold hit@5 96–100%) |

## Question bank generation
1. `topics.py`: `topics/<subject>.txt` lines `Name | hints | priority` (279 topics) → `topic_map.json` + coverage good/thin/missing.
2. `qbank.py` (resumable): Qwen3-8B per topic writes questions with `reference_answer`, 3–5 `key_points` each with `quote` (must fuzzy-match slide text ≥88), `followup`, `followup_answer`; thinking-mode judge pass; no invented examples. `llm_client.py` (Ollama, token-counted prompts, JSON schema, fixed seed, `PromptTooLong`).
3. `rank_bank.py`: confidence from signals (support, judge, quotes, grounding, first_try …); below threshold → `active: false`. Hand-reviewed questions (`quality_score` set) keep their `active` flag.
4. `enrich_bank.py`: per key point `variants` (informal phrasings) and `followup_replies` (short correct replies); `core_point`. `--no-generate` re-applies cache.
5. `interview_priority.py`: hand-assigned tier 3/2/1 per topic → `interview_priority`.
6. `apply_repairs.py question_bank/repairs/<batch>.json [--dry-run]`: hand edits by question id (quality_score, quality_note, reference_answer, active, question, difficulty, key_points…); changed points drop their variants; each point re-checked against its quote (MiniLM ≥ .35). Batches 1–7 exist (2026-10-03, 2026-10-25).
Order to rebuild: build → topics → qbank → rank_bank → enrich_bank → interview_priority (→ apply_repairs).

## Bank JSON (one array per subject: cn, dbms, dsa, ooad, os)
```json
{ "id": "os.preemptive_vs_non_preemptive_scheduling.medium1", "subject": "os",
  "topic_id": "os.preemptive_vs_non_preemptive_scheduling", "topic": "...", "unit": "CPU scheduling",
  "priority": "high", "topic_coverage": "good", "question": "...", "difficulty": "easy|medium|hard",
  "reference_answer": "...",
  "key_points": [{"point": "...", "quote": "<slide text>", "followup": "...", "followup_answer": "...",
                  "variants": ["..."], "followup_replies": ["nope", "..."]}],
  "source_pages": [126], "source_sections": [89], "runtime": "ollama-qwen3-8b-q4_k_m", "prompt_version": "6",
  "review": "...", "confidence": 0.914, "confidence_signals": {...},
  "active": true, "curated": true, "quality_score": 9, "quality_note": "...", "interview_priority": 3,
  "core_point": {"point": "...", "variants": [...]} }
```
App reads: id, subject, topic_id, topic, difficulty, question, reference_answer, key_points[point, followup, followup_answer, variants?, followup_replies?], confidence, source_pages, core_point?, curated, interview_priority, active.
Counts: 425 / 323 active / 321 curated. `question_bank/quality_review.md` = per-question hand scores + uncovered topics (29 of 279 topics have no question, mostly CN).

## Key-point rules (measured)
Short, single-claim points (long "complete" points made NLI grading worse). Every point must quote the slides. After editing, run `python grader_eval/sanity_check.py --ids <id>` (own reference answer must score ≥ .70; other questions' answers < .50).

## Tests
`slide_rag/tests/test_pipeline.py` (19 tests; needs faiss-cpu, rank-bm25).
Limits: OOAD index predates latest extractor fixes (rebuild); vision only on CN; 8B judge is lenient on reasoning.
