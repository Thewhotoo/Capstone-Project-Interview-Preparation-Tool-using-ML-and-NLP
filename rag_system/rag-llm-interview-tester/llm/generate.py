from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")


def generate_question(context):
    prompt = f"""
Generate ONE technical interview question based on the concept below.

STRICT RULES:
- Output ONLY the question
- Do NOT include explanations
- Do NOT repeat instructions
- The question MUST mention the concept explicitly
- It must be a computer science interview question

Example:
Input: Deadlock is a situation where processes wait indefinitely...
Output: What is deadlock in operating systems and what are its necessary conditions?

Now generate:

{context}
"""

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True)

    outputs = model.generate(
        **inputs,
        max_length=64,
        do_sample=False,
        temperature=0.3   # 🔥 reduces randomness
    )

    result = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # 🔥 SAFETY FILTER (fix garbage outputs)
    if len(result.split()) < 5 or "generate" in result.lower():
        return f"What is {context.split()[0]} and how does it work in computer systems?"

    return result