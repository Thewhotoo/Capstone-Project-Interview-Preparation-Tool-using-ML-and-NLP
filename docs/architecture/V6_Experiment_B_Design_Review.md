# V6 — Experiment B Design Review: Dimension-Specific MLP Projections

**Status: READ-ONLY design review. No code changed, no training run, no
dataset created or modified, no commit/push beyond this document.** Written
after Experiment A2 (smoothed CORAL threshold weighting, `alpha=0.4`) was
trained and evaluated against the frozen 58-example V4 diagnostic
(`artifacts/v4_diagnostic/`, see `a2_inference/` and
`a1_inference/`). This document proposes and scopes Experiment B; it does
not implement it.

## 0. Premise: why B, not more of A

A0 → A1 → A2 all varied the same single knob — the CORAL threshold
`pos_weight` exponent — while holding architecture fixed. The trend across
that axis was consistently a gain in *calibration* (bias reduction) and
some discrimination, but A2 still fails the core relevance-alignment
contrast (concise/direct vs. detailed/off-target answers): several of the
8 relevance pair groups remain tied or borderline, and detailed-but-
irrelevant answers are still sometimes scored high. That is the signature
of a **representation** problem, not a **calibration** problem — reweighting
the loss changes which mistakes cost more, but the shared pooled vector
feeding all four CORAL heads may simply not carry enough
dimension-separated signal for `relevance_completeness` to be distinguished
from e.g. `depth_specificity`/`technical_correctness` (both of which
reward "detailed"). Experiment B's architecture hypothesis targets that
directly: give each dimension a small private nonlinear projection between
the shared encoder and its CORAL head, so each head can learn to attend to
different components of the shared 768-d representation instead of all
four reading the identical vector through an identical (per-dimension only
in its final linear layer) transform.

---

## 1. Where the current shared representation is produced

`model_backbone.py:186-194`, `CrossEncoderBackbone.forward`:

```python
def forward(self, input_ids, attention_mask):
    outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
    hidden = outputs.last_hidden_state          # (batch, seq, hidden)
    if self.config.pooling == "cls":
        return hidden[:, 0, :]                  # CLS pooling (default)
    ...                                          # mean pooling (alternative)
```

This returns one `(batch, 768)` tensor per (text_a, text_b) pair — the
single shared pooled representation. It is produced **once** per forward
pass and is architecturally identical regardless of which dimension is
being scored (cross-encoder convention, `model_backbone.py`'s own module
docstring: "ONE shared encoder, invoked once per pair"). `hidden_size=768`
for `microsoft/deberta-v3-base` (`CrossEncoderBackbone.__init__`,
`model_backbone.py:184`, reads it straight from `encoder.config.hidden_size`
— never hard-coded).

## 2. Exactly what tensor enters each CORAL head today

`model_heads.py:264-271`, `MultiTaskModel.forward_dimensions`:

```python
def forward_dimensions(self, input_ids, attention_mask):
    pooled = self.backbone(input_ids, attention_mask)      # (batch, 768)
    dimension_logits = self.dimension_heads(pooled)        # <- SAME pooled tensor, all 4 heads
    ...
```

`model_heads.py:177-178`, `DimensionOrdinalHeads.forward`:

```python
def forward(self, pooled):
    return {name: head(pooled) for name, head in self.heads.items()}
```

Every one of the four `CoralOrdinalHead` instances (`technical_correctness`,
`depth_specificity`, `relevance_completeness`, `grounding_ownership`)
receives the **exact same `(batch, 768)` pooled tensor**, unmodified. Each
head's only dimension-specific parameters are its own
`shared = nn.Linear(768, 1, bias=False)` plus its own threshold biases
(`model_heads.py:83-88`) — i.e. today, "dimension-specific capacity" is
literally one 768-length weight vector per dimension. That is the entire
representational bottleneck Experiment B targets.

## 3. Where the dimension-specific MLPs should be inserted

