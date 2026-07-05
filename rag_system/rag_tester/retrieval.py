"""
RAG Retrieval Module - Retrieves relevant content from FAISS index
"""
import faiss
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')


def load_knowledge_base(subject_name):
    """
    Load FAISS index and chunks from knowledge_base directory
    
    Args:
        subject_name: Name of the subject (e.g., 'cn_unit1')
    
    Returns:
        tuple: (index, chunks) or (None, None) if not found
    """
    index_path = f"knowledge_base/{subject_name}.index"
    json_path = f"knowledge_base/{subject_name}_chunks.json"

    if not os.path.exists(index_path) or not os.path.exists(json_path):
        print(f"❌ Knowledge base not found for '{subject_name}'")
        print(f"   Run: python ingestor.py first to create the index")
        return None, None

    print(f"📂 Loading index: {subject_name}")
    index = faiss.read_index(index_path)
    
    with open(json_path, "r", encoding='utf-8') as f:
        chunks = json.load(f)
    
    return index, chunks


def retrieve_relevant_content(subject_name, query, top_k=5):
    """
    Retrieve top-k most relevant content chunks for a query
    
    Args:
        subject_name: Name of the subject
        query: User query/topic
        top_k: Number of results to return
    
    Returns:
        list: List of dicts with page, text, and score
    """
    index, chunks = load_knowledge_base(subject_name)
    
    if index is None:
        return []
    
    # Encode query
    query_vector = model.encode([query]).astype('float32')
    
    # Search FAISS index
    distances, indices = index.search(query_vector, k=min(top_k, len(chunks)))
    
    results = []
    for i, idx in enumerate(indices[0]):
        if 0 <= idx < len(chunks):
            chunk = chunks[idx]
            results.append({
                'page': chunk['page'],
                'text': chunk['text'],
                'distance': float(distances[0][i]),
                'relevance_score': 1 / (1 + float(distances[0][i]))  # Convert distance to relevance
            })
    
    return results


def get_best_context(subject_name, query):
    """
    Get the best single context chunk for generation
    
    Args:
        subject_name: Name of the subject
        query: User query/topic
    
    Returns:
        str: Best matching text or empty string
    """
    results = retrieve_relevant_content(subject_name, query, top_k=1)
    
    if results and len(results[0]['text'].strip()) > 30:
        return results[0]['text']
    
    return ""


def get_context_with_pages(subject_name, query, top_k=2):
    """
    Get multiple context chunks with page references
    
    Args:
        subject_name: Name of the subject
        query: User query/topic
        top_k: Number of chunks to retrieve
    
    Returns:
        tuple: (combined_text, page_references)
    """
    results = retrieve_relevant_content(subject_name, query, top_k=top_k)
    
    if not results:
        return "", []
    
    combined_text = " ".join([r['text'] for r in results])
    pages = [r['page'] for r in results]
    
    return combined_text, pages
