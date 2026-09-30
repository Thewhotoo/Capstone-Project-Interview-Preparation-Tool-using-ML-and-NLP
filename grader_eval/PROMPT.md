# Grader evaluation set: instructions for the LLM

**Round 2 (100 questions):** attach `questions.json` and save the reply as
`output_questions.json`. If the LLM stops partway (400 answers is long), ask it to continue
from the last question_id and paste the parts into the same JSON array.
(The first 25-question test, used to tune the grader, is in `tuning_set/`; leave it alone.)

---

For each of the 100 questions in the attached file, write 4 candidate answers as a student would
**speak** them in a technical interview. Use these styles, spread across the set:

- `good`: correct and complete, all key points
- `good_paraphrase`: correct and complete, but in the student's own words or with an example, not the key points' wording
- `partial`: gets some key points right and leaves the others out
- `vague`: sounds relevant but says nothing specific
- `confident_wrong`: fluent and confident, but contains a real technical error
- `hesitant`: mostly correct, but with fillers (um, uh, like, you know) and broken sentences
- `off_topic`: answers a different question
- `dont_know`: says they don't know (use rarely, ~5 in total)

Every question gets one `good` or `good_paraphrase`, one `partial`, and two other styles.
Answers are 2–6 sentences; no markdown; no mention of "key points".

For each answer, label **every key point** of that question, in the same order as `key_points`:
- `covered`: the answer clearly and correctly states it (any wording)
- `partial`: touches on it but is incomplete or imprecise
- `missing`: absent, or stated wrongly

Also give `overall` from 0 to 1: how a fair interviewer would score the answer.

Output **only** a JSON array, one object per answer:

```json
[
  {
    "question_id": "copied exactly from the attached file",
    "style": "partial",
    "answer": "the spoken answer",
    "labels": ["covered", "missing", "partial"],
    "overall": 0.4
  }
]
```

`labels` must have exactly as many entries as that question's `key_points`.

---

Then check the output yourself, especially the labels, and fix any you disagree with.
Save it as `grader_eval/output_questions.json`.
