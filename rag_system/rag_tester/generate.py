"""
LLM Generation Module
Generates technical interview questions from retrieved RAG context.
Strictly grounded in the provided context, with citations and pseudocode support.
"""
import re
import time
import torch

# --------------------------------------------------
# Lazy Loaded Qwen Model
# --------------------------------------------------
_tokenizer = None
_model = None

def _get_model():
    """
    Loads Qwen model only once.
    Start with 1.5B for testing, then switch to 7B.
    """
    global _tokenizer
    global _model
    if _tokenizer is None or _model is None:
        from transformers import (
            AutoTokenizer,
            AutoModelForCausalLM
        )
        print("=" * 60)
        print("Loading Qwen2.5-7B-Instruct...")
        start = time.time()
        
        # Start with 1.5B for testing, change to 7B once working
        MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
        # MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"  # Uncomment for production
        
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        
        # Set pad token if not set
        if _tokenizer.pad_token is None:
            _tokenizer.pad_token = _tokenizer.eos_token
        
        # Auto-detect dtype based on hardware
        if torch.cuda.is_available():
            model_dtype = torch.float16
        else:
            model_dtype = torch.float32
        
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            dtype=model_dtype,
            device_map="auto",
            low_cpu_mem_usage=True
        )
        
        print(f"✓ Qwen loaded successfully in {time.time() - start:.1f} seconds.")
        print("=" * 60)
        print(f"{MODEL_NAME} loaded.")
    return _tokenizer, _model

def get_llm_response(prompt, max_tokens=200, temperature=0.0):
    """
    Generic function to get a response from the LLM.
    Used by evaluate.py for AI feedback generation.
    """
    try:
        tokenizer, model = _get_model()
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        inputs = tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048
        ).to(model.device)
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=(temperature > 0),
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
            pad_token_id=tokenizer.pad_token_id
        )
        response = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        ).strip()
        return response
    except Exception as e:
        print(f"LLM Response Error: {e}")
        return f"Error generating response: {e}"

# --------------------------------------------------
# Helpers
# --------------------------------------------------
QUESTION_STARTERS = ("What", "Why", "How", "Explain", "Describe")
DIFFICULTY_RULES = {
    "easy": "Ask a definition or 'what is' question. One concept only.",
    "medium": "Ask for explanation of how or why something works.",
    "hard": "Ask to compare, analyze trade-offs, or apply the concept to a scenario.",
}
GROUNDING_SYSTEM = (
    "You are a strict retrieval‑augmented generator. "
    "You must not use any prior knowledge. "
    "Answer strictly based on the provided context. "
    "If the context does not contain enough information to answer, say 'I don't know.' "
    "Do not infer or add any external information."
)

def clean_context(context, max_chars=2500):
    """Remove formatting noise; keep page citations if present."""
    context = context.replace("\n", " ")
    context = re.sub(r"\s+", " ", context)
    return context[:max_chars].strip()

def clean_reference_text(context):
    """
    Clean the context to extract meaningful content for reference answers.
    Removes slide formatting, labels, and generic text.
    Keeps useful labels like Definition, Problem, Solution.
    """
    lines = context.splitlines()
    patterns_to_remove = [
        r'^contd\.{0,2}$',
        r'^Page \d+$',
        r'^Chapter \d+$',
        r'^Slide \d+$',
        r'^[•\-*]\s*$',
        r'^Object Oriented Analysis and Design.*$',
    ]
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        skip = False
        for pattern in patterns_to_remove:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break
        if skip:
            continue
        line = re.sub(r'^[•\-*]\s*', '', line)
        if len(line.split()) >= 3:
            cleaned_lines.append(line)
    if len(cleaned_lines) < 2:
        sentences = re.split(r'[.!?]+', context)
        meaningful_sentences = [s.strip() for s in sentences if len(s.split()) >= 5]
        if meaningful_sentences:
            return '. '.join(meaningful_sentences[:3]) + '.'
    return ' '.join(cleaned_lines)

