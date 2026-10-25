# V7 — A2 Production Cutover: Developer Handoff / Checkpoint

**Date:** 2026-09-13. **Purpose:** checkpoint the end of today's session so a
fresh Claude session (or any developer) can pick this up tomorrow with full
context, without re-deriving anything below.

---

## 1. What we completed today

1. **Inspection report** tracing the full production evaluation path
   end-to-end (evaluator, checkpoint loading, input construction, API
   response schema, frontend rendering, config mechanism) and comparing it
   against A2's actual training/inference requirements — no code changed
   during this step.
2. **A2 production cutover implementation** (code + tests only, not yet
   committed to production use — see §2/§3):
   - New isolated deployment directory `main_cap/cap/deployed_model_a2/`.
   - `deployment_evaluator.py` updated to target `deployed_model_a2/`,
     `max_length=256`, `dimension_names=CANONICAL_DIMENSION_KEYS`,
     `use_private_mlp=False` (explicit, for architecture-reconstruction
     clarity — A2 does not use B0's private-MLP architecture).
   - `final_promotion_decision.json` authored using the real
     `PromotionDecision` Pydantic schema (manual/human decision — see §5).
   - `hybrid_evaluator.py` inspected and left **completely unchanged** —
     confirmed its existing "no overlapping dimensions" code path already
     handles A2 correctly (see §5).
   - `templates/index.html` updated to render A2's four canonical
     dimensions **alongside** (not replacing) the legacy 12-dimension
     rendering, so rollback to the legacy evaluator still renders
     correctly.
   - Test suites added/updated (see §4).

---

## 2. Current A2 deployment state

**NOT YET LIVE.** `deployed_model_a2/` currently contains only:
- `README.md` (documents exactly what's missing and why)
- `final_promotion_decision.json` (real, schema-valid, `approved=True`)

It is **missing**:
- `best_checkpoint_weights.pt`
- `best_checkpoint.json`

Until those two files are copied in, `deployment_evaluator.
bootstrap_production_evaluator()` will fail at the `Checkpoint` JSON load
and **safely fall back to a bare `HeuristicEvaluator`** — this is the
existing, documented, tested degrade-gracefully behavior, not a bug. The
app is fully functional right now; it is just not yet serving A2 scores.

**Legacy `deployed_model/` (12-dimension `experiment_4` checkpoint) is
completely untouched** — still present, still loadable, rollback is a
one-line revert of `deployment_evaluator.py`'s constants (or of the commit
below) since the legacy data was never moved or deleted.

---

## 3. Exact missing artifacts that still need to be copied from Colab

Copy these two files **unrenamed** from wherever the A2 Colab training run
wrote them:

```
artifacts/four_dim_training_v3_expA2/best_checkpoint_weights.pt
    -> main_cap/cap/deployed_model_a2/best_checkpoint_weights.pt

artifacts/four_dim_training_v3_expA2/best_checkpoint.json
    -> main_cap/cap/deployed_model_a2/best_checkpoint.json
```

These were **not** fabricated locally — the real files only exist on
Colab/Drive (per this project's established pattern for every
four-dimension experiment checkpoint). `deployed_model_a2/README.md` has
the full explanation and the exact architecture the checkpoint must match
(`microsoft/deberta-v3-base`, `max_length=256`, four canonical dimensions,
`use_private_mlp=False`).

**Once copied in, run this before trusting it live:**
```bash
cd main_cap/cap
python -m pytest test_deployment_evaluator_a2.py -q
```
If it loads correctly, `bootstrap_production_evaluator()` will pick it up
automatically on next app startup — no further code change needed.

---

## 4. Tests passed / the one unrelated failing test

All run today, all green except one pre-existing, unrelated failure:

| Suite | Result |
|---|---|
| `test_deployment_evaluator_a2.py` (new, 21 tests) | 21/21 passed |
| `test_canonical_dimension_rendering.js` (new, 11 tests) | 11/11 passed |
| `test_deployment_evaluator.py`, `test_evaluator_registry.py`, `test_hybrid_evaluator.py`, `test_evaluation_engine.py`, `test_conversation_engine.py`, `test_model_evaluator.py` (regression) | 166/166 passed |
| `test_model_heads.py`, `test_loss_weighting.py`, `test_four_dim_training_entrypoint.py`, `test_dimension_private_mlp.py`, `test_v4_diagnostic.py`, `test_model_checkpoint_io.py` (regression) | 144/144 passed |
| Existing JS suites (`test_report_*.js`, `test_typeline_race.js`) | all passed |
| **`test_startup_guard.js`** | **FAILS** — `ReferenceError: initializeGazeMonitoring is not defined`. Confirmed via `git stash` that this pre-dates today's changes entirely (fails identically on the pre-session baseline, in code nowhere near anything touched today). Not a regression from this work; needs its own investigation another day, unrelated to A2. |

---

## 5. Important architectural decisions made today

- **HybridEvaluator: retained unchanged, not bypassed.** Line-by-line
  inspection confirmed it already has a dedicated code path for "no
  overlapping dimension names between the trained model and the heuristic"
  — A2's four canonical names never match any legacy heuristic name, so
  every dimension takes that path: A2's `dimensions`/`overall_score`/
  `grade` pass through **completely unmodified**, and `confidence` honestly
  degrades to the trained model's own confidence (rationale text literally
  says so already). Verified directly with adversarial tests, not just
  assumed. No heuristic-to-canonical dimension mapping was invented; no
  legacy score can ever overwrite an A2 score.
