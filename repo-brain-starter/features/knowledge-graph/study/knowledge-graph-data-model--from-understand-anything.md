# Knowledge Graph Data Model — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
This is the single JSON document the entire product revolves around. It describes a codebase as a
typed graph: **nodes** (files, functions, classes, configs, docs, services, tables, endpoints…),
**edges** (imports, calls, contains, deploys…), **layers** (architectural groupings), and a
**tour** (ordered learning path). It lives at `.understand-anything/knowledge-graph.json`, and you
can commit it to git so your whole team skips re-analysis.

## Why it exists
Every feature — search, chat, diff, dashboard, tours, onboarding — needs the same picture of the
code. Rather than each computing its own, they all read and write this one schema. Making it a
plain, versioned JSON file (not a database) means it's diffable, committable, shareable, and
renderable anywhere. The schema is the product's backbone; the agents are just things that fill
it in.

## How it actually works
The document has five top-level parts:
- **`project`** — name, languages, frameworks, description, `analyzedAt`, `gitCommitHash` (the
  last one powers incremental re-runs).
- **`nodes`** — each has an `id`, a `type` (one of 13), `name`, `summary`, `tags`, `filePath`,
  `complexity`. IDs follow strict conventions so they're stable and joinable: `file:<path>`,
  `function:<path>:<name>`, `class:<path>:<name>`.
- **`edges`** — `source`, `target`, `type` (one of ~26), `weight`, `confidence`. Weights are
  standardized (1.0 for `contains`, 0.9 for inheritance, 0.8 for calls/imports, 0.5 default) so
  downstream ranking is consistent.
- **`layers`** — architectural groups, each with `id` (`layer:<kebab>`), `name`, `description`,
  and the `nodeIds` it owns. Every file node must live in exactly the set of layers (full coverage).
- **`tour`** — ordered steps (`order`, `title`, `description`, `nodeIds`, optional
  `languageLesson`).

Because the schema is closed (fixed node/edge vocabularies) and IDs are deterministic, independent
analysis batches merge cleanly, and an incremental run can surgically delete and re-add the nodes/
edges for one file.

## The non-obvious parts
- **The graph is the integration layer.** Search, diff, tours, and the dashboard don't talk to
  each other — they all just read this file. That's what keeps the system modular.
- **Commit it, don't regenerate it.** Teams are meant to commit `knowledge-graph.json` (excluding
  the temp `intermediate/` dir), and large graphs can use git-lfs. Onboarding = `git pull`.
- **Standardized edge weights** aren't cosmetic — fan-in/fan-out and tour ordering depend on them
  being consistent across the whole graph.
- **Fingerprints + `meta.json`** sit alongside the graph to detect what structurally changed
  between runs, enabling cheap incremental updates.

## Related
- [[hybrid-static-semantic-extraction--from-understand-anything]] — produces the nodes/edges
- [[multi-agent-analysis-pipeline--from-understand-anything]] — fills the whole schema
- [[diff-impact-analysis--from-understand-anything]] / [[graph-search-retrieval--from-understand-anything]] / [[interactive-graph-dashboard--from-understand-anything]] — all read it
