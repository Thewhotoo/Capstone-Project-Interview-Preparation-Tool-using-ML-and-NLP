from sentence_transformers import SentenceTransformer, util

# 🔥 Load embedding model once
model = SentenceTransformer("all-MiniLM-L6-v2")


# -------------------------
# BUILD EMBEDDINGS
# -------------------------
def build_index(chunks):
    """
    Convert text chunks into embeddings
    """
    embeddings = model.encode(chunks, convert_to_tensor=True)
    return embeddings, chunks   # ⚠️ order matters


# -------------------------
# RETRIEVE RELEVANT CHUNKS (RAG)
# -------------------------
def retrieve(query, embeddings, chunks, top_k=5):
    query_embedding = model.encode(query, convert_to_tensor=True)

    scores = util.cos_sim(query_embedding, embeddings)[0]

    # 🔥 FIX: prevent overflow
    top_k = min(top_k, len(chunks))

    top_results = scores.topk(k=top_k)

    results = [chunks[i] for i in top_results.indices]

    return results