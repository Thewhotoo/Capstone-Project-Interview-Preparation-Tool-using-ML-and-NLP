"""
Run the CURRENT parser on every resume and store baseline outputs.
Also serves as the evaluation engine: compares against ground_truth when available.
Generates reports/ at the end.

Usage:
    python evaluate_parser.py                  # full benchmark
    python evaluate_parser.py --resume 001     # single resume
    python evaluate_parser.py --verbose        # detailed output
"""

import sys
import os
import json
import re
import glob
import argparse
import traceback
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────

FRAMEWORK_DIR = os.path.dirname(os.path.abspath(__file__))
RESUMES_DIR   = os.path.join(FRAMEWORK_DIR, "resumes")
BASELINE_DIR  = os.path.join(FRAMEWORK_DIR, "baseline")
GROUND_TRUTH_DIR = os.path.join(FRAMEWORK_DIR, "ground_truth")
METADATA_DIR  = os.path.join(FRAMEWORK_DIR, "metadata")
REPORTS_DIR   = os.path.join(FRAMEWORK_DIR, "reports")

CLASSIFIER_DIR = os.path.abspath(os.path.join(FRAMEWORK_DIR, "..", "resume_classifier"))
if CLASSIFIER_DIR not in sys.path:
    sys.path.insert(0, CLASSIFIER_DIR)


# ── Scoring Helpers ──────────────────────────────────────────────────────────

def _normalise_phone(phone):
    if not phone:
        return ""
    return re.sub(r'[\s\-\(\)\.]+', '', str(phone))


def _score_name(actual, expected):
    if not actual or not expected:
        return 0.0
    a, e = str(actual).strip().lower(), str(expected).strip().lower()
    if a == e:
        return 1.0
    if e in a or a in e:
        return 0.75
    a_words, e_words = set(a.split()), set(e.split())
    if not e_words:
        return 0.0
    overlap = len(a_words & e_words) / len(e_words)
    return round(0.5 + 0.25 * overlap, 2) if overlap >= 0.5 else 0.0


def _score_exact(actual, expected):
    if actual is None and expected is None:
        return 1.0
    if actual is None or expected is None:
        return 0.0
    return 1.0 if str(actual).strip().lower() == str(expected).strip().lower() else 0.0


def _score_domain(actual, expected):
    if not actual or not expected:
        return 0.0
    a, e = str(actual).strip().lower(), str(expected).strip().lower()
    if a == e:
        return 1.0
    if e in a or a in e:
        return 0.75
    return 0.0


def _score_experience_years(actual, expected):
    diff = abs(int(actual or 0) - int(expected or 0))
    if diff == 0:
        return 1.0
    if diff <= 1:
        return 0.5
    return 0.0


