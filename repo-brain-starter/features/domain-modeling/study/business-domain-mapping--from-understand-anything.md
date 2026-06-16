# Business Domain Mapping — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
It reads the code and tells you what *business* it implements — not "here are the files," but
"this codebase does Order Management, and Order Management contains a Create-Order flow, which has
these steps: validate input, reserve inventory, charge payment." It produces a second graph whose
nodes are business domains, flows, and steps, mapped back to the actual files and line ranges.

## Why it exists
Engineers navigate by files; everyone else (product, support, new hires, the business) thinks in
processes. The gap between "where is the code" and "what does the company do" is where knowledge
goes to die. This feature bridges it — making the codebase legible to non-engineers and showing
engineers where business logic actually lives, grounded only in what the code really does.

## How it actually works
Run via `/understand-domain`. It takes either a preprocessed domain context (file tree, entry
points, imports/exports, code snippets) or the existing structural knowledge graph, and the
`domain-analyzer` agent organizes it into a strict three-level hierarchy:
- **Business Domain** — a high-level area ("Order Management"). Carries `domainMeta`: entities,
  business rules, and cross-domain interactions.
- **Business Flow** — a process inside a domain ("Create Order"). Has an `entryPoint` and
  `entryType`.
- **Business Step** — one action inside a flow ("Validate input"), pointing at a `filePath` and
  `lineRange`.

These connect with typed edges: `contains_flow` (domain → flow) and `flow_step` (flow → step). The
steps in a flow are *ordered* by giving their `flow_step` edges monotonically increasing weights —
for N steps, each weight increments by `round(1/N, 1)`, staying within 0.0–1.0 — so the sequence of
a process is explicit. `cross_domain` edges capture interactions between domains. The result is
written to `.understand-anything/intermediate/domain-analysis.json` (a domain-graph).

## The non-obvious parts
- **Ordered edges encode process sequence.** The monotonically-increasing `flow_step` weights are
  how a flat graph represents "step 1 then step 2 then step 3" — a neat trick for putting order
  into edges.
- **Only document what exists.** The agent is explicitly told not to invent flows that aren't in
  the code — no aspirational business processes, only ones traceable to real files.
- **kebab-case IDs everywhere** (`domain:order-management`, `flow:create-order`,
  `step:validate-input`) — consistent with the main graph's ID discipline.
- **Every flow must link to its domain** via `contains_flow`, or it's an orphan.
- It reuses the same nodes/edges philosophy as the
  [[knowledge-graph-data-model--from-understand-anything]], just at the business layer.

## Related
- [[knowledge-graph-data-model--from-understand-anything]] — the structural graph it can build on
- [[multi-agent-analysis-pipeline--from-understand-anything]] — domain analysis is a parallel command
- See also: Domain-Driven Design — this is an automated, code-grounded DDD context map
