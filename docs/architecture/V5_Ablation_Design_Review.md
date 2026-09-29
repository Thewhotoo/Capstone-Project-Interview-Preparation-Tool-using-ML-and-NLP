# V5 Ablation Design Review — READ-ONLY

**Status: design review only. No code changed, no training run, nothing
committed.** Written against branch `maburan-new`, informed by
`V3_Forensic_Analysis_and_V4_Diagnostic_Design.md` and
`main_cap/cap/artifacts/v4_diagnostic/v3_on_v4_report.json`.

Files inspected this pass (read-only): `model_backbone.py`, `model_heads.py`,
`model_dataset.py`, `training_experimentation.py` (partial — split/checkpoint
helpers), `run_four_dim_training.py` (full), `model_evaluator.py`
(`TrainedEvaluator.evaluate`), `evaluation_dimensions.py` (rubric/enum
structure), `artifacts/v4_diagnostic/*`.

---

## 1. Diagnosis from V3-on-V4 evidence

Three independent, converging observations from the V4 experiment:

1. **Relevance is not a partial failure, it is a total one in the cleanest
   cases available.** 0/8 relevance_alignment pair groups separated at all
   — every "detailed/generic/adjacent-topic" answer (gold relevance 0–1) was
   scored identically (4) to its "concise/directly-relevant" pair partner,
   in 8/8 topically-varied, hand-matched contrasts. This is not noise: the
   same collapse appears regardless of project, phrasing, or the specific
   flavor of irrelevance (off-topic, generic-to-specific, neighboring-topic).
2. **Grounding and depth are not failing the same way.** Grounding's
   *relative ranking* survives (8/9 and 4/6 concordant pairs across GRD-1/2)
   even though its *absolute calibration* is shifted down ~1 tier. Depth's
   ordering is mostly correct. If the shared representation were simply
   incapable of carrying any dimension-specific signal, we would expect
   grounding and depth to collapse the same way relevance does — they don't.
3. **TC fails selectively, not uniformly.** The most extreme misconceptions
   (confident, flatly-wrong claims) were correctly separated from correct
   answers; the *subtle* misconceptions (one wrong causal claim inside
   otherwise-fluent correct-sounding reasoning) were not. This looks like a
   *resolution* problem (not enough discriminative margin for close cases),
   not a total absence of signal.

Taken together, this argues against a single blanket explanation ("the
model can't use the input at all") and toward **relevance specifically
having the weakest signal path**, with TC showing a *milder* version of the
same problem and grounding/depth being comparatively healthy. That
selectivity is itself informative: it is more consistent with relevance's
signal being disproportionately squeezed out (by loss imbalance, by head
capacity, or by the pooled representation genuinely not encoding
alignment) than with a uniform architectural incapacity across all four
heads. The ablation ladder below is designed specifically to find out
*which* of those three it is, for relevance in particular — not to fix TC
or grounding, which show more modest, differently-shaped problems.

---

## 2. Hypothesis table H1–H4

| # | Hypothesis | What would be TRUE if this is the (main) cause | What the V4 evidence already says |
|---|---|---|---|
| H1 — Loss/calibration | Training labels are tier-imbalanced (technical_correctness 91% tier 3–4 pool-wide; relevance 59% tier 4) and the loss is unweighted plain BCE per CORAL threshold — the model settles on "predict the training majority" | Consistent with the **uniform +0.74 relevance bias** and **-1.03 grounding bias** on V4 (systematic shift toward/away from specific tiers, not random scatter) — but does NOT by itself explain why relevance ties even the CONCISE-relevant example at 4 (both answers, not just the majority-class one, land on 4) | Partially supported, not sufficient alone |
| H2 — Head capacity | A single `nn.Linear(hidden, 1, bias=False)` CORAL head per dimension, reading the same shared pooled vector, cannot express a decision boundary for relevance that a linear probe can't separate | Consistent with relevance being the WORST dimension despite the input genuinely containing the question text (ruling out H4 as sole cause is not possible from V4 alone, but if capacity were fine, an unweighted-loss-only fix (H1) should still show SOME separation on the cleanest 8 pairs — it currently shows none) | Plausible, testable directly (Experiment B) |
| H3 — Explicit relational supervision | Relevance is fundamentally a *comparison* (does answer X address question Y), and independent per-example ordinal labels give the model no direct training signal that says "these two answers to the same question should NOT get the same score" | V4 IS exactly this kind of paired evidence, but V4 is diagnostic-only (never trained on) — nothing in current training ever exposes the model to a same-question, different-relevance pair with an explicit "these must differ" signal | Cannot be ruled in/out without a real experiment; V4's design specifically anticipated this gap |
| H4 — Input representation | Single CLS-pooled vector conflates fluency/topic-relatedness with actual question-answering; the alignment signal exists in cross-attention internally but doesn't survive pooling into one vector shared by 4+ heads | Consistent with relevance being worse than grounding/depth (arguably the "hardest" alignment task) but this is the most invasive hypothesis and the LEAST cheaply testable — should be investigated last, only if A/B/C don't move relevance | Untested; deliberately last in the ladder per your instruction |

None of these are mutually exclusive. The ladder below is ordered from
cheapest/most surgical to most invasive specifically so each experiment's
result rules hypotheses in or out before committing to the next.

---

## 3. Proposed ablation ladder

All four experiments share: **same 220-example V2/V3 pool, same frozen
`four_dim_experiment_v2/split.json` (166/27/27), same tokenizer, same
`microsoft/deberta-v3-base` backbone initialization, same input builder
(`build_dimension_pair`/`QUESTION+RELEVANT CONTEXT+EXPECTED CONCEPTS` /
answer), same max_length=256, same V4 diagnostic set used ONLY for
post-hoc evaluation.** Nothing about the dataset, split, or checkpoint
promotion process changes between experiments — only the one variable named
per experiment.

### Experiment A — improved loss/calibration only (tests H1)

- **Exact code change**: replace `model_heads.coral_loss`'s plain
  `F.binary_cross_entropy_with_logits(logits, targets)` with a
  **class-balanced weighted** version — e.g. per-threshold `pos_weight`
  computed from the training split's own tier frequencies (inverse-frequency
  or effective-number-of-samples weighting), passed through
  `compute_batch_loss`. No new hyperparameter search — one weighting scheme
  computed deterministically from the frozen train split's label
  distribution, logged in the checkpoint's `experiment_config`.
