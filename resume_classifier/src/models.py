import os
import torch
from utils.config import (
    SBERT_BASE, BERT_BASE, BERT_MODEL_DIR,
    MAX_LENGTH, ALPHA, BETA, DOMAIN_LABELS, DOMAINS_FILE
)
from utils.helpers import load_json, truncate_text

# ── Device Detection ──────────────────────────────────────────────────────────

def get_device():
    """Automatically detect best device (GPU if available, else CPU)"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    return device

DEVICE = get_device()

# ── Lazy-loaded global instances ──────────────────────────────────────────────

_sbert_instance = None
_bert_instance = None

def get_sbert():
    """Lazy load SBERT model on first use"""
    global _sbert_instance
    if _sbert_instance is None:
        _sbert_instance = SBERTMatcher()
    return _sbert_instance

def get_bert():
    """Lazy load BERT model on first use"""
    global _bert_instance
    if _bert_instance is None:
        _bert_instance = BERTClassifier()
    return _bert_instance

# ── SBERT Model ───────────────────────────────────────────────────────────────

class SBERTMatcher:
    def __init__(self):
        # Lazy import sentence_transformers to avoid slow startup
        from sentence_transformers import SentenceTransformer, util
        
        self.model = SentenceTransformer(SBERT_BASE, device=DEVICE)
        self.model.eval()
        domain_descriptions = load_json(DOMAINS_FILE)
        self.domains = list(domain_descriptions.keys())
        
        with torch.no_grad():
            self.domain_embeddings = self.model.encode(
                list(domain_descriptions.values()),
                convert_to_tensor=True,
                device=DEVICE
            )
        self.util = util

    def predict(self, text: str) -> dict:
        with torch.no_grad():
            emb = self.model.encode(truncate_text(text), convert_to_tensor=True, device=DEVICE)
            scores = self.util.cos_sim(emb, self.domain_embeddings)[0]
        return {domain: float(scores[i]) for i, domain in enumerate(self.domains)}


# ── BERT Classifier ───────────────────────────────────────────────────────────

class BERTClassifier:
    def __init__(self, model_path: str = None):
        # Lazy import transformers to avoid slow startup
        from transformers import BertTokenizer, BertForSequenceClassification
        
        path = model_path or BERT_MODEL_DIR
        
        # Always try local path first, regardless of GPU
        load_path = path if os.path.exists(path) else BERT_BASE
        
        self.tokenizer = BertTokenizer.from_pretrained(load_path)
        self.model = BertForSequenceClassification.from_pretrained(
            load_path,
            num_labels=len(DOMAIN_LABELS)
        )
        self.model = self.model.to(DEVICE)
        self.model.eval()
        self.labels = DOMAIN_LABELS

    def predict(self, text: str) -> dict:
        """Predict domain for given text with inference optimization"""
        truncated = truncate_text(text)
        inputs = self.tokenizer(truncated, return_tensors="pt", truncation=True, max_length=MAX_LENGTH)
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits[0]
        
        scores = torch.softmax(logits, dim=-1)
        return {label: float(scores[i]) for i, label in enumerate(self.labels)}

# ── Ensemble ──────────────────────────────────────────────────────────────────

class EnsembleClassifier:
    def __init__(self, alpha: float = ALPHA, beta: float = BETA):
        self.alpha = alpha
        self.beta = beta

    def predict(self, text: str) -> dict:
        try:
            sbert_scores = get_sbert().predict(text)
            bert_scores = get_bert().predict(text)

            domains = set(sbert_scores) & set(bert_scores)
            final = {
                d: round((self.alpha * sbert_scores[d]) + (self.beta * bert_scores[d]), 4)
                for d in domains
            }
            top_domain = max(final, key=final.get)
            return {
                "predicted_domain": top_domain,
                "confidence":       final[top_domain],
                "all_scores":       dict(sorted(final.items(), key=lambda x: -x[1]))
            }
        except Exception as e:
            return {
                "predicted_domain": "Unknown",
                "confidence": 0.0,
                "all_scores": {d: 0.0 for d in DOMAIN_LABELS},
                "error": str(e)
            }