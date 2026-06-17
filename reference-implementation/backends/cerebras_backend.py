"""
cerebras_backend.py ??Real Cerebras Inference API adapter (OpenAI-compatible).

Requires CEREBRAS_API_KEY in the environment (see .env.example). No
credit card required to sign up. As of 2026 the free tier offers
roughly 1M tokens/day, which comfortably covers a multi-task validation
run (compare: Gemini's free tier on this account capped at just 20
requests/day, and NIM's free tier proved unreliable under burst load
even with long retry backoff).

Cerebras runs on custom wafer-scale chip hardware rather than GPUs,
making it a genuinely different infrastructure stack from Groq's LPU
hardware ??but note it hosts mostly the same open-weight model families
(Llama, Qwen) that Groq and NIM also host. For a cross-*model-family*
comparison (not just cross-infrastructure), pair this with a
non-Llama backend like nim_deepseek rather than with groq alone.

Default model is gpt-oss-120b. Override via the `model` constructor
arg for other models in Cerebras's catalog (e.g. "llama3.1-8b" for a
smaller/faster option, or check the current list at
inference-docs.cerebras.ai for newer additions like Qwen3 variants).

Includes the same retry-with-backoff as the other free-tier backends
for transient server errors (429, 500, 503).
"""
import os
import time
import requests
from .base import Backend

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2.0


class CerebrasBackend(Backend):
    name = "cerebras"

    def __init__(self, model: str = "gpt-oss-120b"):
        self.model = model
        self.api_key = os.environ.get("CEREBRAS_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "CEREBRAS_API_KEY not set. Copy .env.example to .env and fill it in."
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
            try:
                resp = requests.post(
                    "https://api.cerebras.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=60,
                )
            except requests.exceptions.Timeout as e:
                if attempt < MAX_RETRIES:
                    wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                    print(
                        f"[cerebras_backend] read timeout on attempt {attempt + 1}, "
                        f"retrying in {wait:.0f}s..."
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise RuntimeError(
                    f"Cerebras request timed out after {MAX_RETRIES + 1} attempts."
                ) from e

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                print(
                    f"[cerebras_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        last_error.raise_for_status()