- **PromotionDecision: manual/human decision, not automated
  `run_benchmark`.** The existing `run_benchmark`/`decide_promotion`
  machinery scores a single legacy `overall_label.grade` and structurally
  does not apply to the four-dimension per-dimension ordinal scheme
  (`run_four_dim_training.py`'s own module docstring says so). The
  `final_promotion_decision.json` we authored cites A2's real,
  previously-reported metrics (val/test mean QWK, per-dimension QWK, V4
  pair-separation counts vs. A0/A1) as its rationale — nothing invented,
  matches the real `PromotionDecision` schema exactly.
- **Frontend: additive, not a replacement.** `templates/index.html`'s
  dimension phrase banks/labels/detail-grid now support A2's four
  canonical names **alongside** the legacy 11 (not merged, not aliased —
  canonical phrasing was authored fresh from `evaluation_dimensions.py`'s
  own real rubric text, never mapped from legacy phrases). A session
  scored by either family renders correctly; only one family is ever
  present in a real session since a session is pinned to one evaluator for
  its whole duration.
- **Cutover is code-level only.** `deployment_evaluator.py`'s constants now
  point at `deployed_model_a2/` by default; the legacy `deployed_model/`
  directory and its 3 files are untouched on disk. Rollback = revert this
  commit (or just the constants), not a data-recovery operation.

---

## 6. Explicit decision: no more ML experiments tonight

**We decided NOT to run any more model training or architecture
experiments tonight.** A2 remains the final selected four-dimension
evaluator from the completed A0/A1/A2 loss-weighting ablation and the B0
private-MLP architecture ablation. No B1/B2/etc. All V1–V3/A0/A1/A2/B0
experiment artifacts and the frozen V4 diagnostic benchmark were
confirmed untouched throughout today's session (verified via `git diff
--stat -- main_cap/cap/artifacts/` being empty at every checkpoint).

---

## 7. Proposed future direction (NOT implemented — noted only)

A direction under consideration, **not started, not designed in detail,
not implemented in any way today**: use DeBERTa (A2) for a single overall
0–4 score, and let the existing heuristic evaluator continue to supply the
four *diagnostic* dimension breakdowns (strengths/weaknesses/etc.) shown
to the candidate, rather than using A2's four per-dimension CORAL heads as
the displayed breakdown. This would be a meaningfully different product
decision from today's work (which wires up A2's own four canonical
dimensions as the displayed breakdown) and needs its own design review
before any implementation — flagged here purely so it isn't lost, not
because it was decided or is in progress.

---

## 8. What to do next (tomorrow)

1. Get the real A2 checkpoint files onto this machine (§3) — either copy
   from Colab/Drive directly, or re-run the Colab training session if the
   artifacts weren't saved off.
2. Run `python -m pytest test_deployment_evaluator_a2.py -q` — should
   still be 21/21 green (nothing about it depends on the real checkpoint;
   it's a pre-flight check).
3. Copy the two files into `deployed_model_a2/`, then do a real local
   smoke test: start the Flask app, run a resume-discussion session
   end-to-end, confirm the four canonical dimensions render correctly in
   the report UI (Performance Snapshot + per-turn detail grid), and check
   the startup log line for `Production evaluator ACTIVE: 'hybrid-v1'
   (trained checkpoint 'deberta_v3_base_four_dim_training_v3_expA2_epoch7'
   is authoritative...)`.
4. Only after that manual smoke test passes, consider committing/pushing
   the actual checkpoint-bearing `deployed_model_a2/` update (the
   checkpoint binary itself should NOT be committed to git — same policy
   as every other checkpoint in this repo; `deployed_model/`'s own
   `best_checkpoint_weights.pt` isn't tracked either).
5. Investigate `test_startup_guard.js`'s pre-existing `initializeGazeMonitoring`
   failure separately — unrelated to A2, but worth fixing at some point.
6. If/when ready to explore §7's "DeBERTa overall score + heuristic
   dimension breakdown" direction, start with a fresh design review (new
   `docs/architecture/V8_*` doc) before writing any code — same discipline
   used for A2/B0.
