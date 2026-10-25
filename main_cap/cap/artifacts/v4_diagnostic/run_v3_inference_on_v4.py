"""
V3-checkpoint-on-V4 inference runner — READ-ONLY, INFERENCE-ONLY.

Loads the EXISTING trained V3 four-dimension checkpoint via the project's
own `model_checkpoint_io.load_checkpoint_artifact` (no new/incompatible
loader) and runs it, in `model.eval()` + `torch.no_grad()`, against the 58
V4 diagnostic examples, using the PRODUCTION input-construction functions
directly (`model_backbone.grounding_to_text` / `build_dimension_pair` /
`tokenize_pair`, `model_heads.coral_predict`) rather than
`v4_input_builder.py`'s standalone reimplementation -- so this experiment
reproduces exactly what `model_evaluator.TrainedEvaluator.evaluate()` would
do, without needing to construct a full `EvaluationRequest`/
`QuestionSpecification` object per example (this script builds only the
minimal duck-typed grounding object `grounding_to_text` actually reads).

Does NOT:
- train, fine-tune, or call `.backward()`/`optimizer.step()` anywhere.
- modify `model_backbone.py`, `model_heads.py`, `model_checkpoint_io.py`,
  `model_evaluator.py`, or any other production file.
- modify `v4_diagnostic_58.jsonl` or any V1/V2/V3 artifact.

Writes exactly one new file: `v3_predictions_on_v4.json` in this directory.
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_CAP_DIR = os.path.dirname(os.path.dirname(_HERE))  # main_cap/cap
sys.path.insert(0, _CAP_DIR)
sys.path.insert(0, _HERE)

import torch  # noqa: E402

from evaluation_dimensions import all_keys as canonical_dimension_keys  # noqa: E402
from model_backbone import BackboneConfig, build_tokenizer, build_dimension_pair, grounding_to_text, tokenize_pair  # noqa: E402
from model_checkpoint_io import load_checkpoint_artifact  # noqa: E402
from model_heads import coral_predict  # noqa: E402

CANONICAL_DIMENSION_KEYS = canonical_dimension_keys()
CHECKPOINT_PATH = os.path.join(_CAP_DIR, "artifacts", "four_dim_training_v3", "best_checkpoint_weights.pt")
V4_DATASET_PATH = os.path.join(_HERE, "v4_diagnostic_58.jsonl")
OUTPUT_PATH = os.path.join(_HERE, "v3_predictions_on_v4.json")


def _load_v4_examples() -> list[dict]:
    with open(V4_DATASET_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _grounding_object(example: dict):
    """Minimal duck-typed stand-in for the real `Grounding`/`ProjectGrounding`
    objects, matching exactly the attributes `model_backbone.grounding_to_text`
    reads (`.project.title/.summary/.technologies/.concepts`) -- this is the
    SAME function the real training/inference pipeline uses, called here
    with the same shape of object, not a reimplementation of its logic."""
    g = example["grounding"]
    project = SimpleNamespace(
        title=g.get("title", ""), summary=g.get("summary", ""),
        technologies=tuple(g.get("technologies", ())), concepts=(),
    )
    return SimpleNamespace(project=project, experience=None, certification=None)


def main() -> None:
    assert os.path.exists(CHECKPOINT_PATH), f"checkpoint not found at {CHECKPOINT_PATH}"
    size_mb = os.path.getsize(CHECKPOINT_PATH) / (1024 * 1024)
    print(f"Checkpoint found: {CHECKPOINT_PATH} ({size_mb:.1f} MB)")

    backbone_config = BackboneConfig(hf_model_id="microsoft/deberta-v3-base", max_length=256, pooling="cls")
    print("Loading tokenizer (microsoft/deberta-v3-base)...")
    tokenizer = build_tokenizer(backbone_config)

    print("Reconstructing MultiTaskModel architecture (4 canonical CORAL heads) and loading checkpoint weights...")
    model = load_checkpoint_artifact(
        CHECKPOINT_PATH, backbone_config,
        dimension_names=CANONICAL_DIMENSION_KEYS,
        num_ordinal_classes=5,
        map_location="cpu",
    )
    model.eval()
    print("Checkpoint loaded successfully. dimension_names:", model.dimension_names)

    examples = _load_v4_examples()
    print(f"Loaded {len(examples)} V4 diagnostic examples.")

    predictions = []
    with torch.no_grad():
        for ex in examples:
            grounding_obj = _grounding_object(ex)
            grounding_text = grounding_to_text(grounding_obj)  # PRODUCTION function
            text_a, text_b = build_dimension_pair(  # PRODUCTION function
                ex["question"], grounding_text, tuple(ex.get("expected_concepts") or ()), ex["answer"],
            )
            encoding = tokenize_pair(tokenizer, text_a, text_b, backbone_config.max_length)  # PRODUCTION function
            batch = tokenizer.pad([encoding], return_tensors="pt")
            outputs = model.forward_dimensions(batch["input_ids"], batch["attention_mask"])

            row = {
                "example_id": ex["example_id"],
                "diagnostic_category": ex["diagnostic_category"],
                "pair_group_id": ex["pair_group_id"],
                "question": ex["question"],
                "answer": ex["answer"],
            }
            for dim in CANONICAL_DIMENSION_KEYS:
                logits = outputs["dimension_logits"][dim]
                pred = int(coral_predict(logits)[0].item())  # PRODUCTION CORAL decoding
                row[f"{dim}_true"] = ex["gold_labels"][dim]
                row[f"{dim}_pred"] = pred
            predictions.append(row)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(predictions)} predictions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
