# V3 Forensic Analysis + Proposed V4 Diagnostic Dataset Design

**Status: read-only analysis. No code modified, no training run, nothing committed.**
Branch: `maburan-new`. This document is new (docs-only); it does not touch any
frozen dataset, split, checkpoint, or production code path.

Prediction artifacts used (recovered from Colab downloads, placed under the
gitignored `artifacts/` tree, not committed):
- `main_cap/cap/artifacts/four_dim_training_v1/test_predictions.json` (22 rows)
- `main_cap/cap/artifacts/four_dim_training_v2/test_predictions.json` (27 rows) — verified QWK 0.0061/0.7410/0.0733/0.5326, mean 0.3383, matches reported V2.
- `main_cap/cap/artifacts/four_dim_training_v3/test_predictions.json` (27 rows) — verified QWK 0.1037/0.8002/0.1690/0.5810, mean 0.4135, matches reported V3.

---

## 1. EXECUTIVE VERDICT

The dominant failure mode is **not** primarily a data-volume problem, and it is
**not** primarily an annotation problem. Three independent lines of evidence
converge on the same conclusion:

1. **Architectural bottleneck**: every dimension head is a *single linear
   projection* (`CoralOrdinalHead.shared = nn.Linear(hidden, 1, bias=False)`)
   reading off the **same shared CLS-pooled vector**. There is no per-dimension
   nonlinearity and no explicit question↔answer alignment mechanism beyond
   whatever DeBERTa's self-attention learns implicitly during fine-tuning on
   166 training rows over 8 epochs. Four dimensions that are conceptually
   distinct (is it correct? is it deep? is it on-topic? is it owned?) are
   forced to be near-linear directions of one pooled embedding.
2. **Severe class imbalance with zero counter-measure**: `compute_batch_loss`
   uses plain, unweighted `binary_cross_entropy_with_logits` per CORAL
   threshold — no class weights, no focal loss, no resampling. Across the
   220-example pool, `technical_correctness` is 91% tier 3–4 (128 tier-4, 72
   tier-3, only 20 examples across tiers 0–2 combined). The V3 test-set
   predictions confirm the consequence directly: `technical_correctness_pred`
   never goes below 3 (22×4, 5×3, 0×{0,1,2}) and `relevance_completeness_pred`
   is 4 in 24/27 rows. The model has functionally learned "predict the
   majority tier" for these two dimensions, and QWK stays positive only
   because the *true* distribution is itself majority-tier-4 in the test
   split, not because the model discriminates.
3. **Confirmed on real held-out failures**: every one of the 13 failures you
   listed is an answer that is fluent, detailed, and on-topic-*adjacent* —
   exactly the surface features `depth_specificity` (QWK 0.80, the strongest
   dimension) rewards — but wrong or off-target in a way that requires
   checking the answer *against the question*, not just against itself. The
   model has no architectural or training pressure to make that check.

**Bottom line**: the input pipeline already puts the question and answer in
one cross-encoder pair, so the *information* is present. The problem is that
(a) the model has too little capacity/pressure to use it discriminatively for
TC/relevance specifically, and (b) the training distribution gives it very
little contrastive evidence that "detailed" and "correct/relevant" can
diverge. Recommend V4 as a **read-only diagnostic instrument** to determine
which of these two (representation/objective vs. data coverage) is binding
before spending effort on either.

---

## 2. IMPLEMENTATION AUDIT

Files inspected (line-level read, not modified): `model_backbone.py`,
`model_heads.py`, `model_dataset.py`, `four_dim_experiment_split.py`,
`run_four_dim_training.py`, `grounding_lookup.py`, `evaluation_dimensions.py`,
`model_evaluator.py`, `training_experimentation.py`.

**Input builder** (`model_backbone.build_dimension_pair` /
`build_dimension_input_text`): text_a = `QUESTION:\n...` +
(`RELEVANT CONTEXT:\n...` if non-empty) + (`EXPECTED CONCEPTS:\n...` if
non-empty); text_b = the raw answer. Single call site shared by training
(`four_dim_experiment_split._to_training_example` → `model_dataset.collate_fn`)
and inference (`model_evaluator.TrainedEvaluator.evaluate`), so train/infer
framing cannot drift. **This part is sound** — question, context, and expected
concepts are genuinely visible to the encoder, not silently dropped.

**Truncation**: HF's default `longest_first` truncation trims text_a
(context) before text_b (answer) under the 256-token budget. For examples
with long grounding text (the 42 V3-enriched ones) this could truncate
*question* content before answer content in pathological cases, since
`longest_first` alternates by whichever sequence is currently longer — worth
flagging as a secondary risk for the enriched subset, not confirmed as
causal here.

