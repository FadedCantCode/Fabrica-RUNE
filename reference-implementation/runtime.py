"""
runtime.py ??Loads a .rune file and executes its genome against a chosen backend.

Usage:
    python runtime.py ../examples/research.rune --task "Who is Alan Turing?" --backend openai
    python runtime.py ../examples/research.rune --task "Who is Alan Turing?" --backend anthropic
    python runtime.py ../examples/research.rune --task "Who is Alan Turing?" --backend ollama --model llama3
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from rune_loader import load_rune, RuneValidationError
from backends.openai_backend import OpenAIBackend
from backends.anthropic_backend import AnthropicBackend
from backends.ollama_backend import OllamaBackend
from backends.gemini_backend import GeminiBackend
from backends.groq_backend import GroqBackend, GroqLargeBackend, GroqQwenBackend
from backends.openrouter_backend import OpenRouterBackend
from backends.deepseek_backend import DeepSeekBackend
from backends.nim_backend import NIMBackend, NIMDeepSeekBackend
from backends.cerebras_backend import CerebrasBackend
from backends.mistral_backend import MistralBackend

load_dotenv()

BACKEND_REGISTRY = {
    "openai": OpenAIBackend,
    "anthropic": AnthropicBackend,
    "ollama": OllamaBackend,
    "gemini": GeminiBackend,
    "groq": GroqBackend,
    "groq_large": GroqLargeBackend,
    "groq_qwen": GroqQwenBackend,
    "openrouter": OpenRouterBackend,
    "deepseek": DeepSeekBackend,
    "nim": NIMBackend,
    "nim_deepseek": NIMDeepSeekBackend,
    "cerebras": CerebrasBackend,
    "mistral": MistralBackend,
}

# Free-tier rate limits vary a lot per provider. Gemini Flash's free tier
# is roughly 10 requests/minute as of early-2026 pricing, so a safe gap is
# ~7s, not the 2s default that's fine for more generous tiers like Groq's.
# Override here rather than guessing one global number that's wrong for
# everyone.
BACKEND_CALL_DELAYS = {
    "gemini": 7.0,
    "groq": 2.0,
    "groq_large": 2.0,
    "groq_qwen": 2.0,
    "openrouter": 3.0,
    "deepseek": 1.0,
    "nim": 2.0,
    "nim_deepseek": 2.0,
    "cerebras": 1.0,
    "mistral": 1.0,
    "openai": 1.0,
    "anthropic": 1.0,
    "ollama": 0.0,  # local, no rate limit
}

STEP_INSTRUCTIONS = {
    "search": (
        "Step: SEARCH. State what information you need to find for this task, "
        "and what you would search for. You do not have live web access in this "
        "step; describe the search queries and the kind of sources you'd expect."
    ),
    "analyze": (
        "Step: ANALYZE. Given the task and any prior findings in this conversation, "
        "reason through what the key facts and relationships are. Be concise."
    ),
    "summarize": (
        "Step: SUMMARIZE. Produce the final answer to the original task in 3-5 sentences."
    ),
    "code": (
        "Step: CODE. Write the minimal code that solves the task. Output only the code "
        "in a fenced block, with a one-line comment explaining the approach."
    ),
    "test": (
        "Step: TEST. Given the code you just wrote, state what test cases would verify "
        "it's correct, and whether you believe it passes them. Be specific."
    ),
}

CONSTRAINT_TEXT = {
    "cite_sources": "You must attribute claims to sources where applicable.",
}


def build_system_prompt(rune) -> str:
    lines = [
        f"You are an agent of species '{rune.species}'.",
        f"Your full task will be executed across these steps in order: {' -> '.join(rune.genome)}.",
        "Follow only the instruction given at each step. Do not skip ahead.",
    ]
    if rune.tools:
        lines.append(f"You may reference use of these tools: {', '.join(rune.tools)}.")
    for c in rune.constraints:
        if c in CONSTRAINT_TEXT:
            lines.append(CONSTRAINT_TEXT[c])
    return " ".join(lines)


def run_agent(rune, backend, task: str, call_delay: float = None) -> dict:
    """
    call_delay: seconds to sleep after each backend call. If not given,
    looks up a per-backend default from BACKEND_CALL_DELAYS, since free
    tiers have very different rate limits (Gemini's ~10 RPM is much
    tighter than Groq's). Pass 0.0 explicitly to disable throttling
    entirely (e.g. if you're on a paid tier with high limits).
    """
    if call_delay is None:
        call_delay = BACKEND_CALL_DELAYS.get(backend.name, 2.0)

    system_prompt = build_system_prompt(rune)
    transcript = []
    context = f"Original task: {task}"

    for step in rune.genome:
        instruction = STEP_INSTRUCTIONS[step]
        user_prompt = f"{context}\n\n{instruction}"
        output = backend.complete(system_prompt, user_prompt, temperature=rune.temperature)
        transcript.append({"step": step, "output": output})
        context += f"\n\n[{step} output]: {output}"
        if call_delay > 0:
            time.sleep(call_delay)

    return {
        "species": rune.species,
        "backend": backend.name,
        "task": task,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "genome": rune.genome,
        "transcript": transcript,
        "final_answer": transcript[-1]["output"] if transcript else "",
    }


def main():
    parser = argparse.ArgumentParser(description="Run a .rune agent against a model backend.")
    parser.add_argument("rune_path", help="Path to a .rune file")
    parser.add_argument("--task", required=True, help="The task for the agent to perform")
    parser.add_argument("--backend", required=True, choices=BACKEND_REGISTRY.keys())
    parser.add_argument("--model", default=None, help="Override the default model for the chosen backend")
    parser.add_argument("--json", action="store_true", help="Print raw JSON result instead of formatted transcript")
    args = parser.parse_args()

    try:
        rune = load_rune(args.rune_path)
    except RuneValidationError as e:
        print(f"??Invalid .rune file: {e}", file=sys.stderr)
        sys.exit(1)

    backend_cls = BACKEND_REGISTRY[args.backend]
    backend = backend_cls(model=args.model) if args.model else backend_cls()

    try:
        result = run_agent(rune, backend, args.task)
    except Exception as e:
        print(f"??Run failed on backend '{args.backend}': {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"=== {result['species']} agent on {result['backend']} ===")
        print(f"Task: {result['task']}")
        print(f"Genome: {' -> '.join(result['genome'])}\n")
        for entry in result["transcript"]:
            print(f"--- {entry['step'].upper()} ---")
            print(entry["output"])
            print()
        print("=== FINAL ANSWER ===")
        print(result["final_answer"])


if __name__ == "__main__":
    main()
