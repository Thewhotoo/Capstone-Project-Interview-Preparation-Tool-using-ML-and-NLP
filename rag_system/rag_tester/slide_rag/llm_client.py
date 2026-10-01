"""Local LLM client for offline generation, backed by Ollama (llama.cpp engine).

Why Ollama: Qwen3-8B in GGUF Q4_K_M under llama.cpp is ~2-3x faster on an 8 GB
GPU than transformers + bitsandbytes, and needs no model loading in Python.

Safety rails:
  * num_ctx is set explicitly. Ollama silently drops the START of a prompt that
    doesn't fit its context window, so every prompt is token-counted first
    (Qwen3 tokenizer) and a prompt that wouldn't fit raises PromptTooLong; the
    server's own prompt_eval_count is also checked afterwards.
  * JSON output is constrained by a JSON schema (`format`), so replies parse by
    construction.
  * Reproducible: fixed seed and temperature, `think` set explicitly, and
    keep_alive long enough that the model stays loaded between topics.
  * `runtime_tag` (model + quantization) goes into cache keys, so outputs from a
    different runtime are never mixed in.

Needs: Ollama running (https://ollama.com) and `ollama pull qwen3:8b`.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from functools import lru_cache

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"            # Ollama's default tag is Q4_K_M
TOKENIZER_ID = "Qwen/Qwen3-8B"        # same tokenizer as the GGUF, used to count prompt tokens
NUM_CTX = 8192
THINK_BUDGET = 3000                   # extra output tokens reserved for thinking-mode reasoning
KEEP_ALIVE = "30m"
CHAT_TEMPLATE_OVERHEAD = 32           # role markers etc. added by the chat template


class PromptTooLong(RuntimeError):
    pass


class OllamaUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(TOKENIZER_ID)


def count_tokens(text: str) -> int:
    return len(_tokenizer()(text)["input_ids"]) + CHAT_TEMPLATE_OVERHEAD


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL, num_ctx: int = NUM_CTX, seed: int = 7):
        self.model, self.num_ctx, self.seed = model, num_ctx, seed
        info = self._post("/api/show", {"model": model}, timeout=30)
        details = info.get("details", {})
        self.quantization = details.get("quantization_level", "unknown")
        self.runtime_tag = f"ollama-{model.replace(':', '-')}-{self.quantization}".lower()
        self.stats = {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "seconds": 0.0}

    def _post(self, path: str, payload: dict, timeout: int = 600) -> dict:
        req = urllib.request.Request(OLLAMA_URL + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise OllamaUnavailable(f"Ollama not reachable at {OLLAMA_URL} ({e}). "
                                    f"Start Ollama and run `ollama pull {self.model}`.") from e

    def chat(self, prompt: str, schema: dict | None = None, think: bool = False, max_tokens: int = 1500,
             temperature: float = 0.2, seed: int | None = None) -> tuple[dict | str, str]:
        """Returns (parsed JSON if a schema was given, else text; thinking text or '')."""
        n = count_tokens(prompt)
        budget = self.num_ctx - max_tokens - (THINK_BUDGET if think else 0)
        if n > budget:
            raise PromptTooLong(f"prompt is {n} tokens; only {budget} fit in num_ctx={self.num_ctx} "
                                f"after reserving {max_tokens} output tokens")
        payload = {
            "model": self.model, "stream": False, "think": think, "keep_alive": KEEP_ALIVE,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"num_ctx": self.num_ctx, "temperature": temperature, "top_p": 0.9,
                        "seed": self.seed if seed is None else seed,
                        "num_predict": max_tokens + (THINK_BUDGET if think else 0)},
        }
        if schema is not None:
            payload["format"] = schema
        t0 = time.time()
        r = self._post("/api/chat", payload)
        served = r.get("prompt_eval_count")
        if served is not None and served < 0.8 * (n - CHAT_TEMPLATE_OVERHEAD):
            raise PromptTooLong(f"server evaluated only {served} of ~{n} prompt tokens: prompt was truncated")
        self.stats["calls"] += 1
        self.stats["prompt_tokens"] += served or n
        self.stats["output_tokens"] += r.get("eval_count", 0)
        self.stats["seconds"] += time.time() - t0
        msg = r.get("message", {})
        content, thinking = msg.get("content", ""), msg.get("thinking", "") or ""
        if schema is None:
            return content, thinking
        if not content.strip() and think:
            # reasoning used up the output budget before the answer: ask again without thinking
            result, _ = self.chat(prompt, schema=schema, think=False, max_tokens=max_tokens,
                                  temperature=temperature, seed=seed)
            return result, thinking
        return json.loads(content), thinking

    def tokens_per_second(self) -> float:
        return self.stats["output_tokens"] / self.stats["seconds"] if self.stats["seconds"] else 0.0