**Backbone**: CLS pooling (default) of a single shared `CrossEncoderBackbone`
— **one pooled vector serves all four dimension heads, the concept head, and
the missing-reasoning head.** No dimension-specific attention, no auxiliary
question-answer entailment/alignment signal, no separate "relevance" pathway.

**CORAL heads** (`model_heads.CoralOrdinalHead`): `nn.Linear(hidden, 1,
bias=False)` + monotonic bias offsets. This is architecturally correct CORAL
(rank-consistency is real, not just encouraged), but it means **each
dimension's entire discriminative power is one 768-dim linear probe** on a
vector that four other tasks are also being read from. If TC and relevance
are not *linearly separable* directions in that shared embedding space — very
plausible, since "sounds technical" and "is technically correct" are
correlated in pretrained language-model embeddings but not identical — a
linear head cannot recover the distinction no matter how much data exists,
unless training actively pushes the shared representation to disentangle them.

**Loss** (`model_heads.compute_batch_loss`): sum of per-dimension CORAL BCE
(masked to valid/labeled dims), missing-reasoning BCE, and concept
cross-entropy when present. **No class weighting, no focal loss, no per-
dimension loss scaling, no sample reweighting anywhere in
`compute_batch_loss` or `train_model`.** Confirmed by direct grep — zero
occurrences of `class_weight`, `sample_weight`, `WeightedRandomSampler`,
`pos_weight`, or `focal` in `model_dataset.py`, `model_heads.py`,
`run_four_dim_training.py`, `training_experimentation.py`.

**Grounding wiring** (`grounding_lookup.py`, `four_dim_experiment_split.py`
lines 85–100): `ProjectGrounding.title`/`technologies` are **always**
populated (from the raw record); `.summary` (the question-scoped enrichment
text) is populated for only 42/220 examples (19%) — the other 178 get `""`.
`.concepts` is hard-coded to `()` for every example regardless of batch — the
`concepts` field of `ProjectGrounding` is dead/unused in this pipeline.

**Expected concepts**: `expected_concepts` on **159/220 examples (72%)** is
an empty tuple — so for nearly three-quarters of training data, the
`EXPECTED CONCEPTS:` section of the input is simply absent (the input builder
correctly omits an empty section rather than emitting a dangling label, but
the practical effect is that the strongest available direct signal for
"did the answer cover what was asked" is missing on most rows).

**No implementation bug found** that would explain the failures as a *defect*
(e.g. mislabeled tensor, wrong target alignment, truncation swapping
question/answer, dimension-name mismatch). The architecture and loss do
exactly what they say; the failure mode is a **design/capacity/data-coverage
gap**, not a bug.

---

## 3. 27-ROW ERROR PATTERN SUMMARY (V3 test set)

Aggregate: 7/27 rows exactly correct on all 4 dims; 20/27 have ≥1 dimension
error. `technical_correctness_pred ∈ {3,4}` for all 27 rows (true range 0–4).
`relevance_completeness_pred = 4` for 24/27 rows (true range 0–4).

Classification of the 13 flagged failures against categories A–H:

