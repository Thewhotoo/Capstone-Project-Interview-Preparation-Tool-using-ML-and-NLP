"""Smoke test: can Qwen3-8B (4-bit) run on this machine, how fast, and does it follow the format?

Not the question-bank generator (see mcq_tobedone.md) -- just the feasibility check:
load in 4-bit, report VRAM / RAM / load time, generate one open question and one MCQ
for a topic from its retrieved slide sections, and report tokens per second.

    python -m slide_rag.llm_smoke_test --subject os --topic "Banker's algorithm"
"""
from __future__ import annotations

import argparse
import json
import re
import time

MODEL_ID = "Qwen/Qwen3-8B"

PROMPT = """You write technical interview questions for computer-science students, using ONLY the lecture slide material below.

Topic: {topic}

Slide material:
<<<
{context}
>>>

Return ONLY a JSON object with this exact structure:
{{
  "open_question": {{
    "question": "an interview-style why/how/compare question about the topic",
    "reference_answer": "a 3-5 sentence answer supported by the slide material",
    "key_points": ["3-5 short points a good answer must mention"],
    "misconceptions": ["2 common wrong ideas students have about this"]
  }},
  "mcq": {{
    "question": "a question with exactly one correct option",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "answer": "A|B|C|D",
    "explanation": "one sentence, supported by the slide material"
  }}
}}"""


def ram_free_gb() -> float:
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys / 1e9


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", default="os")
    ap.add_argument("--topic", default="Banker's algorithm")
    ap.add_argument("--max-new-tokens", type=int, default=900)
    args = ap.parse_args()

    # 1. slide context (retrieval runs first, then its models are released)
    from .retrieve import retrieve
    hits = retrieve(args.subject, args.topic, top_k=3)
    context = "\n\n".join(f"[{h['title']}, p.{h['page_start']}-{h['page_end']}]\n{h['text']}" for h in hits)[:6000]
    print("sections:", [(h["title"], h["page_start"], h["page_end"]) for h in hits])
    import gc
    import torch
    from . import retrieve as r
    r._embedder.cache_clear(); r._reranker.cache_clear(); r.load.cache_clear()
    gc.collect(); torch.cuda.empty_cache()

    # 2. load in 4-bit
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    print(f"RAM free before load: {ram_free_gb():.1f} GB")
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, device_map="cuda", dtype=torch.bfloat16,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_compute_dtype=torch.bfloat16,
                                               bnb_4bit_use_double_quant=True)).eval()
    print(f"loaded in {time.time() - t0:.0f}s | VRAM {torch.cuda.memory_allocated() / 1e9:.2f} GB "
          f"(peak {torch.cuda.max_memory_allocated() / 1e9:.2f}) | RAM free {ram_free_gb():.1f} GB")

    # 3. generate (thinking mode off: we want direct JSON)
    messages = [{"role": "user", "content": PROMPT.format(topic=args.topic, context=context)}]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    inputs = tok(text, return_tensors="pt").to("cuda")
    t1 = time.time()
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False,
                             repetition_penalty=1.05)
    new = out[0, inputs["input_ids"].shape[1]:]
    secs = time.time() - t1
    answer = tok.decode(new, skip_special_tokens=True)
    print(f"prompt {inputs['input_ids'].shape[1]} tokens | generated {len(new)} tokens in {secs:.1f}s "
          f"= {len(new) / secs:.1f} tok/s | VRAM peak {torch.cuda.max_memory_allocated() / 1e9:.2f} GB")

    # 4. did it follow the format?
    m = re.search(r"\{.*\}", answer, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
        print("valid JSON:", data is not None)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except json.JSONDecodeError as e:
        print("JSON parse failed:", e)
        print(answer)


if __name__ == "__main__":
    main()
