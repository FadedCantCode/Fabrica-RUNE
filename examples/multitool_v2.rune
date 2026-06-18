species: multitool_v2
version: "0.1.0"
description: >
  Identical genome shape to multitool.rune (search -> analyze -> search ->
  summarize), but with only the cite_sources constraint, deliberately
  omitting structured_output. Built 2026-06-17 to isolate the
  position-dependent divergence effect observed in multitool.rune from
  the format-anchoring constraint effect also present there — testing
  one structural variable at a time rather than two simultaneously.
  See docs/roadmap.md Stage 1, "Methodological rule" section, for why
  this isolation matters.

genome:
  - search
  - analyze
  - search
  - summarize

tools:
  - search

constraints:
  - cite_sources

behavior:
  curiosity: 0.6