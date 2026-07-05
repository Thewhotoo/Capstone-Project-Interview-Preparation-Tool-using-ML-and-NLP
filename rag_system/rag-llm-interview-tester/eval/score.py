from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")


def evaluate(user_answer, context):
    ref = context[:300]

    emb1 = model.encode(user_answer, convert_to_tensor=True)
    emb2 = model.encode(ref, convert_to_tensor=True)

    score = util.cos_sim(emb1, emb2).item()

    return score, ref