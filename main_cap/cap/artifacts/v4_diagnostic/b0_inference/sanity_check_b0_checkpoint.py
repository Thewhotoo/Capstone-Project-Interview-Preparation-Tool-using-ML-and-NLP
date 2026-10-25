"""
SANITY CHECK ONLY -- not part of the deliverable, writes nothing (except
where explicitly noted below). Same methodology as
`../sanity_check_v3_checkpoint.py` / `../sanity_check_a1_checkpoint.py` /
`../a2_inference/sanity_check_a2_checkpoint.py`, pointed at the B0
checkpoint instead, PLUS two additional checks specific to B0's
architecture flag (not needed for A0/A1/A2, which have no such flag):

1. Confirms the B0 checkpoint (artifacts/four_dim_training_v3_expB0/
   best_checkpoint_weights.pt, reported best epoch: 6) loads successfully
   with `use_private_mlp=True, mlp_hidden_dim=128, mlp_dropout=0.1` -- the
   exact architecture it was trained with -- and reproduces real QWK
   numbers on the frozen `four_dim_experiment_v2` test split (printed to
   stdout; no target numbers are asserted here since none were supplied
   ahead of this check -- this script's job is to REPORT what the
   checkpoint actually does, not to compare against a claim).
2. Confirms that loading the SAME checkpoint file with
   `use_private_mlp=False` (i.e. reconstructing the WRONG architecture --
   plain `CoralOrdinalHead(768, ...)` heads, no private-MLP parameters)
   fails LOUDLY with a `RuntimeError` (strict `load_state_dict` shape
   mismatch), never silently loading partial/wrong weights. This is the
   direct proof of V6 Ablation Design Review §12.4/§14's safety claim,
   run here against the REAL B0 checkpoint file (not just the tiny
   random-init model used in `test_dimension_private_mlp.py`'s unit test).

READ-ONLY: loads frozen pool/split files, does not write to them, does not
train.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V4_DIR = os.path.dirname(_HERE)  # artifacts/v4_diagnostic
_CAP_DIR = os.path.dirname(os.path.dirname(_V4_DIR))  # main_cap/cap
sys.path.insert(0, _CAP_DIR)

import torch  # noqa: E402

from evaluation_dimensions import all_keys as canonical_dimension_keys  # noqa: E402
from four_dim_experiment_v2_split import load_v2_pool  # noqa: E402
from model_backbone import BackboneConfig, build_tokenizer, build_dimension_pair, tokenize_pair  # noqa: E402
from model_checkpoint_io import load_checkpoint_artifact  # noqa: E402
from model_heads import coral_predict  # noqa: E402

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()
CHECKPOINT_PATH = os.path.join(_CAP_DIR, "artifacts", "four_dim_training_v3_expB0", "best_checkpoint_weights.pt")
SPLIT_PATH = os.path.join(_CAP_DIR, "artifacts", "four_dim_experiment_v2", "split.json")

# B0's architecture (V6 Ablation Design Review, approved) -- must match
# training exactly.
USE_PRIVATE_MLP = True
MLP_HIDDEN_DIM = 128
MLP_DROPOUT = 0.1


def qwk(y_true, y_pred, n=5):
    O = [[0] * n for _ in range(n)]
    for t, p in zip(y_true, y_pred):
        O[t][p] += 1
    hist_t = [0] * n
    hist_p = [0] * n
    for t in y_true:
        hist_t[t] += 1
    for p in y_pred:
        hist_p[p] += 1
    N = len(y_true)
    E = [[hist_t[i] * hist_p[j] / N for j in range(n)] for i in range(n)]
    W = [[((i - j) ** 2) / ((n - 1) ** 2) for j in range(n)] for i in range(n)]
    num = sum(W[i][j] * O[i][j] for i in range(n) for j in range(n))
    den = sum(W[i][j] * E[i][j] for i in range(n) for j in range(n))
    return 1.0 if den == 0 else 1 - num / den


def _run_test_metrics(model, test_examples, label_by_dim, tokenizer, backbone_config):
    preds = {d: [] for d in CANONICAL_DIMENSION_KEYS}
    trues = {d: [] for d in CANONICAL_DIMENSION_KEYS}
    with torch.no_grad():
        for ex in test_examples:
            spec = ex.inputs.specification
            grounding_text = ""
            if spec.grounding and spec.grounding.project:
                p = spec.grounding.project
                parts = [p.title or "", p.summary or ""] + list(p.technologies or ()) + list(p.concepts or ())
                grounding_text = " ".join(x for x in parts if x).strip()
            text_a, text_b = build_dimension_pair(
                ex.inputs.question_text, grounding_text, ex.inputs.expected_concepts, ex.inputs.answer_text,
            )
            encoding = tokenize_pair(tokenizer, text_a, text_b, backbone_config.max_length)
            batch = tokenizer.pad([encoding], return_tensors="pt")
            outputs = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])
            for dim in CANONICAL_DIMENSION_KEYS:
                pred = int(coral_predict(outputs["dimension_logits"][dim])[0].item())
                true_score = label_by_dim[ex.metadata.example_id][dim]
                true_tier = round(true_score * 4)
                preds[dim].append(pred)
                trues[dim].append(true_tier)
    return preds, trues


def main():
    with open(SPLIT_PATH, encoding="utf-8") as f:
        split = json.load(f)
    test_ids = set(split["test_ids"])
    print(f"V2 split test_ids: {len(test_ids)}")

    pool = load_v2_pool()
    test_examples = [ex for ex in pool if ex.metadata.example_id in test_ids]
    print(f"Matched {len(test_examples)} test TrainingExamples from the 220-example pool.")

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256, pooling="cls")
    tokenizer = build_tokenizer(backbone_config)
    label_by_dim = {ex.metadata.example_id: {dl.name: dl.score for dl in ex.labels.dimension_labels} for ex in test_examples}

    assert os.path.exists(CHECKPOINT_PATH), f"checkpoint not found at {CHECKPOINT_PATH}"
    size_mb = os.path.getsize(CHECKPOINT_PATH) / (1024 * 1024)
    print(f"B0 checkpoint found: {CHECKPOINT_PATH} ({size_mb:.1f} MB)")

    # ── Check 1: loads correctly with use_private_mlp=True (the TRUE architecture) ──
    print(f"\n--- Check 1: loading with use_private_mlp=True mlp_hidden_dim={MLP_HIDDEN_DIM} "
          f"mlp_dropout={MLP_DROPOUT} (matching training) ---")
    model = load_checkpoint_artifact(
        CHECKPOINT_PATH, backbone_config, dimension_names=CANONICAL_DIMENSION_KEYS,
        num_ordinal_classes=5, map_location="cpu",
        use_private_mlp=USE_PRIVATE_MLP, mlp_hidden_dim=MLP_HIDDEN_DIM, mlp_dropout=MLP_DROPOUT,
    )
    model.eval()
    print("    PASS: checkpoint loaded successfully with the correct (private-MLP) architecture.")
    print("    dimension_heads.use_private_mlp =", model.dimension_heads.use_private_mlp)
    print("    dimension_heads.mlp_hidden_dim  =", model.dimension_heads.mlp_hidden_dim)
    for name in CANONICAL_DIMENSION_KEYS:
        in_features = model.dimension_heads.heads[name].shared.in_features
        print(f"    heads[{name}].shared.in_features = {in_features} (expected {MLP_HIDDEN_DIM})")
        assert in_features == MLP_HIDDEN_DIM

    preds, trues = _run_test_metrics(model, test_examples, label_by_dim, tokenizer, backbone_config)
    print("\n--- B0 real test-set metrics (reported best epoch: 6) ---")
    ks = []
    for dim in CANONICAL_DIMENSION_KEYS:
        k = qwk(trues[dim], preds[dim])
        ks.append(k)
        print(f"{dim}: QWK={k:.4f}  n={len(trues[dim])}")
    print(f"mean QWK = {sum(ks)/len(ks):.4f}")

    # ── Check 2: loading the SAME file with use_private_mlp=False must fail loudly ──
    print("\n--- Check 2: loading the SAME checkpoint file with use_private_mlp=False "
          "(WRONG architecture) -- must fail loudly, not silently ---")
    try:
        load_checkpoint_artifact(
            CHECKPOINT_PATH, backbone_config, dimension_names=CANONICAL_DIMENSION_KEYS,
            num_ordinal_classes=5, map_location="cpu",
            use_private_mlp=False,  # deliberately wrong
        )
    except RuntimeError as e:
        print("    PASS: RuntimeError raised as expected (strict load_state_dict shape mismatch).")
        print(f"    error (truncated): {str(e)[:300]}")
    else:
        raise AssertionError(
            "FAIL: loading the B0 checkpoint with use_private_mlp=False did NOT raise -- "
            "this would silently load the wrong architecture."
        )

    print("\nAll sanity checks passed.")


if __name__ == "__main__":
    main()
