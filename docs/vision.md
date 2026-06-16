# Vision

## What problem this addresses

Agent definitions today are usually one of:

1. A system prompt tightly written for one model's instruction-following style.
2. Code that calls one provider's SDK and function-calling schema directly.
3. A framework-specific config (LangChain, CrewAI, etc.) that locks you into that
   framework's execution model.

In all three cases, moving an agent to a different model or framework means rewriting it,
not just re-pointing it. There's no equivalent of a "portable binary" for agent behavior —
something you can hand to any sufficiently capable model and get comparable behavior out.

## What RUNE proposes

Separate two things that are usually fused:

- **The behavior spec** — what steps the agent takes, in what order, under what
  constraints, using what tools. This is the `.rune` file.
- **The execution backend** — which model actually generates the reasoning and tool
  calls at each step. This is the runtime adapter.

A `.rune` file says "search, then analyze, then summarize, citing sources." It says
nothing about whether GPT-4o, Claude, or a local Llama model is doing the work. The
runtime's job is to take that spec and drive any of them through the same sequence.

## What's actually validated right now

Only this: given a `.rune` spec with three steps, the reference runtime can execute that
spec against OpenAI, Anthropic, and Ollama backends and produce a plan + output that
follows the declared genome sequence on all three. That's it. This is a necessary first
proof point, not a complete claim about portable intelligence.

## What's explicitly *not* claimed

- That agents "evolve" or improve generation over generation (no mutation, no fitness
  function is implemented).
- That a `.rune` file represents a "species" capable of "breeding" into new species.
- That behavioral consistency across backends has been rigorously measured (right now
  it's eyeballed by comparing transcripts; see `docs/roadmap.md` for a real eval plan).
- That this format compresses a model or is related to neural representation learning at
  all. Earlier drafts of this project (v0.1–v0.2) explored a 4KB binary neural encoding
  scheme; that work is unrelated to this format and is not part of the current direction.

## Long-term direction, if validated

If RQ1 and RQ2 (see README) hold up under more rigorous testing — i.e., if behavioral
consistency across backends is measurably high and the spec format generalizes beyond
toy 3-step plans — the next steps worth exploring are:

- A small library of reusable Rune specs for common agent patterns.
- A proper evaluation harness with quantitative similarity metrics (tool-call sequence
  match, output similarity, task completion rate) instead of manual transcript comparison.
- Composability: can two Rune specs be merged into a third without manual editing?

Anything beyond that — self-modifying agents, evolutionary selection, multi-agent
breeding — is interesting to think about but is not on the near-term roadmap because it
requires the basics above to be solid first.
