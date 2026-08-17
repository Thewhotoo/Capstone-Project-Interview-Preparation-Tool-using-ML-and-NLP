"""
Evaluation Module - Scores student answers against reference context
with rubric breakdown and weighted concept matching.
"""

from sentence_transformers import util
from collections import Counter
import re
import math
from generate import get_llm_response

# Lazy loaded SentenceTransformer
_model = None


def get_model():
    """Loads SentenceTransformer only once."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def extract_keywords(text):
    """Extract technical keywords (alphabetic, >5 chars, not stop words)."""
    STOP_WORDS = {
        "the","and","for","with","this","that","from","into","using",
        "have","has","will","also","called","their","there","where",
        "what","when","which","about","these","those","some","would",
        "could","should","been","being","through","between","without",
        "during","within","upon","among","etc","therefore","however"
    }
    words = []
    for word in text.lower().split():
        word = "".join(c for c in word if c.isalpha())
        if len(word) > 5 and word.isalpha() and word not in STOP_WORDS:
            words.append(word)
    word_counts = Counter(words)
    unique_words = []
    for w, _ in word_counts.most_common():
        if w not in unique_words:
            unique_words.append(w)
    return unique_words[:10]


def extract_concepts_from_text(text):
    """
    Extract concepts: bullet points, capitalized phrases, then fallback to keywords.
    Returns a list of concept strings (most important first).
    """
    concepts = []
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(('•', '-', '*', '✓', '○', '▪', '→')):
            parts = line.split(maxsplit=1)
            if len(parts) > 1:
                concept = parts[1].strip()
                if len(concept.split()) >= 2 and not concept.lower().startswith(('the', 'a', 'an')):
                    concepts.append(concept)
    if not concepts:
        cap_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+'
        found = re.findall(cap_pattern, text)
        for phrase in found[:10]:
            if len(phrase.split()) >= 2 and phrase not in concepts:
                concepts.append(phrase)
    if not concepts:
        return extract_keywords(text)
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in concepts:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:10]


def extract_weighted_concepts(text):
    """
    Extract concepts and assign weights based on frequency in text.
    Returns list of (concept, weight) pairs, highest weight first.
    """
    concepts = extract_concepts_from_text(text)
    if not concepts:
        return []
    # Count occurrences of each concept (case-insensitive)
    text_lower = text.lower()
    concept_counts = {}
    for concept in concepts:
        # Count whole word occurrences (approximate)
        count = len(re.findall(r'\b' + re.escape(concept.lower()) + r'\b', text_lower))
        concept_counts[concept] = count or 1
    # Normalize weights: higher count = higher weight, but cap at 2.0
    max_c = max(concept_counts.values()) if concept_counts else 1
    weighted = [(c, min(2.0, count / max_c * 1.5)) for c, count in concept_counts.items()]
    # Sort by weight descending, then by original order
    weighted.sort(key=lambda x: (-x[1], concepts.index(x[0])))
    return weighted


def generate_ai_feedback(student_answer, reference_answer):
    """
    Generate human-like feedback using Qwen, strictly grounded in the reference.
    """
    prompt = f"""
You are evaluating a student's answer against a reference answer.

Reference Answer:
{reference_answer}

Student Answer:
{student_answer}

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:

- You are NOT allowed to use any knowledge outside the reference answer.
- You MUST ignore everything you know.
- If a concept does not appear in the reference answer, DO NOT mention it.
- Do NOT invent examples, languages, design patterns, or databases.
- Only compare the student answer against the supplied reference.
- Focus on missing concepts and clarity.
- Be constructive and concise.

Return ONLY in this format:

Strengths:
- ...

Missing Concepts:
- ...

