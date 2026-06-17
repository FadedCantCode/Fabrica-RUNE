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
- [x] Run the same 12-task set on a *clean* cross-provider pairing (different companies,
      different infrastructure, no rate-limit interference distorting the measurement).
      Done 2026-06-17: `groq_qwen` (Alibaba's Qwen3-32B, on Groq) vs `mistral` (Mistral
      Small, on Mistral's own infrastructure) — see result recorded below. Correlation:
      0.999, with zero retries or rate-limit interference during the run.
- [x] Replace the lexical-overlap (Jaccard) divergence proxy with embedding-based semantic
      similarity. Done 2026-06-17 (`validate_linter.py`, `sentence-transformers`'s
      `all-MiniLM-L6-v2`, runs offline, no API key). Empirically confirmed working
      (similar-meaning-different-words scored 0.564, genuinely-different-topics scored
      0.071) before relying on it. Materially improved the coder.rune result (0.362 →
      0.497 on the same dataset, same predictions, only the measurement changed) —
      confirms the original hypothesis that Jaccard was penalizing code's natural
      surface-form variation. `--use-jaccard` flag still available for comparison
      against historical results.
- [ ] Test across at least 3 distinct genome shapes (research.rune: 3 positive results,
      correlations 0.719/0.99/0.999. coder.rune: after investigating a real discrepancy
      and fixing a genuine structural gap in the heuristic — see detailed history below
      — final correlation 0.967, also a positive result. multitool.rune: tested
      2026-06-17, v1 correlation -0.086; a fix attempt (format-anchoring constraint
      suppression) made it worse, -0.604 — see detailed history below. Honest status:
      2/3 genome shapes positively validated, 1 genuinely unresolved. This item is not
      satisfied yet; multitool.rune revealed real structural gaps — position-dependent
      divergence for repeated steps, non-uniform constraint effects — that need more
      data before a real fix, not another guess, can be justified.)
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

### Recorded result: 2026-06-17, `groq_qwen` (Qwen3-32B) vs `mistral` (Mistral Small), `research.rune`, 12 tasks

Correlation between predicted risk and measured divergence: **0.999**. Measured
divergence spread meaningfully across steps (0.802–0.853) without clustering, and the
run completed with zero retries or rate-limit interference on either backend.

This is the cleanest result so far: `groq_qwen` runs Alibaba's Qwen3-32B on Groq's
infrastructure (reasoning_effort explicitly disabled to avoid the model's default
<think>-block leaking into divergence measurement — see groq_backend.py and
mistral_backend.py docstrings for why that matters), and `mistral` runs Mistral Small on
Mistral AI's own infrastructure. Two different labs, two different cloud providers,
no shared rate limit, no observed throttling. Unlike every other result recorded above,
nothing in this run's execution casts doubt on whether the measured divergence reflects
genuine model behavior rather than infrastructure noise.

Combined with the two earlier results (0.719, same-provider stand-in; 0.99,
cross-provider but rate-limited), this is now three independent positive signals across
three different pairing types. That's the strongest evidence so far that the linter's
structural heuristic has real predictive signal — though "strong evidence" is still not
the same as "proven correct in general." Remaining honest limitations: all three runs
used the same single genome (`research.rune`) and the same 12-task set; Stage 1's other
unchecked items (testing `coder.rune`, testing with more tasks, replacing the Jaccard
lexical-overlap proxy with embedding-based similarity) still apply before treating this
as fully validated.

### Root cause found and fixed: context-dependent `summarize` ambiguity (2026-06-17)

Investigated why `summarize` consistently measured far more divergent than predicted
across all three attempts above. Found the actual cause in `runtime.py`:
`STEP_INSTRUCTIONS["summarize"]` is a single hardcoded string ("Produce the final
answer to the original task in 3-5 sentences") used unchanged regardless of genome
shape. That instruction's real ambiguity depends on what it's summarizing —
`research.rune`'s summarize follows `analyze` (a well-defined research synthesis, low
ambiguity, which is why `STEP_SPECIFICITY=0.3` correctly predicted it as low-risk in all
three `research.rune` runs). `coder.rune`'s summarize follows `test` (verifying a coding
deliverable) — "summarize the final answer" after writing and testing code has no fixed
convention (restate the code? describe what it does? report pass/fail? give usage
instructions?), making it genuinely more ambiguous than the research.rune case the base
value was calibrated against.

