import torch
from torch.utils.data import Dataset, DataLoader
from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from utils.config import BERT_BASE, BERT_MODEL_DIR, MAX_LENGTH, DOMAIN_LABELS
from utils.helpers import load_json
import numpy as np
import os

# ── Dataset ───────────────────────────────────────────────────────────────────

class ResumeDataset(Dataset):
    def __init__(self, texts, labels, tokenizer):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=MAX_LENGTH,
            return_tensors="pt"
        )
        self.labels = torch.tensor(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            **{k: v[idx] for k, v in self.encodings.items()},
            "labels": self.labels[idx]
        }

# ── Training ──────────────────────────────────────────────────────────────────

def train(data_path: str):
    data      = load_json(data_path)
    texts     = [d["text"] for d in data]
    labels    = [DOMAIN_LABELS.index(d["label"]) for d in data]

    tokenizer = BertTokenizer.from_pretrained(BERT_BASE)
    model     = BertForSequenceClassification.from_pretrained(
        BERT_BASE, num_labels=len(DOMAIN_LABELS)
    )

    X_train, X_val, y_train, y_val = train_test_split(
        texts, labels, test_size=0.2, random_state=42
    )

    train_dataset = ResumeDataset(X_train, y_train, tokenizer)
    val_dataset   = ResumeDataset(X_val,   y_val,   tokenizer)

    args = TrainingArguments(
        output_dir=BERT_MODEL_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_dir="./logs"
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset
    )

    trainer.train()
    trainer.save_model(BERT_MODEL_DIR)
    tokenizer.save_pretrained(BERT_MODEL_DIR)
    print(f"Model saved to {BERT_MODEL_DIR}")

# ── Evaluate ──────────────────────────────────────────────────────────────────

def evaluate(data_path: str):
    from src.models import BERTClassifier
    clf  = BERTClassifier()
    data = load_json(data_path)

    preds, truths = [], []
    for d in data:
        result = clf.predict(d["text"])
        preds.append(max(result, key=result.get))
        truths.append(d["label"])

    print(classification_report(truths, preds, target_names=DOMAIN_LABELS))

if __name__ == "__main__":
    train("data/labeled/labeled_resumes.json")