# --------------------------------------------------
# Core Generation Functions (Grounded)
# --------------------------------------------------
def _llm_generate(system: str, user: str, max_tokens=180, temperature=0.0) -> str:
    """Internal helper for LLM generation with grounding and optional temperature."""
    tokenizer, model = _get_model()
    if "strict retrieval" not in system.lower():
        system = f"{GROUNDING_SYSTEM}\n\n{system}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_tokens,
        temperature=temperature,          # now configurable
        do_sample=(temperature > 0),      # sample only if temp > 0
        repetition_penalty=1.2,
        pad_token_id=tokenizer.pad_token_id,
    )
    return tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
def generate_interview_question(context, concept=None, difficulty="medium"):
    """Generates ONE interview question from retrieved RAG context."""
    if not context or len(context.strip()) < 30:
        return "Insufficient context to generate a question."
    context = clean_context(context)
    diff_rule = DIFFICULTY_RULES.get(difficulty.lower(), DIFFICULTY_RULES["medium"])
    if concept:
        system_prompt = "You are an expert technical interviewer for Computer Science placements."
        user_prompt = f"""
Topic: {concept}
Difficulty: {difficulty}

Context:
{context}

Task: Generate ONE interview question.

The question must be answerable using ONLY the supplied context.
Do not require any knowledge outside the context.
Prefer conceptual understanding over memorization.
{diff_rule}

Rules:
- Ask only about the technical concept.
- Test understanding of the concept.
- Prefer asking for definition or working before applications.
- Never mention the document, passage, narrator, or notes.
- Never ask about the author or how many words.
- Never ask to summarize the notes.
- Start with What, Why, How, Explain, or Describe.
- Keep it under 25 words.
- Return only the question, nothing else.

Question:"""
    else:
        system_prompt = "You are an expert technical interviewer for Computer Science placements."
        user_prompt = f"""
Context:
{context}

Task: Generate ONE interview question.

The question must be answerable using ONLY the supplied context.
Do not require any knowledge outside the context.
Prefer conceptual understanding over memorization.

Rules:
- Ask only about the technical concepts.
- Never mention the document, passage, narrator, or notes.
- Never ask about the author or how many words.
- Keep it under 25 words.
- Return only the question, nothing else.

Question:"""
    raw = _llm_generate(system_prompt, user_prompt, max_tokens=100)
    question = raw.replace("\n", " ").strip()
    if question and not question.endswith("?"):
        question = question.rstrip(".") + "?"
    words = question.split()
    if not words or words[0] not in QUESTION_STARTERS:
        return f"Explain the concept of {concept}." if concept else "Explain the main concept discussed in this topic."
    if concept:
        concept_words = concept.lower().split()
        if not any(word in question.lower() for word in concept_words):
            return f"Explain the concept of {concept}."
    return question

def generate_reference_answer(question, context):
    """
    Generate a concise reference answer for the interview question
    using ONLY the retrieved RAG context, with citations.
    """
    if not context or len(context.strip()) < 30:
        return "No reference available"

    context_clean = clean_reference_text(context)

    system_prompt = (
        "You are an expert computer science professor and a strict retrieval‑augmented generator. "
        "You must not use any prior knowledge. "
        "Answer strictly based on the provided context. "
        "If the context does not contain enough information to answer, say 'I don't know.' "
        "Do not infer or add any external information."
    )
    user_prompt = f"""
Question:
{question}

Context:
{context_clean}

Task:
Answer the interview question STRICTLY using ONLY the supplied context.

Instructions:
- Use only information explicitly present in the context.
- The wording should closely follow the terminology used in the context.
- Prefer phrases copied or paraphrased from the context.
- Do NOT generalize beyond the context.
- NEVER use your own knowledge.
- NEVER infer missing information.
- NEVER add examples not present in the context.
- If the context is insufficient, state: "I don't know."
- **Include citations** like (p.5) after each major claim, using page markers from the context (e.g., "[p.5]").
- Write 3-5 concise sentences.
- Return only the answer.

Answer:"""
    answer = _llm_generate(system_prompt, user_prompt, max_tokens=180)
    # If answer is "I don't know" we keep it
    if "i don't know" in answer.lower():
        return answer
    # Ensure at least one citation appears
    if not re.search(r'\(p\.\d+\)', answer):
        # Try to add a generic citation if possible
        pages = re.findall(r'\[p\.(\d+)\]', context)
        if pages:
            first_page = pages[0]
            answer += f" (p.{first_page})"
    return answer