- **Exact files affected**: `model_heads.py` (`coral_loss` gains an optional
  `pos_weight` argument; `compute_batch_loss` computes/passes per-dimension
  weights), `run_four_dim_training.py` (new `EXPERIMENTS["v4a"]` entry,
  `CONFIG` gains a `loss_weighting: "inverse_frequency"` record — additive,
  matches the existing v1/v2/v3 pattern exactly).
- **What remains frozen**: architecture (still one linear CORAL head per
  dimension), input construction, pooling, dataset, split.
- **Dataset**: unchanged — same 220-example pool/split.
- **Confirming metric**: relevance/TC prediction *distribution* on the real
  V2/V3 test set stops collapsing to {mostly 4} (compare predicted-label
  histogram pre/post, not just QWK) AND V4's REL-1..8 pair separation rate
  improves from 0/8.
- **Interpretation**: if separation improves substantially → H1 was a real,
  fixable contributor, proceed to decide whether B is still needed. If V4
  relevance separation stays at ~0/8 despite the real test-set distribution
  visibly de-skewing → H1 alone is insufficient, the problem is deeper
  (proceed to B).
- **V4 role**: diagnostic/validation only, exactly as now — run inference
  post-training, never included in any train/val loader.

### Experiment B — current loss (or A's improved loss) + dimension-specific MLP heads (tests H2)

