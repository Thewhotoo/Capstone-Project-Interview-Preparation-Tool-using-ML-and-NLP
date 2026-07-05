from rag.fetch import search_web, fetch_page
from rag.process import chunk_text
from rag.retrieve import build_index, retrieve
from llm.generate import generate_question
from eval.score import evaluate
from tqdm import tqdm


# -------------------------
# 🔥 PICK BEST CONTEXT CHUNK
# -------------------------
def pick_best_chunk(docs, topic):
    for d in docs:
        d_lower = d.lower()

        # prioritize definition-style sentences
        if f"{topic.lower()} is" in d_lower or f"{topic.lower()} occurs" in d_lower:
            return d

    return docs[0] if docs else ""


def run():
    topic = input("Enter topic: ")

    # -------------------------
    # 🔎 SMART QUERY EXPANSION
    # -------------------------
    queries = [
        f"{topic} definition computer science",
        f"{topic} explanation with example operating system dbms cn",
        f"{topic} causes and conditions computer science",
        f"what is {topic} explain clearly with example"
    ]

    print("🔎 Searching the web...")
    urls = search_web(queries)

    if not urls:
        print("❌ No sources found.")
        return

    # -------------------------
    # 🌐 FETCH CONTENT
    # -------------------------
    print("🌐 Fetching content...")
    all_text = ""
    sources = []

    for url in tqdm(urls, desc="Fetching Pages", unit="site"):
        text = fetch_page(url)
        if text:
            all_text += text + " "
            sources.append(url)

    if not all_text.strip():
        print("❌ No relevant content found.")
        return

    # -------------------------
    # ⚙️ PROCESS TEXT
    # -------------------------
    print("⚙️ Processing text...")
    chunks = chunk_text(all_text)

    if not chunks:
        print("❌ No chunks created.")
        return

    # -------------------------
    # 🧠 BUILD EMBEDDINGS
    # -------------------------
    print("🧠 Building embeddings...")
    embeddings, chunks = build_index(chunks)

    # -------------------------
    # 📌 RETRIEVE
    # -------------------------
    print("📌 Retrieving relevant knowledge...")
    docs = retrieve(topic, embeddings, chunks)

    if not docs:
        print("❌ No relevant documents found.")
        return

    # -------------------------
    # 🔥 SELECT BEST CONTEXT
    # -------------------------
    best_chunk = pick_best_chunk(docs, topic)
    context = best_chunk

    # -------------------------
    # 🧠 GENERATE QUESTION
    # -------------------------
    print("=" * 30)
    print("🧠 GENERATED QUESTION:")
    print("=" * 30)

    question = generate_question(context)
    print(question)

    # -------------------------
    # ✍️ USER ANSWER
    # -------------------------
    user_ans = input("\n✍️ Your Answer: ")

    # -------------------------
    # 📊 EVALUATION
    # -------------------------
    print("📊 Evaluating answer...")
    score, ref = evaluate(user_ans, context)

    print("=" * 30)
    print("📊 RESULT")
    print("=" * 30)
    print(f"Score: {score:.2f} / 1.0")

    print("\n📖 Reference Answer:")
    print(ref[:300])

    print("\n🌐 Sources Used:")
    for s in sources:
        print("-", s)


if __name__ == "__main__":
    run()