"""
runtime.py — Loads a .rune file and executes its genome against a chosen backend.

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
from backends.groq_backend import GroqBackend

load_dotenv()

BACKEND_REGISTRY = {
    "openai": OpenAIBackend,
    "anthropic": AnthropicBackend,
    "ollama": OllamaBackend,
    "gemini": GeminiBackend,
    "groq": GroqBackend,
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


def run_agent(rune, backend, task: str, call_delay: float = 2.0) -> dict:
    """
    call_delay: seconds to sleep after each backend call. Free tiers
    (Gemini, Groq) enforce requests-per-minute limits; a validate_linter.py
    run with many tasks fires many sequential calls and can hit a 429
    without this. 2.0s keeps you comfortably under typical free-tier
    limits (e.g. Gemini's ~15-30 req/min on free models) without making
    a 12-task run unbearably slow. Set to 0.0 if you're on a paid tier
    with higher limits and want faster runs.
    """
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
