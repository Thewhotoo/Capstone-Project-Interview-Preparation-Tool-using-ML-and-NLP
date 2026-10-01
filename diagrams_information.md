# Diagrams information (slide-sized)

Each diagram must fit **one 16:9 slide** with **readable text**, so every section below is deliberately small: about 10–15 boxes, short labels, and only the key fields. The full detail (every field, every relationship) is in `final_context.md` §5, for the written report.

## Rules to give the LLM with every diagram

Paste this block before each section:

> Draw this as **PlantUML**. It must fit one 16:9 slide and stay readable when projected:
> - Use exactly the elements and labels given; add nothing, and leave nothing out.
> - Use `skinparam defaultFontSize 16`, `skinparam shadowing false`, `skinparam linetype ortho`.
> - Use `left to right direction` unless the section says otherwise.
> - Keep every label under ~6 words. Don't show getters, IDs or timestamps.
> - Group with `package` / `rectangle` only where the section says so.

---

## 1. Master diagram: whole-system overview (12 boxes)

One picture of the entire project: what the candidate touches, the modules behind it, where data is stored, and the offline pipeline that feeds the question bank.

**Prompt:** "Using the rules above, draw a system overview as a PlantUML component diagram (`left to right direction`). Use the 4 groups as `rectangle` blocks, the boxes inside them as `component`s, the stores as `database`s, and the candidate as an `actor`. Draw only the arrows listed, with their labels. Make it fit one 16:9 slide."

**Actor:** Candidate

**Group A: Browser** (left)
| Box | Label inside |
|---|---|
| Web UI | Login, Home, Interview, Reports |
| Proctoring | Webcam monitor + session rules |

**Group B: Flask Server** (centre, the largest block)
| Box | Label inside |
|---|---|
| Web API | Flask routes, login guard |
| Resume Engine | 8-stage parser → Candidate Profile |
| Round 1: Resume Discussion | Planner + 10 resume questions |
| Answer Evaluator | DeBERTa-v3 (0.8) + heuristic (0.2) |
| Round 2: Technical Interview | 8 questions, NLI grader, follow-ups |
| Reports & Insights | Combined report, history, Focus next |

**Group C: Storage** (right)
| Box | Type |
|---|---|
| SQLite Database | `database`: users, resumes, sessions, turns |
| Question Bank | `database`: 422 questions (132 curated served) |

**Group D: Offline Pipeline** (bottom, dashed border, label "built once, offline")
| Box | Label inside |
|---|---|
| Lecture Slides → Slide RAG | ~5,800 slides → sections → index |
| Question Generator | Qwen3-8B: generate, verify, rank, curate |

**Arrows**
| From | To | Label |
|---|---|---|
| Candidate | Web UI | uses |
| Proctoring | Web UI | violations end interview |
| Web UI | Web API | HTTP / JSON |
| Web API | Resume Engine | resume upload |
| Resume Engine | Round 1: Resume Discussion | Candidate Profile |
| Round 1: Resume Discussion | Answer Evaluator | each answer |
| Web API | Round 2: Technical Interview | start / answers |
| Round 2: Technical Interview | Question Bank | selects questions |
| Web API | SQLite Database | saves every turn |
| SQLite Database | Reports & Insights | history |
| Lecture Slides → Slide RAG | Question Generator | slide sections |
| Question Generator | Question Bank | writes JSON |

**Optional note on the slide:** "No GPU or LLM needed during an interview; generation runs offline."

---

## 2. Class diagram (13 classes)

**Prompt:** "Using the rules above, draw a UML class diagram. Show each class with only the attributes and methods listed. Draw the relationships exactly as listed, with multiplicities. Use 3 packages: *Data*, *Round 1*, *Round 2*."

**Package *Data***
| Class | Attributes | Methods |
|---|---|---|
| User | email, role | check_password() |
| Resume | parsed_profile, is_current | — |
| InterviewSession | type, status, overall_score | — |
| SessionTurn | question, answer, score | — |

**Package *Round 1***
| Class | Attributes | Methods |
|---|---|---|
| CandidateProfile | projects, experience, skills | — |
| Planner | — | plan_next(), advance() |
| QuestionSpecification | category, grounding | — |
| «interface» Evaluator | name | evaluate() |
| AveragedEvaluator | weight = 0.8 / 0.2 | evaluate() |
| EvaluationResult | overall_score, grade, dimensions | — |

**Package *Round 2***
| Class | Attributes | Methods |
|---|---|---|
| Question | subject, difficulty, key_points | — |
| TechInterview | mode, questions | submit(), summary() |
| Grade | score, covered, missing | — |

