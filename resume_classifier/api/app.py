from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import logging

from src.parser import parse_resume
from src.features import extract_features
from src.models import EnsembleClassifier
from src.quiz_generator import get_quiz_generator
from api.schemas import PredictResponse
from utils.config import RAW_DIR

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Lazy initialize classifier on first request
_classifier = None

def get_classifier():
    """Lazy load classifier on first use"""
    global _classifier
    if _classifier is None:
        logger.info("Initializing classifier models...")
        _classifier = EnsembleClassifier()
        logger.info("Classifier initialized successfully")
    return _classifier

ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/predict", methods=["POST"])
def predict():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        
        if not file or file.filename == "":
            return jsonify({"error": "No file selected"}), 400
            
        if not allowed_file(file.filename):
            return jsonify({"error": "Only .pdf and .docx files allowed"}), 400

        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({"error": f"File too large (max {MAX_FILE_SIZE / (1024*1024):.0f}MB)"}), 400

        filename = secure_filename(file.filename)
        save_path = os.path.join(RAW_DIR, filename)
        file.save(save_path)

        try:
            # Pipeline
            parsed = parse_resume(save_path)
            text = parsed["raw_text"]
            
            if not text or len(text.strip()) < 50:
                return jsonify({"error": "Resume text is too short or empty"}), 400
            
            # Extract features with timeout protection
            features = extract_features(text)
            
            # Get classifier and predict
            classifier = get_classifier()
            result = classifier.predict(text)

            response = {
                **result,
                "experience": features.get("total_experience", {}),
                "skills": features.get("skills", []),
                "email": parsed.get("email"),
                "phone": parsed.get("phone")
            }
            return jsonify(response), 200
        finally:
            # Clean up temp file
            try:
                if os.path.exists(save_path):
                    os.remove(save_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup file: {e}")
                
    except ValueError as e:
        return jsonify({"error": f"Invalid file format: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

# ── Quiz Endpoints ────────────────────────────────────────────────────────────

@app.route("/quiz/generate", methods=["POST"])
def generate_quiz():
    """
    Generate a quiz for a specific domain.
    
    Request JSON:
    {
        "domain": "Software Engineering",
        "num_questions": 3
    }
    """
    try:
        data = request.get_json()
        
        if not data or "domain" not in data:
            return jsonify({"error": "Domain is required"}), 400
        
        domain = data.get("domain")
        num_questions = data.get("num_questions", 3)
        
        # Validate num_questions
        if not isinstance(num_questions, int) or num_questions < 1 or num_questions > 10:
            return jsonify({"error": "num_questions must be between 1 and 10"}), 400
        
        quiz_gen = get_quiz_generator()
        quiz = quiz_gen.get_quiz(domain, num_questions)
        
        if "error" in quiz:
            return jsonify(quiz), 400
        
        return jsonify(quiz), 200
    
    except Exception as e:
        logger.error(f"Quiz generation error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route("/quiz/evaluate", methods=["POST"])
def evaluate_quiz():
    """
    Evaluate quiz answers and return scores.
    
    Request JSON:
    {
        "domain": "Software Engineering",
        "answers": [
            {
                "question_id": 1,
                "answer": "REST uses specific endpoints while GraphQL allows querying..."
            },
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        domain = data.get("domain")
        answers = data.get("answers", [])
        
        if not domain:
            return jsonify({"error": "Domain is required"}), 400
        
        if not answers or not isinstance(answers, list):
            return jsonify({"error": "Answers list is required"}), 400
        
        if len(answers) == 0:
            return jsonify({"error": "At least one answer is required"}), 400
        
        quiz_gen = get_quiz_generator()
        result = quiz_gen.evaluate_quiz(domain, answers)
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Quiz evaluation error: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(RAW_DIR, exist_ok=True)
    app.run(debug=False, use_reloader=False, port=5000, threaded=True)