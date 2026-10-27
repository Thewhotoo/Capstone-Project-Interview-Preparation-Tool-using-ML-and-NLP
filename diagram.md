# Architecture diagram: AI Resume-Grounded Interview Platform

Create a **clean architecture diagram** showing the 4 modules, how they connect, and the flow of one interview. Keep it simple: **about 14 boxes**, short labels, clear arrows, no extra detail.

## Layout (top → bottom)

**Row 1: Candidate (browser)**, one wide box at the top:
- "Candidate's Browser". Inside it, 3 small boxes: **"Interview UI"**, **"Webcam Proctoring"** (orange), **"Voice Recording"** (orange).

**Row 2: App Server**, a large container labelled **"App Server (Flask, local AI models)"** holding the 4 modules side by side:

| Module (colour) | Boxes inside, connected left → right with arrows |
|---|---|
| **Module 1: Resume Intelligence** (blue) | "Resume Parser" → "Candidate Profile" → "Round 1: Resume Interview" |
| **Module 2: Technical Interview & Evaluation** (green) | "Question Bank" → "Round 2: Technical Interview" → "Answer Grader" |
| **Module 3: Proctoring & Voice** (orange) | "Integrity Rules" and "Speech-to-Text (Whisper)" |
| **Module 4: Accounts & Data** (purple) | "Login / Signup" and "Report & Progress" |

**Row 3: Storage (Module 2, infrastructure)**, two cylinders at the bottom:
- **"PostgreSQL"**: users, resumes, sessions
- **"Redis"**: interviews in progress

**Left side, separate dashed box: "Offline (built once, GPU)"**
- "Lecture Slides" → "Slide RAG (search)" → "LLM Question Generation" → arrow into **"Question Bank"** in Module 2.

## Arrows between modules (keep only these)

1. Interview UI → **Login / Signup** → **Resume Parser** (label: "upload resume")
2. **Candidate Profile** → **Round 1** (label: "questions from resume")
3. **Round 1** → **Answer Grader** (label: "score answers")
4. **Round 1** → **Round 2** (label: "next round")
5. **Answer Grader** → **Report & Progress** (label: "scores + feedback")
6. **Voice Recording** → **Speech-to-Text** → Interview UI (label: "answer text")
7. **Webcam Proctoring** → **Integrity Rules** → **Report & Progress** (label: "attention score / violations")
8. **Module 4** → **PostgreSQL** (label: "save everything")
9. **Round 1** and **Round 2** → **Redis** (label: "live state")

## Style

- **Look:** flat, modern, white background.
- **Modules:** rounded rectangles, each module a light tint of its colour. Module 1 blue, Module 2 green, Module 3 orange, Module 4 purple.
- **Text and arrows:** large readable sans-serif text; thin dark-grey arrows with small labels.
- **Labels:** each module's title, e.g. "Module 1: Resume Intelligence", in bold at the top of its box.
- **Footer:** a small line at the bottom: "Runs locally with Docker · No paid APIs".
- **Avoid:** icons, people, 3D and extra boxes not listed above.

---

## Optional: the same diagram as Mermaid (for tools that render code)

```mermaid
flowchart TB
  subgraph B["Candidate's Browser"]
    UI["Interview UI"]
    CAM["Webcam Proctoring"]
    MIC["Voice Recording"]
  end

  subgraph OFF["Offline (built once, GPU)"]
    SL["Lecture Slides"] --> RAG["Slide RAG (search)"] --> GEN["LLM Question Generation"]
  end

  subgraph S["App Server (Flask, local AI models)"]
    subgraph M1["Module 1: Resume Intelligence"]
      P["Resume Parser"] --> CP["Candidate Profile"] --> R1["Round 1: Resume Interview"]
    end
    subgraph M2["Module 2: Technical Interview & Evaluation"]
      QB["Question Bank"] --> R2["Round 2: Technical Interview"] --> G["Answer Grader"]
    end
    subgraph M3["Module 3: Proctoring & Voice"]
      IR["Integrity Rules"]
      STT["Speech-to-Text (Whisper)"]
    end
    subgraph M4["Module 4: Accounts & Data"]
      L["Login / Signup"]
      REP["Report & Progress"]
    end
  end

  PG[("PostgreSQL")]
  RD[("Redis")]

  GEN --> QB
  UI -->|upload resume| L --> P
  R1 -->|score answers| G
  R1 -->|next round| R2
  G -->|scores + feedback| REP
  MIC --> STT -->|answer text| UI
  CAM --> IR -->|attention / violations| REP
  M4 -->|save everything| PG
  R1 & R2 -->|live state| RD

  classDef m1 fill:#dbeafe,stroke:#2563eb;
  classDef m2 fill:#dcfce7,stroke:#16a34a;
  classDef m3 fill:#ffedd5,stroke:#ea580c;
  classDef m4 fill:#f3e8ff,stroke:#9333ea;
  class P,CP,R1 m1;
  class QB,R2,G,PG,RD,SL,RAG,GEN m2;
  class IR,STT,CAM,MIC m3;
  class L,REP m4;
```