**Relationships**
| From | To | Type | Multiplicity |
|---|---|---|---|
| User | Resume | association | 1 → 0..* |
| User | InterviewSession | association | 1 → 0..* |
| InterviewSession | SessionTurn | composition | 1 → 0..* |
| Resume | CandidateProfile | composition (stored) | 1 → 1 |
| CandidateProfile | Planner | input to | 1 → 1 |
| Planner | QuestionSpecification | creates | 1 → 0..* |
| AveragedEvaluator | Evaluator | implements (dashed, hollow arrow) | — |
| Evaluator | EvaluationResult | produces | 1 → 1 per answer |
| TechInterview | Question | aggregation | 1 → 8..10 |
| TechInterview | Grade | produces | 1 → 1 per answer |

**Optional note on the slide:** "AveragedEvaluator = 0.8 × fine-tuned DeBERTa-v3 + 0.2 × heuristic"

---

## 3. Use case diagram (3 actors, 11 use cases)

**Prompt:** "Using the rules above, draw a UML use case diagram. Put the use cases in one system boundary named 'Interview Prep Platform'. Use `top to bottom direction`. Draw only the associations, «include» and «extend» relationships listed."

**Actors**
- **Candidate** (left side)
- **Proctor System**: webcam and session rules (right side)
- **Developer**: offline (right side, bottom)

**Use cases**
| ID | Use case | Connected actor |
|---|---|---|
| U1 | Sign up & upload resume | Candidate |
| U2 | Log in | Candidate |
| U3 | Take Full Interview | Candidate |
| U4 | Take Technical Interview | Candidate |
| U5 | Answer question (text or voice) | (included) |
| U6 | Answer follow-up | (extends U5) |
| U7 | View report & history | Candidate |
| U8 | Camera setup check | Candidate, Proctor System |
| U9 | Monitor attention & liveness | Proctor System |
| U10 | Terminate on rule violation | Proctor System |
| U11 | Generate question bank | Developer |

**Relationships**
- U3 «include» U8, U3 «include» U5
- U4 «include» U8, U4 «include» U5
- U6 «extend» U5 (when a key point is missing)
- U9 «extend» U3 and U4
- U10 «extend» U9 (on tab switch / leaving full screen / copy-paste)

---

## 4. Sequence diagrams (4 scenarios, one slide each)

| # | Scenario | Shows |
|---|---|---|
| 4.1 | Full Interview (end to end) | The overall flow across both rounds |
| 4.2 | Sign up & resume parsing | Account creation and the 8-stage resume parse |
| 4.3 | Technical answer with a follow-up | How Round 2 grades an answer and asks a follow-up |
| 4.4 | Proctoring violation | How a tab switch ends the interview |

Prompt for every scenario: "Using the rules above, draw a UML sequence diagram (top to bottom, no `left to right`). Use only these participants and numbered messages. Draw the `loop` / `alt` / `opt` boxes where marked. Use solid arrows for requests and dashed arrows for replies. Use `autonumber`."

### 4.1 Full Interview (6 participants, 16 messages)

Draw two `loop` boxes and one `opt` box.

**Participants (left to right):** Candidate (actor) · Browser · Flask API · Round 1 Engine · Round 2 Engine · Database

**Messages**
1. Candidate → Browser: log in, choose resume
2. Browser → Flask API: POST /api/resumes/<id>/use
3. Flask API --> Browser: candidate profile
4. Browser → Browser: camera check + full screen
5. Browser → Flask API: POST /resume-discussion-v2/start
6. Flask API → Round 1 Engine: start_conversation()
7. Round 1 Engine --> Browser: first question

**`loop` — 10 Round 1 questions**
8. Browser → Flask API: POST /reply (answer)
9. Flask API → Round 1 Engine: evaluate + plan next
10. Flask API → Database: save turn
11. Flask API --> Browser: score + next question

**Round 2**
12. Browser → Flask API: POST /tech-interview/start
13. Flask API → Round 2 Engine: select 8 questions

**`loop` — 8 Round 2 questions**
14. Browser → Flask API: POST /answer → Flask API → Round 2 Engine: grade answer
    - **`opt` [key point missing]:** Round 2 Engine --> Browser: follow-up question
15. Flask API → Database: save turn

**End**
16. Browser → Flask API: POST /end → Flask API --> Browser: combined report

**Note box beside the diagram:** "Any tab switch / leaving full screen ends the interview."

### 4.2 Sign up & resume parsing (5 participants, 9 messages)

**Participants:** Candidate (actor) · Browser · Flask API · Resume Engine · Database

**Messages**
1. Candidate → Browser: fill 3-step signup + attach resume
2. Browser → Flask API: POST /api/auth/signup (form + resume)
3. Flask API → Flask API: validate fields
4. Flask API → Database: check email not taken
5. Flask API → Resume Engine: parse resume (8 stages)
6. Resume Engine --> Flask API: Candidate Profile

**`alt` [resume unreadable]**
7a. Flask API --> Browser: 400 error, nothing saved

**`else` [parsed OK]**
7b. Flask API → Database: save User, Profile, Resume
8. Flask API --> Browser: 201 Created, logged in
9. Browser → Browser: show Home

