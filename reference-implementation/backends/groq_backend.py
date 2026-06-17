"""
groq_backend.py — Real Groq API adapter (OpenAI-compatible chat completions).

Requires GROQ_API_KEY in the environment (see .env.example). Groq's free
tier has no payment requirement, just rate limits, so this is a genuinely
free second backend to pair with gemini for divergence experiments.

Default model is llama-3.1-8b-instant, a fast open-weight model available
on Groq's free tier. Swap via the `model` constructor arg if you want a
different one (e.g. a larger Llama or a Qwen variant Groq hosts).

Includes the same retry-with-backoff as gemini_backend.py for transient
server errors (429, 500, 503), so a multi-task validation run doesn't
crash on one flaky response.
"""
import os
import time
import requests
from .base import Backend

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2.0


class GroqBackend(Backend):
    name = "groq"

    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.model = model
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Copy .env.example to .env and fill it in."
            )

    def complete(self, system: str, user: str, temperature: float = 0.5) -> str:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60,
            )

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                print(
                    f"[groq_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        last_error.raise_for_status()


class GroqLargeBackend(GroqBackend):
    """
    Same Groq adapter, pointed at a larger model (70B vs the default 8B).

    Use case: when no second *provider* is available (e.g. other free
    tiers are quota-blocked), pairing this with the base GroqBackend lets
    validate_linter.py measure same-provider, different-model-size
    divergence as a temporary substitute. This answers a different,
    narrower question than cross-provider divergence (RUNE's actual
    research question) — treat results from this pairing as a stand-in,
    not equivalent evidence, and prefer a real cross-provider pairing
    (e.g. groq + gemini) once available.
    """
    name = "groq_large"

    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        super().__init__(model=model)

class GroqQwenBackend(GroqBackend):
    """
    Same Groq adapter, pointed at Qwen3-32B (model ID confirmed against
    Groq's own docs: qwen/qwen3-32b). Unlike groq_large, this is a
    genuinely different model family (Alibaba's Qwen, not Meta's Llama)
    running on the same fast, reliable Groq infrastructure already
    verified working throughout this project.

    Useful when a local Qwen comparison (e.g. via ollama_backend.py) is
    impractical — large Qwen models are slow on CPU-only hardware
    without a dedicated GPU — but a cross-family signal involving Qwen
    specifically is still wanted. Note Qwen3 models support a
    `reasoning_effort` parameter (set to "none" to disable reasoning);
    this adapter doesn't set it, so Qwen's default reasoning behavior
    applies, which may affect response length/latency relative to the
    non-reasoning Llama/GPT-OSS backends elsewhere in this project.
    """
    name = "groq_qwen"

    def __init__(self, model: str = "qwen/qwen3-32b"):
        super().__init__(model=model)
