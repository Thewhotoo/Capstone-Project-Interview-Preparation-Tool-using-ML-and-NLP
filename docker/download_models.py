"""Download every Hugging Face model the app uses into the image (HF_HOME), at
build time, the same way the app loads them, so only the files the app reads
are fetched.

Keep in step with model_warmup.REQUIRED_MODELS and TRAINED_BACKBONE. If one is
missing, the app still works: it downloads the model on first use (and logs
"Models not downloaded yet") when the container has internet.
"""

from faster_whisper.utils import download_model
from sentence_transformers import CrossEncoder, SentenceTransformer
from transformers import AutoModel, AutoTokenizer

SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")   # Round 1 evaluator, resume parsing, tech grader
CrossEncoder("cross-encoder/nli-MiniLM2-L6-H768")               # Round 1 evaluator
CrossEncoder("cross-encoder/nli-deberta-v3-base")               # technical grader

# The trained Round 1 evaluator's backbone. Downloaded even though the weights
# are mounted at run time, so adding them later needs no rebuild.
AutoTokenizer.from_pretrained("microsoft/deberta-v3-base")
AutoModel.from_pretrained("microsoft/deberta-v3-base")

# Voice answers (speech_to_text.py, CAP_WHISPER_MODEL): Systran/faster-whisper-base.en.
download_model("base.en")

print("models downloaded")
