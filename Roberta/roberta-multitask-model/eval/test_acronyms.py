from __future__ import annotations
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inference.predict_intent import predict_intent
from inference.predict_difficulty import predict_difficulty
from inference.predict_topic import predict_topic

tests = [
    'what is DSA',
    'what is OOP',
    'what is OS',
    'what is CN',
    'what is DBMS',
]

for text in tests:
    i = predict_intent(text)
    d = predict_difficulty(text)
    t = predict_topic(text)
    intent_str = f"{i['label']} ({i['confidence']:.2f})"
    diff_str = f"{d['label']} ({d['confidence']:.2f})"
    topics_str = ", ".join(t['labels'])
    print(f"Q:  {text}")
    print(f"    Intent={intent_str}  Difficulty={diff_str}  Topics=[{topics_str}]")
    print()
