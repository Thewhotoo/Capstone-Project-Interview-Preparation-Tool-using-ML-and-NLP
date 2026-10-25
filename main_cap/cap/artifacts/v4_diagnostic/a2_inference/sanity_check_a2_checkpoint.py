"""
SANITY CHECK ONLY -- not part of the deliverable, writes nothing. Confirms
the A2 checkpoint reproduces the REPORTED A2 test-set QWK numbers (TC
0.2270, Depth 0.8920, Relevance 0.2890, Grounding 0.5050, mean 0.4783)
before trusting it for V4 inference. Same methodology as
`../sanity_check_v3_checkpoint.py` / `../sanity_check_a1_checkpoint.py`,
pointed at the A2 checkpoint instead.

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
CHECKPOINT_PATH = os.path.join(_CAP_DIR, "artifacts", "four_dim_training_v3_expA2", "best_checkpoint_weights.pt")
SPLIT_PATH = os.path.join(_CAP_DIR, "artifacts", "four_dim_experiment_v2", "split.json")


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
    model = load_checkpoint_artifact(
        CHECKPOINT_PATH, backbone_config, dimension_names=CANONICAL_DIMENSION_KEYS,
        num_ordinal_classes=5, map_location="cpu",
    )
    model.eval()

    label_by_dim = {ex.metadata.example_id: {dl.name: dl.score for dl in ex.labels.dimension_labels} for ex in test_examples}

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

    print("\n--- Reproduced A2 test metrics (should closely match reported: TC 0.2270, Depth 0.8920, Rel 0.2890, Grounding 0.5050, mean 0.4783) ---")
    ks = []
    for dim in CANONICAL_DIMENSION_KEYS:
        k = qwk(trues[dim], preds[dim])
        ks.append(k)
        print(f"{dim}: QWK={k:.4f}  n={len(trues[dim])}")
    print(f"mean QWK = {sum(ks)/len(ks):.4f}")


if __name__ == "__main__":
    main()
