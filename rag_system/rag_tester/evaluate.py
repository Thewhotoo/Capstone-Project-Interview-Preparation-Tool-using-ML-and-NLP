"""
Evaluation Module - Scores student answers against reference context
"""
from sentence_transformers import SentenceTransformer, util

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")


def evaluate_answer(student_answer, reference_context):
    """
    Evaluate how well a student answer matches the reference context
    
    Args:
        student_answer: Student's answer text
        reference_context: Reference/correct answer from the knowledge base
    
    Returns:
        dict: Score and feedback
    """
    if not student_answer or not reference_context:
        return {
            'score': 0.0,
            'feedback': 'Invalid input',
            'grade': 'F'
        }
    
    # Encode both texts
    student_emb = model.encode(student_answer, convert_to_tensor=True)
    reference_emb = model.encode(reference_context, convert_to_tensor=True)
    
    # Calculate cosine similarity
    similarity = util.cos_sim(student_emb, reference_emb).item()
    
    # Convert to score (0-100)
    score = similarity * 100
    
    # Determine grade
    if score >= 80:
        grade = 'A'
        feedback = "Excellent! Your answer closely matches the reference material."
    elif score >= 70:
        grade = 'B'
        feedback = "Good! Your answer is mostly correct and covers key points."
    elif score >= 60:
        grade = 'C'
        feedback = "Fair. Your answer addresses the topic but is missing some details."
    elif score >= 50:
        grade = 'D'
        feedback = "Your answer partially addresses the topic. Review the reference material."
    else:
        grade = 'F'
        feedback = "Your answer does not match the reference material. Try again!"
    
    return {
        'score': round(score, 2),
        'similarity': round(similarity, 4),
        'grade': grade,
        'feedback': feedback,
        'answer_length': len(student_answer.split()),
        'reference_length': len(reference_context.split())
    }


def compare_answers(answer1, answer2):
    """
    Compare two answers for similarity
    
    Args:
        answer1: First answer
        answer2: Second answer
    
    Returns:
        dict: Comparison result
    """
    emb1 = model.encode(answer1, convert_to_tensor=True)
    emb2 = model.encode(answer2, convert_to_tensor=True)
    
    similarity = util.cos_sim(emb1, emb2).item()
    
    return {
        'similarity': round(similarity, 4),
        'percentage': round(similarity * 100, 2)
    }


def evaluate_multiple_answers(student_answers, reference_context):
    """
    Evaluate multiple student answers against reference
    
    Args:
        student_answers: List of student answers
        reference_context: Reference answer
    
    Returns:
        list: List of evaluation results
    """
    results = []
    for answer in student_answers:
        result = evaluate_answer(answer, reference_context)
        results.append(result)
    
    return results
