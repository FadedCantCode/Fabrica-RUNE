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
- [ ] Record actual correlation coefficients, not just the synthetic test in this repo's
      history. If correlation is weak or negative, say so and revise the heuristic weights
      in `divergence_linter.py`, or scrap the specific signals that don't hold up.
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
      — final correlation 0.967, also a positive result. multitool.rune family: v1
      correlation -0.086, a fix attempt made it worse (-0.604, reverted), and an isolated
      follow-up (multitool_v2.rune, no structured_output) confirmed the position effect
      is real and not a constraint artifact (-0.066, same weak correlation, but the
      search-step-1-vs-step-3 divergence gap persisted at the same magnitude) — see
      detailed history below. Honest status: 2/3 genome shapes positively validated, 1
      family genuinely unresolved but now with two repeated, real, separated findings
      — position-dependent divergence, and an analyze-specific constraint-suppression
      effect — that need a real heuristic fix, not another guess, before this item can
      be called satisfied.)

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

### Recorded result: 2026-06-17, `groq_qwen` vs `mistral`, `coder.rune`, 12 tasks (v1, before fix)

Correlation between predicted risk and measured divergence: **0.152** (weak/no
correlation, per `validate_linter.py`'s own interpretation — below the ≤-0.5/≥0.5
thresholds entirely, landing in the "no real signal" middle band).

**This is an important negative result, not a footnote.** All three prior results above
were measured on `research.rune` alone (search → analyze → summarize, one tool step).
`coder.rune` has a structurally different genome (analyze → code → test → summarize,
*zero* tool steps, different constraint). On this genome, the linter predicted `analyze`
as highest risk and `summarize` as lowest — the same ranking pattern it produced for
`research.rune` — but measured divergence came back nearly flat (0.637–0.773) and in a
different order: `test` (0.773) diverged more than the predicted-highest-risk `analyze`
(0.746), the reverse of the prediction.

### Fix attempt: revised `test` step specificity (2026-06-17)

Hypothesis: `STEP_SPECIFICITY["test"] = 0.55` underrated how open-ended "verify your
code works" actually is — no fixed format models converge on (unit tests vs prose
reasoning vs mental trace-through), arguably closer to `analyze`'s ambiguity than to
`code`'s. Revised to 0.75. This was a substantive re-read of the instruction, not a fit
to the v1 dataset — see `divergence_linter.py`'s `STEP_SPECIFICITY` comment for the full
reasoning.

### Recorded result: 2026-06-17, `groq_qwen` vs `mistral`, `coder.rune`, 12 tasks (v2, after fix)

Correlation: **0.362** (still weak/no correlation — improved from 0.152, but not a
pass). The `test`/`analyze` ranking moved closer to matching, which is what the fix
targeted, but a different, more fundamental issue surfaced: measured divergence across
*all four* steps now sits in a narrow band (0.615–0.767), narrower spread than
`research.rune` ever showed even in its weakest moments. `summarize` measured almost as
high as `analyze`/`test` (0.738) despite being predicted as clearly lowest-risk (0.255).

**Honest read: this looks like a measurement-methodology limitation, not a weights
problem.** Code as an output format has many valid surface forms — variable names,
comments, formatting, equivalent control-flow choices — that would register as lexically
divergent under the current Jaccard word-overlap proxy even when two implementations are
functionally identical. If that's what's happening, no amount of reweighting
`STEP_SPECIFICITY` will fix it, because the problem is in how divergence itself is being
measured for code-shaped output, not in which step is "supposed" to be risky. This adds
real weight to the already-planned Stage 1 item below (replacing Jaccard with
embedding-based semantic similarity) — that item was previously framed as a general
improvement; this result suggests it may be a *requirement* specifically for genomes
with code-producing steps, not just a nice-to-have.

**Status: open, not resolved.** Don't tune `STEP_SPECIFICITY` further against this
dataset — that risks fitting noise. The next real step is implementing semantic
similarity for divergence measurement and re-running `coder.rune` before drawing any
further conclusion about whether the heuristic itself is sound for this genome shape.

### Recorded result: 2026-06-17, `groq_qwen` vs `mistral`, `coder.rune`, 12 tasks (v3, semantic similarity)

