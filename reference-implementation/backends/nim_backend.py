"""
nim_backend.py — Real NVIDIA NIM API adapter (OpenAI-compatible).

Requires NVIDIA_API_KEY in the environment (see .env.example), a key
starting with "nvapi-" from build.nvidia.com. The free developer tier
grants 1,000 inference credits on signup, no credit card required, with
a rate limit around 40 requests/minute as of 2026.

NIM hosts models from many different labs (Meta/Llama, DeepSeek, Kimi,
GLM, MiniMax, and others) behind one OpenAI-compatible endpoint. That
makes it a reasonable way to compare genuinely different model lineages
under one account when juggling separate per-provider keys is the
bottleneck — though note this is NVIDIA's hosted version of those
models, not necessarily byte-identical to calling each lab's own API
directly. Treat it as a good stand-in for cross-provider comparison, not
a perfect substitute for it.

Default model is meta/llama-3.1-8b-instruct (the smaller, faster variant —
the 70B model has documented periods of slow or hanging responses under
load on NIM's free tier as of 2026; switch up to 70b-instruct via the
`model` constructor arg once basic connectivity is confirmed working).
Override via the `model` constructor arg to point at any other model ID
from the catalog at build.nvidia.com/models (e.g. "deepseek-ai/deepseek-v3"
or "moonshotai/kimi-k2-instruct" — check the catalog for current IDs,
since NVIDIA's model lineup changes and free models can be deprecated
with short notice).

Includes the same retry-with-backoff as the other free-tier backends for
transient server errors (429, 500, 503), plus an explicit retry path for
connection-level read timeouts, since those don't carry an HTTP status
code and would otherwise crash immediately instead of retrying.
"""
import os
import time
import requests
from .base import Backend

RETRYABLE_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 2.0


class NIMBackend(Backend):
    name = "nim"

    def __init__(self, model: str = "meta/llama-3.1-8b-instruct"):
        self.model = model
        self.api_key = os.environ.get("NVIDIA_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY not set. Copy .env.example to .env and fill it in."
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
            try:
                resp = requests.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120,
                )
            except requests.exceptions.Timeout as e:
                # NIM has documented periods of slow/hanging responses,
                # especially on larger models under load. A read timeout
                # isn't an HTTP status code, so it needs its own retry path
                # rather than falling through the status-code check below.
                if attempt < MAX_RETRIES:
                    wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                    print(
                        f"[nim_backend] read timeout on attempt {attempt + 1}, "
                        f"retrying in {wait:.0f}s..."
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise RuntimeError(
                    f"NIM request timed out after {MAX_RETRIES + 1} attempts "
                    f"(120s each). The model may be under heavy load right now; "
                    f"try again later or switch to a smaller model."
                ) from e

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                print(
                    f"[nim_backend] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        last_error.raise_for_status()


class NIMDeepSeekBackend(NIMBackend):
    """
    Same NIM adapter, pointed at NVIDIA's hosted DeepSeek model — a
    genuinely different model lineage from Llama, useful for a
    cross-family comparison within one NIM account when separate
    per-provider accounts are quota-blocked elsewhere.

    Model ID should be confirmed against the current catalog at
    build.nvidia.com/models before relying on it; NVIDIA's listings
    change and this string may need updating.
    """
    name = "nim_deepseek"

    def __init__(self, model: str = "deepseek-ai/deepseek-v3"):
        super().__init__(model=model)
