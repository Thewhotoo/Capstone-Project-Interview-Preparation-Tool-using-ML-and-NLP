from __future__ import annotations

import json
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from datasets import Dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATASET_PATH = DATA_DIR / "dataset.json"
SAVED_MODELS_DIR = ROOT_DIR / "model" / "saved_models"
MODEL_NAME = "distilroberta-base"
MAX_LENGTH = 64
SEED = 42


class WeightedTrainer(Trainer):
    def __init__(self, *args, class_weights: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")

        if self.class_weights is not None:
            weights = self.class_weights.to(logits.device)
            loss_fct = torch.nn.CrossEntropyLoss(weight=weights)
        else:
            loss_fct = torch.nn.CrossEntropyLoss()

        loss = loss_fct(logits.view(-1, model.config.num_labels), labels.view(-1))
        if return_outputs:
            return loss, outputs
        return loss


class MultiLabelWeightedTrainer(Trainer):
    def __init__(self, *args, pos_weight: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pos_weight = pos_weight

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")

        if self.pos_weight is not None:
            pos_weight = self.pos_weight.to(logits.device)
            loss_fct = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        else:
            loss_fct = torch.nn.BCEWithLogitsLoss()

        loss = loss_fct(logits, labels.float())
        if return_outputs:
            return loss, outputs
        return loss


@dataclass(frozen=True)
class TaskSpec:
    name: str
    label_key: str | None
    labels: list[str]
    save_dir: Path
    multi_label: bool = False
    num_train_epochs: int = 8


def load_dataset_entries(dataset_path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")
    with dataset_path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, list):
        raise ValueError("Dataset JSON must contain a list of records")
    return data


def ensure_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def save_task_metadata(save_dir: Path, spec: TaskSpec, label2id: dict[str, int]) -> None:
    metadata = {
        "task": spec.name,
        "labels": spec.labels,
        "label2id": label2id,
        "id2label": {str(index): label for label, index in label2id.items()},
        "multi_label": spec.multi_label,
    }
    with (save_dir / "task_metadata.json").open("w", encoding="utf-8") as file_handle:
        json.dump(metadata, file_handle, indent=2)


def load_task_metadata(save_dir: Path) -> dict[str, Any]:
    metadata_path = save_dir / "task_metadata.json"
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)
    return {}


def _tokenize_dataset(dataset: Dataset, tokenizer: AutoTokenizer) -> Dataset:
    columns_to_remove = [column for column in dataset.column_names if column != "labels"]

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(
            batch["text"],
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
        )

    tokenized = dataset.map(tokenize, batched=True, remove_columns=columns_to_remove)
    tokenized.set_format(type="torch")
    return tokenized


def prepare_single_label_splits(entries: list[dict[str, Any]], label_key: str, labels: list[str]) -> tuple[dict[str, Dataset], dict[str, int]]:
    label2id = {label: index for index, label in enumerate(labels)}

    def resolve_label(entry: dict[str, Any]) -> str:
        value = entry[label_key]
        if isinstance(value, list):
            if not value:
                raise ValueError(f"Empty label list for key '{label_key}' in dataset entry: {entry}")
            resolved = value[0]
        else:
            resolved = value
        if not isinstance(resolved, str):
            raise ValueError(f"Label for key '{label_key}' must resolve to a string: {entry}")
        return resolved

    for entry in entries:
        if label_key not in entry:
            raise ValueError(f"Missing key '{label_key}' in dataset entry: {entry}")
        resolved_label = resolve_label(entry)
        if resolved_label not in label2id:
            raise ValueError(f"Unknown label '{resolved_label}' for task labels {labels}")

    train_entries, test_entries = train_test_split(
        entries,
        test_size=0.2,
        random_state=SEED,
        stratify=[resolve_label(entry) for entry in entries],
    )

    train_dataset = Dataset.from_list(train_entries)
    test_dataset = Dataset.from_list(test_entries)

    def encode_label(example: dict[str, Any]) -> dict[str, Any]:
        resolved_label = example[label_key][0] if isinstance(example[label_key], list) else example[label_key]
        return {"labels": label2id[resolved_label]}

    encoded_train = train_dataset.map(encode_label)
    encoded_test = test_dataset.map(encode_label)
    return {"train": encoded_train, "test": encoded_test}, label2id


def prepare_multi_label_splits(entries: list[dict[str, Any]], labels: list[str]) -> tuple[dict[str, Dataset], dict[str, int]]:
    label2id = {label: index for index, label in enumerate(labels)}
    for entry in entries:
        if "topics" not in entry:
            raise ValueError(f"Missing key 'topics' in dataset entry: {entry}")
        unknown_labels = [label for label in entry["topics"] if label not in label2id]
        if unknown_labels:
            raise ValueError(f"Unknown topic labels {unknown_labels} for task labels {labels}")

    dataset = Dataset.from_list(entries)

    def encode_labels(example: dict[str, Any]) -> dict[str, Any]:
        encoded = [0.0] * len(labels)
        for label in example["topics"]:
            encoded[label2id[label]] = 1.0
        return {"labels": encoded}

    encoded = dataset.map(encode_labels)
    split = encoded.train_test_split(test_size=0.2, seed=SEED)
    return {"train": split["train"], "test": split["test"]}, label2id


def _single_label_metrics(prediction_output) -> dict[str, float]:
    predictions = np.argmax(prediction_output.predictions, axis=-1)
    references = prediction_output.label_ids
    return {
        "accuracy": float(accuracy_score(references, predictions)),
        "f1": float(f1_score(references, predictions, average="macro")),
    }


def _multi_label_metrics(prediction_output) -> dict[str, float]:
    logits = prediction_output.predictions
    references = np.array(prediction_output.label_ids)
    probabilities = 1 / (1 + np.exp(-logits))
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        references,
        predictions,
        average="micro",
        zero_division=0,
    )
    exact_match = float(np.all(predictions == references, axis=1).mean())
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "exact_match": exact_match,
    }