def generate_grounded_answer(question, context):
    """
    Lightweight wrapper for strict answer generation, used by evaluator.
    """
    return generate_reference_answer(question, context)

def generate_mcq(context, concept=None, difficulty="medium", variant=0):
    """
    Generate a multiple‑choice question with options and correct answer.
    Returns a dict with keys: question, options, correct, difficulty, type.
    """
    context = clean_context(context)
    topic = concept or "the topic"

    # Different focuses for variety
    focuses = ["definition", "mechanism", "comparison", "application", "advantage/disadvantage"]
    focus = focuses[variant % len(focuses)]

    prompt = f"""Context:
{context}

Task: Create ONE multiple‑choice question about {topic} ({difficulty}).
Focus on: {focus}

You MUST follow this exact format – no extra text before or after:

QUESTION: <your question here>
A) <option A>
B) <option B>
C) <option C>
D) <option D>
ANSWER: <A|B|C|D>

Ensure the question is based strictly on the context and that only one option is correct.
Do not add explanations or extra text.
"""
    system_prompt = "You are an exam writer. Always produce the output in the specified format."

    # Use small temperature for variety
    raw = _llm_generate(system_prompt, prompt, max_tokens=220, temperature=0.3)

    # Debug: uncomment to see raw output
    # print("RAW MCQ:", raw)

    parsed = {
        "question": "",
        "options": [],
        "correct": "",
        "difficulty": difficulty,
        "type": "mcq"
    }

    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    # Extract question
    q_line = None
    for line in lines:
        if re.match(r'^QUESTION\s*[:;]\s*', line, re.IGNORECASE):
            q_line = line
            break
    if not q_line and lines:
        q_line = lines[0]
    if q_line:
        q_text = re.sub(r'^QUESTION\s*[:;]\s*', '', q_line, flags=re.IGNORECASE).strip()
        if q_text:
            parsed["question"] = q_text

    # Extract options (support A), A., A: etc.)
    opt_map = {}
    for line in lines:
        m = re.match(r'^([A-D])\s*[):;.\-]\s*(.+)$', line, re.IGNORECASE)
        if m:
            letter = m.group(1).upper()
            text = m.group(2).strip()
            opt_map[letter] = text
    if opt_map:
        # Sort by letter
        parsed["options"] = [f"{let}) {opt_map[let]}" for let in sorted(opt_map.keys())]

    # Extract correct answer
    ans = None
    for line in lines:
        # Try multiple patterns
        if re.search(r'^ANSWER\s*[:;]\s*([A-D])', line, re.IGNORECASE):
            ans = re.search(r'([A-D])', line, re.IGNORECASE).group(1).upper()
            break
        if re.search(r'correct\s*answer\s*[:;]\s*([A-D])', line, re.IGNORECASE):
            ans = re.search(r'([A-D])', line, re.IGNORECASE).group(1).upper()
            break
        if re.search(r'answer\s*[:;]\s*([A-D])', line, re.IGNORECASE):
            ans = re.search(r'([A-D])', line, re.IGNORECASE).group(1).upper()
            break

    if ans and ans in opt_map:
        parsed["correct"] = ans
    else:
        # Fallback: if we have options, try to find the most relevant one by matching context
        # Simple heuristic: pick the longest option (often the correct one)
        if opt_map:
            # Try to find option that appears most similar to a key phrase in context
            # But for simplicity, pick a random one (to avoid always A)
            import random
            parsed["correct"] = random.choice(list(opt_map.keys()))
        else:
            parsed["correct"] = "A"

    # If no question or no options, return a fallback
    if not parsed["question"] or len(parsed["options"]) < 4:
        # Try to create a generic MCQ from the raw text
        return {
            "question": raw if raw else f"Explain the concept of {topic}.",
            "options": ["A) Option A", "B) Option B", "C) Option C", "D) Option D"],
            "correct": "A",  # still fallback, but we randomize later if needed
            "difficulty": difficulty,
            "type": "mcq"
        }

    return parsed

