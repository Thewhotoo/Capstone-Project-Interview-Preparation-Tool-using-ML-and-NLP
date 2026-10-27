# Answer-writing prompt (attach this file + your `<name>_questions.json` to your LLM)

## For the teammate (read first; the LLM can ignore this section)

1. Open a new chat with your LLM (ChatGPT, Gemini, Claude, … any).
2. Attach **this file** and **your questions file**: `nandu_questions.json`, `surya_questions.json`, `ninad_questions.json` or `mayuran_questions.json`.
3. Type: **"Follow ANSWER_PROMPT.md for the attached questions file."**
4. If it stops partway, type "continue from the last question_id" and paste the parts into one JSON array.
5. Save the result as `<name>_answers.json` in `grader_eval/real_set/` (e.g. `nandu_answers.json`).
6. **Check it yourself before sending it back** (about 15 minutes):
   - Do the answers sound like real students, not textbook paragraphs?
   - Are the labels fair? Mark `covered` only if the point is really there and correct.
   - Fix anything you disagree with. Your corrections are what make this data valuable.

---

## Instructions for the LLM

You are helping build a test set for an **automatic grader of technical interview answers** (Computer Networks, DBMS, DSA, OOAD, Operating Systems). The grader will be judged against your answers and your marks, so they must look like **real students answering in a real interview**, not like an AI.

The attached JSON file has 50 questions. For **each question, write exactly ONE answer**, playing a different student each time.

### 1. Sound like a real human, not an AI
Real students answering out loud or typing quickly in an interview:
- **don't** write polished, perfectly structured paragraphs, bullet points, headings or markdown;
- often use lowercase, skip punctuation, make small typos and grammar slips ("its" for "it's", "teh");
- use casual phrasing: "so basically…", "i think", "like", "yeah so", "if i remember right…";
- give **examples** instead of definitions ("like when you open a website…");
- **ramble or repeat themselves**, go slightly off track, then come back;
- explain in their **own words** and almost never repeat the textbook wording of the key points;
- sometimes answer only part of the question and stop;
- vary a lot in length: some reply in 1 line, some in 5–6 sentences;
- are not always confident: "not 100% sure but…", "i might be wrong".

**Never** use phrases an AI would use ("Certainly!", "In summary", "It is important to note", "Great question"). Never mention key points, labels or that you are an AI.

### 2. Use the style given in each question's `target_style`
Each question tells you which kind of answer to write:

| `target_style` | What to write |
|---|---|
| `good` | Correct and complete: covers every key point, in natural student language |
| `good_own_words` | Correct and complete, but in the student's own words, with an analogy or example, wording very different from the key points |
| `partial` | Gets 1–2 key points right, leaves the others out or gets them vague |
| `short_casual` | 1–2 short, casual lines; may be right, half-right or thin (vary it) |
| `hesitant` | Mostly correct but full of fillers (um, uh, like, you know), restarts and broken sentences |
| `confident_wrong` | Fluent and sure of itself, but contains a **real technical error** (swapped definitions, wrong mechanism, wrong reason). Not obviously silly |
| `vague` | Sounds relevant and uses the right buzzwords but says nothing specific |
| `off_topic` | Answers a related but different question (e.g. explains TCP when asked about UDP) |
| `dont_know` | Honestly doesn't know; may guess a few words ("no idea… something to do with memory?") |

### 3. Mix everything up
Across the 50 answers, vary **everything**: length, tone (nervous, casual, confident, rushed), structure, vocabulary and the kind of example used. **No two answers should start the same way or follow the same pattern.** Imagine 50 different students from different colleges. Some answers should feel like they were spoken (fillers, run-on sentences), others typed quickly (lowercase, abbreviations like "bcz", "w/o", "eg").

### 4. Answer the follow-up too
Each question has a `followup_question` (what the interviewer asks next) and `followup_expected` (the correct idea). Write the **same student's** reply, following `target_followup`:
- `correct`: gets the idea right (any wording, can be short, even "yeah, it does because…")
- `partly_correct`: half right or imprecise
- `wrong`: confidently wrong
- `dont_know`: "not sure", "i don't remember"

Keep follow-up replies short (a few words to 2 sentences), like a real quick reply.

### 5. Mark your own answer fairly (as a fair human interviewer would)
- **`labels`**: for **every** key point of that question, in the **same order** as `key_points`:
  - `covered`: clearly and **correctly** stated, in any wording;
  - `partial`: touched on but incomplete or imprecise;
  - `missing`: absent, **or stated wrongly**.
- **`overall`**: a score from 0 to 1 for the main answer, as a fair interviewer would give it. Rough guide: complete and correct ≈ 0.9–1.0; mostly right ≈ 0.6–0.8; half ≈ 0.4–0.5; little ≈ 0.1–0.3; wrong / off-topic / don't know ≈ 0–0.1.
- **`followup_correct`**: `true` if the follow-up reply is right (any wording), `false` otherwise.

Be honest in marking: a fluent but wrong answer gets low labels and a low `overall`.

### 6. Output format
Output **only** a JSON array with one object per question, in the same order as the file:

```json
[
  {
    "question_id": "copied exactly from the file",
    "style": "the target_style you used",
    "answer": "the student's answer",
    "labels": ["covered", "missing", "partial"],
    "overall": 0.45,
    "followup": {
      "question": "copied from followup_question",
      "answer": "the student's short reply",
      "correct": false
    }
  }
]
```

Rules:
- `labels` must have **exactly** as many entries as that question's `key_points`.
- Copy `question_id` exactly.
- No markdown inside the strings, and no text outside the JSON array.
- If the reply is too long for one message, stop after a complete object; continue when asked.