- **Exact code change**: replace `CoralOrdinalHead.shared = nn.Linear(in_features, 1, bias=False)` with a small 2-layer MLP (`Linear(hidden, hidden//4) → GELU → Dropout → Linear(hidden//4, 1, bias=False)`) before the existing monotonic-bias CORAL logic — the CORAL rank-consistency math (`bias_base`, `bias_deltas`, `coral_targets`/`coral_loss`/`coral_predict`) is completely unchanged, only the scalar-logit-producing sub-module gets more capacity. Apply this ONLY to `relevance_completeness` and `technical_correctness` heads first (the two dimensions V4 flagged), keeping `depth_specificity`/`grounding_ownership` as plain linear heads — this is the smallest change that tests H2 without touching what's already working.
- **Exact files affected**: `model_heads.py` (`CoralOrdinalHead.__init__` gains an optional `hidden_layer: bool` or a new `MlpCoralOrdinalHead` subclass; `DimensionOrdinalHeads` picks the head type per-dimension via a small config dict), `run_four_dim_training.py` (new experiment entry recording `head_architecture: "mlp_for_relevance_tc"`).
- **What remains frozen**: backbone, pooling, input construction, loss shape (CORAL BCE, optionally A's weighting), dataset, split.
- **Dataset**: unchanged.
- **Confirming metric**: V4 REL-1..8 and TC-1..3 pairwise separation rate improves specifically (not just aggregate QWK, which a capacity increase could inflate without actually fixing the targeted failure mode — check the SAME 8 relevance pairs and 3 TC groups explicitly).
- **Interpretation**: improvement → H2 was a real contributor (linear probe was the bottleneck for these two dimensions specifically). No improvement even with added capacity → the discriminative signal isn't reliably present in the pooled vector at all for relevance, which is evidence AGAINST H2 alone and points toward H3/H4.
- **V4 role**: same, diagnostic only.

### Experiment C — best of A/B + relevance pairwise ranking loss (tests H3)

- **Exact code change**: add a **new, separate loss term**, computed only
  when a batch contains two-or-more examples sharing the same question
  (grouped by a `question_group_id`, see dataset note below): a margin
  ranking loss (`torch.nn.MarginRankingLoss` or a manual
  `max(0, margin - (score_higher - score_lower))`) over
  `relevance_completeness`'s raw CORAL score for same-question pairs whose
  gold relevance differs by ≥2 tiers. This is **additive to**, not a
  replacement for, the existing per-example CORAL loss — every example
  still gets its own ordinal supervision; pairs where both members happen to
  land in the same training batch get an EXTRA pairwise term.
- **Exact files affected**: `model_dataset.collate_fn`/`build_dataloaders`
  (batches need a `question_group_id` per example — derivable from
  `source_id` + a normalized question string, or from a new explicit field
  on the training-pair dataset described below), `model_heads.py`
  (`compute_batch_loss` gains the optional pairwise term, gated by whether
  `question_group_id` overlaps exist in the batch), `run_four_dim_training.py`
  (new experiment entry, `loss_terms: ["coral", "relevance_pairwise_margin"]`).
- **What remains frozen**: backbone, pooling, CORAL decoding/prediction
  logic (`coral_predict` unchanged — the pairwise term only affects
  *training* gradients, not how a prediction is read out at inference).
- **Dataset**: requires a **new, small, TRAINING-ONLY paired sub-corpus**
  (see Section 6/9 — explicitly NOT V4). The existing 220-example pool
  mostly does NOT have same-question paired answers with differing
  relevance (checked: the V1–V3 pools were authored as independent
  examples, not as contrast sets) — Experiment C's pairwise term would have
  very few real in-pool pairs to train on without this addition.
- **Confirming metric**: V4 REL-1..8 separation rate, PLUS a genuinely
  held-out check (a *new, small* set of paired examples NOT used in the
  pairwise training set and NOT V4 — see Section 9) to make sure the model
  learned relevance discrimination generally, not just memorized the
  specific training pairs' surface patterns.
- **Interpretation**: if C succeeds where A/B didn't → H3 was the missing
  piece — the model needed to be explicitly told "these two must differ,"
  independent ordinal labels alone weren't sufficient signal. If C still
  fails to generalize to the held-out (non-training) paired check → the
  problem is not "insufficient supervision type" but something more
  structural (H4).
- **V4 role**: diagnostic only, still never trained on — the pairwise
  training corpus is a SEPARATE artifact (Section 9).

### Experiment D — richer question-answer interaction representation (tests H4) — ONLY IF A/B/C indicate necessity

- **Not designed in detail here**, per your instruction not to propose a
  giant rewrite prematurely. If reached, the smallest version worth trying
  first (before anything more invasive like a bi-encoder + explicit
  similarity head, or restructuring the cross-encoder's segment layout)
  would be: **replace CLS pooling with a small cross-attention pooling
  layer that explicitly attends the answer's tokens back onto the
  question's tokens** (both already available separately since text_a/text_b
  are tokenized as one sequence — DeBERTa's own `last_hidden_state` still
  has per-token outputs, currently only the CLS position is read). This
  keeps the cross-encoder architecture, keeps CORAL heads, and only changes
  `CrossEncoderBackbone.forward`'s pooling step. Only worth specifying
  further if Experiments A–C leave relevance clearly still broken.

---

## 4. Exact minimal architecture change (if H2 confirmed)

Smallest form: `CoralOrdinalHead` gains one hidden layer, applied
selectively (relevance + TC only, not all four) — see Experiment B above.
No change to `MultiTaskModel`'s overall shape, no change to the backbone, no
change to how many heads exist or what they're named. `model_checkpoint_io`
does not need to change (state_dict keys change shape/names slightly for the
two MLP heads, but `load_checkpoint_artifact` already reconstructs the
architecture from `dimension_names` before loading weights — it would just
need `DimensionOrdinalHeads` to know which heads are MLP vs. linear, which
must be recorded in the checkpoint metadata for reproducibility).

## 5. Exact minimal loss change (if H1 confirmed)

Smallest form: `coral_loss` gains an optional `pos_weight` tensor
(shape `(num_classes-1,)` or per-dimension), computed once from the frozen
training split's tier histogram, passed to
`F.binary_cross_entropy_with_logits(logits, targets, pos_weight=pos_weight)`.
No change to `coral_targets`, `coral_predict`, or `coral_confidence` — only
the loss's weighting, and only during training (inference/decoding
unaffected). This is the cheapest possible experiment in the entire ladder
— worth running first regardless of what else is planned, purely because it
is nearly free and directly tests the most commonly-seen imbalance pattern.

