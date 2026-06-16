# Diff Impact Analysis (build spec) — distilled from Understand-Anything

## Summary
Project a set of changed files onto an existing knowledge graph and return the blast radius:
changed nodes, their contained children, one-hop affected neighbors, impacted edges, and affected
layers. Pure graph traversal, no LLM. A formatter flags high-risk patterns.

## Core logic (inlined)
```typescript
interface DiffContext {
  changedNodes: GraphNode[];
  affectedNodes: GraphNode[];
  impactedEdges: GraphEdge[];
  affectedLayers: Layer[];
}

function buildDiffContext(graph: KnowledgeGraph, changedFiles: string[]): DiffContext {
  // 1. file -> node mapping
  const changed = graph.nodes.filter(n => changedFiles.includes(n.filePath));
  const unmapped = changedFiles.filter(f => !graph.nodes.some(n => n.filePath === f));
  const changedIds = new Set(changed.map(n => n.id));

  // 2. transitive expansion via 'contains' (file -> its functions/classes)
  for (const edge of graph.edges)
    if (edge.type === 'contains' && changedIds.has(edge.source))
      changedIds.add(edge.target);

  // 3. one-hop impact
  const impactedEdges = [], affectedIds = new Set();
  for (const edge of graph.edges) {
    const s = changedIds.has(edge.source), t = changedIds.has(edge.target);
    if (s || t) {
      impactedEdges.push(edge);
      const neighbor = s ? edge.target : edge.source;
      if (!changedIds.has(neighbor)) affectedIds.add(neighbor);
    }
  }

  // 4. affected layers = layers containing any changed or affected node
  const touched = new Set([...changedIds, ...affectedIds]);
  const affectedLayers = graph.layers.filter(L => L.nodeIds.some(id => touched.has(id)));

  return { changedNodes, affectedNodes, impactedEdges, affectedLayers /*, unmapped*/ };
}
```
Risk formatter (`formatDiffAnalysis`) flags:
- complex component changed (node.complexity === 'complex')
- cross-layer impact (affectedLayers.length > 1)
- wide blast radius (affectedNodes.length > 5)
- unmapped files present (graph stale -> recommend re-scan)

## Data contracts
Reads the standard knowledge graph (`nodes[]` with `id,filePath,complexity`; `edges[]` with
`source,target,type`; `layers[]` with `id,name,nodeIds[]`). `changedFiles` is a string[] of repo-
relative paths (e.g. from `git diff --name-only`). Output is the `DiffContext` above.

## Dependencies & assumptions
- An existing knowledge graph for the repo (built by the pipeline).
- A way to obtain changed files (git diff, PR file list, watcher).
- No model calls; runs in-process.

## To port this, you need:
- [ ] A graph with `filePath` on file nodes and a `contains` edge from file -> its members.
- [ ] An edge list traversable both directions.
- [ ] Layer membership (`layers[].nodeIds`) for the layer-aggregation step.
- [ ] A source of changed file paths.

## Gotchas
- Keep it to ONE hop. Transitive closure makes "affected" meaningless on real repos.
- `contains` expansion matters: a changed file must drag in its functions/classes or you under-
  report. Requires the pipeline to have emitted `contains` edges.
- Treat unmapped files as "graph is stale here," not as nothing-to-see.
- Matching is by exact `filePath`; normalize separators/relative roots before comparing.

## Origin (reference only)
`understand-anything-plugin/src/diff-analyzer.ts` (`buildDiffContext`, `formatDiffAnalysis`);
surfaced via the `/understand-diff` skill.