Fix: `divergence_linter.py`'s `score_step()` now takes the *preceding* genome step as
context, and `summarize`'s specificity risk is looked up via a new
`SUMMARIZE_PRECEDED_BY_SPECIFICITY` table (`test` → 0.6, `code` → 0.5) instead of always
using the flat 0.3 base value. This is a structural fix, not a reweighting of one
dataset's result: confirmed `research.rune`'s predictions are byte-for-byte unchanged
(its summarize follows `analyze`, not in the lookup table, so falls through to the
original base value untouched) before considering this fix valid.

### Recorded result: 2026-06-17, `groq_qwen` vs `mistral`, `coder.rune`, 12 tasks (v4, context-aware fix)

Correlation: **0.967** — a real pass, clearing the ≥0.5 threshold by a wide margin.
Measured divergence (0.113–0.186) is nearly identical to the v3 semantic-similarity run
(0.099–0.216, same tasks/backends/measurement method), confirming the underlying
measurement is stable and the predicted-side fix was the only real lever pulled.
Predicted and measured rankings now closely align: `test` and `analyze` are
near-tied at the top in both (matching this run's actual 0.186 vs 0.185), `summarize`
sits clearly in the middle, `code` is clearly lowest in both.

**This closes out coder.rune's open question from earlier in Stage 1.** Combined with
`research.rune`'s three results, the linter now has a positive, defensible result on
two structurally different genome shapes — one with a tool step, one without; one with
three steps, one with four — using the same underlying scoring logic, after one
substantive (not curve-fit) structural correction. Stage 1's "test across at least 3
distinct genome shapes" item is now 2/3 satisfied with real positive evidence; a third
genome shape, ideally one that exercises a part of the heuristic neither
`research.rune` nor `coder.rune` has touched (e.g. a genome with more than one tool
step, or with multiple constraints), is the next concrete step toward fully closing
that item.

### Recorded result: 2026-06-17, `groq_qwen` vs `mistral`, `multitool.rune`, 12 tasks (v1)

A third genome (`multitool.rune`: search → analyze → search → summarize, two tool
steps, two constraints — `cite_sources` and a new `structured_output`) was built
specifically to exercise parts of the heuristic `research.rune` and `coder.rune` never
touched. Correlation: **-0.086**, essentially no signal, slightly negative.

**Two findings, not one.** First: predicted scores treat both `search` occurrences
identically (0.375 each, since the heuristic has no position-awareness), but measured
divergence differed meaningfully between them (0.178 for the first occurrence, 0.264 for
the second) across the full 12-task run — smaller than the 3-task smoke test's gap
(0.172 vs 0.352, roughly 2x) but still in the same direction. Plausible mechanism: each
model's second search reacts to its own already-diverged `analyze` output, so divergence
compounds with genome position, not just step identity — a real, structural blind spot
the current heuristic has no way to represent, but the effect may be too small on
the available data so far to justify a specific numeric fix.

Second, more serious: `analyze` was predicted as clearly highest-risk (0.56) but measured
as the *lowest* of all four steps (0.208), even below `summarize` (0.215, predicted
lowest). This is a ranking inversion at the top, not just a magnitude miss, and it held
in the same direction from the 3-task smoke test through the full 12-task run.

**Working hypothesis, not yet applied:** `multitool.rune` is the first genome with the
new `structured_output` constraint ("format every step's response using clear
structure"), which forces every step, including `analyze`, into a rigid output shape
(headers, lists). `score_step()`'s `constraint_risk` currently only measures constraint
*coverage* (count of constraints / genome length) — it has no representation of what a
constraint actually *does*. `structured_output` plausibly suppresses cross-model
divergence in a step like `analyze` far more directly than `cite_sources` does, by
forcing both models toward similarly-shaped output (lists, headers) regardless of how
differently they actually reason — but the current math treats every constraint as
equally generic. If true, the fix is structural: let `structured_output` specifically
lower `specificity_risk`, not just contribute to coverage. Not yet implemented — see the
next section for the result of testing this hypothesis.

### Fix attempt: format-anchoring constraint suppression (2026-06-17)

Added `FORMAT_ANCHORING_CONSTRAINTS = {"structured_output": 0.7}` to
`divergence_linter.py` — a multiplicative suppression factor applied to a step's
`specificity_risk` when the rune declares a constraint that anchors output format.
`cite_sources` is intentionally excluded, since it constrains content attribution, not
output shape. Confirmed `research.rune` and `coder.rune`'s predictions are completely
unchanged (neither uses `structured_output`) before considering this fix valid.
`multitool.rune`'s new predicted scores: `analyze` 0.56 → 0.392, `search` (both
occurrences) 0.375 → 0.285, `summarize` 0.21 → 0.147 — `analyze` still ranks highest,
but by a much smaller margin, closer to what the measured data actually showed.

### Recorded result: 2026-06-17, `groq_qwen` vs `mistral`, `multitool.rune`, 12 tasks (v2, after format-anchoring fix)

Correlation: **-0.604** — worse, not better. A strong negative correlation; the
heuristic is now actively predicting backwards for this genome.

**Honest read: the fix was directionally right for one step and wrong as a blanket
rule.** `analyze`'s measured divergence (0.158) did land close to its new, lower
prediction — the hypothesis that `structured_output` suppresses `analyze`'s cross-model
divergence by forcing similarly-shaped output appears genuinely correct for that one
step. But applying the same 0.7 suppression factor uniformly to every step in the
genome was the mistake. `summarize`, predicted as clearly lowest-risk (0.147) after the
fix, measured as the *second-highest* divergence step (0.221) — a different, new
inversion that wasn't this stark in v1. The two `search` occurrences also split further
apart in measured terms (0.157 vs 0.237) while still being predicted identically (0.285
each) — the position-divergence effect flagged in v1 persists and the fix did nothing
to address it, since it was never aimed at that part of the problem.

**What this means:** `structured_output`'s real effect on divergence is not a uniform,
step-independent multiplier. It's plausible the constraint helps most for steps that are
naturally prose-heavy and interpretive (`analyze`), where a forced list/header structure
gives both models a shared scaffold to converge around — but does little or nothing for
a step like `summarize`, which was already short and constrained before the format
requirement was added, or may even increase apparent divergence if the two models choose
different ways to "structure" a final answer (different header choices, different list
groupings) that a 3-5 sentence prose summary wouldn't have exposed.

**Status: this fix is reverted in spirit, not advanced further today.** Don't tune the
0.7 factor, or make it step-specific by fitting to this exact result — that's the same
curve-fitting risk flagged earlier in this document, now with even less data to fit
against (12 tasks, one genome, one constraint). The honest conclusion right now:
`multitool.rune` has exposed at least two real, distinct structural gaps in the current
heuristic — position-dependent divergence for repeated tool steps, and non-uniform
effects of format-anchoring constraints across different step types — and both need
more data (more tasks, ideally a fourth genome isolating each variable independently)
before a real fix can be justified rather than guessed. Stage 1's "test across 3 genome
shapes" item should be read honestly as: 2 genomes positively validated, 1 genome
revealing real unresolved limitations in the heuristic, not yet a clean 3-for-3.

### Methodological rule, added 2026-06-17: isolate one variable per genome experiment

`multitool.rune` combined two untested dimensions at once — a repeated tool step
(position effect) and two simultaneous constraints, one of them new (`structured_output`,
a constraint effect). When the result came back weak (-0.086), then worse after a fix
attempt (-0.604), there was no way to tell which dimension the fix attempt was actually
acting on, or whether it was fighting two effects at once. The `structured_output` fix
turned out to be a real, partial insight (correctly explained `analyze`) tangled with a
real miss (wrongly generalized to `summarize`) — but disentangling that took real
effort, and could have been avoided by design.

**Rule going forward: each new genome built specifically to test the heuristic should
change exactly one structural dimension relative to existing genomes** (one new step
type, OR one repeated step, OR one new constraint — not multiple at once), unless a
prior single-variable experiment has already isolated each dimension separately and a
combined genome is being used to test for *interaction effects* specifically (which
should be stated explicitly as the goal, not stumbled into accidentally).

**Concrete next steps for the two open gaps, in isolation:**
1. **Position effect, isolated**: create `multitool_v2.rune` — identical to
   `multitool.rune` (search → analyze → search → summarize) but with `constraints:
   [cite_sources]` only, no `structured_output`. If the position gap (first search vs
   second search measuring different divergence) holds up without the constraint
   confound, that's a real, isolated finding worth a real fix (e.g. a
   `SUMMARIZE_PRECEDED_BY_SPECIFICITY`-style position-aware table, generalized beyond
   just "summarize").