## 6. Pairwise objective design (if H3 justified — i.e., if A and B both fail to fix relevance)

- **Loss**: margin ranking loss over `relevance_completeness`'s raw CORAL
  score (sum of predicted-P(tier>k) probabilities, or the pre-threshold
  linear logit before decoding — needs a specific choice, e.g. the mean
  sigmoid probability across thresholds as a continuous proxy for "how high
  the model currently rates relevance") between two examples sharing a
  question, gated to only fire when |gold_a - gold_b| ≥ 2 (to avoid
  penalizing legitimate near-ties).
- **Training-only pair corpus**: a NEW, small (target: 40–60 examples,
  20–30 pairs — deliberately similar scale to V4 but NOT V4) set of
  same-question, differing-relevance answer pairs, authored the same way
  V4 was (hand-authored, hypothetical or existing-project-consistent,
  validated the same way — SBERT near-dup check against V4 AND the 220-pool,
  no leakage). Call it e.g. `relevance_pairwise_train_v1` to keep it
  clearly distinct from `v4_diagnostic`.
- **Batching**: `build_dataloaders`/`collate_fn` need same-question pairs to
  land in the same batch reliably for the pairwise term to have anything to
  compute — either a custom `BatchSampler` that groups by
  `question_group_id`, or (simpler, smaller change) run the pairwise
  training set as a small SEPARATE fine-tuning pass after the main CORAL
  training converges, rather than co-mingled in every batch. The separate-
  pass version is the smaller change and is the one to try first.

## 7. Evaluation protocol

- **Every experiment (A/B/C)** is evaluated identically:
  1. Real test-set metrics on the frozen `four_dim_experiment_v2/split.json`
     test_ids (27 examples) — accuracy/MAE/within-1/QWK per dimension, same
     as V1/V2/V3, for direct comparability.
  2. **V4 inference pass** (`run_v3_inference_on_v4.py`-equivalent, just
     pointed at the new checkpoint) — full pair-separation analysis
     (`analyze_v3_on_v4.py`-equivalent), specifically the REL-1..8 and
     TC-1..3 group-level separation status, not just aggregate V4 QWK.
  3. **Sanity check**: reproduce-the-checkpoint's-own-metrics verification
     (as done before trusting the V3 checkpoint on V4) before drawing any
     conclusion from step 2.
- **V4 is NEVER in a train or val loader for any experiment.** It exists
  exclusively as a frozen, held-out diagnostic artifact, read only by an
  inference script, exactly as it has been used twice already this project.

## 8. What result would cause us to choose each next branch

```
Run A (loss weighting)
  ├─ V4 REL separation clearly improves (e.g. ≥4/8) ─────────► STOP or refine A; H1 was a major cause
  ├─ Some improvement but still mostly tied (1–3/8) ──────────► proceed to B (H1 partial, capacity likely also binding)
  └─ No improvement (still ~0/8) ──────────────────────────────► proceed to B AND treat H1 as ruled out for relevance specifically
                                                                   (still worth keeping the loss change for TC/grounding calibration)

Run B (MLP heads for relevance+TC, on top of whichever loss won in A)
  ├─ V4 REL separation clearly improves ──────────────────────► H2 confirmed; stop here or polish, re-verify on real test set
  ├─ TC subtle-misconception separation improves but REL doesn't ─► H2 partially confirmed for TC, NOT for relevance;
  │                                                                  relevance needs C or D
  └─ No improvement on either ─────────────────────────────────► H2 ruled out as sole cause; proceed to C

Run C (pairwise ranking, training-only pair corpus)
  ├─ REL separation improves on V4 AND generalizes to the held-out
  │  (non-training) pairwise check ───────────────────────────► H3 confirmed; this is likely the fix worth keeping
  ├─ REL separation improves on V4 but NOT on the held-out check ─► overfitting to the specific pair corpus, not real
  │                                                                  generalization — expand the pair corpus, retry C,
  │                                                                  do not conclude H3 is solved yet
  └─ No improvement even on the training pairs themselves ────► something more structural; proceed to D design work

Only if A+B+C all fail to move V4 relevance separation meaningfully:
  → proceed to designing Experiment D in detail (H4)
```

## 9. Risks / leakage concerns

- **V4 must never appear in any training or validation loader, for any
  experiment.** Concretely: `run_four_dim_training.py`'s `EXPERIMENTS` dict
  must never point `load_pool`/`split_json_path` at anything under
  `artifacts/v4_diagnostic/`; a code-level guard (a test asserting
  `v4_diagnostic` and every V4 `source_id` prefix `v4h_` never appear in any
  `EXPERIMENTS[...]["load_pool"]`'s resolved pool) is cheap insurance,
  mirroring `test_v4_diagnostic.py::TestV4NotWiredIntoTrainingPipeline`
  already in place.
- **The pairwise training corpus (Experiment C) must be independently
  checked against V4 for overlap** — same SBERT near-duplicate methodology
  already used for V4 itself (`validate_v4_diagnostic.py`'s pattern), run
  against BOTH the 220-pool and `v4_diagnostic_58.jsonl`, before any
  training. This is exactly the kind of mistake already caught once this
  session (5 V4 answers accidentally duplicating frozen-pool text) — the
  same discipline must apply to the new pairwise corpus.
- **A held-out pairwise check separate from both the pairwise training
  corpus and V4** is needed for Experiment C specifically (Section 8) —
  otherwise "the model got better at the training pairs" can't be
  distinguished from "the model generalized," which is the entire point of
  testing H3 rather than just curve-fitting to a specific corpus.
- **Experiment B's selective MLP-heads-for-two-dimensions-only design**
  changes the checkpoint's architecture shape — `load_checkpoint_artifact`
  must be told (via `dimension_names`/a new head-type record) which
  architecture a given checkpoint expects, or future evaluators will
  silently mismatch. This needs the same explicit-metadata discipline
  `best_checkpoint.json` already uses elsewhere in the project (record
  `head_architecture` alongside `model_version` in the checkpoint metadata).
- **Small absolute sample sizes throughout**: the real test set is 27
  examples, V4 is 58 across 20 groups (many size 2–3), and any new pairwise
  training/held-out corpus would be similarly small. Every experiment's
  result should be read as directional evidence, not a definitive
  confirmation — consistent with how the V4 experiment itself was framed.
  A single flipped example can move a group's separation status; look at
  the per-group evidence (already logged in the `analyze_v3_on_v4.py`-style
  report), not just the aggregate separation rate.
- **Confound risk between A and B**: if both loss-weighting and MLP heads
  are changed at once, a result can't be attributed to either — the ladder
  is deliberately sequential (A alone, then B on top of whichever A variant
  won, never both introduced simultaneously without an isolated A-only and
  B-only result already in hand).

## 10. Recommended first experiment

**Experiment A (loss/calibration only).** It is the cheapest change in the
entire ladder (one optional loss argument, zero new architecture, zero new
data), it directly targets the most measurable, already-quantified symptom
(relevance +0.74 bias, grounding -1.03 bias, TC +0.21 bias — all consistent
with unweighted-loss-driven majority-class collapse), and — critically — a
negative result (V4 relevance separation stays near 0/8 despite the real
test-set distribution visibly de-skewing) is itself the cleanest possible
evidence that the problem is NOT primarily calibration, which cheaply and
quickly rules H1 in or out before any capacity or architecture work is
justified. This matches your stated priority: the goal right now is
understanding WHY relevance collapses, not maximizing QWK — and Experiment A
is the fastest way to falsify or confirm the simplest hypothesis first.

---

## Explicitly NOT done in this pass

No file was modified. No training was run. No new experiment was added to
`run_four_dim_training.py`'s `EXPERIMENTS` dict. No pairwise training corpus
was created. `v4_diagnostic_58.jsonl`, the 220-example V1/V2/V3 pool, and
the V3 checkpoint are all untouched. Nothing was committed or pushed.
