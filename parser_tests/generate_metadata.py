"""
Generate metadata for every resume in parser_tests/resumes/.
Uses pdfplumber for layout heuristics. Does NOT touch the parser.
"""

import os
import sys
import json
import re

FRAMEWORK_DIR = os.path.dirname(os.path.abspath(__file__))
RESUMES_DIR   = os.path.join(FRAMEWORK_DIR, "resumes")
METADATA_DIR  = os.path.join(FRAMEWORK_DIR, "metadata")

CLASSIFIER_DIR = os.path.join(FRAMEWORK_DIR, "..", "resume_classifier")
if CLASSIFIER_DIR not in sys.path:
    sys.path.insert(0, CLASSIFIER_DIR)


def _detect_two_columns(page) -> bool:
    """Heuristic: if text clusters into two distinct horizontal bands, it is two-column."""
    words = page.extract_words() or []
    if len(words) < 20:
        return False
    x_positions = [w["x0"] for w in words]
    mid = page.width / 2
    left  = sum(1 for x in x_positions if x < mid)
    right = sum(1 for x in x_positions if x >= mid)
    total = len(x_positions)
    if total < 20:
        return False
    # Both sides must have at least 15% of words
    return (left / total > 0.15) and (right / total > 0.15)


def _detect_tables(page) -> bool:
    """Check if page contains table structures."""
    tables = page.find_tables()
    return len(tables) > 0


def _detect_graphics(page) -> bool:
    """Heuristic: large number of non-text drawing operations suggests graphics/charts."""
    # pdfplumber pages have .objects; check for rects/curves that are large
    graphics_count = 0
    for obj_type in ["rect", "curve", "line"]:
        objs = page.objects.get(obj_type, [])
        graphics_count += len(objs)
    # A few small lines/borders are normal; many rects = likely graphics
    return graphics_count > 15


def _detect_ats_friendly(text: str) -> bool:
    """ATS-friendly resumes are typically plain text with clear section headers and no complex layout."""
    has_sections = bool(re.search(
        r'(?:EXPERIENCE|EDUCATION|SKILLS|PROJECTS|CERTIFICATIONS|SUMMARY|OBJECTIVE)',
        text, re.IGNORECASE
    ))
    # Check text density (ATS resumes tend to have good text-per-page ratio)
    word_count = len(text.split())
    has_enough_text = word_count > 80
    return has_sections and has_enough_text


def _estimate_domain(text: str) -> str:
    """Very rough domain estimation based on keyword frequency."""
    text_lower = text.lower()
    domain_signals = {
        "Software Engineering": [
            "software", "developer", "engineer", "programming", "python", "java",
            "javascript", "react", "docker", "kubernetes", "api", "backend",
            "frontend", "full stack", "microservices", "devops", "git",
        ],
        "Data Science": [
            "data scientist", "machine learning", "deep learning", "neural network",
            "tensorflow", "pytorch", "nlp", "data analysis", "model", "dataset",
            "pandas", "scikit-learn", "statistics",
        ],
        "Healthcare": [
            "clinical", "patient", "medical", "healthcare", "hospital",
            "nursing", "pharmaceutical", "diagnosis", "treatment",
        ],
        "Finance": [
            "financial", "accounting", "investment", "banking", "portfolio",
            "risk management", "audit", "compliance", "trading",
        ],
        "Cybersecurity": [
            "cybersecurity", "information security", "penetration testing",
            "vulnerability", "firewall", "siem", "incident response",
        ],
        "Education": [
            "teacher", "curriculum", "pedagogy", "student", "lecture",
            "academic", "professor", "education",
        ],
        "Marketing": [
            "marketing", "seo", "social media", "brand", "campaign",
            "content strategy", "analytics", "advertising",
        ],
    }
    scores = {}
    for domain, keywords in domain_signals.items():
        scores[domain] = sum(1 for kw in keywords if kw in text_lower)
    if max(scores.values()) == 0:
        return "Unknown"
    return max(scores, key=scores.get)


