class GroqQwenBackend(GroqBackend):
    """
    Same Groq adapter, pointed at Qwen3-32B (model ID confirmed against
    Groq's own docs: qwen/qwen3-32b). Unlike groq_large, this is a
    genuinely different model family (Alibaba's Qwen, not Meta's Llama)
    running on the same fast, reliable Groq infrastructure already
    verified working throughout this project.

    Useful when a local Qwen comparison (e.g. via ollama_backend.py) is
    impractical — large Qwen models are slow on CPU-only hardware
    without a dedicated GPU — but a cross-family signal involving Qwen
    specifically is still wanted.

    IMPORTANT: Qwen3 models default to "thinking mode" and return a
    visible <think>...</think> reasoning block before the actual answer.
    Confirmed via real testing (2026-06-17): without intervention, this
    block appears directly in the response content, often hundreds of
    words long. Left in place, this would badly distort any divergence
    comparison against non-reasoning backends (Llama, DeepSeek,
    gpt-oss-120b elsewhere in this project) — the lexical-overlap
    divergence score would be inflated by formatting/verbosity
    differences, not genuine differences in the actual answer. This
    adapter sets reasoning_effort="none" to disable thinking mode, and
    additionally strips any <think>...</think> block defensively in case
    the parameter doesn't fully suppress it for a given prompt.
    """
    name = "groq_qwen"

    def __init__(self, model: str = "qwen/qwen3-32b"):
        super().__init__(model=model)

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
                    f"[groq_backend:qwen] {resp.status_code} on attempt {attempt + 1}, "
                    f"retrying in {wait:.0f}s..."
                )
                time.sleep(wait)
                last_error = resp
                continue

            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Defensive strip: remove any <think>...</think> block even if
            # reasoning_effort="none" didn't fully suppress it for this
            # particular prompt. re is stdlib-only, no new dependency.
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content

        last_error.raise_for_status()
