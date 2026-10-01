"""Pick the questions for one technical interview.

Rules, in priority order:
  1. every question from a different topic (never relaxed);
  2. questions this user has already been asked are skipped while unseen ones
     remain for that slot;
  3. subjects rotate (a shuffled round-robin), so a 10-question session gets
     about 2 per subject;
  4. a difficulty arc: warm-up easy questions first, mostly medium, 1-2 hard
     near the end (see difficulty_plan);
  5. among the candidates for a slot, topics asked often in placement interviews
     are weighted up (Question.interview_priority: tier 3 x6, tier 2 x1,
     tier 1 x0.2), weak topics are weighted up (the user's average score on the
     topic), and higher-confidence questions are preferred.
When a slot has no candidate, the constraints are relaxed in this order:
difficulty, then subject, then "already seen".
"""
from __future__ import annotations

import random
from typing import Mapping, Sequence

from .bank import Question

WEAK_TOPIC_BOOST = 2.0        # weight = 1 + boost * (1 - average score) for topics the user has answered
INTERVIEW_PRIORITY_WEIGHT = {3: 6.0, 2: 1.0, 1: 0.2}   # how often the topic is asked in interviews (tier-3 topics = 87% of questions asked)


def difficulty_plan(n: int) -> list[str]:
    """Easy warm-ups, then medium, then hard at the end.
    n=8 -> 2 easy, 5 medium, 1 hard;  n=10 -> 2 easy, 6 medium, 2 hard."""
    if n <= 0:
        return []
    easy = max(1, round(n * 0.2))
    hard = max(1, round(n * 0.15)) if n >= 4 else 0
    medium = max(0, n - easy - hard)
    return ["easy"] * easy + ["medium"] * medium + ["hard"] * hard


def _weight(q: Question, topic_scores: Mapping[str, float]) -> float:
    w = 0.5 + q.confidence                                   # 1.25 .. 1.5 for the active bank
    w *= INTERVIEW_PRIORITY_WEIGHT.get(q.interview_priority, INTERVIEW_PRIORITY_WEIGHT[2])
    if q.topic_id in topic_scores:
        w *= 1.0 + WEAK_TOPIC_BOOST * (1.0 - max(0.0, min(1.0, topic_scores[q.topic_id])))
    return w


def select_questions(bank: Sequence[Question], n: int, *, seen_ids: set[str] | None = None,
                     topic_scores: Mapping[str, float] | None = None,
                     rng: random.Random | None = None) -> list[Question]:
    rng = rng or random.Random()
    seen_ids = seen_ids or set()
    topic_scores = topic_scores or {}
    subjects = sorted({q.subject for q in bank})
    rng.shuffle(subjects)
    chosen: list[Question] = []
    used_topics: set[str] = set()

    for slot, level in enumerate(difficulty_plan(n)):
        subject = subjects[slot % len(subjects)] if subjects else None
        base = [q for q in bank if q.topic_id not in used_topics and q.id not in {c.id for c in chosen}]
        # progressively relax: difficulty -> subject -> already-seen
        tiers = (
            lambda q: q.subject == subject and q.difficulty == level and q.id not in seen_ids,
            lambda q: q.subject == subject and q.id not in seen_ids,
            lambda q: q.difficulty == level and q.id not in seen_ids,
            lambda q: q.id not in seen_ids,
            lambda q: True,
        )
        pool: list[Question] = []
        for keep in tiers:
            pool = [q for q in base if keep(q)]
            if pool:
                break
        if not pool:
            break                                            # bank exhausted (fewer topics than n)
        pick = rng.choices(pool, weights=[_weight(q, topic_scores) for q in pool], k=1)[0]
        chosen.append(pick)
        used_topics.add(pick.topic_id)
    # a relaxed slot may hold a different level: a stable sort keeps the easy -> hard arc
    rank = {"easy": 0, "medium": 1, "hard": 2}
    return sorted(chosen, key=lambda q: rank.get(q.difficulty, 1))