Suggestions:
- ...
"""

    try:
        return get_llm_response(prompt)
    except Exception:
        return "AI feedback unavailable."


def compute_rubric_breakdown(student_answer, reference_context):
    """
    Compute separate scores for semantic similarity, concept coverage, and clarity.
    Returns a dict with keys: semantic, concept, clarity, overall.
    """
    model = get_model()
    # Encode
    student_emb = model.encode(student_answer, convert_to_tensor=True)
    reference_emb = model.encode(reference_context, convert_to_tensor=True)
    semantic_sim = util.cos_sim(student_emb, reference_emb).item()
    semantic_sim = max(0.0, min(1.0, semantic_sim))
    semantic_score = semantic_sim * 100

    # Weighted concept matching
    weighted_ref_concepts = extract_weighted_concepts(reference_context)
    if not weighted_ref_concepts:
        concept_score = 100.0
    else:
        student_lower = student_answer.lower()
        total_weight = 0.0
        matched_weight = 0.0
        for concept, weight in weighted_ref_concepts:
            total_weight += weight
            if concept.lower() in student_lower:
                matched_weight += weight
            else:
                # Partial match: check if all words in concept appear
                concept_words = concept.lower().split()
                if len(concept_words) > 1:
                    if all(w in student_lower for w in concept_words):
                        matched_weight += weight * 0.7
        concept_score = (matched_weight / total_weight) * 100 if total_weight > 0 else 0.0

    # Clarity score: based on answer length and sentence structure
    ref_words = len(reference_context.split())
    student_words = len(student_answer.split())
    # Ideal length is at least 60% of reference length, but not too long
    if student_words == 0:
        length_ratio = 0
    else:
        length_ratio = min(1.0, student_words / (max(1, ref_words) * 0.6))
        length_ratio = min(length_ratio, 1.5)  # cap at 1.5
    # Also count sentences (by punctuation)
    sentences = re.split(r'[.!?]+', student_answer)
    sent_count = len([s for s in sentences if s.strip()])
    sentence_score = min(1.0, sent_count / 3)  # at least 3 sentences is good
    # Combine: 70% length ratio, 30% sentence structure
    clarity_score = (0.7 * min(1.0, length_ratio) + 0.3 * min(1.0, sentence_score)) * 100

    # Overall: weighted average
    overall = (0.45 * semantic_score + 0.35 * concept_score + 0.20 * clarity_score)
    overall = max(0, min(100, overall))

    return {
        "semantic_score": round(semantic_score, 2),
        "concept_score": round(concept_score, 2),
        "clarity_score": round(clarity_score, 2),
        "overall_score": round(overall, 2),
    }


def evaluate_answer(student_answer, reference_context, question_type="open", test_cases=None, language="python"):
    """
    Evaluate how well the student answer matches the reference.
    Returns dict with scores, grade, feedback, and breakdown.
    """
    if not student_answer or not reference_context:
        return {
            'score': 0.0,
            'feedback': 'Invalid input',
            'grade': 'F',
            'matched_keywords': [],
            'missing_keywords': [],
            'strengths': [],
            'weaknesses': [],
            'ai_feedback': 'Invalid input - no answer or reference provided.',
            'rubric': {
                'semantic_score': 0,
                'concept_score': 0,
                'clarity_score': 0,
                'overall_score': 0
            }
        }

    # Compute rubric breakdown
    rubric = compute_rubric_breakdown(student_answer, reference_context)
    overall = rubric["overall_score"]

    # Extract matched/missing concepts (unweighted)
    ref_concepts = extract_concepts_from_text(reference_context)
    student_lower = student_answer.lower()
    matched = []
    missing = []
    for concept in ref_concepts:
        if concept.lower() in student_lower:
            matched.append(concept)
        else:
            # partial match
            words = concept.lower().split()
            if len(words) > 1 and all(w in student_lower for w in words):
                matched.append(concept)
            else:
                missing.append(concept)

    # Determine grade
    if overall >= 80:
        grade = 'A'
    elif overall >= 70:
        grade = 'B'
    elif overall >= 60:
        grade = 'C'
    elif overall >= 50:
        grade = 'D'
    else:
        grade = 'F'

    # Build strengths/weaknesses
    strengths = []
    weaknesses = []
    if matched:
        strengths.append(f"Correctly covered concepts: {', '.join(matched[:3])}")
    if len(student_answer.split()) >= len(reference_context.split()) * 0.5:
        strengths.append("Good answer length and coverage")
    if rubric["semantic_score"] >= 70:
        strengths.append("Good semantic alignment with reference")

    if missing:
        if len(missing) <= 3:
            weaknesses.append(f"Missing concepts: {', '.join(missing)}")
        else:
            weaknesses.append(f"Missing concepts: {', '.join(missing[:3])} and {len(missing)-3} more")
    if rubric["semantic_score"] < 60:
        weaknesses.append("Answer could be more aligned with the reference material")
    if rubric["clarity_score"] < 50:
        weaknesses.append("Answer lacks clarity or sufficient detail")

    feedback_lines = []
    if strengths:
        feedback_lines.append("Strengths:")
        feedback_lines.extend([f"  ✓ {s}" for s in strengths])
    if weaknesses:
        feedback_lines.append("\nWeaknesses:")
        feedback_lines.extend([f"  ✗ {w}" for w in weaknesses])
    if not strengths and not weaknesses:
        feedback_lines.append("Mixed answer quality. Review the reference material for improvement.")

    # Generate AI feedback (strictly grounded)
    ai_feedback = generate_ai_feedback(student_answer, reference_context)

    return {
        'score': round(overall, 2),
        'similarity': rubric['semantic_score'],
        'concept_coverage': rubric['concept_score'],
        'quality_score': rubric['clarity_score'],
        'grade': grade,
        'feedback': '\n'.join(feedback_lines),
        'ai_feedback': ai_feedback,
        'answer_length': len(student_answer.split()),
        'reference_length': len(reference_context.split()),
        'matched_keywords': matched,
        'missing_keywords': missing,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'rubric': rubric,  # detailed breakdown
    }


def compare_answers(answer1, answer2):
    """Compare two answers for similarity."""
    model = get_model()
    emb1 = model.encode(answer1, convert_to_tensor=True)
    emb2 = model.encode(answer2, convert_to_tensor=True)
    similarity = util.cos_sim(emb1, emb2).item()
    similarity = max(0.0, min(1.0, similarity))
    return {'similarity': round(similarity, 4), 'percentage': round(similarity * 100, 2)}


def evaluate_multiple_answers(student_answers, reference_context):
    """Evaluate multiple student answers."""
    return [evaluate_answer(ans, reference_context) for ans in student_answers]