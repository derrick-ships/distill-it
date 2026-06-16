# Graph Search & Retrieval (build spec) — distilled from Understand-Anything

## Summary
Retrieve a focused subgraph for a query: match seed nodes via a SearchEngine over node text, then
expand one hop along edges, keep only edges with both endpoints in the set, and attach containing
layers. Output is a localized context window for an LLM (chat/search), not the whole graph.

## Core logic (inlined)
```javascript
// 1. seed match
const engine = new SearchEngine(graph.nodes);     // from @understand-anything/core
const seeds  = engine.search(query, { limit });   // best-matching nodes

// 2. one-hop expansion
const relevant = new Set(seeds.map(n => n.id));
for (const e of graph.edges)
  if (relevant.has(e.source)) relevant.add(e.target);
  else if (relevant.has(e.target)) relevant.add(e.source);
// (expansion adds neighbors of the ORIGINAL seeds)

// 3. coherent edge set: keep edges whose BOTH endpoints are relevant
const edges = graph.edges.filter(e => relevant.has(e.source) && relevant.has(e.target));

// 4. attach layers containing any relevant node
const layers = graph.layers.filter(L => L.nodeIds.some(id => relevant.has(id)));

// 5. context = { nodes: [...relevant], edges, layers } -> feed to LLM
```
For chat (`/understand-chat`): build this context, then prompt the model with it + the user
question; render the answer (markdown).

## Data contracts
Input: knowledge graph (`nodes`, `edges`, `layers`) + query string + `limit`. Output context:
`{ nodes: GraphNode[], edges: GraphEdge[], layers: Layer[] }`. SearchEngine I/O:
`new SearchEngine(nodes)` / `.search(query, {limit}) -> GraphNode[]`.

## Dependencies & assumptions
- The `@understand-anything/core` `SearchEngine`. No Fuse.js in deps → matching is a custom
  lexical (and possibly semantic) scorer, presumably over `name`, `summary`, `tags`.
- An LLM for the chat answer step (retrieval itself is model-free).

## To port this, you need:
- [ ] A node matcher (lexical over name/summary/tags; add embeddings for true semantic search).
- [ ] One-hop expansion + both-endpoints edge filter.
- [ ] Layer attachment for architectural framing.
- [ ] A prompt template that consumes {nodes,edges,layers} + question.

## Gotchas
- Without the both-endpoints filter the context balloons with dangling edges.
- One hop is usually right; 2+ hops explode context size — make depth configurable, default 1.
- **Gap (verify before relying):** the SearchEngine's scoring (fuzzy threshold? semantic?
  field weights?) is inside `@understand-anything/core` and NOT visible in the consumer code.
  If exact ranking matters, read `packages/core` before reimplementing — don't assume Fuse-style.

## Origin (reference only)
`understand-anything-plugin/src/context-builder.ts` + `understand-chat.ts`;
`SearchEngine` in `@understand-anything/core`.