### 4.3 Technical answer with a follow-up (6 participants, 11 messages)

**Participants:** Candidate (actor) · Browser · Flask API · TechInterview · NLI Grader · Database

**Messages**
1. Candidate → Browser: type answer
2. Browser → Flask API: POST /tech-interview/<id>/answer
3. Flask API → TechInterview: submit(answer)
4. TechInterview → NLI Grader: grade each key point
5. NLI Grader --> TechInterview: covered / partial / missing

**`alt` [all key points covered]**
6a. TechInterview --> Browser: next question

**`else` [a key point is missing]**
6b. TechInterview --> Browser: follow-up question
7. Candidate → Browser: answer follow-up
8. Browser → Flask API: POST /answer (follow-up)
9. TechInterview → NLI Grader: check follow-up answer
10. NLI Grader --> TechInterview: point recovered (0.75 credit)

**After the `alt`**
11. Flask API → Database: save turn → Flask API --> Browser: next question

**Note:** "At most 2 follow-ups per question."

### 4.4 Proctoring violation (5 participants, 9 messages)

**Participants:** Candidate (actor) · Proctor (in browser) · Browser UI · Flask API · Database

**Messages**
1. Proctor → Proctor: rules armed, webcam monitoring on

**`opt` [looking away > 8.5 s]**
2. Proctor → Browser UI: attention warning (lowers attention score)

**Violation**
3. Candidate → Browser UI: switches tab / leaves full screen
4. Browser UI → Proctor: visibility / full-screen change event
5. Proctor → Proctor: record violation (type, round, question)
6. Proctor → Browser UI: show "Session terminated", disable input
7. Browser UI → Flask API: POST /end {integrity: terminated}
8. Flask API → Database: save session as terminated
9. Flask API --> Browser UI: report with termination banner

**Note:** "Zero tolerance: the first violation ends the interview."

---

## 5. Package diagram (9 packages)

**Prompt:** "Using the rules above, draw a UML package diagram (top to bottom). Draw the packages as folders with the 2–3 contents listed inside each. Draw dependencies as dashed arrows labelled «use». Arrange in 3 rows: UI → Application → Data, with the Offline Pipeline on the right."

**Packages**
| Row | Package | Contents (show inside) |
|---|---|---|
| UI | **Frontend** | index.html, webcam monitor, session rules |
| Application | **Web API** | app.py, account routes, session routes |
| Application | **Resume Engine** | 8-stage parser, profile mapper |
| Application | **Round 1** | planner, question realizer, conversation engine |
| Application | **Evaluation** | evaluators, answer gate, feedback |
| Application | **Technical Interview** | selector, NLI grader, follow-ups |
| Data | **Persistence** | SQLite models, session history |
| Data | **Question Bank** | 422 questions (JSON) |
| Right side | **Offline Pipeline** | slide RAG, question generation |

**Dependencies («use»)**
- Frontend → Web API
- Web API → Resume Engine, Round 1, Technical Interview, Persistence
- Round 1 → Evaluation
- Technical Interview → Question Bank
- Offline Pipeline → Question Bank

---

## 6. Deployment diagram (3 physical nodes + cloud)

**Package = how the code is organised; Deployment = where the code runs.** This diagram shows physical machines, the software deployed on each, and how they talk.

**Prompt:** "Using the rules above, draw a UML deployment diagram (top to bottom). Draw each physical node as a 3D box (`node`). Inside it, draw its execution environment and the deployed components/artifacts listed, and draw the database as a `database` shape. Label every connection with its protocol."

**Nodes**
| Node (physical) | Execution environment | Deployed on it |
|---|---|---|
| **Client Device** (laptop with webcam + mic) | Web browser (Chrome / Edge) | Web UI (index.html), MediaPipe face tracking, speech-to-text |
| **Application Server** (Python 3.12) | Flask server (port 5000) | Flask app, AI models (DeBERTa-v3, NLI, MiniLM), question bank (JSON); **database inside this node:** SQLite `app.db` + uploaded resumes |
| **Offline GPU Machine** (RTX 5050 laptop) | Ollama + Python | Qwen3-8B, slide pipeline (builds the question bank) |
| **Cloud** (small cloud icon) | — | jsDelivr CDN (MediaPipe), GitHub (code + model weights) |

**Connections**
| From | To | Protocol / label |
|---|---|---|
| Client Device | Application Server | HTTP / JSON |
| Flask app | SQLite database (inside the server node) | SQL via SQLAlchemy |
| Client Device | Cloud (CDN) | HTTPS: MediaPipe library |
| Offline GPU Machine | Cloud (GitHub) | Git push: question bank JSON |
| Application Server | Cloud (GitHub) | Git pull: code + weights (Git LFS) |

**Optional note on the slide:** "Webcam frames never leave the client device; no GPU needed at interview time."