Correlation: **0.497** — a real improvement from 0.362, but landing just under
`validate_linter.py`'s own ≥0.5 threshold for a positive signal. Measured divergence
dropped sharply across every step (0.099–0.216, down from 0.615–0.773 under Jaccard) and
the relative spread between steps became much clearer: `code` is now unambiguously the
lowest-divergence step, `test` the highest, `analyze` and `summarize` in between.

**This partially confirms the measurement-bias hypothesis.** The sharp overall drop in
divergence scores, especially for `code` — supports the theory that Jaccard was
penalizing code for surface-level variation (variable names, formatting) that semantic
similarity correctly recognizes as equivalent. Switching measurement methods produced a
materially more informative result, not just a smaller number.

**But it didn't fully resolve the mismatch.** Predicted order is `analyze` > `test` >
`code` > `summarize`; measured order is `test` > `analyze` > `summarize` > `code`. `test`
now correctly ranks near the top (validating the earlier `STEP_SPECIFICITY` fix's
direction), but `summarize` measured as the second-highest-divergence step despite being
predicted as clearly lowest-risk (0.255) — that specific mismatch has now persisted
across all three `coder.rune` runs (v1, v2, v3) regardless of which fix was applied.
That consistency across three different conditions is itself informative: it points at
`summarize`'s `STEP_SPECIFICITY` value (0.3) or its constraint-coverage scoring as the
next place to actually look, rather than at measurement noise.

**Honest summary across all three coder.rune attempts:** the measurement method
mattered (Jaccard → semantic similarity moved correlation from 0.362 to 0.497), and the
`test` specificity fix mattered (0.152 → 0.362), but neither fix alone, nor both
combined, has yet produced a result that clears the project's own bar for "the linter
predicts this genome's divergence." `summarize` is the one consistent, unexplained
discrepancy across every version of this experiment. Before claiming the linter
generalizes to `coder.rune`, that needs a real explanation — not another reweighting
guess, but the same kind of substantive reasoning that produced the `test` fix:
what about "summarize your test results" specifically might make models diverge more
than `STEP_SPECIFICITY=0.3` assumes?

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
lower `specificity_risk`, not just contribute to coverage.

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

### Recorded result: 2026-06-18, `groq_qwen` vs `mistral`, `multitool_v2.rune`, 12 tasks (position effect, isolated)

`multitool_v2.rune` is identical to `multitool.rune` (search → analyze → search →
summarize) but with only `cite_sources` — no `structured_output` — to isolate the
position effect from the constraint effect per the methodological rule above.
Correlation: **-0.066**, still weak/negative, same magnitude as `multitool.rune`'s v1
result (-0.086). This was expected: the heuristic itself wasn't touched for this run,
only the genome, so no correlation improvement was predicted going in. The point of
this run was diagnostic, not a fix attempt.

**Position effect: confirmed, not a constraint artifact.** `search (step 1)` measured
0.156, `search (step 3)` measured 0.26 — a ~1.7x gap, closely matching `multitool.rune`
v1's ~1.5x gap (0.178 vs 0.264) in the same direction, now with `structured_output`
completely removed from the picture. This is the second independent genome to show the
same pattern: a repeated tool step measures higher divergence later in the genome than
earlier, regardless of which constraints are present. This is now real, repeated
evidence — not yet enough to justify a specific numeric fix (still only two genomes,
12 tasks each), but enough to treat the underlying hypothesis (divergence compounds
with position, since each model's later steps react to its own already-diverged earlier
output) as a credible, falsifiable claim worth testing further rather than open
speculation.

**Constraint-on-`analyze` hypothesis: gained supporting evidence.** In `multitool.rune`
v1 (with `structured_output`), `analyze` measured as the *lowest*-divergence step
(0.208) despite being predicted highest. Here, with `structured_output` removed,
`analyze` measured 0.223 — still below its prediction, but no longer the clear lowest;
it now sits in the middle of the pack alongside `summarize` (0.233), rather than at the
bottom. That's the direction the `structured_output`-suppresses-`analyze` hypothesis
predicts: remove the constraint, `analyze`'s relative divergence should creep back up
toward (though not necessarily reach) its prediction, and it did. Two data points
pointing the same direction is suggestive, not proof, but it's a second, independent
genome supporting the same specific mechanism.

