from __future__ import annotations

from pathlib import Path
import sys


CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from model.multitask_utils import SAVED_MODELS_DIR, TaskSpec, train_task_model


TOPIC_LABELS = ["OS", "DBMS", "CN", "OOP", "DSA"]


def main() -> None:
    spec = TaskSpec(
        name="topic",
        label_key=None,
        labels=TOPIC_LABELS,
        save_dir=SAVED_MODELS_DIR / "topic",
        multi_label=True,
        num_train_epochs=8,
    )
    model_dir = train_task_model(spec)
    print(f"Topic model saved to: {model_dir}")


if __name__ == "__main__":
    main()
