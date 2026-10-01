import faiss
import json
import numpy as np
import os
from sentence_transformers import SentenceTransformer

# 1. SETUP
# Make sure this matches the model in your main project
print("Loading Model... ⏳")
model = SentenceTransformer('all-MiniLM-L6-v2')

def run_rag_test(subject_name, user_query):
    """
    Tests the retrieval quality of your processed PDFs.
    """
    index_path = f"knowledge_base/{subject_name}.index"
    json_path = f"knowledge_base/{subject_name}_chunks.json"

    # Check if files exist
    if not os.path.exists(index_path) or not os.path.exists(json_path):
        print(f"❌ Error: Could not find index files for '{subject_name}' in knowledge_base/")
        print("Run your ingestor.py script first!")
        return

    # 2. LOAD DATA
    print(f"📂 Loading Index: {index_path}")
    index = faiss.read_index(index_path)
    with open(json_path, "r") as f:
        chunks = json.load(f)

    # 3. SEARCH (RETRIEVAL)
    print(f"🔍 Searching for: '{user_query}'")
    query_vector = model.encode([user_query]).astype('float32')
    
    # We retrieve top 5 so we can filter out 'garbage' slides
    distances, indices = index.search(query_vector, k=5)

    print("\n" + "="*50)
    print(f"RAG RESULTS FOR: {user_query.upper()}")
    print("="*50)

    valid_context = []
    for i, idx in enumerate(indices[0]):
        slide = chunks[idx]
        text = slide['text']
        dist = distances[0][i]

        # QUALITY FILTER: Skip slides with less than 30 characters (usually noise)
        if len(text.strip()) < 30:
            print(f"⚠️  Skipping Slide {slide['page']} (Too short/Noise)")
            continue

        print(f"\n✅ MATCH #{len(valid_context)+1} | Slide: {slide['page']} | Score: {dist:.4f}")
        print(f"CONTENT: {text[:200]}...") # Print first 200 chars
        valid_context.append(text)

        # Stop once we have 2 good slides
        if len(valid_context) >= 2:
            break

    # 4. SIMULATED GENERATION
    if valid_context:
        print("\n" + "-"*50)
        print("🤖 SIMULATED AI QUESTION GENERATION:")
        print("-"*50)
        
        # This mimics the 'generate_dynamic_qa' function in your app.py
        main_context = valid_context[0]
        
        print(f"Target Skill: {user_query}")
        print(f"Draft Question: 'Explain the core principles of {user_query} as discussed in the material.'")
        print(f"Reference Answer Source: Slide {chunks[indices[0][0]]['page']}")
    else:
        print("\n❌ No high-quality matches found for this topic.")

if __name__ == "__main__":
    SUBJECT = "cn_unit1" 
    QUERY = "Explain the OSI Model layers" 
    
    run_rag_test(SUBJECT, QUERY)