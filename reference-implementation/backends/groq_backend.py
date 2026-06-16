"""
groq_backend.py — Real Groq API adapter (OpenAI-compatible chat completions).

Requires GROQ_API_KEY in the environment (see .env.example). Groq's free
tier has no payment requirement, just rate limits, so this is a genuinely
free second backend to pair with gemini for divergence experiments.

Default model is llama-3.1-8b-instant, a fast open-weight model available
on Groq's free tier. Swap via the `model` constructor arg if you want a
different one (e.g. a larger Llama or a Qwen variant Groq hosts).
"""
import os
import requests
from .base import Backend


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
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()