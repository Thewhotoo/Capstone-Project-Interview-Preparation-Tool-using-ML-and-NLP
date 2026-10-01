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
