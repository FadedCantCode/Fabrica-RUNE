"""
ollama_backend.py — Local model adapter via Ollama's HTTP API.

Requires a running `ollama serve` instance (default http://localhost:11434)
and the target model already pulled, e.g.:
    ollama pull llama3
    ollama pull qwen2.5-coder
"""
import os
import requests
from .base import Backend


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model: str = "llama3"):
        self.model = model
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, system: str, user: str, temperature: float = 0.5) -> str:
        resp = requests.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "options": {"temperature": temperature},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()
