"""
gemini_backend.py — Real Google Gemini API adapter via the REST endpoint.

Requires GOOGLE_API_KEY in the environment (see .env.example).
Uses the raw generateContent REST endpoint directly (no google-genai SDK
dependency), matching the same requests-based style as the other backends.
"""
import os
import requests
from .base import Backend


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
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": user}]}
                ],
                "systemInstruction": {
                    "parts": [{"text": system}]
                },
                "generationConfig": {
                    "temperature": temperature,
                },
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            # Can happen on safety blocks or empty responses; surface clearly
            # rather than crashing on an index error.
            reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
            raise RuntimeError(f"Gemini returned no candidates (reason: {reason})")

        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()