Between step 1's output and step 2's input — i.e. inside
`DimensionOrdinalHeads` (or a new sibling module), immediately after
`pooled = self.backbone(...)` and before each `CoralOrdinalHead.forward`.
Concretely, the cleanest insertion point is `DimensionOrdinalHeads.forward`
(`model_heads.py:177-178`): instead of every dimension calling
`head(pooled)` directly, each dimension first passes `pooled` through its
own private `nn.Sequential` MLP, and the MLP's *output* — not `pooled`
itself — is what reaches `CoralOrdinalHead`. `CoralOrdinalHead` does not
need to change at all (see §9); it already accepts an `in_features`
parameter, so it simply gets constructed with the MLP's output width
instead of `backbone.hidden_size`.

```
DeBERTa (unchanged)
  → pooled (768,)                              [unchanged, shared, one forward pass]
  ├── TC_MLP(768→h→h)   → CoralOrdinalHead(h)   [new]
  ├── Depth_MLP(768→h→h) → CoralOrdinalHead(h)  [new]
  ├── Relevance_MLP(768→h→h) → CoralOrdinalHead(h) [new]
  └── Grounding_MLP(768→h→h) → CoralOrdinalHead(h) [new]
```

`self.concept_head` and `self.missing_reasoning_head`
(`model_heads.py:261-262`) are untouched — they are separate heads off the
same `pooled` tensor and are out of scope for this ablation (see §20,
"single variable").

## 4. Conservative MLP architecture recommendation

Smallest sensible change, one hidden layer, projecting **down** rather than
staying at 768 or projecting up:

```
Linear(768 → h)  →  activation  →  Dropout(p)  →  Linear(h → h)   [optional, see §6]
```

Recommendation: **skip the second `Linear(h → h)`** for the initial B run
(see §6) — i.e. the smallest version is:

```
Linear(768 → h) → GELU → Dropout(0.1)
```

feeding directly into `CoralOrdinalHead(in_features=h)`. This is a single
new linear layer plus nonlinearity plus dropout per dimension — the
smallest change that gives each dimension a genuinely separate,
nonlinear function of the shared representation (a bare `Linear(768→h)`
with no activation would be representationally still just a linear
re-projection, and a stack of two linear layers with no nonlinearity
between them collapses to one linear layer — the activation is what
actually buys new capacity, not the extra layer).

## 5. Hidden dimension recommendation and parameter-count increase

Recommend **h = 128**. Reasoning:

- Backbone (`microsoft/deberta-v3-base`) is ~184M parameters. Any head-side
  addition here is trivial by comparison, so the constraint is not "will
  this make the model too big" but "will this overfit 166 training
  examples" (see §18) — so bias toward the smaller end of reasonable, not
  the largest the parameter budget could tolerate.
- Current per-dimension head cost: `CoralOrdinalHead(768, 5)` has
  `768 (shared.weight) + 1 (bias_base) + 3 (bias_deltas)` ≈ 772 parameters.
  Four dimensions ≈ 3,088 parameters total today.
- With `h=128`, one `Linear(768, 128)` MLP layer is `768*128 + 128 =
  98,432` parameters; four dimensions ≈ **393,728 new parameters**. The
  CORAL head itself then shrinks slightly (`CoralOrdinalHead(128, 5)` ≈
  `128 + 1 + 3 = 132` params/dim vs. 772 before, since `in_features` drops
  from 768 to 128) — net new parameters ≈ 393,728 − (4×(772−132)) ≈
  **391,168**, i.e. ~0.21% of the 184M backbone. Negligible relative to the
  encoder, non-negligible relative to 166 training examples (see §18) —
  which is exactly why h should stay small and single-layer.
- `h=128` is a deliberately round, conservative choice — not tuned against
  V4 or any held-out split (per the ablation constraint in §16/§17). If a
  narrower bottleneck is wanted, `h=64` roughly halves the new-parameter
  count again (~196K) at the cost of representational headroom; `h=256`
  would be the upper end still worth calling "conservative." §19 discusses
  an even smaller alternative.

