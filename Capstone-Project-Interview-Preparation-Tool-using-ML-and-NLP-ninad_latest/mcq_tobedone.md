# MCQ generation — plan (to be done)

Plan for generating the technical MCQ bank (and the open-question bank it shares a
pipeline with). Not built yet. Written 2026-09-29 from the design discussion.

## Decisions already made

| Item | Decision |
|---|---|
| MCQ test format | 30 MCQs, one 30-minute timer, random across subjects/topics |
| Scoring | +1 correct, −0.25 wrong, 0 unanswered |
| Technical interview | 8–10 main concept questions (no MCQs), all different (spread across subjects, no two from the same topic). After each answer: a good answer moves on; otherwise at most 1–2 follow-ups (clarification or probing) only when the system judges them needed. Same format as standalone and as Round 2 of the Full Interview |
| When questions are generated | **Offline, ahead of time (Option A)** into a checked question bank. The app only *selects* questions live; nothing a user sees is generated unchecked. |
| Generator model | Cost is a constraint → **local Qwen3-8B (4-bit) on the RTX 5050 8 GB**, pending a pilot. Claude API remains the fallback if pilot quality is too low (≈ $10–30 one-time with the Batch API). |
| Proctoring / history | Every session type (MCQ test, technical interview, full interview) is proctored and saved in Sessions history with a per-topic breakdown |

## Inputs that already exist

- `rag_system/rag_tester/topics/<subject>.txt` — ~280 topics (cn, dbms, dsa, ooad, os), each
  checked against the slides; `name | hints`, `#` unit headers.
- `rag_system/rag_tester/knowledge_base_v2/<subject>/` — sections, slide pages, hybrid index
  (`slide_rag.retrieve`), plus `quiz.json`: **94 faculty-written quiz MCQs** (style examples).
- Stage 3 vision model (Qwen3-VL-2B) for diagram/table/formula slides — downloaded, not yet run.

## Pipeline (what the best systems do, replicated for free)

1. **Grounded source.** For each topic, retrieve its slide sections (topic → sections mapping,
   saved as `topic_map.json`). Questions are written only from that text.
2. **Stem + key first, distractors second.** Two separate prompts; one-shot generation gives
   lazy options.
3. **Distractors from structured sources**, not the model's imagination:
   - *Misconceptions* — "common mistakes students make about X" → options
     (e.g. transmission vs propagation delay).
   - *Sibling concepts* — terms from neighbouring sections of the same unit, picked by
     embedding similarity: similar to the key, but not too similar.
   - *Calculation slips* for numericals — bits vs bytes (×8), off-by-one, RTT vs RTT/2.
4. **Over-generate, then filter.** ~5 candidates per slot, keep the best 3. Checks:
   - **Blind solve** — the model answers from the slides *without* the key, several times;
     drop the item unless it consistently picks the key (catches wrong keys and "two correct
     options").
   - **Options-only** — answer without the stem; if it still succeeds, the options leak the
     answer (e.g. the key is the longest option).
   - **Item-writing rules in code** — no "all/none of the above", similar option lengths,
     no double negatives, one best answer, no stem/key word overlap that cues the answer.
   - **Duplicates** — embedding similarity against the rest of the bank.
5. **Style examples.** Few-shot with the faculty quiz MCQs so items read like real exam
   questions; interview style guide: mostly why / how / compare / what-if, ~10–15 %
   numericals only where the topic calls for it.
6. **Human spot-check.** ~10 % sample on a small approve / reject / edit page (admin only);
   rejection rate by subject and reason drives prompt/threshold tuning.
7. **Calibration from real use** (add once the MCQ test is live). Per item from session
   history: difficulty (% correct) and discrimination (do strong users get it right more
   often than weak users?). Auto-flag items nearly everyone misses (likely a broken key) or
   that don't separate strong from weak users; retire or regenerate them. (IRT later if
   needed.)

## Bank sizes and run time (estimates)

| Bank | Generated | Expected to survive checks | Enough for |
|---|---|---|---|
| MCQs | 5 candidates → 3 kept per topic ≈ 840 | ~600–700 | ~20 fully distinct 30-question tests |
| Open questions | 2 per topic ≈ 560 | ~480–500 | ~50 interviews without repeats |

Each open question also stores a reference answer, key points and 2–3 common misconceptions
(used by the grader and for follow-up probes).

Qwen3-8B 4-bit on the RTX 5050: ~1–1.5 min per topic for generation + checks, ~1.5× more
with over-generation → roughly **10–13 h total**, run one subject per evening. Every output is
cached by (content hash, prompt version, model), so runs resume after interruption and never
redo finished topics.

## Expected quality with Qwen3-8B (estimate, not measured)

| Part | Expectation |
|---|---|
| Open questions, reference answers, key points | Good |
| MCQ correct answer | Good once blind-solve filtering is applied |
| Distractors | Weakest part — mitigated by steps 3–5 |
| Tricky interview-style MCQs | Medium; some will be plain recall |

Qwen2.5-1.5B (used by the old `rag_tester/generate.py`) is **not viable** for this.

## Smoke test results (2026-09-29, `python -m slide_rag.llm_smoke_test`)

Qwen3-8B, 4-bit NF4 via bitsandbytes 0.50.2 on the RTX 5050 (compute capability 12.0) — **works**.

| Measure | Result |
|---|---|
| Load time | ~25 s |
| GPU memory | 6.1 GB (peak 6.5 GB of 8 GB) |
| System RAM | fine (5.9–6.5 GB free before load) |
| Generation speed | ~16 tokens/s (thinking mode off) |
| JSON format | valid on both samples |

Samples (one open question + one MCQ each, from retrieved slide sections):
- **OS / Banker's algorithm:** accurate, slide-grounded answer and key points; correct MCQ key; distractors
  too easy ("immediately allocate without checking").
- **CN / TCP congestion control:** good answer and plausible distractors, **but two defensible options**
  (halve cwnd on loss vs reset to 1 MSS on timeout). Confirms the blind-solve / "exactly one correct option"
  check is essential, and prompts should ask the model to state the condition in the stem.

At ~16 tok/s, one topic (≈5 items + checks, ~2,500–3,500 generated tokens) takes ~3–4 min →
~280 topics ≈ 14–18 h in total; run a subject per night. Next: the ~10-topic pilot with the full
generation + filtering steps above.

## Risks

- Only ~4.5 GB system RAM free on the laptop — 4-bit loading streams weights to the GPU;
  close other apps; the pilot confirms it fits.
- The Qwen3-VL-2B vision model and Qwen3-8B cannot share the 8 GB GPU; run them at
  different times (vision is ingestion-only).
- Some weak MCQs will pass the checks → spot review + calibration (step 7) catch them.

## Next steps

1. Run Stage 3 (vision) on all subjects; rebuild `knowledge_base_v2`.
2. `slide_rag/topics.py`: topics → sections mapping + coverage report (`topic_map.json`).
3. **Pilot**: install `bitsandbytes`, load Qwen3-8B 4-bit, generate ~10 topics (~50 items)
   across subjects with steps 1–5; review together; decide local vs API.
4. Full generation per subject → `question_bank/<subject>.json`
   (`id, topic_id, type (mcq|open), stem, options, key, explanation, reference_answer,
   key_points, misconceptions, difficulty, source_pages, model, prompt_version`).
5. Review page (step 6).
6. App: MCQ Test session (30 Q / 30 min / +1 −0.25), Technical Interview (8–10 Q, follow-ups),
   Full Interview round 2 switched to concept questions; per-topic stats (`UserTopicStat`),
   history, proctoring.
7. Calibration job (step 7) once real answers accumulate.
