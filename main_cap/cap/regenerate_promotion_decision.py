"""
Regenerate a missing `final_promotion_decision.json` from an already-trained
checkpoint -- INFERENCE ONLY, no retraining, no gradient steps.

Why this exists: `best_checkpoint_weights.pt`/`best_checkpoint.json` do not
themselves contain a QWK value (verified directly against
`training_experimentation.Checkpoint`'s fields) -- `PromotionDecision` can
only be produced by actually running the trained model over the held-out
test set. This script does exactly that, reusing the SAME, unmodified
benchmarking/promotion functions the training scripts already call
(`run_benchmark`, `decide_promotion`, `PromotionPolicy`, `HeuristicEvaluator`)
against Experiment 2's already-generated dataset/split
(`artifacts/experiment_2/`) -- no new methodology, no architecture change,
no dataset change.

Usage:
    python regenerate_promotion_decision.py <checkpoint_dir>

<checkpoint_dir> must contain `best_checkpoint_weights.pt` and
`best_checkpoint.json` (wherever the downloaded checkpoint currently lives).
Writes `regenerated_benchmark.json` and `final_promotion_decision.json` into
that same directory.
"""

from __future__ import annotations

import os
import sys

from dataset_manifest import DatasetManifest
from experiment_dataset_io import load_examples_jsonl, load_json, save_json
from heuristic_evaluator import HeuristicEvaluator
from model_backbone import BackboneConfig, build_tokenizer
from model_checkpoint_io import load_checkpoint_artifact
from model_evaluator import TrainedEvaluator
from training_experimentation import Checkpoint, DatasetSplit, PromotionPolicy, decide_promotion, run_benchmark

_CORE_GRADES = frozenset({"poor", "weak", "adequate", "good", "excellent"})
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts", "experiment_2")


def main(checkpoint_dir: str) -> int:
    weights_path = os.path.join(checkpoint_dir, "best_checkpoint_weights.pt")
    checkpoint_path = os.path.join(checkpoint_dir, "best_checkpoint.json")
    if not os.path.exists(weights_path) or not os.path.exists(checkpoint_path):
        print(f"BLOCKER: expected both {weights_path!r} and {checkpoint_path!r} to exist.", file=sys.stderr)
        return 1

    checkpoint = load_json(Checkpoint, checkpoint_path)

    manifest = load_json(DatasetManifest, os.path.join(DATASET_DIR, "manifest.json"))
    if manifest.dataset_version != checkpoint.dataset_version:
        print(f"BLOCKER: dataset_version mismatch -- manifest={manifest.dataset_version!r} "
              f"vs checkpoint={checkpoint.dataset_version!r}. Refusing to benchmark against the wrong dataset.",
              file=sys.stderr)
        return 1

    examples = load_examples_jsonl(os.path.join(DATASET_DIR, "dataset.jsonl"))
    split = load_json(DatasetSplit, os.path.join(DATASET_DIR, "split.json"))
    by_id = {e.metadata.example_id: e for e in examples}
    test_examples = tuple(by_id[i] for i in split.test_ids)
    core_test_examples = tuple(e for e in test_examples if e.labels.overall_label.grade in _CORE_GRADES)
    print(f"Re-benchmarking checkpoint {checkpoint.model_version!r} against "
          f"{len(core_test_examples)}/{len(test_examples)} core-grade TEST examples "
          f"(identical held-out set/methodology used during training).")

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=128)
    tokenizer = build_tokenizer(backbone_config)
    model = load_checkpoint_artifact(weights_path, backbone_config)  # inference only
    trained_evaluator = TrainedEvaluator(checkpoint, model, tokenizer, backbone_config)
    baseline = HeuristicEvaluator()

    benchmark = run_benchmark(trained_evaluator, baseline, core_test_examples, dataset_version=checkpoint.dataset_version)
    print(f"candidate QWK={benchmark.candidate_qwk:.4f}  baseline QWK={benchmark.baseline_qwk:.4f}")

    decision = decide_promotion(checkpoint, benchmark, PromotionPolicy())
    print(f"Promotion decision: approved={decision.approved} -- {decision.rationale}")

    save_json(benchmark, os.path.join(checkpoint_dir, "regenerated_benchmark.json"))
    save_json(decision, os.path.join(checkpoint_dir, "final_promotion_decision.json"))
    print(f"Wrote regenerated_benchmark.json + final_promotion_decision.json to {checkpoint_dir!r}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python regenerate_promotion_decision.py <checkpoint_dir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
