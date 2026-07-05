import argparse
import json
from src.parser import parse_resume
from src.features import extract_features
from src.models import EnsembleClassifier

def run(path: str):
    print(f"\nParsing: {path}")
    parsed   = parse_resume(path)
    text     = parsed["raw_text"]
    features = extract_features(text)
    result   = EnsembleClassifier().predict(text)

    output = {
        **result,
        "total_experience": features["total_experience"],
        "job_experiences": features["job_experiences"],
        "skills":          features["skills"],
        "email":           parsed.get("email"),
        "phone":           parsed.get("phone")
    }

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Classifier CLI")
    parser.add_argument("file", help="Path to resume (.pdf or .docx)")
    args = parser.parse_args()
    try:
        run(args.file)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()