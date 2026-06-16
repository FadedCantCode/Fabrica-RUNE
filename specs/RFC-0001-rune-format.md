# RFC-0001: The Rune File Format

Status: Draft
Version: 0.1.0

## 1. Purpose

Define the `.rune` file format: a YAML document describing an agent's behavior
specification independent of any model backend.

## 2. File Extension and Encoding

- Extension: `.rune`
- Encoding: UTF-8 YAML, parseable by any standard YAML 1.1 parser
- A `.rune` file MUST be valid YAML. It is not a binary format.

## 3. Top-Level Schema

```yaml
species: <string>          # required — identifier for this agent spec
version: <string>          # required — semver of the rune schema this file targets
description: <string>      # optional — human-readable summary

genome:                    # required — ordered list of steps the agent executes
  - <step_name>
  - <step_name>

tools:                     # required — tools the agent is permitted to invoke
  - <tool_name>

constraints:                # optional — behavioral rules the runtime should enforce
  - <constraint_name>

behavior:                  # optional — scalar parameters influencing model sampling
  <key>: <float 0.0-1.0>
```

### 3.1 `species` (required, string)

A human-readable identifier, e.g. `research`, `coder`. Used for logging and for
naming generated transcripts. Not currently used for any matching/dispatch logic.

### 3.2 `version` (required, string)

Semver string identifying which version of this RFC's schema the file was written
against. The current schema version is `0.1.0`. Runtimes MUST reject files declaring
a major version they don't support.

### 3.3 `genome` (required, list of strings)

An ordered list of step names. The runtime executes these steps in sequence, prompting
the backend model to perform each one before moving to the next. Step names are free-form
strings interpreted by the runtime's prompt-construction logic; this RFC reserves the
following step names with defined meaning:

| Step name | Meaning |
|---|---|
| `search` | The agent must look up information relevant to the task |
| `analyze` | The agent must reason over previously gathered information |
| `summarize` | The agent must produce a condensed final answer |
| `code` | The agent must produce a code artifact |
| `test` | The agent must verify a previously produced code artifact |

Runtimes MAY support additional step names; unsupported step names MUST cause a
load-time error rather than being silently skipped.

### 3.4 `tools` (required, list of strings)

Tool names the agent is permitted to use. In the reference implementation, only `search`
is implemented (a literal web search call). This list functions as a permission allowlist;
a step requiring a tool not listed here MUST cause a load-time error.

### 3.5 `constraints` (optional, list of strings)

Free-form behavioral rules injected into the system prompt sent to the backend model.
The reference implementation defines one:

| Constraint | Effect |
|---|---|
| `cite_sources` | Instructs the model to attribute claims to sources found during `search` |

Constraints are advisory: the runtime does not currently verify model compliance with a
constraint at execution time. See `docs/roadmap.md` Stage 1 for planned compliance
checking.

### 3.6 `behavior` (optional, map of string to float)

Scalar parameters in `[0.0, 1.0]` that the runtime maps to backend-specific sampling
settings (currently: `curiosity` maps to `temperature` linearly). Reserved keys:

| Key | Effect |
|---|---|
| `curiosity` | Higher values increase backend sampling temperature |

## 4. Minimal Valid Example

```yaml
species: research
version: "0.1.0"

genome:
  - search
  - analyze
  - summarize

tools:
  - search

constraints:
  - cite_sources

behavior:
  curiosity: 0.8
```

## 5. Runtime Contract

A conforming runtime MUST:

1. Parse the file as YAML and validate it against §3 before execution.
2. Execute `genome` steps in the declared order, regardless of backend.
3. Refuse to execute a step requiring a tool absent from `tools`.
4. Pass declared `constraints` into whatever instruction-construction mechanism it uses
   for the backend (e.g. system prompt, structured instruction field).
5. Produce a transcript recording, at minimum: which step was executing, what the backend
   produced for that step, and the final summarized output.

A conforming runtime is NOT required to guarantee identical output text across backends.
Behavioral *consistency* (same step sequence followed, same tools invoked, comparable
final answer) is the target; output text identity is not, and should never be claimed.

## 6. Non-Goals of This RFC

This RFC does not define:

- Mutation, crossover, or any evolutionary operator over Rune files
- A binary serialization of this format
- Multi-agent communication or composition semantics

These may be addressed in future RFCs once the schema in this document has been used and
tested. No future RFC number is reserved or implied here.
