from __future__ import annotations

from inference.predict_intent import predict_intent
from inference.predict_difficulty import predict_difficulty
from inference.predict_topic import predict_topic

TESTS = [
    "What is tree traversal and sorting?",
    "Explain tree traversal and transactions",
    "Explain dynamic programming",
    "Explain greedy algorithm",
    "Explain BFS and DFS",
    "How would you handle deadlock in a system with multiple resources?",
    "What is recursion?",
    "Explain TCP and UDP",
]

for text in TESTS:
    i = predict_intent(text)
    d = predict_difficulty(text)
    t = predict_topic(text)
    intent_str = f"{i['label']} ({i['confidence']:.2f})"
    diff_str = f"{d['label']} ({d['confidence']:.2f})"
    topics_str = ", ".join(t["labels"])
    print(f"Q:  {text}")
    print(f"    Intent={intent_str}  Difficulty={diff_str}  Topics=[{topics_str}]")
    print()