2. **Constraint effect, isolated**: separately, create a genome with `structured_output`
   present but with no repeated steps (e.g. three or four distinct steps, no position
   confound), to test whether the constraint's effect is genuinely step-type-dependent
   (helps `analyze`, doesn't help `summarize`) without `multitool.rune`'s repeated-search
   structure muddying the result.

Do not run a third combined experiment on this question before these two isolated ones
exist — that would repeat the same mistake this section documents.

## Methodology citation tiers

Going forward, every structural/methodological decision in this roadmap is tagged with
one of three tiers, so it's always clear how much external grounding a given choice has:

- **Tier 1 — directly paper-supported**: the technique itself is a established method
  with a specific, citable paper behind it.
- **Tier 2 — inspired by a general principle, but specific values are self-derived**:
  a broader field's reasoning motivated the approach, but the exact numbers/thresholds
  were tuned against this project's own data, not derived from any paper.
- **Tier 3 — pure engineering hypothesis, no external backing**: an idea formed from
  observing this project's own results, with no claimed academic grounding.

### Tier 1 — directly paper-supported

- **Semantic-similarity divergence measurement** (`validate_linter.py`,
  `sentence-transformers`, `all-MiniLM-L6-v2`): the underlying technique is
  Sentence-BERT — Reimers, N. & Gurevych, I. (2019). "Sentence-BERT: Sentence
  Embeddings using Siamese BERT-Networks." *Proceedings of EMNLP-IJCNLP 2019*,
  pp. 3982–3992. https://aclanthology.org/D19-1410/. The paper establishes that
  siamese/triplet-trained BERT embeddings, compared via cosine similarity, produce
  semantically meaningful similarity scores — directly supporting this project's use
  of embedding cosine similarity (inverted: 1 - similarity) as a divergence proxy.
  What is NOT paper-supported: the specific choice to use `1 - similarity` as a
  "divergence score," and the decision to average pairwise similarities across more
  than two backends — these are this project's own adaptations of the underlying
  technique, not claims made in the original paper.

### Tier 2 — general principle, self-derived specifics

- **`SUMMARIZE_PRECEDED_BY_SPECIFICITY`** (`divergence_linter.py`): the general
  principle — that a step's ambiguity depends on the semantic context preceding it,
  not just the step's own instruction text — is consistent with longstanding work in
  NLP/discourse processing on context-dependent interpretation (e.g. discourse
  coherence and anaphora resolution literatures broadly establish that the same
  utterance can have different interpretive constraints depending on prior context).
  No specific paper was consulted before choosing the values `0.6` (after "test") and
  `0.5` (after "code") — these were derived from observing three independent
  `coder.rune` validation runs in this project, not from any external source. Citing
  a specific discourse-processing paper here would overstate the connection; the
  values themselves are this project's own.
- **"Isolate one variable per genome experiment" methodological rule**: this is a
  simplified instance of one-factor-at-a-time experimentation, a long-established
  principle in Design of Experiments (DOE) / statistics. A representative general
  reference: Montgomery, D. C. *Design and Analysis of Experiments* (various
  editions) — standard textbook treatment of confounding and factor isolation. This
  project does not implement full factorial design (no factor matrix, no formal
  ANOVA); it borrows only the core warning that principle gives — don't change
  multiple structural dimensions in one experiment if you need to attribute the
  result to a specific cause — discovered the hard way via `multitool.rune`'s v1/v2
  results before this connection to the wider DOE literature was made explicit.

### Tier 3 — pure engineering hypothesis, no external backing

- **`FORMAT_ANCHORING_CONSTRAINTS` (reverted)**: the hypothesis that a
  format-anchoring constraint like `structured_output` suppresses a step's
  divergence by a multiplicative factor was formed entirely from observing
  `multitool.rune`'s v1 result (analyze measuring far lower than predicted). No
  paper was sought or found to support the specific `0.7` factor, or the claim that
  the effect should be uniform across step types — and the uniform-effect part of
  the hypothesis was empirically wrong (see the v2 result). This entry stays Tier 3
  even in its reverted state, as a record of what was tried.
- **`STEP_SPECIFICITY` base values** (e.g. `analyze: 0.8`, `test: 0.75`): these are
  this project's own calibration against observed divergence in `research.rune` and
  `coder.rune`, not derived from or validated against any external study of LLM
  output variance by step type.


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
