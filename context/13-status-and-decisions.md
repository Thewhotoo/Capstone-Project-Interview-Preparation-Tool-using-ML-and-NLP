# 13 — Current status, decisions, open work (as of 2026-11-12, main = `99bdba9`)

## State right now
- main is clean, pushed, CI green at `99bdba9`. Local == GitHub main.
- Mayuran's branch (`maburan-new`) is fully merged; he should `git pull` main before new work.
- Test run (from `main_cap/cap`, `python -m pytest -q`): **1,898 passed, 22 skipped** (1,429 collected outside
  `resume_engine/tests` + 491 inside). slide_rag: 19. JS: 11 files.
- Ollama on this laptop has `qwen3:8b` and `qwen3:4b`; RTX 5050 8 GB runs 8b "100% GPU".
- Docker image builds and runs (CPU-only torch inside the container → NLI/MiniLM/Whisper on CPU there;
  `python app.py` on the laptop uses the GPU and is faster for daily use).

## Headline numbers (cite these; all measured)
| What | Number |
|---|---|
| Round 2, fresh set (never tuned): fast grader → with LLM blend | decision 66% → 80%, r 0.55 → 0.848, per-point 0.64 → 0.76 |
| Round 2, frontier LLMs on the same fresh answers | Claude Opus 5.5: 0.84 / 88% / r 0.95; Gemini: 0.85 / 86% / r 0.93 |
| Round 2, 28 real team answers (`human_answers`) | blend: decision 75%, r 0.64, gap 0.107 |
| Round 2, team_test | r 0.904 (after 2026-11-07 cap change) |
| Round 2 follow-up replies (fresh) | judged right 86% → 96%, wrong accepted 29% → 8% |
| Round 1, qwen3:4b → 8b | final test pairwise 84% → 94%, QWK 0.79 → 0.86; holdout QWK 0.67 → 0.78 |
| Round 2, 4b vs 8b | decision 86.9% vs 90.3%, r 0.91 vs 0.95; follow-ups equal (89.6%) |
| Code size (tracked .py/.html/.js/.css) | 84,684 lines: app 39.4k (backend 29.9k + index.html 9.5k), tests 26.6k, eval 7.7k, data-building 6.5k, RAG 3.4k, training 0.9k |

## Decisions (newest first) — and why
- **2026-11-07 Contradiction cap needs the LLM to agree** (`llm_judge.CONTRADICTION_CAP_BELOW = 0.5`). The fast grader's
  NLI contradiction check capped 3 of 28 good real answers at 0.2. Chosen on tuning sets, measured once on held-out.
- **2026-11-07 No blind human labelling.** The team typed 28 answers (`grader_eval/human_set/answers_*.json`) but will
  not label. Claude Opus 5.5 labelled them (`human_answers.json`, `label_source`). **In the paper: "28 real student
  answers, labelled by Claude Opus 5.5" — never call it a human evaluation, never claim labels were done by the team.**
  All older labelled sets are LLM-drafted too (members corrected some). Keep this wording honest in any write-up.
- **2026-10-29 qwen3:8b first in both rounds** (4b on GPUs < 8 GB via install.py). Measured better in both rounds.
- **2026-10-29 `CAP_ALLOW_NO_LLM=1` opt-out** restored on top of Mayuran's mandatory-LLM startup check.
- **2026-10-28 Round 2 final = 0.6 × LLM holistic + 0.4 × fast** (was 0.5/0.5 point-count blend).
- **2026-10-26 Follow-up reply counts only if BOTH graders accept it** (wrong accepted 17.6% → 4.1%).
- **Live interview never waits on an LLM**: fast graders decide follow-ups instantly; LLM re-grades run on one
  background thread and only change the final report.
- **Never tune on `fresh`** (or team_test / human_answers): tune on llm400 / mine40 / team_tune, measure once.
- Round 1 production evaluator is `ResumeEvidenceEvaluator` v2 (Tier 0), not DeBERTa (Tier 1 fallback).

## Open work (not started unless the user asks)
1. **Weak key points in the bank.** e.g. `dsa.depth_first_search.medium1` key point 3 "analogous to pre-order traversal"
   isn't asked by the question; both graders mis-marked a real answer (fast: credited it; LLM: missed "stack-like due to
   recursion"). Fix = repair batch (see `08`), then audit the bank for key points the question doesn't ask. Changed
   questions make old labels stale (benchmark skips them) — keep it honest.
2. **Fully offline frontend**: MediaPipe JS (`cdn.jsdelivr.net`) and Google Fonts load from the internet; bundle into
   `static/` (~10 MB). Everything else already runs offline.
3. **Round 1 LLM blend weight** (`LLM_BLEND_WEIGHT = 0.6`) was tuned with qwen3:4b; retune for 8b on the dev set.
4. **Round 2 gap to frontier**: few-shot examples in the judge prompt, grading twice and averaging, re-tuning the blend.
5. GitHub Actions versions (Node 20 deprecation warning).
6. Move one-off dataset scripts out of `main_cap/cap/` (`artifacts/v4_diagnostic/`, `build_v5_*`), archive not delete.
7. Stale docstrings/docs listed in `12-gotchas-and-drift.md` (user chose to leave them for now).
8. Whisper mishears phrases ("last in, first out" → "lasting first out"); the tech-vocabulary prompt helps terms only.

## Paper notes
- Strongest honest claims: two-stage grading (instant + background LLM) closes much of the gap to frontier LLMs at
  zero cost and fully local; fresh-set and held-out methodology; real-answer test set.
- Must disclose: labels are LLM-made (Claude/Gemini drafted; some corrected by members); human_answers labelled by
  Claude; frontier comparison likely favours LLM judges because labels are LLM-drafted.
- Mohler human-graded benchmark (Round 1 model choice) is the only fully human-labelled external set.

## Application/interview blurbs already written (2026-11-12)
Short descriptions of the project, hardest problem (real-interview feel vs grading human language → two-stage
grading), and a debugging story (contradiction cap misfire found via worst-gap list → traced per component) were
drafted for the user; numbers above are the ones to reuse.
