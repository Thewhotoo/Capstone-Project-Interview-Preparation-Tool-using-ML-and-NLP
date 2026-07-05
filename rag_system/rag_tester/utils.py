"""
Utils Module - Caching and Quality Control
"""
import json
import os
from datetime import datetime

CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)


def cache_questions(topic, questions, subject_name="cn_unit1"):
    """
    Cache generated questions to avoid re-generation
    
    Args:
        topic: Topic name
        questions: List of question dicts
        subject_name: Subject identifier
    """
    cache_file = f"{CACHE_DIR}/{subject_name}_questions.json"
    
    # Load existing cache
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)
    else:
        cache = {}
    
    # Add new questions with timestamp
    cache[topic] = {
        'questions': questions,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)


def get_cached_questions(topic, subject_name="cn_unit1"):
    """
    Get cached questions for a topic
    
    Returns:
        list or None: Cached questions or None if not found
    """
    cache_file = f"{CACHE_DIR}/{subject_name}_questions.json"
    
    if not os.path.exists(cache_file):
        return None
    
    with open(cache_file, "r") as f:
        cache = json.load(f)
    
    return cache.get(topic, {}).get('questions', None)


def is_quality_question(question):
    """
    Check if a generated question meets quality standards
    
    Args:
        question: Question text
    
    Returns:
        bool: True if high quality
    """
    # Check length
    words = question.split()
    if len(words) < 5 or len(words) > 25:
        return False
    
    # Check for required patterns
    if not question.endswith("?"):
        return False
    
    # Check for bad keywords
    bad_keywords = ["generate", "create", "context", "material", "explain this"]
    if any(bad in question.lower() for bad in bad_keywords):
        return False
    
    # Must start with question word
    question_starters = ["what", "how", "why", "describe", "explain", "compare", "discuss"]
    if not any(question.lower().startswith(q) for q in question_starters):
        return False
    
    return True


def rank_by_quality(questions):
    """
    Rank questions by quality score
    
    Args:
        questions: List of question strings
    
    Returns:
        list: Sorted questions by quality
    """
    scored = []
    
    for q in questions:
        score = 0
        
        # Length score (5-20 words optimal)
        word_count = len(q.split())
        if 5 <= word_count <= 20:
            score += 30
        
        # Ends with ?
        if q.endswith("?"):
            score += 20
        
        # Starts with good word
        starters = ["what", "how", "why", "describe", "explain", "compare"]
        if any(q.lower().startswith(s) for s in starters):
            score += 25
        
        # No bad keywords
        bad_words = ["generate", "create", "context", "material"]
        if not any(bad in q.lower() for bad in bad_words):
            score += 25
        
        scored.append((q, score))
    
    # Sort by score descending
    return sorted(scored, key=lambda x: x[1], reverse=True)


def batch_generate_with_quality(topics, retrieve_func, generate_func, max_attempts=3):
    """
    Generate questions with quality control - retry if poor quality
    
    Args:
        topics: List of topics
        retrieve_func: Function to retrieve content
        generate_func: Function to generate question
        max_attempts: Max retry attempts per topic
    
    Returns:
        dict: {topic: question}
    """
    results = {}
    
    for topic in topics:
        attempts = 0
        question = None
        
        while attempts < max_attempts:
            try:
                # Retrieve content
                content = retrieve_func(topic)
                
                if not content:
                    break
                
                # Generate question
                question = generate_func(content, concept=topic)
                
                # Quality check
                if is_quality_question(question):
                    results[topic] = question
                    break
                
                attempts += 1
            
            except Exception as e:
                print(f"⚠️  Error generating for {topic}: {e}")
                break
        
        if topic not in results:
            results[topic] = "Unable to generate quality question"
    
    return results


def export_questions_to_csv(questions_dict, filename="questions.csv"):
    """
    Export questions to CSV for review
    
    Args:
        questions_dict: Dict of {topic: question}
        filename: Output CSV filename
    """
    import csv
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Topic', 'Question', 'Quality'])
        
        for topic, question in questions_dict.items():
            quality = 'Good' if is_quality_question(question) else 'Needs Review'
            writer.writerow([topic, question, quality])
    
    print(f"✅ Exported {len(questions_dict)} questions to {filename}")


def stats_summary(subject_name="cn_unit1"):
    """
    Show cached questions statistics
    """
    cache_file = f"{CACHE_DIR}/{subject_name}_questions.json"
    
    if not os.path.exists(cache_file):
        print("No cached questions found")
        return
    
    with open(cache_file, "r") as f:
        cache = json.load(f)
    
    print(f"\n📊 CACHED QUESTIONS STATISTICS")
    print(f"{'='*50}")
    print(f"Total topics: {len(cache)}")
    
    total_questions = sum(len(v['questions']) for v in cache.values())
    print(f"Total questions: {total_questions}")
    
    print(f"\nTopics:")
    for topic, data in cache.items():
        print(f"  • {topic}: {len(data['questions'])} questions")
