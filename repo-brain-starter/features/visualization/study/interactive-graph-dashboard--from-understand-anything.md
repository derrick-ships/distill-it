# Interactive Graph Dashboard — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
It turns the knowledge-graph JSON into a living, explorable map in your browser. You see the
codebase as a graph of connected nodes you can drag, zoom, search, and click — click a node and a
panel shows its summary, type, and connections. Nodes are grouped and colored by architectural
layer, and the UI adjusts how much detail it shows based on who you are (a "persona").

## Why it exists
A JSON file isn't comprehension; a picture is. Reading code linearly doesn't reveal structure —
seeing the dependency web does. The dashboard is the payoff for all the analysis: it's where a new
hire actually *gets* the system, where you trace what connects to what, and where the guided tour
and search become tactile instead of textual.

## How it actually works
It's a local React app served by Vite — no cloud, your code never leaves your machine:
- **Launch**: build the core package, then `GRAPH_DIR=<project> npx vite --host 127.0.0.1` on port
  5173 (auto-fallback if taken). The graph data is read from the local
  `.understand-anything/knowledge-graph.json`.
- **Access control**: the URL carries a token (`http://127.0.0.1:<port>?token=<token>`); without
  it you hit an "Access Token Required" gate. Even though it's localhost, it's gated.
- **Rendering**: React 19 + React Flow (`@xyflow/react`) for the interactive canvas, with layout
  computed by `d3-force` (force-directed) and/or `dagre` and `elkjs` (hierarchical). `graphology`
  holds the graph in memory, and `graphology-communities-louvain` detects clusters/communities for
  grouping. State is managed with `zustand`; styling is Tailwind v4; code snippets render via
  `prism-react-renderer`; markdown via `react-markdown`.
- **Layers**: nodes are grouped/colored by the `layers` from the graph, so the architecture is
  visible at a glance.
- **Persona-adaptive UI**: the dashboard changes complexity based on the selected role (show more
  or fewer node types / detail). *(Exact persona mechanics aren't fully specified in the public
  skill docs — see the gap note in the build spec.)*

## The non-obvious parts
- **Multiple layout engines, not one.** Force (d3-force) for organic exploration, dagre/elkjs for
  clean hierarchical views, plus Louvain community detection to cluster related nodes — different
  questions want different layouts.
- **Local-first + token-gated.** It's a private dev tool: localhost only, but still behind a token
  so a stray open port doesn't leak your codebase map.
- **The core package must be built first** (`pnpm --filter @understand-anything/core build`) — the
  dashboard imports shared graph logic (incl. the search engine) from it.
- It is a pure *reader* of the [[knowledge-graph-data-model--from-understand-anything]]; it computes
  no analysis itself.

## Related
- [[knowledge-graph-data-model--from-understand-anything]] — the data it renders
- [[graph-search-retrieval--from-understand-anything]] — search box behavior
- [[dependency-ordered-guided-tours--from-understand-anything]] — tour playback in the UI
