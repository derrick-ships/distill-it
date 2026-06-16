# Graph Search & Retrieval — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
It finds the nodes in the graph that match what you typed — by name or by meaning — and then,
crucially, pulls in their immediate neighbors so the answer arrives with its context. This powers
both the dashboard search box and the `/understand-chat` "ask your codebase" feature.

## Why it exists
"Ask questions about your codebase" is really a retrieval problem: you can't stuff the whole graph
into an LLM prompt. You need to pick the handful of nodes that matter for the question — and a bare
keyword match isn't enough, because the *answer* usually involves what those nodes connect to. So
retrieval here is two moves: find seeds, then expand one hop to include their neighborhood.

## How it actually works
- A `SearchEngine` (from `@understand-anything/core`) is constructed over the graph's nodes:
  `new SearchEngine(graph.nodes)`, then `engine.search(query, { limit })`. It returns the
  best-matching seed nodes. *(The internal scoring isn't exposed in the consuming source — see the
  gap note in the build spec; there's no Fuse.js dependency, so matching is custom, likely over
  name/summary/tags.)*
- **One-hop expansion**: take the seed nodes and add every node directly connected by an edge.
- **Edge filtering**: keep only edges where *both* endpoints are in the relevant set — so the
  context is internally coherent, not a hairball.
- **Layer attach**: include any layers that contain the relevant nodes, for architectural framing.
- The bundled result (seeds + neighbors + their edges + layers) becomes a focused context window
  handed to the LLM, instead of the entire knowledge base.

## The non-obvious parts
- **Retrieval = match + expand.** The one-hop expansion is what makes answers useful; matching
  alone returns isolated nodes with no relationships to reason over.
- **Both-endpoints edge rule** keeps the subgraph tight — you don't drag in edges that dangle out
  to unrelated nodes.
- **Localized, not global context** — deliberately feeds the model a neighborhood, balancing
  completeness against prompt size and cost. This is RAG, but the "documents" are graph nodes.

## Related
- [[knowledge-graph-data-model--from-understand-anything]] — what it searches over
- [[interactive-graph-dashboard--from-understand-anything]] — the search box UI
- See also: vector RAG — here retrieval is graph-structural rather than embedding-only
