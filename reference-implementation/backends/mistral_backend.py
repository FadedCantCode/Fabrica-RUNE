"""
mistral_backend.py — Real Mistral AI API adapter (OpenAI-compatible).

Requires MISTRAL_API_KEY in the environment (see .env.example). Sign up
at console.mistral.ai for the free "Experiment" tier — no credit card
required, but phone number verification is required (a real-world
identity check, distinct from a card). Confirmed free-tier rate limit
is roughly 1 request/second, comfortably covered by this project's
existing per-call delay pattern.

Mistral is a genuinely different model lineage (a French lab, distinct
training pipeline) from every other backend in this project as of
2026-06-17 — Llama (Groq, NIM), Qwen (Groq), DeepSeek (NIM), gpt-oss-120b
(Cerebras) — making this a real cross-family addition, not just another
flavor of something already covered.

Default model is mistral-small-latest, Mistral's always-current alias
for the small/fast tier (currently Mistral Small 4 as of mid-2026).

IMPORTANT: Mistral Small 4 supports a reasoning_effort parameter
(default leans toward deeper reasoning; "none" disables it). Set
proactively here to "none" to avoid the same visible <think>-block
leakage into divergence measurements that was found and fixed in
groq_backend.py's GroqQwenBackend earlier today — don't wait to
discover the same bug twice.

Includes retry-with-backoff for transient server errors (429, 500, 503),
plus an explicit retry path for connection-level read timeouts (same
pattern as nim_backend.py) — confirmed necessary 2026-06-17 when a real
run against multitool.rune (a heavier genome: two "search" steps plus
analyze accumulate more context per call than research.rune/coder.rune
ever did) hit a hard ReadTimeout that crashed the run immediately,
since a Timeout exception isn't an HTTP status code and bypassed the
status-code retry check entirely. Timeout also raised 60s -> 90s, since
60s wasn't enough margin for this genome's longer accumulated prompts.
"""
import os
import re
import time
import requests
from .base import Backend

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 90


class MistralBackend(Backend):
    name = "mistral"

    def __init__(self, model: str = "mistral-small-latest"):
        self.model = model
        self.api_key = os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY not set. Copy .env.example to .env and fill it in."
            )

    def complete(self, system: str, user: str, temperature: float = 0.5) -> str:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "reasoning_effort": "none",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.exceptions.Timeout as e:
                if attempt < MAX_RETRIES:
                    wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                    print(
                        f"[mistral_backend] read timeout on attempt {attempt + 1}, "
                        f"retrying in {wait:.0f}s..."
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise RuntimeError(
                    f"Mistral request timed out after {MAX_RETRIES + 1} attempts "
                    f"({REQUEST_TIMEOUT_SECONDS}s each). The model may be under heavy "
                    f"load, or the prompt may be unusually long for this genome."
                ) from e

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                print(
                    f"[mistral_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()

            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content

        last_error.raise_for_status()
