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

- [ ] Run `validate_linter.py` across at least 10 distinct tasks and both example genomes
- [ ] Record actual correlation coefficients, not just the synthetic test in this repo's
      history. If correlation is weak or negative, say so and revise the heuristic weights
      in `divergence_linter.py`, or scrap the specific signals that don't hold up.
- [ ] Replace the lexical-overlap (Jaccard) divergence proxy with embedding-based semantic
      similarity, since two backends can say the same thing in different words and get
      penalized as "divergent" under pure word-overlap scoring.
- [ ] Test across at least 3 distinct genome shapes (current: research, coder)

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