**Still unexplained:** `summarize`'s instability under `structured_output` (predicted
lowest, measured second-highest in `multitool.rune` v2) hasn't been tested in isolation
from the position effect or from `analyze`'s behavior — that requires the second
isolated experiment from the methodological rule above (a genome with
`structured_output` and no repeated steps), still not yet built.

**Status: two real, separate findings now have repeated evidence; no new fix has been
attempted on either.** The honest next step is either (a) building the
constraint-effect-isolated genome to get a clean read on `structured_output` without any
position confound at all, or (b) accepting these two findings as the project's two
clearest open limitations and moving forward on a different priority (sample size,
cross-pairing validation) while documenting these as known, unresolved gaps rather than
chasing a third fix attempt on limited data.

### NULL RUNE baseline added (2026-06-18)

Added `examples/null_baseline.rune`: a single `summarize` step, no tools, no
constraints, intended to measure a "divergence floor" — how much disagreement exists
between models even when the genome imposes essentially no structure.

**Honest tradeoff, documented in the file itself, not just here:** this reuses the
existing `summarize` step rather than introducing a genuinely neutral step type.
`summarize` carries real task semantics — compression, abstraction, rephrasing — that
are themselves a kind of structure, not the absence of one. A true causal zero-point
would need a new step type (e.g. `direct_response`) with no inherent transformation
bias, requiring changes to `KNOWN_STEPS` in `rune_loader.py` and `STEP_INSTRUCTIONS` in
`runtime.py`. That's deferred for now as real, but currently unjustified, engineering
cost. Treat any divergence measured against this baseline as a rough floor estimate
contaminated by `summarize`'s own task semantics, not a precise zero-point — useful for
relative comparison ("is genome X's divergence meaningfully above this floor?"), not
for strict causal attribution claims.

**Technical note for running this:** `validate_linter.py`'s `correlation` field will
correctly come back `null` for this genome, since correlation requires variance across
at least two data points and this genome has only one step. That's expected, not a
bug — the quantity of interest here is the raw `measured_divergence` value itself, not
a correlation. Read the `measured_divergence` field directly when using this baseline;
ignore the `null` correlation and the "too few steps" interpretation message, both are
working as intended for a single-step genome.

### Recorded result: 2026-06-18, `groq_qwen` vs `mistral`, `null_baseline.rune`, 12 tasks

Measured divergence on the single `summarize` step, no tools, no constraints: **0.116**.
This is the floor — roughly how much two different models will disagree on *any*
unconstrained question, independent of any genome structure at all.

**Re-reading every prior result as a multiple of this floor changes the picture
materially.** Raw divergence scores in isolation don't say much; expressed as
floor-multiples, they reveal which results represent a real, structure-induced effect
and which are statistically close to noise:

| Genome | Step | Measured | × floor |
|---|---|---|---|
| research.rune | analyze | 0.853 | 7.35× |
| research.rune | search | 0.823 | 7.09× |
| research.rune | summarize | 0.802 | 6.91× |
| coder.rune | test | 0.186 | 1.60× |
| coder.rune | analyze | 0.185 | 1.59× |
| coder.rune | summarize | 0.154 | 1.33× |
| coder.rune | code | 0.113 | 0.97× |
| multitool_v2.rune | search (step 3) | 0.26 | 2.24× |
| multitool_v2.rune | summarize | 0.233 | 2.01× |
| multitool_v2.rune | analyze | 0.223 | 1.92× |
| multitool_v2.rune | search (step 1) | 0.156 | 1.34× |

**Honest read: `research.rune`'s validation is much stronger evidence than `coder.rune`'s
or `multitool_v2.rune`'s, even though all three produced usable correlations.**
`research.rune`'s every step sits 7× above the noise floor — a large, unambiguous,
structure-induced effect. `coder.rune`'s `code` step (0.97×) is statistically
indistinguishable from two models answering literally any unconstrained question; its
other three steps sit only 1.3–1.6× above floor, real but modest. `multitool_v2.rune`'s
steps sit in a similar 1.3–2.2× range. `coder.rune`'s 0.967 correlation and
`multitool_v2.rune`'s position-effect finding are both still real — the *rankings* among
steps clearly aren't random — but the *absolute magnitude* of divergence being predicted
in these two genomes is much smaller and closer to baseline noise than `research.rune`'s
was. This doesn't invalidate either result, but it does mean "the linter works" should
be read as having much stronger support on `research.rune`-shaped genomes than on
`coder.rune`- or `multitool`-shaped ones, where the effect being measured is real but
considerably weaker relative to baseline noise.

