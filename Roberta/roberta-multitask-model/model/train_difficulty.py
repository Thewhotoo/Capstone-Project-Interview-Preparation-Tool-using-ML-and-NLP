from __future__ import annotations

from pathlib import Path
import sys


CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from model.multitask_utils import SAVED_MODELS_DIR, TaskSpec, train_task_model


DIFFICULTY_LABELS = ["easy", "medium", "hard"]


def main() -> None:
    spec = TaskSpec(
        name="difficulty",
        label_key="difficulty",
        labels=DIFFICULTY_LABELS,
        save_dir=SAVED_MODELS_DIR / "difficulty",
        num_train_epochs=10,
    )
    model_dir = train_task_model(spec)
    print(f"Difficulty model saved to: {model_dir}")


if __name__ == "__main__":
    main()
