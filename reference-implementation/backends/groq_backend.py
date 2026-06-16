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
