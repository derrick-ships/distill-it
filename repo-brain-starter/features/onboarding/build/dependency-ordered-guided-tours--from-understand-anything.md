# Dependency-Ordered Guided Tours (build spec) — distilled from Understand-Anything

## Summary
Generate a 5–15 step learning tour from a knowledge graph: a deterministic script computes
fan-in/fan-out, entry-point scores, a BFS depth map, and coupled clusters; an LLM reads ONLY that
output and writes ordered, newcomer-facing steps (with optional language lessons). Output is the
graph's `tour[]` array.

## Core logic (inlined)
```
PHASE 1 — analysis script (Node, Python fallback), reads graph(nodes,edges,layers):
  fanIn[n]  = count incoming edges;  fanOut[n] = count outgoing edges
  entryPointCandidates = score(node):
        + filename pattern (index.ts/main.py/...)  + shallow depth (root/one level)
        + fanOut percentile  + fanIn percentile  ; README.md at root += 5
  bfsTraversal = BFS from top entry point over edges type in {imports, calls}
        -> { startNode, order[], depthMap{id:depth}, byDepth{0:[...],1:[...],2:[...]} }
  nonCodeFiles = { documentation[], infrastructure[], data[], config[] }
  clusters = groups of 2..5 nodes with high mutual connectivity (bidirectional / shared deps)
  layers = [{id,name,description}]
  nodeSummaryIndex = { id: {name,type,summary} }
  emit JSON { scriptCompleted:true, entryPointCandidates, fanInRanking, fanOutRanking,
              bfsTraversal, nonCodeFiles, clusters, layers, nodeSummaryIndex,
              totalNodes, totalEdges }

PHASE 2 — LLM designer (reads ONLY phase-1 JSON; does NOT re-read source/graph):
  start = README.md if present else top code entry point
  map bfsTraversal.byDepth -> steps (depth 0-1 overview, depth 2+ features/utils)
  weave >=1-2 non-code stops at logical junctures
  collapse each tight cluster into one step
  order foundational layers before dependent layers
  write step.description (2-4 sentences: WHAT, WHY, link to prior step)
  attach languageLesson where a known pattern appears (optional)
  emit tour[] (JSON array)
```

## Data contracts
Output `tour[]` (also a top-level key of the knowledge graph):
```json
[ { "order": 1, "title": "2-5 words", "description": "2-4 sentences",
    "nodeIds": ["node:id", "..."], "languageLesson": "optional" } ]
```
Invariants: `order` sequential 1..N no gaps; `nodeIds` length 1–5, never empty; every id exists
in `nodeSummaryIndex`; tour length 5–15. Phase-1 JSON shape as above.

Language-lesson catalog (12): TypeScript (generics/unions/decorators), React (hooks/context/
suspense), Python (decorators/generators/context-managers/protocols), Go (goroutines/channels/
interfaces), Rust (ownership/lifetimes/traits/async), Docker (multi-stage/layer cache),
docker-compose (depends_on/healthchecks/volumes), SQL (normalization/idempotent migrations),
GraphQL (type system/resolvers/fragments), Protobuf (permanent field numbers/backward compat),
YAML CI (triggers/jobs/matrix/cache), Kubernetes (Deployments/Services/ConfigMaps).

## Dependencies & assumptions
- A built knowledge graph with `imports`/`calls` edges and `layers`.
- Node (or Python) for the analysis script; an LLM for design.
- Accurate fan-in/fan-out → depends on the "emit ALL import edges" invariant from
  [[hybrid-static-semantic-extraction--from-understand-anything]].

## To port this, you need:
- [ ] A deterministic graph-signals script (fan-in/out, entry scoring, BFS depth, clusters).
- [ ] An LLM prompt that consumes only that JSON and emits ordered steps.
- [ ] Tour invariants validation (sequential order, non-empty existing nodeIds, 5–15 steps).
- [ ] (Optional) a language-lesson lookup keyed by node language/type.

## Gotchas
- If the LLM re-analyzes the graph itself, tours drift and hallucinate — hard-forbid it.
- Empty or dangling `nodeIds` break the player; validate every id against the index.
- Always include a non-code stop or two; pure-code tours miss the "why."
- Entry-point scoring leans on README +5 and filename patterns — tune for non-JS ecosystems.

## Origin (reference only)
`understand-anything-plugin/agents/tour-builder.md` + its bundled graph-analysis script.