**One important limitation of this baseline itself:** the floor was measured using
`summarize`, which per the caveat above carries its own task semantics — it is not
necessarily *the* floor for every step type. `code`, for instance, might have a
different natural floor than `summarize` does (code may have a narrower or wider band of
"reasonable answers" than prose summary does), so comparing `coder.rune`'s `code` step
(0.113) directly against a `summarize`-derived floor (0.116) and calling it "at the
floor" is suggestive, not rigorously established — a fully neutral baseline (the
`direct_response` step type discussed above) would be needed to confirm this cleanly per
step type, rather than using one floor value for every comparison.

### Recorded result: 2026-06-18, `groq_qwen` vs `mistral`, `coder_structured.rune`, 12 tasks (constraint effect, isolated)

`coder_structured.rune` is identical to `coder.rune` (analyze → code → test →
summarize, no repeated steps, no tool steps) but with `structured_output` added
alongside `cite_sources`, to isolate the constraint effect from the position effect with
zero position confound at all. Correlation: **-0.419**, weak/negative, similar magnitude
to the `multitool.rune` family's results.

**This contradicts the working hypothesis from `multitool.rune`, not confirms it.** The
hypothesis going in was that `structured_output` suppresses `analyze`'s divergence
specifically. The direct paired comparison against `coder.rune`'s existing measured
values (same tasks, same backends, only `structured_output` added) shows a different,
unexpected pattern:

| Step | coder.rune | coder_structured.rune | Δ | Direction |
|---|---|---|---|---|
| analyze | 0.185 | 0.176 | -0.009 | flat |
| code | 0.113 | 0.384 | +0.271 | sharply up |
| test | 0.186 | 0.355 | +0.169 | sharply up |
| summarize | 0.154 | 0.188 | +0.034 | modestly up |

**`analyze` barely moved at all** — essentially flat, not the clear suppression seen
in `multitool.rune`. This is a real strike against treating that earlier finding as a
general property of `structured_output`; it may have been specific to the `multitool`
genome shape (where `analyze` sits between two `search` steps) rather than a property of
the constraint itself.

**`code` and `test` moved sharply in the opposite direction — amplified, not
suppressed.** `code` was sitting almost exactly at the `null_baseline.rune` noise floor
in plain `coder.rune` (0.97×); under `structured_output` it jumped to roughly 3.3× floor.
`test` nearly doubled. Neither step was part of the original hypothesis at all.

**Working reinterpretation, not yet tested further:** a plausible mechanism — stated as
a hypothesis, not a conclusion — is that `structured_output`'s effect may depend on
whether a step's *natural* output format is already prose-like or not. `analyze` and
`summarize` (whose unconstrained output is already prose) show flat-to-modest movement
under the constraint. `code` and `test` (whose unconstrained output naturally wants to
be a code block or a procedural trace, not headers-and-lists) show large movement —
possibly because forcing two different models to "listify" something that doesn't
naturally fit that shape produces *more* divergent structural choices between them, not
fewer. This would mean the earlier framing ("helps interpretive steps like analyze")
was the wrong generalization; a better one might be "the effect depends on how far the
constraint pushes a step away from its natural unconstrained format," which is a
different, more specific claim than what was tested for here.

**Status: open, not resolved, and the original hypothesis is now weakened, not
supported.** This result does NOT justify reinstating `FORMAT_ANCHORING_CONSTRAINTS`
with `analyze`-specific suppression — that hypothesis just failed its first clean,
position-confound-free test. Before any further fix attempt, this new
natural-format-distance hypothesis needs its own additional isolated test (e.g. a genome
mixing prose-natural and non-prose-natural steps in a different combination) — not
another single-run fix applied directly to this dataset, which would repeat the exact
curve-fitting mistake already documented twice in this file.

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