## 6. Whether one hidden layer is sufficient

Yes — recommend **exactly one hidden layer** (`Linear(768→h) → activation
→ Dropout`), not two. With only 166 training examples split four ways
across dimensions with already-skewed tier histograms (the entire reason
A1/A2 exist), a second hidden layer roughly doubles the new-parameter count
for a hypothesis this ablation isn't even testing (architecture *depth*,
not *presence of any private capacity at all*). If Experiment B's single
hidden layer shows the predicted effect (better relevance separation,
without collapsing other dimensions), a deeper-MLP ablation is a
legitimate **future**, separate experiment — not part of B, since this
review's own constraint (§ "Important" in the task) is to isolate exactly
one architectural variable at a time.

## 7. Activation recommendation

**GELU.** `microsoft/deberta-v3-base`'s own transformer layers use GELU
internally (`transformers`' `DebertaV2Config` default
`hidden_act="gelu"`), so this keeps the new MLP's nonlinearity consistent
with the backbone it sits on top of, rather than introducing a second
activation convention into the model for no reason (ReLU would work
mechanically but has no motivating advantage here — it's an unnecessary
extra degree of freedom for an ablation whose variable is "private
capacity or not," not "which activation function").

## 8. Dropout recommendation

**p = 0.1**, matching the encoder's own existing dropout rate
(`microsoft/deberta-v3-base`'s default `hidden_dropout_prob=0.1`,
also the exact value already named in A0/A1/A2's training config, per the
task's own stated hyperparameters: "dropout .1"). This is the same
"don't introduce a second, untuned convention" argument as §7: reusing the
value already validated as reasonable for this model/dataset size avoids
adding a fifth free hyperparameter to an ablation whose whole point is to
isolate one variable (architecture presence), not sweep dropout too.
Applied after the activation, before the value reaches `CoralOrdinalHead`.

## 9. Whether the CORAL implementation itself remains completely unchanged

**Yes, completely unchanged — zero lines of `CoralOrdinalHead`,
`coral_targets`, `coral_loss`, `coral_predict`, or `coral_confidence`
(`model_heads.py:66-152`) need to change.** `CoralOrdinalHead.__init__`
already takes `in_features` as a parameter (`model_heads.py:77`); B only
changes what value is passed for that parameter at construction time
(`h` instead of `backbone.hidden_size`) and what tensor is passed into
`.forward()` at call time (the per-dimension MLP's output instead of raw
`pooled`). The monotonic-bias rank-consistency guarantee
(`model_heads.py:90-100`) lives entirely inside `CoralOrdinalHead` and is
a property of its own bias structure, completely independent of what
upstream representation feeds it — exactly the same isolation argument
`loss_weighting.py`'s module docstring already made for Experiment A's
`pos_weight`, and it applies identically here.

## 10. Should A2 loss weighting be retained, or should B start from A0/unweighted?

**Start from A0 (unweighted loss).** This is an ablation study; the task
statement is explicit that the primary variable must be architecture, and
"do not propose changing multiple variables simultaneously." Training B
with A2's `alpha=0.4` weighting active would confound two independent
hypotheses (does private per-dimension capacity help? does smoothed
threshold reweighting help?) into one result, making it impossible to
attribute any V4 change to architecture alone. Concretely:

- **B0** = new architecture (private MLPs) + **A0's unweighted loss**
  (`loss_weighting="none"`, exactly `v3_expA0`'s loss configuration) — this
  is the direct, clean architecture-only comparison against A0.
- A **separate**, later experiment (call it **B-A2** or similar, not part
  of this ablation) could combine the winning architecture with A2's
  weighting once each variable has been evaluated independently — that is
  future work, explicitly out of scope for "Experiment B" as scoped here.

This mirrors exactly how A0→A1→A2 held architecture fixed while varying
loss weighting; B should symmetrically hold loss weighting fixed (at the
"off" baseline) while varying architecture.

## 11. How B should be isolated into its own experiment/output namespace

Follow the exact existing pattern from `run_four_dim_training.py`'s
`EXPERIMENTS` dict (`v3_expA0`/`v3_expA1`/`v3_expA2`, each with its own
`artifacts_dir` under `main_cap/cap/artifacts/`, verified in the current
codebase to never collide — `test_loss_weighting.py`'s
`test_a2_does_not_overwrite_v3_a0_or_a1_artifacts_dirs` already asserts
exactly this property for A0/A1/A2):

- New experiment key: `v3_expB0` (or `v4_expB0` — naming is a small
  decision for implementation time, not this review; `v3_expB0` keeps the
  "reuses V3's pool/split" naming convention A0/A1/A2 already use).
- New isolated output directory:
  `artifacts/four_dim_training_v3_expB0/` — sibling to, never overlapping
  with, `four_dim_training_v3`, `_v3_expA0`, `_v3_expA1`, `_v3_expA2`.
- New V4 inference isolation directory (mirroring `a1_inference/`,
  `a2_inference/`): `artifacts/v4_diagnostic/b0_inference/`, containing
  its own `run_b0_inference_on_v4.py`, `sanity_check_b0_checkpoint.py`,
  `analyze_b0_on_v4.py`, `b0_predictions_on_v4.json`,
  `b0_on_v4_report.json`, `README.md` — same read-only, additive,
  never-overwrites-existing-files pattern already established for A1/A2.
- New architecture code should be **additive**, not an in-place edit of
  `DimensionOrdinalHeads`/`MultiTaskModel`: e.g. a new
  `DimensionMLPOrdinalHeads` class (or a `use_dimension_mlp: bool`
  constructor flag on the existing class, defaulting to `False` so every
  existing call site — A0/A1/A2's training and every already-committed
  checkpoint's loader — is byte-for-byte unaffected). This is the same
  "default-preserves-old-behavior" convention every prior additive change
  in this codebase already follows (`alpha=A1_ALPHA` default in
  `loss_weighting.py`, `dimension_pos_weights=None` default in
  `compute_batch_loss`/`train_model`, etc.).

## 12. Exact config changes required (when implementation actually happens)

Not performed in this review (read-only), but scoped precisely for
whoever implements B:

1. `model_heads.py`: add a new class (e.g. `DimensionMLPOrdinalHeads`) or
   extend `DimensionOrdinalHeads` with an opt-in flag
   `use_private_mlp: bool = False` and `mlp_hidden_dim: int = 128`
   constructor parameters — default `False`/unused, so `MultiTaskModel`'s
   existing signature and every existing checkpoint's architecture stay
   identical when the flag is off.
2. `model_heads.py`, `MultiTaskModel.__init__`: forward the new flag(s)
   through to whichever heads class is used — additive constructor
   parameters only, defaulting to current behavior.
3. `run_four_dim_training.py`: add `"v3_expB0"` to `EXPERIMENTS`, copying
   `v3_expA0`'s exact `load_pool`/`split_json_path`/`split_seed`/
   `expected_total`/`expected_counts`/`loss_weighting="none"` (§10), with
   a new `artifacts_dir` (§11) and a new `use_private_mlp=True,
   mlp_hidden_dim=128` pair of keys (or equivalent), read by `train()`
   the same way `loss_weight_alpha` is already read today
   (`run_four_dim_training.py`'s `train()` function,
   `cfg.get("loss_weight_alpha", ...)` pattern).
4. `model_checkpoint_io.load_checkpoint_artifact`: needs the same new
   optional parameters forwarded to `MultiTaskModel(...)` so a saved B
   checkpoint can be reloaded with the matching (non-default) architecture
   — additive parameters, default `False`, so loading an A0/A1/A2
   checkpoint is completely unaffected (and, per §14, would now correctly
   *fail loudly* — via `state_dict` shape mismatch — if someone
   accidentally tried to load a B checkpoint with the flag off, or an
   A-family checkpoint with the flag on; `load_state_dict` is strict by
   default, `model_checkpoint_io.py:68`, so this is a hard error, not
   silent corruption).
5. No change anywhere to `evaluation_dimensions.py`'s four canonical keys,
   `model_dataset.py`'s label/target encoding, `four_dim_experiment_v2_split.py`'s
   split, or `loss_weighting.py`.

## 13. Exact tests required (when implementation actually happens)

Mirroring the existing test-file conventions
(`test_loss_weighting.py`, `test_four_dim_training_entrypoint.py`):

- **Architecture/shape tests** (new, e.g. `test_dimension_mlp_heads.py`):
  - Each dimension's MLP produces the expected output shape `(batch, h)`.
  - `CoralOrdinalHead` receiving the MLP's output still produces
    `(batch, num_classes-1)` logits, rank-consistent (non-increasing
    biases) exactly as today — reuse whatever existing CORAL
    monotonicity test already covers `CoralOrdinalHead` unchanged, applied
    with the new `in_features=h`.
  - Two different dimensions' MLPs have independent parameters (a
    gradient step on one dimension's loss does not change another
    dimension's MLP weights) — this is the property the whole ablation
    hypothesis rests on, so it must be directly tested, not assumed.
  - `use_private_mlp=False` (or the equivalent default) produces a
    `MultiTaskModel` whose `state_dict()` keys and shapes are
    **identical** to today's — a direct regression test that the additive
    flag is truly a no-op when unset.
- **Config/selector tests** (extend `test_four_dim_training_entrypoint.py`,
  mirroring `TestA2ConfigurationSelector` in `test_loss_weighting.py`):
  - `v3_expB0` is registered in `EXPERIMENTS`.
  - `v3_expB0`'s `artifacts_dir` collides with none of
    `v3`/`v3_expA0`/`v3_expA1`/`v3_expA2` (extend the existing
    `test_a2_does_not_overwrite_v3_a0_or_a1_artifacts_dirs`-style
    assertion to include B0).
  - `v3_expB0` uses the exact same `load_pool`, `split_json_path`,
    `split_seed`, `expected_total=220`, `expected_counts=(166,27,27)` as
    `v3_expA0` (mirrors `test_a2_same_pool_split_hyperparams_as_a1`) — the
    ONLY difference from A0's config is the architecture flag(s).
  - `v3_expB0`'s `loss_weighting` is `"none"` (confirms §10: B starts
    unweighted, not from A2).
- **Checkpoint round-trip test**: save a B0 model via
  `save_checkpoint_artifact`, reload via `load_checkpoint_artifact` with
  matching flags, confirm identical outputs on a fixed input (same pattern
  any existing checkpoint round-trip test already uses).
- **Finite-loss / dry-run tests**: a `compute_batch_loss` call on a tiny
  random-init B0 model produces a finite loss (mirrors
  `TestA2FiniteLoss.test_a2_weighted_compute_batch_loss_is_finite`).
- **`--dry-run v3_expB0`**: must print the same pool/split confirmation
  (`pool: 220 examples. Split: train=166 val=27 test=27`) as every other
  `v3_exp*` entry, with zero download/training, exactly like the existing
  dry-run tests already verify for A0/A1/A2.
- **V4 inference isolation tests** (mirroring the intent of
  `test_v4_diagnostic.py` + the manual verification already done for A1/A2
  inference): `run_b0_inference_on_v4.py` produces exactly 58 predictions;
  `b0_inference/` never touches any file outside itself.

## 14. How to prove A0/A1/A2 remain unchanged

Because every change in §12 is additive-with-default-off:

1. **State-dict identity check**: construct a `MultiTaskModel` with the
   new flag left at its default and diff its `state_dict()` key set and
   shapes against a `MultiTaskModel` built the exact same way today
   (before B exists) — must be byte-identical. This is the single
   strongest proof: if the default-path architecture is provably
   unchanged, A0/A1/A2's already-trained checkpoints remain loadable and
   their already-published `v3_predictions_on_v4.json` /
   `a1_inference/a1_predictions_on_v4.json` / (future)
   `a2_inference/a2_predictions_on_v4.json` results are not invalidated,
   since nothing about how they were produced changes retroactively.
2. **Existing checkpoint reload**: `load_checkpoint_artifact` with the new
   flag(s) at their default must still successfully load
   `four_dim_training_v3/best_checkpoint_weights.pt`,
   `..._v3_expA0/...`, `..._v3_expA1/...`, and `..._v3_expA2/...` exactly
   as before — a direct regression test, not merely an inference-by-design
   argument.
3. **Full existing test suite green**: re-run `test_loss_weighting.py`
   (73 tests, currently 73/73 passing) and
   `test_four_dim_training_entrypoint.py` unmodified — B's additions must
   not require editing a single existing assertion in either file (only
   new test classes/functions are added, per §13). If any existing A0/A1/A2
   assertion needs to change to accommodate B, that is a signal the change
   was not actually additive and must be redesigned before proceeding.
4. **Byte-diff of frozen artifact files**: `git diff` (or checksum
   comparison) of `artifacts/four_dim_experiment_v2/split.json`,
   `artifacts/v2_targeted_50/*.jsonl`, `artifacts/v4_diagnostic/*` — all
   must show zero changes, the same check already applied before every
   A1/A2 commit in this project's history.
5. **Re-run, don't just re-read, A0/A1/A2's existing dry-runs** (as was
   done for A2 in the previous session) after B's code lands, confirming
   identical stdout (`pool: 220 examples. Split: train=166 val=27
   val=27`) for `v3`, `v3_expA0`, `v3_expA1`, `v3_expA2` — proves B's
   registration in `EXPERIMENTS` didn't perturb any existing entry's dict.

## 15. How to ensure the production evaluator is untouched

`model_evaluator.py`'s `TrainedEvaluator` (`model_evaluator.py:171-223`)
calls `self.model.forward_dimensions(...)` and reads
`outputs["dimension_logits"][dim_name]` through `coral_predict`/
`coral_confidence` — it never constructs `MultiTaskModel` itself (that
happens at load time, outside this class) and never inspects internal
head structure. As long as:

- `forward_dimensions`'s **return contract** stays identical
  (`{"pooled": ..., "dimension_logits": {name: (batch, num_thresholds)
  tensor, ...}, "presence_logits": ..., "severity_pred": ...}`), and
- the production deployment continues instantiating `TrainedEvaluator`
  with an A0/A1/A2-family checkpoint and `use_private_mlp=False`/default
  config (i.e. nothing about production deployment code changes to opt
  into B),

`model_evaluator.py` requires **zero code changes** for B to exist
alongside it, and needs **zero changes at all** unless/until a B-family
checkpoint is deliberately chosen for production use (a separate,
later decision, not part of this ablation). This should be directly
tested: `test_four_dim_training_entrypoint.py`/any existing
`model_evaluator.py` test suite re-run unmodified and green, same
principle as §14.3.

## 16. Same V2 220-example pool and frozen 166/27/27 split?

**Yes, unchanged, exactly as A0/A1/A2 used it.** The task's own framing is
explicit: architecture is the ONE variable under test. Changing the
pool or split alongside architecture would confound "does private
capacity help" with "does a different data split help," making the A-vs-B
comparison uninterpretable. `load_v2_pool` /
`artifacts/four_dim_experiment_v2/split.json` /
`split_seed="four_dim_v2_split_348"` /
`expected_total=220`/`expected_counts=(166,27,27)` should be copied
verbatim from `v3_expA0`'s config (§12.3), not regenerated or reselected.

## 17. Same V4 58-example diagnostic, completely inference-only?

**Yes.** V4 (`artifacts/v4_diagnostic/v4_diagnostic_58.jsonl`, frozen,
20 pair groups, validated `all_passed=true`, `v4_vs_frozen_pool_near_
duplicates=0`) is read-only diagnostic infrastructure, never a training or
tuning signal, for B exactly as it was for A0/A1/A2. Concretely this means:

- B's checkpoint selection (which epoch is "best," e.g. the analogue of
  A2's "best epoch: 7") must be chosen from **val mean QWK on the frozen
  166/27/27 split's val set only** — never from V4 pair-separation
  results. V4 is evaluated strictly *after* a checkpoint is already
  selected on that basis, as a downstream diagnostic report, exactly
  mirroring how A1/A2's `README.md` files in this repo already document
  their checkpoint provenance from the real test split before any V4
  inference is run.
- `h` (§5), one-hidden-layer (§6), GELU (§7), and dropout=0.1 (§8) must
  all be fixed *before* looking at any V4 result, not swept against V4 —
  this review fixes them now, in advance, on architectural/consistency
  grounds alone, precisely so no V4-based hyperparameter search is even
  possible later.
- B's own V4 inference workflow (§11's `b0_inference/`) must be, like
  `a1_inference/`/`a2_inference/` before it, additive-only: it must not
  modify `v4_diagnostic_58.jsonl`, `manifest.json`,
  `validation_report.json`, or any other experiment's prediction/report
  file.

## 18. Risks of over-parameterization given only 220 training examples

Real risk, and the primary reason §5/§6 land on the conservative end:

- 166 training examples is small for *any* new trainable capacity, and
  the risk compounds per-dimension: `technical_correctness` and
  `relevance_completeness` are exactly the two dimensions A1/A2 already
  found to have skewed, sparse tier histograms (motivating `pos_weight`
  in the first place) — adding ~98K new parameters to a head trained on
  an already-imbalanced few dozen effective positive examples at some
  thresholds is a real overfitting vector, not a hypothetical one.
- Concrete failure modes to watch for empirically once B is actually
  trained (out of scope to resolve in this review, but should be named as
  acceptance criteria for implementation):
  - Train loss drops noticeably faster/lower than A0's while val loss
    does not improve or gets worse — classic capacity-without-signal
    overfitting.
  - Per-dimension MLPs "specialize" in a degenerate way (e.g. one
    dimension's predictions collapse to a near-constant tier) rather than
    genuinely differentiating relevance from depth/TC.
  - Val mean QWK improves but V4 pair-separation does not (or regresses)
    — would suggest the extra capacity is fitting the 27-example val set's
    idiosyncrasies rather than a genuinely more separable representation.
- Mitigations already built into the conservative recommendation: single
  hidden layer (§6), small bottleneck `h=128` (§5), dropout 0.1 matching
  the encoder's own rate (§8), and — unchanged from A0/A1/A2 — weight
  decay 0.01 on the AdamW optimizer (`train_model`'s existing default,
  `model_heads.py:451`, already applied to every parameter including any
  new MLP weights with no extra wiring needed). If B0 still overfits at
  `h=128`, the next lever is shrinking `h` further (§19), not adding
  depth.

## 19. A more conservative alternative architecture, if appropriate

Two options, from least to most capacity, worth naming even though §4-6
already recommend a specific point on this spectrum:

1. **Linear-only per-dimension bottleneck (no activation, no dropout)**:
   `Linear(768 → h)` feeding directly into `CoralOrdinalHead(h)`, no
   nonlinearity at all. This is *more* conservative than the recommended
   design but is representationally weaker than it sounds: without an
   intervening activation, `Linear(768→h)` followed by
   `CoralOrdinalHead`'s own `Linear(h→1)` is mathematically equivalent to
   a single `Linear(768→1)` with different weights (composition of two
   linear maps is linear) — i.e. it is NOT actually more expressive than
   today's single shared-projection CORAL head, just reparameterized.
   This option would not test the "private nonlinear capacity" hypothesis
   at all, so it is **not recommended** as B's main run, but is worth
   keeping in mind as a sanity-check control (if this "linear-only"
   variant matches A0's V4 results almost exactly, that is expected and
   confirms the private-MLP result, if any, comes from the nonlinearity
   and not merely from re-parameterizing dimension weights).
2. **FiLM-style per-dimension affine modulation** (scale + shift, ~1,536
   new parameters total for `h=768`: two `768`-length vectors per
   dimension, `γ_dim`, `β_dim`, applied as `pooled * γ_dim + β_dim` before
   the *existing, unchanged* `CoralOrdinalHead(768, ...)`): an even
   smaller-footprint way to give each dimension *some* private
   parameters without a full MLP, at the cost of much less
   representational flexibility (per-channel scale/shift can reweight
   which of the 768 shared dimensions matter most per task, but cannot
   introduce a genuinely new nonlinear combination of them the way a
   hidden layer can). Worth considering as an even-smaller first probe if
   `h=128`'s MLP still shows overfitting symptoms per §18 — but the task's
   own conceptual diagram (§ Experiment B hypothesis, "private MLP
   projection/head") specifically asks for an MLP, so this is offered as
   a fallback, not the primary recommendation.

The recommended design in §4-8 (`Linear(768→128) → GELU → Dropout(0.1) →
CoralOrdinalHead(128)`) sits deliberately between these two: genuinely
nonlinear (unlike option 1) but still the smallest single-hidden-layer
form (unlike a deeper MLP), which is why it is the primary
recommendation rather than either extreme.

## 20. Clear recommendation: what Experiment B should be

**Experiment B0** (single, isolated architecture-only ablation):

- Architecture: per-dimension private projection inserted between the
  shared `CrossEncoderBackbone` pooled output and each `CoralOrdinalHead`
  — `Linear(768 → 128) → GELU → Dropout(0.1)`, one hidden layer, per
  dimension, four independent MLPs (one each for `technical_correctness`,
  `depth_specificity`, `relevance_completeness`, `grounding_ownership`).
  `CoralOrdinalHead` itself: completely unchanged code, constructed with
  `in_features=128` instead of `768`.
- Loss weighting: **none** (A0's unweighted baseline) — architecture is
  the only variable relative to A0.
- Pool/split/seed/hyperparameters: identical to A0/A1/A2 — V2 pool of 220,
  frozen 166/27/27 split (`four_dim_v2_split_348`), seed 42, LR 2e-5,
  batch size 8, epochs 8, max_length 256, AdamW, weight decay 0.01,
  (encoder) dropout 0.1.
- Output namespace: `artifacts/four_dim_training_v3_expB0/`, isolated from
  every existing `v3*` artifacts dir.
- V4 diagnostic: used strictly read-only, strictly after checkpoint
  selection, in a new `artifacts/v4_diagnostic/b0_inference/` directory,
  mirroring `a1_inference/`/`a2_inference/` exactly.
- Primary success criterion (decided now, before any training, so V4
  cannot retroactively become a tuning signal): relevance-alignment pair
  separation on V4 improves over **A0's** 0/8 (the comparison implied by
  "architecture vs. no architecture change," both unweighted) — with A1's
  3/8 and A2's 3/8 as secondary reference points showing what loss
  weighting alone achieved, so a reader can see how much of any B0 gain is
  attributable to architecture vs. how A0→A1→A2's gains compared. A
  regression in `depth_specificity`/`technical_correctness`/
  `grounding_ownership` QWK, if any, should also be reported explicitly
  (mirroring A1/A2's own "cross-dimension effects" transparency) rather
  than only highlighting the relevance-dimension result.
- Explicitly out of scope for B0 (future, separate experiments if B0
  succeeds): combining B0's architecture with A2's loss weighting; a
  second hidden layer; per-dimension bottleneck widths other than 128;
  extending private capacity to the concept-observation or
  missing-reasoning heads.
