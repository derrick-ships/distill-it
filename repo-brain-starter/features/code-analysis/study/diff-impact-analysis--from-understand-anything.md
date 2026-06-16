# Diff Impact Analysis — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
You're about to change some files. This tells you what else might break — the "blast radius."
Given the list of changed files, it highlights every node in the knowledge graph those files
touch, every node one hop away that depends on them, and which architectural layers are affected.
It then flags the scary cases: complex components, changes that cross more than one layer, or a
ripple hitting more than five downstream components.

## Why it exists
The cost of a change isn't the diff — it's everything the diff quietly affects. Reviewers and
newcomers can't hold a big system's dependency web in their heads. By projecting a git diff onto
the pre-built graph, the tool turns "I changed `auth.ts`" into "this touches 3 layers and 8
downstream components, two of them complex — review carefully." It's a cheap early-warning system
that reuses analysis already done.

## How it actually works
It's a graph traversal, not another LLM pass — fast and deterministic:

1. **Map files to nodes** — for each changed file, find graph nodes whose `filePath` matches.
   Files with no node are tracked as "unmapped" (they need re-analysis; the graph doesn't know
   them yet).
2. **Pull in contained children** — if a changed file node `contains` functions/classes, those
   come along too (a changed file implies its definitions changed).
3. **One-hop impact** — walk every edge touching a changed node; the node on the other end is
   marked *affected* (unless it's itself changed), and the edge is recorded as *impacted*. That's
   the immediate blast radius.
4. **Aggregate layers** — any layer containing a changed or affected node is an *affected layer*,
   giving architectural context.

Then a formatter turns the raw `DiffContext` into a human risk report, raising flags for complex
components, cross-layer impact (>1 layer), wide blast radius (>5 downstream), and unmapped files.

## The non-obvious parts
- **It's one hop, on purpose.** It doesn't compute full transitive closure — that would mark half
  the repo "affected" and be useless. One hop is the sweet spot for "what should I actually look
  at." (Contrast the full pipeline's incremental mode, which *re-analyzes* changed files rather
  than scoring their impact — see [[multi-agent-analysis-pipeline--from-understand-anything]].)
- **Unmapped files are a signal, not an error** — they mean the graph is stale for those paths and
  a re-scan is warranted.
- **It's free comprehension reuse** — no new model calls; it rides entirely on the existing graph.

## Related
- [[knowledge-graph-data-model--from-understand-anything]] — the nodes/edges/layers it traverses
- [[multi-agent-analysis-pipeline--from-understand-anything]] — incremental re-analysis (different goal)
- [[interactive-graph-dashboard--from-understand-anything]] — where impact can be visualized