| # | Project/Q gist | Categories | TC/Rel error, most likely cause |
|---|---|---|---|
| 1 | QueryTune composite index — generic textbook answer | **E** (generic textbook), A (doesn't address "why composite specifically") | TC 3 vs gold 4 is minor/defensible; **Rel 4 vs gold 1 is severe** — model rewards fluent generic DB explanation without checking it answers "why composite vs. two single-column." Objective + capacity: relevance head can't tell generic-on-topic from specifically-responsive. |
| 2 | DefectScan labeling, imbalance question — only labeling answered | **B** (partial/multipart omission) | Rel 4 vs gold 2: model has no explicit mechanism to check "does this cover both asked parts" — expected_concepts likely empty here (labeling-only answers are common surface pattern). Input-representation limitation. |
| 3 | FraudScore explainability question — answer is retraining/model-choice | **A** (misalignment, answer to a different-but-adjacent question) | Rel 4 vs gold 0 — the most severe kind of relevance failure: answer is detailed, fluent, technically sound, and **completely off-topic**. This is the clearest evidence of "detailed ≠ relevant" not being learned. |
| 4 | HarborETL dedup question — answer is Avro schema evolution | **A** | Same pattern as #3. Rel 4 vs gold 0. |
| 5 | GeoPulse calories question — answer is GPS/Kalman filtering | **A** | Same pattern. Rel 4 vs gold 0. Three of four "textbook A-pattern" failures (#3,#4,#5) are structurally identical: technically excellent, wrong topic — a strong, repeatable signature. |
| 6 | SensorLoop responsiveness — answer describes **removing a mutex causing a race** | **C** (technically incorrect but fluent), **worst TC miss in the set** | TC 4 vs gold 0 — the answer describes an objectively unsafe change (introducing a race condition) delivered with confident, fluent engineering vocabulary. This is the single cleanest "fluent misconception" case and the strongest evidence for a hard-negative/contrastive-training gap on TC specifically. |
| 7 | DefectScan PyTorch-vs-TensorFlow — false claim about TF eager mode | **C** | TC 3 vs gold 1 — same pattern as #6, less extreme miss. |
| 8 | Fraud model accuracy-as-primary-metric — known-bad practice (class imbalance) | **C** / **E** | TC 4 vs gold 2 — the model does not appear to have "accuracy is a bad primary metric under class imbalance" as encoded knowledge that overrides fluency. |
| 9 | CloudBudget underutilized-resources — vague/generic answer | **E** (generic) | Depth 3 vs gold 0, Rel 4 vs gold 3 — model conflates "sounds like an explanation" with actual specificity; this is a depth/relevance confound (see Phase 4). |
| 10 | GeoPulse tracking+battery — omits battery half entirely | **B** | Rel 3 vs gold 2, Grounding 0 vs gold 3 — partial multipart, and the grounding miss (predicted 0, true 3) suggests the model is *also* penalizing on the omitted half rather than crediting the ownership signal present in the answered half — grounding head appears coupled to relevance/completeness rather than independent. |
| 11 | LedgerSync MongoDB justification — grounding true 0, predicted 3 | **G** (valid answer, wrong grounding score) | The answer is detailed and plausible-sounding but (per gold) not actually anchored to real project specifics — model over-credits fluency as if it were ownership evidence. |
| 12 | IntentParser regex classifier — grounding true 0, predicted 2 | **G** | Same pattern as #11. |
| 13 | DefectScan augmentation — Rel 4 vs gold 3, TC 4 vs gold 3 | **D**/**E** boundary, mild | Smallest miss in the set; plausibly within annotation tolerance rather than a real model failure. |

**Category tally across the 13**: A=3 (severe, clean signature), B=2, C=3
(TC-specific), E=3 (generic-reads-as-good), G=2 (grounding over-credits
fluency), D=0 clean. **F (unsupported ownership) did not appear as a clean
case in this list** — #11/#12 are closer to G than a clean ownership-claim
mismatch.

**Likely-cause attribution for TC and relevance** (per dimension, not per row):
- **Relevance_completeness**: primarily **input-representation limitation**
  (no explicit alignment/entailment signal between question and answer beyond
  implicit attention) compounded by **objective limitation** (unweighted loss
  lets the model settle on predicting the training-majority tier). Not
  primarily insufficient training examples in raw count — the pool actually
  has decent tier spread (13/22/22/33/130) — the issue is that spread is not
  being *used* effectively (see Phase 4). Not annotation issue: the 13 flagged
  cases have unambiguous gold labels by inspection.
- **Technical_correctness**: primarily **insufficient training examples at
  low tiers** (only 20/220 pool-wide at tiers 0–2, and V2's split doc records
  val has *zero* TC tier 0/1/2 — test alone carries that signal) combined with
  **objective limitation** (no class weighting to compensate). Row #6
  (mutex/race) is the strongest single piece of evidence that the model has
  not learned domain-correctness at all, only tone/fluency.

---

## 4. V2 vs V3 COMPARISON

Row-by-row (all 27 test IDs, dimensions with any prediction difference or
error shown):

| example_id | dim(s) with true/V2/V3 | note |
|---|---|---|
| v2t50_v1_011 | tech 3/4/4; depth 3/4/3; grnd 3/3/2 | depth fixed by V3, grounding slightly worse |
| v2t50_v1_020 | grnd 4/3/3 | unchanged |
| v2t50_v1_032 | tech 4/3/3; depth 1/2/2; rel 1/4/4; grnd 0/1/1 | unchanged — relevance still maximally wrong (rel 1 gold, both predict 4) |
| seed_v1_002 | tech 3/4/4; depth 1/3/2; rel 3/4/4 | depth partially fixed |
| seed_v1_015 | tech 3/4/4; depth 3/4/3; rel 2/4/4; grnd 4/2/1 | depth fixed; **grounding got worse** (4→2→1) |
| seed_v1_034 | depth 0/1/0; rel 2/3/2; grnd 2/0/0 | depth+rel fixed; grounding still wrong |
| seed_v1_046 | grnd 0/2/2 | unchanged |
| seed_v1_058 | tech 1/4/3; depth 1/3/2; rel 3/4/4; grnd 1/2/1 | TC/depth/grounding partially improved; rel unchanged (still maxed) |
| seed_v1_070 | tech 3/4/4; depth 2/2/3; rel 3/4/4; grnd 3/1/1 | depth got worse; grounding unchanged-wrong |
| seed_v1_082 | — | perfect both versions |
| seed_v1_091 | — | perfect both versions |
| v2t50_v1_015 | tech 3/4/4; grnd 3/2/2 | unchanged |
| v2t50_v1_023 | tech 2/4/4; depth 2/4/3 | depth partially fixed |
| v2t50_v1_027 | depth 3/4/4; rel 0/4/4; grnd 3/4/3 | **rel unchanged at maximal error** (true 0, both predict 4) |
| gap20_v1_003 | rel 0/4/4; grnd 2/4/3 | rel unchanged at maximal error |
| hand50_v1_033/034/036/048/049 | — | perfect all versions |
| hand50_v1_035 | rel 1/3/2 | improved, still wrong |
| hand50_v1_047 | tech 3/4/4; depth 0/2/3; rel 3/4/4; grnd 0/1/1 | depth got worse (further from truth) |
| gap20_v1_005 | depth 3/4/4; grnd 0/4/3 | grounding partially improved, still badly wrong |
| gap20_v1_009 | depth 3/4/4; grnd 0/3/2 | grounding partially improved |
| v2t50_v1_025 | rel 0/4/4; grnd 3/3/2 | rel unchanged at maximal error |
| v2t50_v1_038 | tech 4/4/3; depth 2/2/1; rel 2/4/3; grnd 3/1/0 | **V3 worse on every dim except unchanged tech direction** — a genuine regression row |
| gap20_v1_013 | tech 0/4/4; depth 3/4/4 | **unchanged, maximal TC error (true 0, predicted 4 both versions)** |

**Aggregate** (exact match / MAE, 27 rows):

| dim | V2 acc | V3 acc | V2 MAE | V3 MAE |
|---|---|---|---|---|
| technical_correctness | 0.63 | 0.59 | 0.59 | 0.59 |
| depth_specificity | 0.56 | 0.59 | 0.59 | 0.48 |
| relevance_completeness | 0.56 | 0.59 | 0.96 | 0.85 |
| grounding_ownership | 0.48 | 0.48 | 0.93 | 0.89 |

Rows: **9 improved** (lower total abs error), **4 worsened**, **14
unchanged**, **7 perfect in both**. QWK mean rose 0.3382→0.4135 almost
entirely because **depth_specificity MAE dropped** (0.59→0.48, QWK
0.741→0.800) — the one dimension the pool already had good coverage for.
**relevance_completeness MAE also dropped (0.96→0.85) but exact accuracy is
flat (0.56→0.59) and the maximal-error rows (true 0 → predicted 4, four of
them: v2t50_v1_027, gap20_v1_003, v2t50_v1_025, and effectively
v2t50_v1_032) are unchanged between V2 and V3** — grounding enrichment did
not touch these specific failures. `technical_correctness` accuracy actually
*fell* slightly (0.63→0.59); gap20_v1_013 (true TC 0) is wrong by the maximum
possible margin in **both** versions.

**Does grounding enrichment correlate with improvement?** Weak/inconclusive
at this sample size. `seed_v1_015` and `v2t50_v1_038` (both plausibly among
the 42 grounding-enriched examples, not independently confirmed row-by-row
here) show grounding *predictions* moving — but in `seed_v1_015` grounding
got measurably worse (4/2/1), and in `v2t50_v1_038` every dimension worsened.
The four unchanged maximal-relevance-error rows show grounding enrichment,
where present, did not fix the underlying alignment problem. **Given n=27,
this comparison cannot support a causal claim either way** — consistent with
your instruction not to infer causality from a version change alone.

**Same failure modes remain**: yes, unambiguously. Every "true 0, predicted
4" relevance row in V2 is still "true 0, predicted 4" in V3. The systemic
pattern (fluent+detailed → over-scored) is structurally identical across both
versions; V3's overall QWK gain is concentrated in depth, not in the two
dimensions this task cares about.

---

## 5. DATASET GAPS (Phase 4 quantification, full 220-example V2/V3 pool)

Computed directly from the judged label files (`judged_dimension_labels`),
not from `target_profile`, to match what training actually saw.

**Dimension distributions (0–4), pool-wide, n=220:**

| dim | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| technical_correctness | 12 | 4 | 4 | 72 | 128 |
| relevance_completeness | 13 | 22 | 22 | 33 | 130 |
| depth_specificity | 27 | 22 | 45 | 45 | 81 |
| grounding_ownership | 45 | 42 | 22 | 47 | 64 |

- **technical_correctness is the most imbalanced dimension by far**: 91%
  (200/220) at tier 3–4; only **20 examples total** span tiers 0–2, and the
  V2 split doc already records val has *zero* TC tier-0/1/2 rows — meaning
  effectively all of that signal has to come from a ~14-row slice of train
  plus whatever landed in test. This is a genuine **data coverage gap**, not
  just an artifact of how the split was drawn.
- **relevance_completeness has better raw spread** (13/22/22/33/130) than TC,
  so the failure is less "no data exists" and more "the data isn't being
  leveraged" — consistent with the representation/objective hypothesis above.
- **grounding_ownership has the best spread** of any dimension and is also
  mid-table on QWK (0.58) — partially corroborating that spread, not just
  input richness, matters.

**Heuristic contrastive-evidence counts** (proxy filters, not model-verified
labels — meant to size the phenomenon, not certify each example):

| Signal | Count / 220 |
|---|---|
| Answer >250 chars but relevance_completeness ≤ 2 ("detailed ≠ relevant") | **24** |
| relevance_completeness ≥ 3 but depth_specificity ≤ 1 ("relevant ≠ deep") | **24** |
| technical_correctness ≤ 1 (near-incorrect, any surface fluency) | **16** |
| Question shaped as multi-part ("and"/"both") with relevance in 1–3 (plausible partial-answer) | **11** (heuristic under-count — free-text scan, not a tagged field) |
| grounding_ownership ≤ 1 but first-person language present in the answer ("I"/"we"/"my") | **47** (over-count — many are legitimate low-grounding first-person answers, not unsupported-ownership *claims* specifically; needs manual triage, not usable as-is) |
| `expected_concepts` empty (no direct completeness signal in the input) | **159 / 220 (72%)** |

**Interpretation**: the raw *counts* for "detailed≠relevant" (24) and
"relevant≠deep" (24) are not negligible, but they are (a) scattered across
train/val/test by the frozen V2 split rather than deliberately concentrated,
and (b) confounded with dozens of other varying factors per example (domain,
reasoning type, project) rather than isolated as **controlled, paired**
contrasts. A model with a single linear probe per dimension, trained on 166
rows with no class weighting, has a much harder time extracting "detailed vs
relevant is the operative difference" from 24 *scattered* naturalistic
examples than from a **matched pair** where everything else is held constant.
This is the direct motivation for the V4 design below: not more naturalistic
volume, but tightly controlled contrast pairs that isolate exactly one
dimension's variation at a time.

The 72% empty-`expected_concepts` rate is a second, independent gap: even
where relevance-relevant contrastive answers exist, the model is usually not
given the direct "what should this answer, at minimum, contain" signal that
the input format supports — it has to infer completeness from the question
text alone in 3 of 4 cases.

---

## 6. PROPOSED V4 DIAGNOSTIC DESIGN

**Purpose**: not a training-data expansion. A small, tightly controlled,
paired/contrastive **diagnostic benchmark** to determine, before any further
model or data investment, whether the V3 model's TC/relevance failures are a
*data-coverage* problem (fixable by more contrastive examples of the same
kind) or a *representation/objective/architecture* problem (not fixable by
more data of this shape). Designed to be run purely as inference against the
existing V3 checkpoint — **no training implied by this document.**

**Target size**: 52 examples (within the 40–60 target), across 20 groups.
Every group holds all fields constant except the one dimension under test, so
a correct model should show a large gold-label swing between paired items
with everything else equal, and a broken model should show a much smaller
swing (or none) in its predictions on the same pair.

**Schema for every example** (internal-only rationale field, never fed to the
model — matches the existing input builder, which only ever sees
question/grounding/expected_concepts/answer):

```json
{
  "example_id": "v4_diag_<group>_<letter>",
  "source_id": "<project or hypothetical-project id>",
  "pair_group_id": "<shared id across the contrast set>",
  "diagnostic_category": "relevance_alignment | multipart_completeness | technical_correctness | depth_control | grounding_ownership | cross_dimension",
  "question": "...",
  "grounding": {"title": "...", "technologies": ["..."], "summary": ""},
  "expected_concepts": ["...", "..."],
  "answer": "...",
  "gold_labels": {
    "technical_correctness": 0-4,
    "depth_specificity": 0-4,
    "relevance_completeness": 0-4,
    "grounding_ownership": 0-4
  },
  "rationale": {
    "technical_correctness": "internal-only justification, not model input",
    "depth_specificity": "...",
    "relevance_completeness": "...",
    "grounding_ownership": "..."
  }
}
```

### 6.1 Relevance alignment pairs — 16 examples, 8 groups

Same question; two answers, everything else (length band, vocabulary
register, technical density) matched as closely as possible so relevance is
the *only* thing that should move.

| Group | Question anchor | A (fails) | B (passes) | Gold swing |
|---|---|---|---|---|
| REL-1 | "How does FraudScore explain a flagged transaction to a human reviewer?" | Detailed retraining-cadence/model-choice answer (mirrors real failure #3 above, generalized to a new hypothetical instance so it's not a duplicate of an existing test row) | Concise SHAP-style feature-attribution surfaced-to-reviewer answer | rel 0→4, TC/depth held ~equal |
| REL-2 | "How did HarborETL deduplicate late-arriving events?" | Detailed schema-evolution answer, no dedup mechanism | Concise watermark+idempotency-key dedup answer | rel 0→4 |
| REL-3 | "How does GeoPulse calculate calories burned?" | Detailed GPS/Kalman filtering answer | Concise MET-formula-plus-heart-rate answer | rel 0→4 |
| REL-4 | "Why did the composite index specifically help over two single-column indexes?" | Generic "indexes speed up queries" answer | Answer naming the specific covering-index / avoided-sort mechanism | rel 1→4 |
| REL-5 | "How did you decide between REST and gRPC for the internal service mesh?" | Detailed answer about *load balancer* choice (adjacent topic) | Direct REST-vs-gRPC tradeoff answer | rel 0→4 |
| REL-6 | "Why did the cache stampede after deploy?" | Detailed answer about cache *eviction policy* tuning (adjacent) | Direct thundering-herd/locking answer | rel 0→4 |
| REL-7 | "How do you handle PII in the analytics pipeline?" | Detailed answer about *access-control roles* (adjacent, not PII-specific) | Direct tokenization/redaction-at-ingest answer | rel 1→4 |
| REL-8 | "Why was Redis chosen over Memcached for the session store?" | Long, fluent, technically accurate answer about Redis's *persistence* features generally, never contrasting Memcached | Direct comparative answer addressing why *vs Memcached specifically* | rel 1→4, TC held high in both |

### 6.2 Multipart completeness pairs — 9 examples, 3 groups (both/one/neither)

| Group | Question anchor | Variant | Gold relevance |
|---|---|---|---|
| MP-1 | "Explain both how you labeled training data and how you handled class imbalance." | (a) both parts, (b) labeling only, (c) neither (generic ML pipeline overview) | 4 / 2 / 0 |
| MP-2 | "How does GeoPulse track your route accurately in the background AND preserve battery life?" | (a) both, (b) tracking only, (c) neither | 4 / 2 / 0 |
| MP-3 | "Why did you choose Postgres, and how did you handle the migration from MySQL?" | (a) both, (b) choice only, (c) neither | 4 / 2 / 0 |

### 6.3 Technical correctness pairs — 12 examples, 3 groups (4 variants each)

| Group | Question anchor | Variants | Gold TC |
|---|---|---|---|
| TC-1 | "How did you make the control loop more responsive?" | (a) concise-correct (reduced critical-section width), (b) detailed-but-subtly-incorrect (widened lock scope but frames it as an optimization), (c) confident misconception (removed the mutex entirely, described as a fix — mirrors real failure #6), (d) correct-with-unnecessary-detail (correct fix, padded with irrelevant profiling trivia) | 4 / 1 / 0 / 4 |
| TC-2 | "Why did you use gradient boosted trees over a neural net for the fraud model?" | (a) concise-correct (heterogeneous tabular features + interpretability), (b) subtly-incorrect (claims neural nets "can't handle categorical features" — false), (c) confident misconception (claims GBTs are unable to overfit), (d) correct + unnecessary detail | 4 / 1 / 0 / 4 |
| TC-3 | "Why did you choose PyTorch over TensorFlow?" | (a) concise-correct (dynamic graph / debugging ergonomics), (b) subtly-incorrect (mild mischaracterization of TF's current eager-mode support), (c) confident misconception (claims TF "cannot do eager/debug mode once deployed" — mirrors real failure #7), (d) correct + unnecessary detail | 4 / 1 / 0 / 4 |

### 6.4 Depth control pairs — 6 examples, 2 groups (3 variants each)

| Group | Question anchor | Variants | Gold depth |
|---|---|---|---|
| DEP-1 | "How does CloudBudget identify underutilized resources?" | (a) correct-but-shallow ("looks at usage metrics and flags anything inefficient" — mirrors real failure #9), (b) correct+mechanism (specific utilization thresholds, lookback window), (c) correct+mechanism+tradeoff (adds why false-positive rate was tuned down at cost of recall) | 0 / 3 / 4 |
| DEP-2 | "How did you speed up the dashboard's slowest query?" | (a) shallow ("added an index"), (b) +mechanism (composite index, avoided sort), (c) +mechanism+tradeoff (write-amplification cost accepted for a read-heavy table) | 1 / 3 / 4 |

### 6.5 Grounding/ownership pairs — 9 examples, 2 groups

| Group | Question anchor | Variants | Gold grounding |
|---|---|---|---|
| GRD-1 | "What database did you choose for the ledger store and why?" | (a) generic-correct (textbook Postgres-vs-Mongo tradeoffs, no project specifics), (b) project-specific-no-ownership ("the team chose Postgres for X reason", third person), (c) project-specific-explicit-ownership ("I benchmarked write latency and pushed for Postgres because..."), (d) unsupported-ownership (first-person claim of a decision with no verifiable specifics, generic justification only), (e) project-specific + genuine ownership + a real tradeoff acknowledged | 0 / 2 / 4 / 1 / 4 |
| GRD-2 | "How does IntentParser classify user intents?" | (a) generic-correct (rule-based classifier textbook description), (b) project-specific-no-ownership, (c) explicit-ownership, (d) unsupported-ownership | 0 / 2 / 4 / 1 |

### 6.6 Cross-dimension disentanglement — 6 examples, 2 groups

Each group holds three of the four dimensions approximately constant while
deliberately swinging the fourth, to test whether the model's four heads are
actually independent or whether (as row #10/#11/#12 above suggest) grounding
and relevance move together spuriously.

| Group | Design | What should move | What should stay flat |
|---|---|---|---|
| XD-1 | Same project, same correct+deep answer content; swing only person/ownership framing (third-person textbook → first-person specific ownership) across 3 variants | grounding_ownership only | TC, depth, relevance |
| XD-2 | Same project, same first-person ownership framing; swing only topical relevance (on-topic → adjacent-topic) across 3 variants | relevance_completeness only | grounding_ownership, TC (depth may drop slightly if the adjacent answer is also less specific — flagged in rationale, not assumed away) |

**Total**: 16 + 9 + 12 + 6 + 9 + 6 = **58 examples**, close to your suggested
weighting (you asked ~15/10/8/8/5/5=51; this lands at 16/9/12/6/9/6 — relevance
and TC given slightly more weight than depth, per what the 27-row analysis
showed is actually broken; depth is deliberately kept minimal since V3
already handles it well and it mainly serves as a sanity-check baseline).

**Hypothetical-project policy**: REL-1/2/3 and TC-1/2/3 deliberately mirror
the *shape* of real observed failures (#3,#4,#5,#6,#7,#9,#10,#11,#12 above)
but use **new hypothetical project instances**, not the existing FraudScore/
HarborETL/GeoPulse/SensorLoop/DefectScan/LedgerSync/IntentParser/CloudBudget/
QueryTune records — reusing the exact same project+question would just
re-test memorized examples, not generalization, and would risk the V4 set
overlapping the frozen V1–V3 pools. Where a real supported fact pattern
exists (e.g., composite index avoiding a sort — genuinely true, general CS
knowledge, not a fabricated project fact), it is reused because it's
domain-general truth, not a specific unverifiable claim about an existing
project.

---

## 7. DECISION TREE FOR NEXT MODEL CHANGE

Run V4 read-only against the existing V3 checkpoint (no retraining), then:

- **If the model correctly separates the paired contrasts** (e.g. REL-1a vs
  REL-1b differ by ≥2 tiers on relevance in the predicted direction, across
  most of the 8 relevance groups) → the architecture *can* use the signal
  when it's isolated and unambiguous. **Conclusion: data coverage problem** —
  recommend a targeted V5 training-data expansion built the same way as V4
  (paired/contrastive), not more naturalistic volume.
- **If the model cannot distinguish detailed-but-irrelevant from
  concise-but-relevant even in these maximally clean, isolated pairs** →
  **investigate input representation / objective / architecture**:
  specifically, consider (a) per-dimension MLP heads instead of single linear
  probes, (b) an explicit auxiliary entailment/alignment loss between
  question and answer, (c) class-weighted or focal CORAL loss for TC and
  relevance specifically. Do not spend further effort on naturalistic data
  volume until this is ruled out.
- **If TC fails specifically on the fluent-misconception group (TC-1c/TC-2c/
  TC-3c) but succeeds on the concise-correct and confident-misconception-is-
  obviously-wrong-length signal is what's driving it** — i.e., if TC-1c
  (short, fluent, wrong) is missed but TC-1d (long, correct) is right →
  that's strong evidence the model is using **length/fluency as a TC proxy**
  rather than correctness. **Recommend hard-negative-focused training data**
  (confident, concise misconceptions specifically) over general TC volume.
- **If grounding stays confused independent of what relevance/TC do** (XD-1
  shows grounding not moving when only ownership framing changes) →
  **investigate grounding representation separately** — e.g. whether
  first-person language is being used as a shortcut instead of verifiable
  project-specificity, independent of the relevance/TC fixes above.
- **Given n=27 test rows already produces QWK swings of ±0.07 on small
  distribution shifts, and V4 itself is only 58 rows** — treat V4 results as
  **directional, not confirmatory**. If V4's signal is itself ambiguous
  (mixed results within a group, or pairs that don't cleanly separate),
  **recommend building a larger held-out diagnostic benchmark (150+ rows,
  same paired-contrast design, more groups per category) before committing
  to an architecture or objective change** — a single 27-row test set and a
  58-row diagnostic set are both too small to be the sole basis for a
  structural model decision.

---

## 8. EXACT FILES INSPECTED

Implementation: `main_cap/cap/model_backbone.py`, `main_cap/cap/model_heads.py`,
`main_cap/cap/model_dataset.py` (grep only — collate/target construction),
`main_cap/cap/four_dim_experiment_split.py`, `main_cap/cap/run_four_dim_training.py`
(partial — training-entrypoint experiment registration, grep for weighting),
`main_cap/cap/grounding_lookup.py`, `main_cap/cap/evaluation_dimensions.py`
(grep — dimension enum), `main_cap/cap/model_evaluator.py` (referenced, not
deep-read this pass).

Data: `main_cap/cap/artifacts/four_dim_training_v1/test_predictions.json`,
`.../four_dim_training_v2/test_predictions.json`,
`.../four_dim_training_v3/test_predictions.json` (all recovered from Colab
downloads this session, placed in gitignored paths, not committed),
`main_cap/cap/artifacts/seed_dataset_v1/seed_v1_3_repaired.jsonl` +
`seed_v1_3_judged.jsonl`, `main_cap/cap/artifacts/hand_authored_50/
hand_authored_50_v1.jsonl` + `_judged.jsonl`, `main_cap/cap/artifacts/
gap_coverage_20/gap20_v1.jsonl` + `_judged.jsonl`, `main_cap/cap/artifacts/
v2_targeted_50/v2_targeted_50_v1.jsonl` + `_judged.jsonl` (the full 220-example
V2/V3 pool, judged labels only — no records modified).

Docs read for context (not modified): `docs/architecture/
DeBERTa_V2_Data_Expansion_Status.md`, `docs/architecture/
DeBERTa_Dataset_Expansion_Checkpoint.md`.

---

## 9. CONFIDENCE / LIMITATIONS

- **High confidence**: the architectural bottleneck (single linear CORAL
  head per dimension on one shared pooled vector) and the absence of any
  class weighting are directly confirmed by reading the code, not inferred.
- **High confidence**: the TC/relevance prediction-distribution collapse in
  V3 test predictions (TC never <3, relevance =4 in 24/27) is a direct
  computation from the artifact, not an estimate.
- **Medium confidence**: the causal story ("collapse because of imbalance +
  linear heads, not because of insufficient raw data volume") is the
  best-supported explanation given the evidence, but **is not proven** — it
  is a hypothesis this document recommends V4 be used to test, per your own
  Phase 6 instructions. Do not treat Section 1's verdict as settled fact.
- **Low confidence / explicitly flagged as heuristic, not verified**: the
  Phase 4 quantification table (Section 5) uses proxy filters (answer length
  >250 chars, "and"/"both" string matching, first-person pronoun presence) —
  these size the phenomenon roughly but individual examples were **not**
  manually re-verified against their gold labels. The "47 unsupported-
  ownership-shaped" count in particular is almost certainly an over-count
  and needs manual triage before being used for anything beyond rough sizing.
- **V2-vs-V3 comparison (Section 4) is explicitly correlational**, per your
  instruction not to infer causality from a version change on 27 rows.
- **V3 checkpoint weights were not loaded or run in this session** — this
  report is entirely from static artifact/code inspection, consistent with
  the read-only, no-training constraint. The V4 decision tree in Section 7
  requires actually running inference (still not training) once V4 is built
  and approved — that is explicitly the next step, not done here.
- The `four_dim_training_v1`/`_v2`/`_v3` prediction JSON files did not exist
  in this local checkout at the start of this session (artifacts/ is
  gitignored, training ran on Colab) — they were located in `Downloads/` and
  placed into the expected paths as part of this session, unmodified, not
  committed.

---

## RECOMMENDATION (not implemented)

Build V4 exactly as designed in Section 6 (58 examples, paired/contrastive,
new hypothetical project instances to avoid overlap with the frozen pools),
run it read-only against the existing V3 checkpoint, and use Section 7's
decision tree to decide between (a) a per-dimension head/loss architecture
change or (b) a targeted contrastive data-expansion pass — **before** doing
either. Do not expand training data broadly, and do not touch the CORAL
head/loss architecture, until V4's read against the real checkpoint confirms
which failure mode is actually binding.
