from __future__ import annotations

from inference.predict_difficulty import predict_difficulty
from inference.predict_intent import predict_intent
from inference.predict_topic import predict_topic


SAMPLE_INPUTS = [
    "What is a process?",
    "Explain database schema",
    "What is a subnet mask?",
    "Difference between TCP and UDP",
    "Compare HTTP/1.1 and HTTP/2 performance characteristics",
    "How would you design an ER model for online food delivery platform?",
    "How would you reason about amortized complexity of dynamic array resizing?",
    "Design deadlock-free resource allocation strategy for three competing processes",
    "How would you optimize Dijkstra for sparse graph with a million edges?",
    "Design a class-based LRU cache using hash map and doubly linked list",
    "Compare transaction locking in DBMS with semaphore-based synchronization in OS",
]


def main() -> None:
    for text in SAMPLE_INPUTS:
        intent_result = predict_intent(text)
        difficulty_result = predict_difficulty(text)
        topic_result = predict_topic(text)
        print(f"Input: {text}")
        print(f"Intent: {intent_result['label']} | Difficulty: {difficulty_result['label']} | Topics: {', '.join(topic_result['labels'])}")
        print()


if __name__ == "__main__":
    main()
