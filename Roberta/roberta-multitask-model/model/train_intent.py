from __future__ import annotations

from pathlib import Path
import sys


CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from model.multitask_utils import SAVED_MODELS_DIR, TaskSpec, train_task_model


INTENT_LABELS = ["definition", "explanation", "comparison", "procedure", "reasoning"]


def main() -> None:
    spec = TaskSpec(
        name="intent",
        label_key="intent",
        labels=INTENT_LABELS,
        save_dir=SAVED_MODELS_DIR / "intent",
    )
    model_dir = train_task_model(spec)
    print(f"Intent model saved to: {model_dir}")


if __name__ == "__main__":
    main()
