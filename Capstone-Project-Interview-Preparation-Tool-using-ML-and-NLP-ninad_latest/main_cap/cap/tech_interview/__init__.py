"""Technical interview engine (Phase 2).

Concept questions from the slide-grounded question bank
(rag_system/rag_tester/question_bank), asked one at a time, each answer graded
against the question's key points, with at most MAX_FOLLOWUPS follow-ups per
main question when the answer is unclear or misses a key point.

    bank.py      load the ACTIVE questions of the bank (read-only, cached)
    selector.py  pick a session's questions: different topics, spread across
                 subjects, a difficulty arc, no repeats for the user, weak
                 topics weighted up
    grader.py    score an answer: key-point coverage by meaning + similarity to
                 the reference answer + clarity signals (fillers, "I don't
                 know", too short, vague)
    followup.py  after each answer: move on, ask for clarification, or ask the
                 prepared follow-up for a missing key point
    session.py   one live interview (in memory; each finished main question is
                 saved to the database by session_history)

Nothing here generates text or needs a GPU: questions and follow-ups were
written offline; grading uses the small MiniLM embedding model.
"""