def train_task_model(spec: TaskSpec, dataset_path: Path = DATASET_PATH) -> Path:
    entries = load_dataset_entries(dataset_path)
    ensure_directory(spec.save_dir)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    if spec.multi_label:
        splits, label2id = prepare_multi_label_splits(entries, spec.labels)
    else:
        if spec.label_key is None:
            raise ValueError(f"label_key is required for task {spec.name}")
        splits, label2id = prepare_single_label_splits(entries, spec.label_key, spec.labels)

    tokenized_splits = {
        split_name: _tokenize_dataset(split_dataset, tokenizer)
        for split_name, split_dataset in splits.items()
    }

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(spec.labels),
        id2label={index: label for label, index in label2id.items()},
        label2id=label2id,
        ignore_mismatched_sizes=True,
    )
    if spec.multi_label:
        model.config.problem_type = "multi_label_classification"

    training_kwargs: dict[str, Any] = {
        "output_dir": str(spec.save_dir),
        "num_train_epochs": spec.num_train_epochs,
        "per_device_train_batch_size": 8,
        "per_device_eval_batch_size": 8,
        "learning_rate": 2e-5,
        "weight_decay": 0.01,
        "warmup_ratio": 0.1,
        "lr_scheduler_type": "linear",
        "save_strategy": "epoch",
        "logging_strategy": "epoch",
        "logging_steps": 10,
        "load_best_model_at_end": True,
        "metric_for_best_model": "f1" if spec.multi_label else "accuracy",
        "greater_is_better": True,
        "do_train": True,
        "do_eval": True,
        "seed": SEED,
        "save_total_limit": 1,
        "report_to": [],
        "fp16": torch.cuda.is_available(),
    }

    if "evaluation_strategy" in TrainingArguments.__init__.__code__.co_varnames:
        training_kwargs["evaluation_strategy"] = "epoch"
    else:
        training_kwargs["eval_strategy"] = "epoch"

    training_args = TrainingArguments(**training_kwargs)

    class_weights: torch.Tensor | None = None
    if not spec.multi_label:
        train_labels = np.array(splits["train"]["labels"], dtype=np.int64)
        class_counts = np.bincount(train_labels, minlength=len(spec.labels)).astype(np.float32)
        class_counts[class_counts == 0.0] = 1.0
        total = float(class_counts.sum())
        weights = total / (len(spec.labels) * class_counts)
        class_weights = torch.tensor(weights, dtype=torch.float)

    if spec.multi_label:
        train_labels = np.array(splits["train"]["labels"], dtype=np.float32)
        positives = train_labels.sum(axis=0)
        negatives = train_labels.shape[0] - positives
        positives = np.maximum(positives, 1.0)
        pos_weight = torch.tensor(negatives / positives, dtype=torch.float)

        trainer = MultiLabelWeightedTrainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_splits["train"],
            eval_dataset=tokenized_splits["test"],
            compute_metrics=_multi_label_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
            pos_weight=pos_weight,
        )
    else:
        trainer = WeightedTrainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_splits["train"],
            eval_dataset=tokenized_splits["test"],
            compute_metrics=_single_label_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
            class_weights=class_weights,
        )

    trainer.train()
    trainer.save_model(str(spec.save_dir))
    tokenizer.save_pretrained(str(spec.save_dir))
    save_task_metadata(spec.save_dir, spec, label2id)
    return spec.save_dir


