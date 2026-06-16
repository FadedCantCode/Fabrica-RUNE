"""
openrouter_backend.py — Real OpenRouter API adapter (OpenAI-compatible).

Requires OPENROUTER_API_KEY in the environment (see .env.example).
OpenRouter's free tier allows up to 20 requests/minute and 200/day as of
2026, noticeably more headroom than Gemini's per-project daily cap, which
makes it a useful third free backend when Gemini's quota runs out mid-day.

Default model is a `:free`-suffixed model, which OpenRouter does not bill
for. Swap via the `model` constructor arg to try other free-tagged models
if you want different behavior to compare against Gemini/Groq.

Includes the same retry-with-backoff as the other free-tier backends for
transient server errors (429, 500, 503).
"""
import os
import time
import requests
from .base import Backend

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2.0


class OpenRouterBackend(Backend):
    name = "openrouter"

    def __init__(self, model: str = "meta-llama/llama-3.3-70b-instruct:free"):
        self.model = model
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set. Copy .env.example to .env and fill it in."
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
                "https://openrouter.ai/api/v1/chat/completions",
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
                    f"[openrouter_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()

            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"OpenRouter returned no choices: {data}")

            return choices[0]["message"]["content"].strip()

        last_error.raise_for_status()