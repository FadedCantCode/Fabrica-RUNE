"""
deepseek_backend.py — Real DeepSeek API adapter (OpenAI-compatible).

Requires DEEPSEEK_API_KEY in the environment (see .env.example). New
DeepSeek accounts get a 5M-token free grant on signup, no credit card
required, valid for 30 days, and the API has no enforced rate limit as
of 2026, making it the most headroom-friendly free backend for a
multi-task validation run (compare: Gemini's free tier caps at 20
requests/day per model on some projects, OpenRouter's free models can
402 on accounts with $0 balance).

Default model is deepseek-v4-flash, the current fast/cheap tier (the
legacy deepseek-chat alias still works but is being phased out).

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


class DeepSeekBackend(Backend):
    name = "deepseek"

    def __init__(self, model: str = "deepseek-v4-flash"):
        self.model = model
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY not set. Copy .env.example to .env and fill it in."
            )

    def complete(self, system: str, user: str, temperature: float = 0.5) -> str:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
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
                    f"[deepseek_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        last_error.raise_for_status()