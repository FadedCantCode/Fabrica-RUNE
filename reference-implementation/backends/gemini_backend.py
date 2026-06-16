"""
gemini_backend.py — Real Google Gemini API adapter via the REST endpoint.

Requires GOOGLE_API_KEY in the environment (see .env.example).
Uses the raw generateContent REST endpoint directly (no google-genai SDK
dependency), matching the same requests-based style as the other backends.

Includes retry-with-backoff for transient server errors (429 rate limit,
500/503 server overload), since free-tier traffic gets routed to
capacity-constrained infrastructure and occasional 503s are expected, not
a sign anything is misconfigured. Client errors (400/401/403) fail fast,
since retrying a bad request or bad key would just waste time.
"""
import os
import time
import requests
from .base import Backend

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2.0


class GeminiBackend(Backend):
    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY not set. Copy .env.example to .env and fill it in."
            )

    def complete(self, system: str, user: str, temperature: float = 0.5) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": user}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system}]
            },
            "generationConfig": {
                "temperature": temperature,
            },
        }

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                print(
                    f"[gemini_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates", [])
            if not candidates:
                reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                raise RuntimeError(f"Gemini returned no candidates (reason: {reason})")

            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip()

        last_error.raise_for_status()
