import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Data paths
DATA_DIR        = os.path.join(ROOT_DIR, "data")
RAW_DIR         = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR   = os.path.join(DATA_DIR, "processed")
LABELED_DIR     = os.path.join(DATA_DIR, "labeled")
DOMAINS_FILE    = os.path.join(DATA_DIR, "domains.json")

# Model paths
MODEL_DIR       = os.path.join(ROOT_DIR, "models")
BERT_MODEL_DIR  = os.path.join(ROOT_DIR, "bert_resume_model")

# Model settings
BERT_BASE       = "bert-base-uncased"
SBERT_BASE      = "all-MiniLM-L6-v2"
MAX_LENGTH      = 512

# Ensemble weights (tune after fine-tuning BERT)
ALPHA           = 0.4   # SBERT weight
BETA            = 0.6   # BERT weight

# Experience level thresholds (years)
EXPERIENCE_LEVELS = {
    "Junior": (0, 2),
    "Mid":    (2, 5),
    "Senior": (5, float("inf"))
}

# Domain labels (must match labeled data)
DOMAIN_LABELS = [
    "Software Engineering",
    "Data Science",
    "Finance",
    "Healthcare",
    "Marketing",
    "Law",
    "Education",
    "Mechanical Engineering",
    "Cybersecurity",
    "Product Management"
]