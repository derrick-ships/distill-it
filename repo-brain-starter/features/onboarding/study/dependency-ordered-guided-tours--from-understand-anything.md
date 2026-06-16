# Dependency-Ordered Guided Tours — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
It builds a guided walkthrough of a codebase — 5 to 15 steps that teach the architecture in a
sensible order, starting from the README or entry point and following the dependency structure
outward. Each step has a title, a 2–4 sentence explanation of what and why, the nodes it covers,
and optionally a short language lesson (e.g., how React hooks work) tied to what you're seeing.

## Why it exists
The worst way to learn a codebase is alphabetically or by clicking around randomly. People learn
best in dependency order: understand the foundations first, then the things built on them. But
computing that order by hand is exactly the kind of graph math humans are bad at — so a script
computes the structure and an LLM writes the narrative. You get a guided onboarding path instead
of a file tree.

## How it actually works
Two phases, mirroring the project's deterministic-then-semantic philosophy:
1. **Graph analysis script** (deterministic) computes the signals a good tour needs:
   - **Fan-in ranking** (most depended-upon nodes → explain early), **fan-out ranking** (broad-
     scope nodes → good for overviews).
   - **Entry-point candidates**, scored by filename patterns (`index.ts`, `main.py`), shallow
     depth, and fan-in/fan-out percentiles; the root `README.md` gets a +5 bonus.
   - **BFS traversal** from the top entry point along `imports`/`calls` edges, recording visit
     order and depth (depth 0 = entry, 1 = direct deps, 2+ = deeper).
   - **Tightly-coupled clusters** (2–5 mutually connected nodes → teach as one step).
   - A node-summary index and the architectural layer list.
2. **Pedagogical design** (LLM) reads *only* that script output (never re-analyzes the graph) and
   composes the tour: start at the README/entry point, follow BFS depth for overview→detail, weave
   in non-code stops (Dockerfile, CI, SQL schema) at logical points, group coupled clusters, and
   structure foundational layers before dependent ones. It writes newcomer-friendly step
   descriptions and optional language lessons.

## The non-obvious parts
- **The LLM is forbidden from re-reading source.** All structural truth comes from the script;
  the model only narrates. This keeps tours grounded and reproducible.
- **Non-code stops matter.** A good tour includes at least one or two non-code files (docs, infra,
  schema) — they're often where the "why" lives.
- **Strict ordering invariant**: steps are numbered 1..N with no gaps, each with 1–5 node IDs,
  none empty, every ID verified to exist. A dangling ID breaks the tour player.
- **Language lessons are contextual teaching**: 12 concepts across TS/React/Python/Go/Rust plus
  non-code formats (Docker multi-stage, SQL idempotency, Protobuf field numbering, K8s
  Deployments…), attached where the pattern actually appears.
- Same deterministic-signals-then-LLM-narrative split as the whole
  [[multi-agent-analysis-pipeline--from-understand-anything]].

## Related
- [[knowledge-graph-data-model--from-understand-anything]] — provides the `tour` array + nodes
- [[multi-agent-analysis-pipeline--from-understand-anything]] — the tour phase
- [[interactive-graph-dashboard--from-understand-anything]] — plays the tour back visually
