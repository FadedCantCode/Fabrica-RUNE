# Roadmap

Staged by what's actually demonstrable, not by ambition. Each stage requires the previous
one to be working and measured before starting the next.

## Stage 0 — Done in this repo

- [x] `.rune` YAML schema (genome, tools, constraints)
- [x] Runtime loader with OpenAI, Anthropic, Ollama backends
- [x] Manual side-by-side comparison script (`evaluation.py`)
- [x] Divergence risk linter (`divergence_linter.py`) — structural heuristic predicting
      which genome steps are likely to diverge across backends
- [x] Validation harness (`validate_linter.py`) — measures real lexical divergence across
      backends and correlates it against the linter's predictions

## Stage 1 — Needed before claiming the linter works

- [x] Run `validate_linter.py` across 12 distinct tasks on the `research` genome
      (2026-06-16, `groq` vs `groq_large` — see caveat below)
- [ ] Run the same 12-task set on a *clean* cross-provider pairing (different companies,
      different infrastructure, no rate-limit interference distorting the measurement).
      `groq` vs `cerebras` (recorded below, 0.99) is genuinely cross-provider, but
      Cerebras was rate-limited throughout that run — every task hit at least one 429
      before succeeding via retry — so some of that divergence may reflect request
      throttling rather than pure model behavior. This box stays unchecked until a
      cross-provider run completes without that kind of interference.
- [ ] Run `validate_linter.py` across at least 10 distinct tasks and both example genomes
- [ ] Record actual correlation coefficients, not just the synthetic test in this repo's
      history. If correlation is weak or negative, say so and revise the heuristic weights
      in `divergence_linter.py`, or scrap the specific signals that don't hold up.
- [ ] Replace the lexical-overlap (Jaccard) divergence proxy with embedding-based semantic
      similarity, since two backends can say the same thing in different words and get
      penalized as "divergent" under pure word-overlap scoring.
- [ ] Test across at least 3 distinct genome shapes (current: research, coder)

### Recorded result: 2026-06-16, `groq` vs `groq_large`, `research.rune`, 12 tasks

Correlation between predicted risk and measured divergence: **0.719** (positive signal
per `validate_linter.py`'s own interpretation threshold of ≥0.5).

**Caveat, important:** `groq` and `groq_large` are the same provider (Groq), differing
only in model size (8B vs 70B). This is a same-provider, different-model-size comparison,
*not* the cross-provider comparison this project is actually trying to validate. It was
run as a temporary substitute on a day when Gemini, OpenRouter, and DeepSeek's free tiers
were all blocked (quota exhaustion / zero account balance). Treat this 0.719 as a weaker,
narrower data point — evidence the linter has *some* predictive signal, not evidence it
predicts cross-provider divergence specifically. Measured divergence across all three
genome steps was unusually tight (0.74–0.80), which may mean model-size difference alone
dominates the signal regardless of step structure — a real cross-provider run is needed to
tell whether that holds, or whether it's an artifact of this particular pairing.

### Recorded result: 2026-06-16, `groq` (Llama) vs `cerebras` (gpt-oss-120b), `research.rune`, 12 tasks

Correlation between predicted risk and measured divergence: **0.99** (strong positive
signal). Measured divergence spread meaningfully across steps (0.873–0.906) rather than
clustering tightly, a different and more informative shape than the groq/groq_large run
above.

**Caveat, important:** this is a genuinely different pairing than groq/groq_large — Llama
(Meta) on Groq vs gpt-oss-120b (OpenAI's open-weight model) on Cerebras, two different
labs' model lineages on two different hardware stacks (LPU vs wafer-scale chips). That's
closer to a real cross-provider comparison than this morning's same-provider run, but it
is not the original research question's framing of comparing identical or near-identical
model classes across providers. A second caveat specific to this run: Cerebras's free
tier was visibly rate-limited throughout (every task triggered at least one 429, recovered
via retry-with-backoff). It's possible request throttling itself introduced extra response
variance independent of the linter's structural logic — this run cannot rule that out.
Treat 0.99 as a strong second data point, not as definitive proof: two independent
positive signals (0.719 and 0.99) across two different pairings is more convincing than
either alone, but a cleaner, non-rate-limited cross-provider run is still the strongest
remaining validation step.

## Stage 2 — Spec maturity

- [ ] Versioned schema (semver on the `.rune` format itself, not just the repo)
- [ ] Validation tool: lint a `.rune` file for malformed genome/tool references before run
- [ ] Composability: merge two `.rune` files into a third (e.g. research + coder → research-coder)
      with a defined, deterministic merge rule — not vague "breeding" language until the
      merge semantics are actually specified and tested

## Stage 3 — Open questions, not commitments

These are directions worth exploring *if* Stage 1–2 hold up. None of this is promised,
and none of it should be referenced as a current feature:

- Automated genome search: given a task and a fitness function, can a search procedure
  propose genome edits that measurably improve task performance? (This is closer to
  hyperparameter search / AutoML than "evolution," and should be described that way
  unless and until something more biologically-structured is actually built and justified.)
- Cross-model fine-tuning of constraint adherence (e.g. a backend that ignores
  `cite_sources` — can the runtime detect and correct this automatically?)

## Explicitly out of scope indefinitely

- Binary/compressed agent representations (this was explored in an earlier, separate
  draft of this project and is not part of the current direction)
- Claims about "agent species," "cognitive genomes evolving," or similar framing until
  there is a concrete, falsifiable experiment behind each term