def _estimate_experience_level(text: str) -> str:
    """Rough experience level from year spans in the text."""
    years = [int(y) for y in re.findall(r'(20[12]\d)', text)]
    if len(years) < 2:
        # Check for "fresher" / "entry level" signals
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["fresher", "entry level", "recent graduate", "final year"]):
            return "Junior"
        return "Unknown"
    span = max(years) - min(years)
    if span < 2:
        return "Junior"
    elif span < 5:
        return "Mid"
    else:
        return "Senior"


def _classify_layout(page_count: int, two_column: bool, text_length: int) -> str:
    """Classify overall resume layout."""
    if two_column:
        return "two-column"
    if page_count == 1 and text_length < 2000:
        return "single-column-compact"
    if page_count == 1:
        return "single-column"
    if page_count == 2:
        return "multi-page"
    return "multi-page"


def generate_metadata(resume_path: str, resume_id: str, original_filename: str) -> dict:
    """Generate metadata for a single resume."""
    import pdfplumber

    meta = {
        "id": resume_id,
        "original_filename": original_filename,
        "layout": "unknown",
        "pages": 0,
        "estimated_domain": "Unknown",
        "estimated_experience_level": "Unknown",
        "contains_tables": False,
        "contains_two_columns": False,
        "contains_graphics": False,
        "ats_friendly": False,
    }

    try:
        with pdfplumber.open(resume_path) as pdf:
            meta["pages"] = len(pdf.pages)

            all_text = ""
            any_two_col = False
            any_tables = False
            any_graphics = False

            for page in pdf.pages:
                page_text = page.extract_text() or ""
                all_text += page_text + "\n"

                if _detect_two_columns(page):
                    any_two_col = True
                if _detect_tables(page):
                    any_tables = True
                if _detect_graphics(page):
                    any_graphics = True

            meta["contains_two_columns"] = any_two_col
            meta["contains_tables"] = any_tables
            meta["contains_graphics"] = any_graphics
            meta["ats_friendly"] = _detect_ats_friendly(all_text)
            meta["estimated_domain"] = _estimate_domain(all_text)
            meta["estimated_experience_level"] = _estimate_experience_level(all_text)
            meta["layout"] = _classify_layout(
                meta["pages"], any_two_col, len(all_text)
            )

    except Exception as e:
        meta["error"] = str(e)

    return meta


def main():
    os.makedirs(METADATA_DIR, exist_ok=True)

    resumes = sorted([
        f for f in os.listdir(RESUMES_DIR)
        if f.endswith(".pdf")
    ])

    print(f"Generating metadata for {len(resumes)} resumes...\n")

    all_metadata = []
    for filename in resumes:
        resume_id = filename.replace(".pdf", "")
        resume_path = os.path.join(RESUMES_DIR, filename)

        # Find original filename from the copy mapping (we stored it at copy time)
        # Reconstruct from the naming convention we used
        original_map = {
            "001": "MayuranResume.pdf",
            "002": "resume1.pdf",
            "003": "resume2.pdf",
            "004": "resume3.pdf",
            "005": "resume4.pdf",
            "006": "resume5.pdf",
            "007": "resume6.pdf",
            "008": "resume7.pdf",
            "009": "resume8.pdf",
            "010": "Shubham-Mookim-Resume.pdf",
        }
        original = original_map.get(resume_id, filename)

        meta = generate_metadata(resume_path, resume_id, original)
        all_metadata.append(meta)

        # Save individual metadata
        meta_path = os.path.join(METADATA_DIR, f"{resume_id}.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        print(f"  {resume_id}: {original:<30} pages={meta['pages']}  "
              f"layout={meta['layout']:<25} domain={meta['estimated_domain']}")

    # Save combined mapping
    mapping_path = os.path.join(METADATA_DIR, "file_mapping.json")
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(all_metadata, f, indent=2)

    print(f"\nMetadata saved to {METADATA_DIR}")
    print(f"Mapping saved to {mapping_path}")

    # Summary
    layouts = {}
    domains = {}
    for m in all_metadata:
        layouts[m["layout"]] = layouts.get(m["layout"], 0) + 1
        domains[m["estimated_domain"]] = domains.get(m["estimated_domain"], 0) + 1

    print(f"\nLayout distribution:")
    for k, v in sorted(layouts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"\nEstimated domain distribution:")
    for k, v in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
