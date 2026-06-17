# RUNE

**A portable agent definition format that produces consistent behavior across different LLM backends.**

```
research.rune
      │
      ▼
┌──────────┐        ┌──────────┐        ┌─────────────┐
│  OpenAI  │        │ Anthropic│        │  Ollama     │
│ (GPT-4o) │        │ (Claude) │        │ (Llama/Qwen)│
└────┬─────┘        └────┬─────┘        └─────┬───────┘
     ▼                   ▼                    ▼
Research Agent      Research Agent       Research Agent
(search → analyze → summarize, on all three)
```

**One `.rune` file. Three different models. The same agent.**

## What this is

A `.rune` file is a plain YAML spec describing an agent: what steps it takes, what tools
it's allowed to use, and what constraints it must follow. A `.rune` file is *not* code and
is *not* tied to any model provider. The `runtime/` loader reads it and drives whichever
backend you point it at — OpenAI, Anthropic, or a local Ollama model — through the same
fixed instruction sequence.

This repo is the MVP proving that idea works, plus the spec it's built on.

## What this is not (yet)

This is **not** a self-evolving agent ecosystem, a genome-mutation engine, or a model
compression format. Earlier drafts of this project explored those directions; none of
that is implemented or validated here. What's in this repo is the part that actually
runs: load a `.rune` file, execute it against a real model API, compare the output across
providers. Evolutionary/breeding mechanics are listed under [Roadmap](docs/roadmap.md) as
explicitly unvalidated future work, not a current feature.

## Quickstart

```bash
cd reference-implementation
pip install -r requirements.txt
cp .env.example .env   # add the key(s) for whichever backends you want to use
python runtime.py ../examples/research.rune --task "Who is Alan Turing?" --backend openai
python runtime.py ../examples/research.rune --task "Who is Alan Turing?" --backend anthropic
python runtime.py ../examples/research.rune --task "Who is Alan Turing?" --backend ollama --model llama3
```

Backends currently supported: `openai`, `anthropic`, `ollama` (local), `gemini`, `groq`,
`groq_large` (same as `groq`, larger Llama model), `groq_qwen` (Qwen3-32B on Groq),
`openrouter`, `deepseek`, `nim` (NVIDIA NIM, Llama), `nim_deepseek` (NVIDIA NIM, DeepSeek),
`cerebras` (gpt-oss-120b), `mistral` (Mistral Small). Not every backend's free tier
behaves the same way — some cap requests per day, some require a funded account balance
even for "free" models, some rate-limit unpredictably under real load. See each
adapter's docstring in
[`reference-implementation/backends/`](reference-implementation/backends/) for specifics
and known caveats per backend.

Each run prints the same plan structure (`search → analyze → summarize`) executed by a
different model. See [`evaluation.py`](reference-implementation/evaluation.py) to run all
three backends side by side and compare outputs.

### Divergence risk linter

The newest piece here: a linter that predicts, from a `.rune` file's structure alone,
*which steps are likely to behave differently across backends* before you spend API
calls finding out.

```bash
python divergence_linter.py ../examples/research.rune
```

This is a heuristic, not a measured fact, until it's checked against real data. Run the
validation harness with your own API keys to see whether the predictions actually hold up:

```bash
python validate_linter.py ../examples/research.rune \
    --tasks "Who is Alan Turing?" "Explain how vaccines work" \
    --backends openai anthropic
```

This prints a correlation between predicted risk and measured divergence (lexical
overlap across backend outputs per step). See
[`divergence_linter.py`](reference-implementation/divergence_linter.py) for the scoring
logic and [`validate_linter.py`](reference-implementation/validate_linter.py) for the
honesty check. Until you've run this against real data across multiple tasks and
genomes, treat the linter's scores as an untested hypothesis, not a result.

## Results

**First recorded data point (2026-06-16):** a 12-task run on `research.rune` comparing
`groq` against `groq_large` (same provider, different model size — a temporary stand-in
used while other free-tier backends were quota-blocked) produced a correlation of 0.719
between predicted risk and measured divergence. This is a positive signal, but it is
*not* cross-provider evidence.

**Second recorded data point (2026-06-16, same day):** a 12-task run comparing `groq`
(Llama) against `cerebras` (gpt-oss-120b) — two different labs' models on two different
hardware stacks — produced a correlation of **0.99**, with measured divergence spread
meaningfully across genome steps rather than clustering tightly. This is the stronger of
the two results so far, though Cerebras's free tier was visibly rate-limited throughout
the run (every task hit at least one 429 before succeeding via retry), so some of that
divergence may reflect request throttling rather than pure model behavior.

**Third recorded data point (2026-06-17), the cleanest so far:** a 12-task run comparing
`groq_qwen` (Alibaba's Qwen3-32B, on Groq) against `mistral` (Mistral Small, on Mistral
AI's own infrastructure) produced a correlation of **0.999**, with measured divergence
spread meaningfully across steps (0.802–0.853) and zero retries or rate-limit
interference during the run. Two different labs, two different cloud providers, nothing
in the run's execution casts doubt on whether the divergence reflects genuine model
behavior. This is the first result that satisfies the "clean cross-provider pairing"
bar this project has been working toward. See [`docs/roadmap.md`](docs/roadmap.md)
Stage 1 for the full detail on all three results and what's still left to validate
(more genomes, more tasks, a better divergence-measurement proxy than lexical overlap).

## Why

Most agent frameworks couple the agent's behavior definition to a specific model's prompt
format, function-calling schema, or SDK. Moving an agent to a different model means
rewriting it. RUNE separates "what the agent does" (the `.rune` spec) from "which model
runs it" (the runtime adapter), so the same spec is portable across backends.

## Core concepts

| Concept | Definition |
|---|---|
| **Rune** | A YAML file declaring an agent's genome (ordered steps), tools, and constraints |
| **Runtime** | An adapter that executes a Rune against a specific model backend |
| **Agent** | The result of `Runtime.load(rune).run(task)` — a Rune bound to one backend at execution time |

## Research questions this project is investigating

- **RQ1**: Can agent behavior be specified independently of any single model's prompting conventions?
- **RQ2**: How much behavioral variance exists across backends when given the identical Rune spec?
- **RQ3**: What's the minimal schema needed to constrain an LLM into a fixed multi-step plan reliably?

These are open questions. The demo here is evidence toward RQ1 and RQ2, not a final answer.

## Repo structure

```
RUNE/
├── README.md
├── docs/
│   ├── vision.md
│   └── roadmap.md
├── specs/
│   └── RFC-0001-rune-format.md
├── examples/
│   ├── research.rune
│   └── coder.rune
└── reference-implementation/
    ├── runtime.py
    ├── evaluation.py
    ├── divergence_linter.py
    ├── validate_linter.py
    ├── backends/
    │   ├── base.py
    │   ├── openai_backend.py
    │   ├── anthropic_backend.py
    │   ├── ollama_backend.py
    │   ├── gemini_backend.py
    │   ├── groq_backend.py       (GroqBackend + GroqLargeBackend)
    │   ├── openrouter_backend.py
    │   └── deepseek_backend.py
    ├── requirements.txt
    └── .env.example
```

## License

MIT.
