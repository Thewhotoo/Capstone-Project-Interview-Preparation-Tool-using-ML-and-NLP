# 12 — Gotchas, doc drift, small issues (as of 99bdba9)

None of these have been fixed; the user chose to keep them listed only.

## Stale docstrings / docs (trust the code)
- `resume_evidence_evaluator.py` module + class docstrings say "NOT DEPLOYED … v5_1088 remains the active production evaluator" — wrong: it is Tier 0, active by default (`deployment_evaluator._try_activate_resume_evidence`).
- `overall_single_evaluator.py` / `overall_score_model.py` say "NOT DEPLOYED" — it is the Tier 1 fallback.
- `deployment_evaluator.py` lower docstring still describes the Hybrid wiring as the main path.
- `deployed_model_overall_single_v5_1088/README.md` references `deployed_model_overall_single_v3/` and `deployed_model_a2/` rollback tiers that no longer exist.
- `fact_checker.py` module docstring: default `qwen2.5:3b`, timeout 20 — code: `qwen3:8b` first, timeout 30.
- `app.py` `/reply` docstring and `conversation_engine.advance_conversation` docstring say there is no adaptive probing — adaptive follow-ups are on (`enable_adaptive_followups=True`).
- `question_realizer.realize` annotated `-> InterviewQuestion` but returns `(InterviewQuestion, variant_idx)`.
- `PROJECT_DOCUMENTATION.md`: §1 says Round 1 re-grade uses qwen3:4b (now qwen3:8b first); §2 says Ollama is "not needed to run the app / the app never calls it" (now required at startup and used by both rounds); §3.6 says "There is no CI" (there is). §7 is otherwise a good, current limitations list.
- `docs/architecture/ResumeDiscussion_v2.md` describes v1 behaviour (random jitter, 12/20 questions, SBERT dedup). `Experiment4_TrackB_APIFree.md` says "pilot only".
- `resume_engine` docstrings in `pipeline.py`, `factory.py`, `confidence.py`, `extractor.py` still say "Milestone 0 stub" / "DOCX lands later".
- Liveness: doc says head-turn only — correct; the blink code is still present but disabled (`index.html` ~6933).

## Behaviour traps
- **Bank is `lru_cache`d** → restart the app after editing `question_bank/*.json`.
- **Changing Round 1 planning/phrasing** breaks replay of in-flight conversations in Redis (they get dropped → 404); harmless after the 2 h TTL.
- `/api/resume-discussion-v2/reply|end` take the conversation id under the key `session_id`.
- Two grade scales: per-turn (.90/.75/.55/.30) vs session/report (.80/.60/.40/.25).
- Round 1 answers have **no length cap** (only the 10 MB request limit); Round 2 truncates at 5000 chars. A huge Round 1 answer makes SBERT/NLI + LLM work expensive.
- Abandoning a session cannot cancel an already-running re-grade; it writes an orphan `regrade:*` / `techregrade:*` key that expires after 2 h.
- `evaluator_registry` is a module-global dict (not thread-safe; same name overwrites).
- `_availability` checks for Ollama are cached 300 s — if Ollama starts after the app, re-grades stay off up to 5 min.
- Full Interview = two unlinked DB sessions; the combined report exists only client-side at the end.
- Proctoring/integrity are client-side; backend only sanitises what the client sends.
- No CSRF tokens (SameSite=Lax cookies only); no email verification.
- `hybrid_diagnostics.jsonl` grows without bound (only when the Hybrid tier is active).
- `parser_tests/resumes/` contains real resumes (PII) in git.
- `CAP_RESUME_PARSER=gemini` is never consulted by `app.py`.
- Windows console: printing docstrings with non-ASCII chars needs `python -X utf8`.

## Known limits worth remembering
- Round 2 live move-on decision uses the fast grader only (66% on fresh); LLM blend only affects the final report.
- NLI grader checks that points are *stated*, not that facts are right; strict on short informal answers.
- 29/279 topics have no bank question; hard questions mostly held back (25 curated hard).
- Round 1 DeBERTa scores track length; evidence evaluator avoids that but can't verify correctness without the LLM.