@lru_cache(maxsize=4)
def _load_model_and_tokenizer(model_dir: Path) -> tuple[AutoTokenizer, AutoModelForSequenceClassification, dict[str, Any]]:
    if not model_dir.exists():
        raise FileNotFoundError(f"Saved model directory not found: {model_dir}")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    metadata = load_task_metadata(model_dir)
    return tokenizer, model, metadata


def predict_single_label(text: str, model_dir: Path) -> dict[str, Any]:
    tokenizer, model, metadata = _load_model_and_tokenizer(model_dir)
    model.eval()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
    )
    with torch.no_grad():
        outputs = model(**inputs)
        probabilities = torch.softmax(outputs.logits, dim=-1)[0]
    id2label = metadata.get("id2label") or {str(index): label for index, label in model.config.id2label.items()}
    ordered_scores = {
        id2label[str(index)]: float(probability.item())
        for index, probability in enumerate(probabilities)
    }

    lowered_text = text.lower()

    # Difficulty calibration — two-tier system based on signal strength.
    #
    # Tier 1 — STRONG: sentence prefix is structurally unambiguous.
    #   "What is/are..." or "Define..." → always easy regardless of topics mentioned.
    #   "Design/Implement/Build/Optimize..." → always hard regardless of topics.
    #   These override even a confident model (boost = 0.55).
    #
    # Tier 2 — MODERATE: prefix is a soft signal (explain, compare, how would, why).
    #   Boost is adaptive: higher when model is uncertain, lower when confident.
    #
    # Key insight: difficulty is determined by the TYPE of answer expected, not the
    # number of topics. "What is tree traversal and sorting?" is still easy because
    # two definition questions together are still definitional.
    if model_dir.name == "difficulty" and {"easy", "medium", "hard"}.issubset(set(ordered_scores.keys())):
        stripped = lowered_text.strip()

        # Detect structural tier and target label directly from sentence prefix.
        STRONG_EASY_PREFIXES = ("what is ", "what are ", "define ", "what do ", "what does ")
        STRONG_HARD_PREFIXES = ("design ", "implement ", "build ", "derive ", "prove ", "optimize ")

        is_strong_easy = any(stripped.startswith(p) for p in STRONG_EASY_PREFIXES)
        is_strong_hard = any(stripped.startswith(p) for p in STRONG_HARD_PREFIXES)

        # Edge case: "What is the difference between X and Y?" looks like easy but is comparison → medium.
        is_comparison_disguised = is_strong_easy and (
            "difference between" in stripped or " vs " in stripped
        )

        if is_comparison_disguised:
            rule_label, boost = "medium", 0.40
        elif is_strong_easy:
            rule_label, boost = "easy", 0.55   # Strong: override even confident model
        elif is_strong_hard:
            rule_label, boost = "hard", 0.55   # Strong: override even confident model
        else:
            # Moderate tier: use rule_based() for explain/compare/how would/why patterns.
            from inference.rule_based import get_difficulty as _rule_difficulty
            rule_label = _rule_difficulty(text)
            model_top_conf_temp = max(ordered_scores.values())
            boost = max(0.20, 0.55 - model_top_conf_temp)   # Adaptive: weaker when model is sure

        model_top_label = max(ordered_scores, key=lambda k: ordered_scores[k])
        model_top_conf = ordered_scores[model_top_label]

        # Apply calibration when model disagrees OR model is uncertain (< 0.70).
        if (model_top_label != rule_label or model_top_conf < 0.70) and rule_label in ordered_scores:
            ordered_scores[rule_label] = min(1.0, ordered_scores[rule_label] + boost)
            for other_label in ordered_scores:
                if other_label != rule_label:
                    ordered_scores[other_label] = max(0.0, ordered_scores[other_label] - boost / 2)
            total = sum(ordered_scores.values())
            if total > 0:
                ordered_scores = {label: score / total for label, score in ordered_scores.items()}

    # Intent calibration: use unambiguous grammatical patterns to correct the model.
    if model_dir.name == "intent" and {
        "definition", "explanation", "comparison", "procedure", "reasoning"
    }.issubset(set(ordered_scores.keys())):
        # Map each deterministic rule pattern to its correct intent label.
        rule_intent: str | None = None
        if lowered_text.startswith(("how would", "how to", "implement", "design", "write", "describe how")):
            rule_intent = "procedure"
        elif lowered_text.startswith(("what is", "what are", "define", "what do")):
            rule_intent = "definition"
        elif lowered_text.startswith("why"):
            rule_intent = "reasoning"
        elif lowered_text.startswith("explain") or "how does" in lowered_text or "how do" in lowered_text:
            rule_intent = "explanation"
        elif (
            lowered_text.startswith("compare")
            or lowered_text.startswith("difference")
            or "difference between" in lowered_text
            or "compare " in lowered_text
        ):
            rule_intent = "comparison"

        if rule_intent is not None and rule_intent in ordered_scores:
            current_model_top = max(ordered_scores.values())
            # Apply a strong nudge when the model is wrong or uncertain (confidence < 0.60).
            if ordered_scores[rule_intent] < current_model_top or current_model_top < 0.60:
                boost = 0.45
                ordered_scores[rule_intent] = min(1.0, ordered_scores[rule_intent] + boost)
                # Suppress all other labels proportionally.
                for other_label in ordered_scores:
                    if other_label != rule_intent:
                        ordered_scores[other_label] = max(0.0, ordered_scores[other_label] - boost / 4)
                total = sum(ordered_scores.values())
                if total > 0:
                    ordered_scores = {label: score / total for label, score in ordered_scores.items()}

    predicted_label = max(ordered_scores.items(), key=lambda item: item[1])[0]
    return {
        "label": predicted_label,
        "confidence": float(ordered_scores[predicted_label]),
        "scores": ordered_scores,
    }