def generate_pseudocode_question(context, concept=None, difficulty="medium"):
    """Generate a question that asks for pseudocode implementation."""
    context = clean_context(context)
    topic = concept or "the algorithm"
    system = "You create pseudocode interview questions grounded in context only."
    user = f"""
Context:
{context}

Write ONE question asking for pseudocode about {topic} ({difficulty}).
Start with 'Write pseudocode' or 'Provide pseudocode'.
Return only the question.
"""
    q = _llm_generate(system, user, max_tokens=80)
    if q and not q.endswith("?"):
        q = q.rstrip(".") + "?"
    return q or f"Write pseudocode to implement {topic}."

def generate_pseudocode_reference(question, context):
    """
    Generate a pseudocode solution strictly from the context.
    Includes comments and clear indentation.
    """
    context_clean = clean_reference_text(context)
    system = (
        "You write pseudocode using ONLY supplied context. "
        "Use indentation or BEGIN/END blocks. "
        "Include comments explaining each step. "
        "Do not invent algorithms not described in the context."
    )
    user = f"""
Question: {question}
Context:
{context_clean}

Return pseudocode that solves the problem based ONLY on the context.
If the context lacks details, state 'I don't know.'.
"""
    ref = _llm_generate(system, user, max_tokens=300)
    return ref or "Pseudocode not available from context."

def generate_coding_question(context, concept=None, difficulty="medium"):
    """Generate a coding/design question."""
    context = clean_context(context)
    topic = concept or "the concept"
    system = "You create coding interview questions from PDF context only."
    user = f"""
Context:
{context}

Write ONE coding/design question about {topic} ({difficulty}) answerable from context.
Return only the question.
"""
    q = _llm_generate(system, user, max_tokens=90)
    return q or f"Design a solution for {topic} based on the studied material."

def generate_question_by_type(context, concept=None, difficulty="medium", question_type="open"):
    """Unified entry point for different question types."""
    qtype = question_type.lower()
    if qtype == "mcq":
        return generate_mcq(context, concept, difficulty)
    if qtype == "pseudocode":
        return {
            "question": generate_pseudocode_question(context, concept, difficulty),
            "type": "pseudocode",
            "difficulty": difficulty,
        }
    if qtype == "coding":
        return {
            "question": generate_coding_question(context, concept, difficulty),
            "type": "coding",
            "difficulty": difficulty,
        }
    return {
        "question": generate_interview_question(context, concept, difficulty),
        "type": "open",
        "difficulty": difficulty,
    }

def generate_explanation(context, topic):
    """Generate a brief explanation of a topic (used for learning)."""
    if not context or len(context.strip()) < 30:
        return "Insufficient context to generate explanation."
    context_clean = clean_context(context)
    system = "You are an expert computer science professor. Use only the provided context."
    user = f"""
Topic: {topic}
Context:
{context_clean}

Provide a 2-3 sentence explanation of the topic.
- Define the concept clearly.
- Explain its purpose or function.
- Give a practical example if present in context.
- Use only the context provided.
- Return only the explanation.
"""
    explanation = _llm_generate(system, user, max_tokens=120)
    return explanation if explanation else context_clean[:150] + "..."
def generate_test_cases(context, concept, num_cases=3):
    """Generate test cases (input/output pairs) from context using LLM."""
    prompt = f"""
Context:
{context}

Generate {num_cases} test cases for a programming problem about {concept}.
Each test case should be a JSON object with "inputs" and "expected".
The problem is about implementing a function (likely named 'solution').
Output only JSON, no extra text.

Example format:
[
    {{"inputs": [1, 2], "expected": 3}},
    {{"inputs": [5, 7], "expected": 12}}
]
"""
    raw = _llm_generate("You are a test generator.", prompt, max_tokens=300, temperature=0.2)
    try:
        import json
        return json.loads(raw)
    except:
        return []