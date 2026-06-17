"""
ollama_backend.py — Local model adapter via Ollama's HTTP API.

Requires a running `ollama serve` instance (default http://localhost:11434)
and the target model already pulled, e.g.:
    ollama pull qwen3.6
    ollama pull llama3

Runs entirely on local hardware — no API key, no rate limit, no daily
quota, no account balance to run out. This makes it a uniquely clean
backend for divergence experiments: unlike every cloud backend tested
in this project so far (Gemini's 20/day account cap, OpenRouter's $0
balance 402s, NIM's rate-limit instability under burst load, Cerebras
being throttled mid-run), nothing here can fail due to someone else's
infrastructure or billing state. The tradeoff is local compute time —
expect responses to be slower than fast cloud inference (Groq, Cerebras)
unless running on a capable GPU.

Default model is qwen3.6, a different model family from the Llama
(Groq, NIM) and DeepSeek (NIM) and gpt-oss-120b (Cerebras) lineages
already covered elsewhere in this project — useful for a genuinely
local point of cross-family comparison.
"""
import os
import requests
from .base import Backend


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model: str = "qwen3.6"):
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
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()
