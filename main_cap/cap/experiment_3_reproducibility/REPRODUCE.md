# How to Reproduce `v_experiment_3_relabeled_dimensions` from Experiment 2

This dataset is produced by a **fully deterministic relabeling pass** — zero new text
generation, zero new API calls, zero new random sampling. Re-running the steps below against
an unchanged `artifacts/experiment_2/dataset.jsonl` will always produce byte-identical
output.

## Prerequisites

1. Repository checked out at the commit/working-tree state pinned in
   [`provenance.json`](provenance.json) (`git_provenance` + `file_content_hashes_sha256` —
   verify `dataset_relabeling.py`'s hash matches before trusting the output against this
   package's documented statistics).
2. `artifacts/experiment_2/dataset.jsonl` and `artifacts/experiment_2/split.json` already
   exist. If they don't: `python run_experiment_2.py generate` (from `main_cap/cap/`) — see
   that script's own docs; this package does not cover Experiment 2's generation, only the
   relabeling step on top of it.
3. Python environment with this repository's dependencies installed (same one the test suite
   runs under).

## Steps

```bash
cd main_cap/cap

# 1. (Optional but recommended) Run the relabeling-specific test suite first.
python -m pytest test_dataset_relabeling.py -q
# Expected: 19 passed

# 2. Run the relabeling script.
python run_dataset_relabel.py relabel
```

Expected console output (values will match if inputs/code are unchanged):

```
[HH:MM:SS] === Dataset Relabeling / Phase: RELABEL (Stage 1A) ===
[HH:MM:SS] Loaded 2479 examples from '...artifacts\experiment_2\dataset.jsonl'.
[HH:MM:SS] Relabeled 2479 examples (dimension_labels recomputed from each example's own recipe data).
[HH:MM:SS] Score changes: 4675 individual dimension scores changed across 2340/2479 examples.
[HH:MM:SS] Changes by dimension: {'architecture': 398, 'communication': 1187, 'completeness': 2315, 'ownership': 392, 'testing': 188, 'tradeoffs': 195}
[HH:MM:SS] DatasetManifest assembled: 2479 examples, tier_distribution={...}, label_source_distribution={'synthetic_ground_truth': 2479}.
[HH:MM:SS] Split reused unchanged from '...artifacts\experiment_2\split.json': train=1738, val=379, test=362.
[HH:MM:SS] Persisted dataset/manifest/split/relabel_summary to '...artifacts\experiment_3_relabeled'.
[HH:MM:SS] === RELABEL PHASE COMPLETE ===
```

This produces (all gitignored, local-only, same convention as every other experiment's
`artifacts/` output):

- `artifacts/experiment_3_relabeled/dataset.jsonl` — the 2,479 relabeled examples
- `artifacts/experiment_3_relabeled/manifest.json` — copied into this package as
  [`manifest.json`](manifest.json)
- `artifacts/experiment_3_relabeled/split.json` — identical to Experiment 2's split.json
- `artifacts/experiment_3_relabeled/relabel_summary.json` — copied into this package as
  [`change_summary.json`](change_summary.json)

## Verify the reproduction matches this package

```bash
# 3. Full repository regression suite.
python -m pytest -q
# Expected: 1213 passed, 21 subtests passed, 0 failed
```

To regenerate the statistical comparison in [`statistics.json`](statistics.json) and
[`COMPARISON.md`](COMPARISON.md) yourself, load `artifacts/experiment_2/dataset.jsonl` and
`artifacts/experiment_3_relabeled/dataset.jsonl` as JSONL and recompute: tier distribution,
per-dimension mean/stdev/histograms, pairwise Pearson correlation across
`labels.dimension_labels`, the `completeness`-equals-flat-tier-value rate, and the
WEAK/POOR exact-0.0 rate. `statistics.json`'s structure documents exactly which fields feed
each of those numbers, so this is mechanical, not code you need to read to understand what
it means.

## What must NOT change between reproductions

- `artifacts/experiment_2/dataset.jsonl` and `split.json` — the input.
- `dataset_relabeling.py` — the core relabeling logic (hash pinned in `provenance.json`).
- `generation_recipe.py`, `training_example_assembler.py`,
  `reasoning_dimension_relevance.py` — read by relabeling but never modified by it; if any of
  these change, the *inputs* to relabeling would themselves have changed, which is a
  different scenario from "reproducing this dataset" (those changes would require
  re-running Experiment 2's generation first).