def predict_multi_label(text: str, model_dir: Path, threshold: float = 0.5) -> dict[str, Any]:
    tokenizer, model, metadata = _load_model_and_tokenizer(model_dir)
    model.eval()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
    )
    with torch.no_grad():
        outputs = model(**inputs)
        probabilities = torch.sigmoid(outputs.logits)[0].cpu().numpy()

    id2label = metadata.get("id2label") or {str(index): label for index, label in model.config.id2label.items()}
    ordered_scores = {id2label[str(index)]: float(score) for index, score in enumerate(probabilities)}

    # Lightweight calibration for common DBMS/OOP vs DSA confusion.
    lowered_text = text.lower()
    dbms_keywords = {
        "dbms",
        "database management",
        "database",
        "databases",
        "relational",
        "sql",
        "schema",
        "schemas",
        "table",
        "tables",
        "normalization",
        "foreign key",
        "primary key",
        "transaction",
        "transactions",
        "orm",
        "entity",
        "entities",
        "column",
        "columns",
    }
    dsa_keywords = {
        "dsa",
        "data structure",
        "data structures",
        "array",
        "arrays",
        "hash",
        "hashing",
        "hash map",
        "hashmap",
        "hash table",
        "linked list",
        "stack",
        "queue",
        "tree",
        "trees",
        "graph",
        "graphs",
        "sorting",
        "sort",
        "traversal",
        "traversals",
        "recursion",
        "heap",
        "binary search",
        "complexity",
        "dynamic programming",
        "dp",
        "greedy",
        "backtracking",
        "memoization",
        "bfs",
        "dfs",
        "dijkstra",
        "trie",
        "priority queue",
        "big o",
        "amortized",
        "sliding window",
        "two pointer",
        "divide and conquer",
        "algorithm",
        "algorithms",
    }
    oop_keywords = {
        "oop",
        "object oriented",
        "class",
        "object",
        "inheritance",
        "polymorphism",
        "polymorjpis",
        "polymor",
        "encapsulation",
        "abstraction",
        "interface",
        "constructor",
        "method",
        "overloading",
        "overriding",
        "solid",
    }
    os_keywords = {
        "os",
        "operating system",
        "process",
        "thread",
        "deadlock",
        "starvation",
        "semaphore",
        "scheduling",
        "paging",
        "critical section",
        "kernel",
        "context switch",
        "context switching",
    }
    has_dbms_signal = any(keyword in lowered_text for keyword in dbms_keywords)
    has_dsa_signal = any(keyword in lowered_text for keyword in dsa_keywords)
    has_oop_signal = any(keyword in lowered_text for keyword in oop_keywords)
    has_os_signal = any(keyword in lowered_text for keyword in os_keywords)

    # Keep pure DSA prompts from leaking into OOP.
    if has_dsa_signal and not has_oop_signal and "DSA" in ordered_scores:
        ordered_scores["DSA"] = min(1.0, ordered_scores["DSA"] + 0.12)
        if "OOP" in ordered_scores:
            ordered_scores["OOP"] = max(0.0, ordered_scores["OOP"] - 0.22)

    # For hashing-style prompts without DBMS terms, prefer DSA over DBMS.
    if "hash" in lowered_text and not has_dbms_signal:
        if "DSA" in ordered_scores:
            ordered_scores["DSA"] = min(1.0, ordered_scores["DSA"] + 0.10)
        if "DBMS" in ordered_scores:
            ordered_scores["DBMS"] = max(0.0, ordered_scores["DBMS"] - 0.18)

    # Keep pure OOP prompts from leaking into DSA.
    if has_oop_signal and not has_dsa_signal and "OOP" in ordered_scores:
        ordered_scores["OOP"] = min(1.0, ordered_scores["OOP"] + 0.12)
        if "DSA" in ordered_scores:
            ordered_scores["DSA"] = max(0.0, ordered_scores["DSA"] - 0.22)

    # If both DSA and OOP concepts are explicitly present, strengthen both.
    if has_dsa_signal and has_oop_signal:
        if "DSA" in ordered_scores:
            ordered_scores["DSA"] = min(1.0, ordered_scores["DSA"] + 0.14)
        if "OOP" in ordered_scores:
            ordered_scores["OOP"] = min(1.0, ordered_scores["OOP"] + 0.14)

    # Keep pure DBMS prompts from leaking into OS.
    if has_dbms_signal and not has_os_signal and "DBMS" in ordered_scores:
        ordered_scores["DBMS"] = min(1.0, ordered_scores["DBMS"] + 0.12)
        if "OS" in ordered_scores:
            ordered_scores["OS"] = max(0.0, ordered_scores["OS"] - 0.22)

    if has_dbms_signal and not has_dsa_signal:
        if "DBMS" in ordered_scores:
            ordered_scores["DBMS"] = min(1.0, ordered_scores["DBMS"] + 0.20)
        if "DSA" in ordered_scores:
            ordered_scores["DSA"] = max(0.0, ordered_scores["DSA"] - 0.30)

    # Strong Topic Calibration: If rule_based directly caught the acronym/keyword, give it a massive boost.
    from inference.rule_based import get_topic_labels as _rule_topics
    rule_topics = _rule_topics(text)
    if "General" not in rule_topics:
        for rt in rule_topics:
            if rt in ordered_scores:
                ordered_scores[rt] = min(1.0, ordered_scores[rt] + 0.6)
        for other in ordered_scores:
            if other not in rule_topics:
                ordered_scores[other] = max(0.0, ordered_scores[other] - 0.4)

    selected_labels = [label for label, score in ordered_scores.items() if score >= threshold]

    if has_dsa_signal and has_oop_signal:
        for label in ("DSA", "OOP"):
            if label in ordered_scores and label not in selected_labels:
                selected_labels.append(label)

    if not selected_labels:
        top_label = max(ordered_scores.items(), key=lambda item: item[1])[0]
        selected_labels = [top_label]
    return {
        "labels": selected_labels,
        "scores": ordered_scores,
    }