def _score_education(actual_edus, expected_edus):
    if not expected_edus:
        return 1.0
    if not actual_edus:
        return 0.0
    scores = []
    for i, exp in enumerate(expected_edus):
        if i >= len(actual_edus):
            scores.append(0.0)
            continue
        act = actual_edus[i]
        entry_scores = []
        for key in ["institution_contains", "degree_contains", "major_contains"]:
            if key in exp:
                field_name = key.replace("_contains", "")
                val = (act.get(field_name) or "").lower()
                matches = all(kw.lower() in val for kw in exp[key])
                entry_scores.append(1.0 if matches else 0.0)
        if "graduation_year" in exp:
            entry_scores.append(1.0 if act.get("graduation_year") == exp["graduation_year"] else 0.0)
        if "graduation_year_min" in exp and "graduation_year_max" in exp:
            gy = act.get("graduation_year")
            entry_scores.append(1.0 if gy and exp["graduation_year_min"] <= gy <= exp["graduation_year_max"] else 0.0)
        scores.append(sum(entry_scores) / len(entry_scores) if entry_scores else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _score_skills(actual_skills, must_include, must_not_include):
    actual_lower = {s.lower() for s in (actual_skills or [])}
    if must_include:
        found = sum(1 for s in must_include if s.lower() in actual_lower)
        recall = found / len(must_include)
    else:
        recall = 1.0
    if must_not_include:
        false_pos = sum(1 for s in must_not_include if s.lower() in actual_lower)
        penalty = min(1.0, false_pos * 0.25)
    else:
        penalty = 0.0
    return max(0.0, recall - penalty)


def _score_projects(actual, min_c, max_c):
    if actual is None:
        return 0.0
    if min_c <= actual <= max_c:
        return 1.0
    if abs(actual - min_c) <= 2 or abs(actual - max_c) <= 2:
        return 0.5
    return 0.0


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class FieldResult:
    name: str
    score: float
    expected: Any = None
    actual: Any = None
    detail: str = ""


@dataclass
class ResumeResult:
    resume_id: str
    filename: str
    fields: list = field(default_factory=list)
    overall_score: float = 0.0
    parse_error: str = ""
    has_ground_truth: bool = False

    def compute_overall(self):
        if self.fields:
            self.overall_score = round(sum(f.score for f in self.fields) / len(self.fields), 3)
        else:
            self.overall_score = 0.0


# ── Parser Runner ────────────────────────────────────────────────────────────

def run_parser(resume_path):
    """Run the current parser pipeline. Returns (parsed_dict, features_dict, sbert_domain, sbert_confidence)."""
    from src.parser import parse_resume
    from src.features import extract_features
    from src.models import SBERTMatcher
    from utils.helpers import clean_text as _flatten

    parsed = parse_resume(resume_path)
    text = parsed.get("raw_text", "")
    features = extract_features(text)

    sbert_domain = "Unknown"
    sbert_confidence = 0.0
    try:
        flat = _flatten(text)
        clf = SBERTMatcher()
        scores = clf.predict(flat)

        swe_keywords = [
            'microservices', 'rest api', 'restful', 'docker', 'kubernetes',
            'ci/cd', 'devops', 'flask', 'fastapi', 'django', 'express',
            'react', 'angular', 'node.js', 'spring boot', 'laravel',
            'postgresql', 'mongodb', 'redis', 'nginx', 'jenkins',
            'terraform', 'ansible', 'github actions', 'agile', 'scrum',
            'system design', 'architecture', 'deployment', 'scalable',
            'api', 'web app', 'full stack', 'full-stack', 'backend', 'frontend',
            'unity', 'blender', 'vr', 'virtual reality', 'simulation',
            'interview platform', 'soc platform', 'dashboard',
            'tensorflow', 'pytorch', 'scikit-learn', 'keras', 'opencv',
            'langchain', 'langgraph', 'llamaindex', 'rag',
            'machine learning', 'deep learning', 'neural network',
            'transformers', 'hugging face', 'openai', 'llm',
            'data pipeline', 'mlops', 'model deployment',
            'algorithms', 'data structures', 'oop', 'database',
            'git', 'github', 'linux', 'python', 'java',
        ]
        swe_hits = sum(1 for kw in swe_keywords if kw in flat.lower())
        if swe_hits >= 3:
            boost = min(0.15, swe_hits * 0.015)
            scores["Software Engineering"] = scores.get("Software Engineering", 0) + boost

        sbert_domain = max(scores, key=scores.get)
        sbert_confidence = scores[sbert_domain]
    except Exception:
        pass

    return parsed, features, sbert_domain, sbert_confidence


def build_parser_output(parsed, features, sbert_domain, sbert_confidence):
    """Build the standard parser output dict."""
    return {
        "name": parsed.get("name"),
        "email": parsed.get("email"),
        "phone": parsed.get("phone"),
        "domain": sbert_domain,
        "confidence": round(sbert_confidence, 4),
        "experience": features.get("total_experience", {}),
        "education": features.get("education", []),
        "skills": features.get("skills", []),
        "projects_count": features.get("projects_count", 0),
    }


# ── Evaluator ────────────────────────────────────────────────────────────────

def evaluate_resume(resume_id, resume_path, ground_truth=None):
    """Run parser and score against ground truth if available."""
    result = ResumeResult(
        resume_id=resume_id,
        filename=f"{resume_id}.pdf",
        has_ground_truth=ground_truth is not None,
    )

    try:
        parsed, features, sbert_domain, sbert_conf = run_parser(resume_path)
        output = build_parser_output(parsed, features, sbert_domain, sbert_conf)
    except Exception as e:
        result.parse_error = f"{type(e).__name__}: {e}"
        result.compute_overall()
        return result, None

    if ground_truth is None:
        # No ground truth — just store output, no scoring
        result.compute_overall()
        return result, output

    gt = ground_truth
    exp = output.get("experience", {})

    # Score each field
    result.fields.append(FieldResult("name",
        _score_name(output.get("name"), gt.get("name")),
        gt.get("name"), output.get("name")))

    result.fields.append(FieldResult("email",
        _score_exact(output.get("email"), gt.get("email")),
        gt.get("email"), output.get("email")))

    result.fields.append(FieldResult("phone",
        _score_exact(output.get("phone"), gt.get("phone")),
        gt.get("phone"), output.get("phone")))

    result.fields.append(FieldResult("domain",
        _score_domain(output.get("domain"), gt.get("domain")),
        gt.get("domain"), output.get("domain")))

    result.fields.append(FieldResult("experience_years",
        _score_experience_years(exp.get("years", 0), gt.get("experience_years", 0)),
        gt.get("experience_years", 0), exp.get("years", 0)))

    result.fields.append(FieldResult("experience_level",
        _score_exact(exp.get("level", "Unknown"), gt.get("experience_level", "Unknown")),
        gt.get("experience_level", "Unknown"), exp.get("level", "Unknown")))

    result.fields.append(FieldResult("education",
        _score_education(output.get("education", []), gt.get("education", [])),
        gt.get("education"), output.get("education", [])))

    result.fields.append(FieldResult("skills",
        _score_skills(output.get("skills", []), gt.get("skills_must_include", []), gt.get("skills_must_not_include", [])),
        f"{len(gt.get('skills_must_include', []))} required",
        f"{len(output.get('skills', []))} found"))

    result.fields.append(FieldResult("projects_count",
        _score_projects(output.get("projects_count", 0), gt.get("projects_count_min", 0), gt.get("projects_count_max", 999)),
        f"{gt.get('projects_count_min', 0)}-{gt.get('projects_count_max', 999)}",
        output.get("projects_count", 0)))

    result.compute_overall()
    return result, output


# ── Report Generation ────────────────────────────────────────────────────────

def _bar(score, width=20):
    filled = int(score * width)
    return f"[{'#' * filled}{'.' * (width - filled)}] {score:.0%}"


def generate_summary_md(results, all_outputs, metadata_map):
    """Generate benchmark_summary.md — one section per resume."""
    lines = []
    lines.append("# Parser Benchmark Summary\n")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Resumes evaluated:** {len(results)}\n")

    scored = [r for r in results if r.has_ground_truth]
    unscored = [r for r in results if not r.has_ground_truth]

    if scored:
        avg = sum(r.overall_score for r in scored) / len(scored)
        lines.append(f"**Overall accuracy (scored):** {avg:.0%}\n")

    lines.append("---\n")

    for r in results:
        resume_id = r.resume_id
        lines.append(f"## {resume_id} — {metadata_map.get(resume_id, {}).get('original_filename', 'unknown')}\n")

        meta = metadata_map.get(resume_id, {})
        lines.append(f"| Property | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Pages | {meta.get('pages', '?')} |")
        lines.append(f"| Layout | {meta.get('layout', '?')} |")
        lines.append(f"| Tables | {meta.get('contains_tables', '?')} |")
        lines.append(f"| Two-column | {meta.get('contains_two_columns', '?')} |")
        lines.append(f"| ATS-friendly | {meta.get('ats_friendly', '?')} |")
        lines.append(f"| Est. domain | {meta.get('estimated_domain', '?')} |")
        lines.append(f"| Est. experience | {meta.get('estimated_experience_level', '?')} |")
        lines.append("")

        if r.parse_error:
            lines.append(f"**PARSE ERROR:** `{r.parse_error}`\n")
            continue

        output = all_outputs.get(resume_id, {})
        if not output:
            lines.append("*No output captured.*\n")
            continue

        exp = output.get("experience", {})
        lines.append(f"### Parser Output\n")
        lines.append(f"| Field | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| **Name** | {output.get('name', 'N/A')} |")
        lines.append(f"| **Email** | {output.get('email', 'N/A')} |")
        lines.append(f"| **Phone** | {output.get('phone', 'N/A')} |")
        lines.append(f"| **Domain** | {output.get('domain', 'N/A')} ({output.get('confidence', 0):.2%}) |")
        lines.append(f"| **Experience** | {exp.get('years', 0)} years, {exp.get('level', 'Unknown')} |")
        lines.append(f"| **Projects** | {output.get('projects_count', 0)} |")

        skills = output.get("skills", [])
        lines.append(f"| **Skills** | {len(skills)} found: {', '.join(skills[:15])}{'...' if len(skills) > 15 else ''} |")

        edus = output.get("education", [])
        if edus:
            for i, edu in enumerate(edus):
                degree = edu.get("degree") or "N/A"
                major = edu.get("major") or "N/A"
                inst = edu.get("institution") or "N/A"
                year = edu.get("graduation_year") or "N/A"
                gpa = edu.get("gpa") or "N/A"
                lines.append(f"| **Education {i+1}** | {degree} in {major}, {inst} ({year}) GPA={gpa} |")
        else:
            lines.append(f"| **Education** | None extracted |")

        lines.append("")

        if r.has_ground_truth:
            lines.append(f"### Accuracy: {r.overall_score:.0%}\n")
            lines.append(f"| Field | Score | Expected | Actual |")
            lines.append(f"|---|---|---|---|")
            for f in r.fields:
                status = "PASS" if f.score >= 0.75 else ("PARTIAL" if f.score > 0 else "FAIL")
                lines.append(f"| {f.name} | {status} ({f.score:.0%}) | {f.expected} | {f.actual} |")
            lines.append("")

    return "\n".join(lines)


def generate_failures_md(results, all_outputs, metadata_map):
    """Generate parser_failures.md — identify recurring problems ranked by frequency."""
    # Categorize failures
    failure_categories = {
        "text_extraction": [],
        "section_detection": [],
        "experience_extraction": [],
        "education_extraction": [],
        "skill_extraction": [],
        "domain_classification": [],
        "name_extraction": [],
        "contact_extraction": [],
    }

    for r in results:
        if r.parse_error:
            failure_categories["text_extraction"].append(r.resume_id)
            continue

        output = all_outputs.get(r.resume_id, {})
        exp = output.get("experience", {})

        # Check each field
        for f in r.fields:
            if f.score >= 0.75:
                continue

            if f.name in ("experience_years", "experience_level"):
                failure_categories["experience_extraction"].append(
                    f"{r.resume_id} (expected={f.expected}, got={f.actual})")
            elif f.name == "education":
                failure_categories["education_extraction"].append(
                    f"{r.resume_id} (expected={f.expected}, got={f.actual})")
            elif f.name == "skills":
                failure_categories["skill_extraction"].append(
                    f"{r.resume_id} (expected={f.expected}, got={f.actual})")
            elif f.name == "domain":
                failure_categories["domain_classification"].append(
                    f"{r.resume_id} (expected={f.expected}, got={f.actual})")
            elif f.name == "name":
                failure_categories["name_extraction"].append(
                    f"{r.resume_id} (expected={f.expected}, got={f.actual})")
            elif f.name in ("email", "phone"):
                failure_categories["contact_extraction"].append(
                    f"{r.resume_id} (expected={f.expected}, got={f.actual})")

    # Also detect structural issues from all outputs
    for rid, output in all_outputs.items():
        if output.get("name") is None:
            failure_categories["name_extraction"].append(f"{rid} (name is null)")
        if output.get("education") == []:
            failure_categories["education_extraction"].append(f"{rid} (no education extracted)")
        if output.get("experience", {}).get("years", 0) == 0 and output.get("experience", {}).get("level") == "Unknown":
            failure_categories["experience_extraction"].append(f"{rid} (0 years, Unknown level)")

    lines = []
    lines.append("# Parser Failures Analysis\n")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Resumes analyzed:** {len(results)}\n")

    # Rank by frequency
    ranked = sorted(failure_categories.items(), key=lambda x: -len(x[1]))

    lines.append("## Failure Frequency Ranking\n")
    lines.append("| Rank | Category | Count | Severity |")
    lines.append("|---|---|---|---|")

    for i, (cat, failures) in enumerate(ranked, 1):
        count = len(failures)
        if count == 0:
            severity = "OK"
        elif count <= 2:
            severity = "LOW"
        elif count <= 5:
            severity = "MEDIUM"
        else:
            severity = "HIGH"
        lines.append(f"| {i} | {cat} | {count} | {severity} |")

    lines.append("")

    for i, (cat, failures) in enumerate(ranked, 1):
        if not failures:
            continue
        lines.append(f"## {i}. {cat} ({len(failures)} failures)\n")
        for f in failures:
            lines.append(f"- {f}")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations\n")
    active_failures = [(cat, f) for cat, f in ranked if f]
    if active_failures:
        lines.append(f"The top issue is **{active_failures[0][0]}** with {len(active_failures[0][1])} failures.")
        lines.append(f"This should be the highest-priority fix.\n")
        for cat, failures in active_failures[:3]:
            lines.append(f"- **{cat}**: {len(failures)} occurrences")
    else:
        lines.append("No failures detected in scored resumes.")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Parser Benchmark Framework")
    parser.add_argument("--resume", help="Evaluate a single resume by ID (e.g. 001)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    os.makedirs(BASELINE_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Discover resumes
    resume_files = sorted(glob.glob(os.path.join(RESUMES_DIR, "*.pdf")))
    if not resume_files:
        print("No resumes found in parser_tests/resumes/")
        sys.exit(1)

    if args.resume:
        target = os.path.join(RESUMES_DIR, f"{args.resume}.pdf")
        if not os.path.exists(target):
            print(f"Resume {args.resume}.pdf not found")
            sys.exit(1)
        resume_files = [target]

    # Load metadata
    metadata_map = {}
    mapping_path = os.path.join(METADATA_DIR, "file_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path, "r") as f:
            for m in json.load(f):
                metadata_map[m["id"]] = m

    # Load ground truth if available
    ground_truth_map = {}
    for gt_file in glob.glob(os.path.join(GROUND_TRUTH_DIR, "*.json")):
        rid = os.path.splitext(os.path.basename(gt_file))[0]
        with open(gt_file, "r", encoding="utf-8") as f:
            ground_truth_map[rid] = json.load(f)

    # Process each resume
    results = []
    all_outputs = {}

    for resume_path in resume_files:
        resume_id = os.path.splitext(os.path.basename(resume_path))[0]
        gt = ground_truth_map.get(resume_id)

        status = "with ground truth" if gt else "baseline only"
        print(f"[{resume_id}] Running parser ({status})...")

        result, output = evaluate_resume(resume_id, resume_path, gt)
        results.append(result)

        if output:
            all_outputs[resume_id] = output
            # Save baseline
            baseline_path = os.path.join(BASELINE_DIR, f"{resume_id}.json")
            with open(baseline_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)

        if result.parse_error:
            print(f"  ERROR: {result.parse_error}")
        elif result.has_ground_truth:
            print(f"  Score: {result.overall_score:.0%}")
        else:
            skills_count = len(output.get("skills", [])) if output else 0
            print(f"  OK: name={output.get('name')}, domain={output.get('domain')}, "
                  f"skills={skills_count}, exp={output.get('experience', {}).get('years', '?')}yr")

    # Generate reports
    print("\nGenerating reports...")

    summary_md = generate_summary_md(results, all_outputs, metadata_map)
    failures_md = generate_failures_md(results, all_outputs, metadata_map)

    summary_path = os.path.join(REPORTS_DIR, "benchmark_summary.md")
    failures_path = os.path.join(REPORTS_DIR, "parser_failures.md")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)
    with open(failures_path, "w", encoding="utf-8") as f:
        f.write(failures_md)

    # Also save JSON report
    json_report = {
        "generated": datetime.now().isoformat(),
        "total_resumes": len(results),
        "scored_resumes": sum(1 for r in results if r.has_ground_truth),
        "overall_accuracy": round(
            sum(r.overall_score for r in results if r.has_ground_truth) /
            max(1, sum(1 for r in results if r.has_ground_truth)), 3
        ),
        "per_resume": [
            {
                "id": r.resume_id,
                "score": r.overall_score if r.has_ground_truth else None,
                "has_ground_truth": r.has_ground_truth,
                "parse_error": r.parse_error or None,
            }
            for r in results
        ],
    }
    json_path = os.path.join(REPORTS_DIR, "benchmark_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2)

    print(f"\nReports saved:")
    print(f"  {summary_path}")
    print(f"  {failures_path}")
    print(f"  {json_path}")
    print(f"\nBaseline outputs saved to {BASELINE_DIR}/")


if __name__ == "__main__":
    main()
