# Interactive Graph Dashboard (build spec) — distilled from Understand-Anything

## Summary
A local React 19 + Vite single-page app that reads the knowledge-graph JSON and renders an
interactive, layer-colored, searchable node/edge map with multiple layout engines. Served on
localhost behind a URL token. Persona selection adjusts displayed complexity.

## Core logic (inlined)
Launch sequence:
```
cd <plugin-root> && pnpm --filter @understand-anything/core build   # build shared core first
cd <plugin-root>/packages/dashboard
GRAPH_DIR=<project-dir> npx vite --host 127.0.0.1                    # default port 5173, auto-fallback
# open: http://127.0.0.1:<PORT>?token=<TOKEN>   (token gate: "Access Token Required")
```
Data load: app fetches/reads `<GRAPH_DIR>/.understand-anything/knowledge-graph.json`
(version, project, nodes, edges, layers, tour).

Rendering stack (from packages/dashboard/package.json):
```
react ^19 + react-dom ^19
@xyflow/react ^12          # React Flow canvas: nodes, edges, pan/zoom/drag, side panel
d3-force ^3                # force-directed layout positions
@dagrejs/dagre ^2 + elkjs ^0.9   # hierarchical/layered layout options
graphology ^0.25 + graphology-types          # in-memory graph model
graphology-communities-louvain ^2            # community/cluster detection for grouping
zustand ^5                 # UI state (selected node, persona, layout mode, search query)
tailwindcss ^4 (@tailwindcss/vite)           # styling
prism-react-renderer       # syntax-highlighted code
react-markdown + hast-util-to-jsx-runtime    # render summaries/docs
vite ^6 + @vitejs/plugin-react + vitest      # dev server / build / tests
```
Conceptual component flow:
```
load graph -> build graphology Graph(nodes, edges)
           -> compute layout positions (mode: force | dagre | elk)
           -> color/group nodes by graph.layers (or Louvain communities)
           -> render <ReactFlow nodes edges/>; on node click -> zustand.selectedNode
           -> side panel: name, type, summary, tags, neighbors (edges), code preview
           -> search box -> SearchEngine (see graph-search-retrieval) -> filter/highlight
           -> persona selector -> zustand.persona -> gates which node types / detail show
           -> tour mode -> step through graph.tour[], focus nodeIds per step
```

## Data contracts
Input: the knowledge graph JSON (read-only). No writes back. `GRAPH_DIR` env var points at the
analyzed project. Token passed as `?token=` query param, validated client-/server-side before
data renders.

## Dependencies & assumptions
- Node + pnpm workspace; the `@understand-anything/core` package (shared graph + SearchEngine).
- Browser; localhost-only serving (`--host 127.0.0.1`).
- Assumes a fully-built `knowledge-graph.json` already exists.

## To port this, you need:
- [ ] A graph JSON with nodes/edges/layers/tour.
- [ ] A canvas lib (React Flow here; cytoscape/sigma are alternatives) + a layout engine
      (force and/or hierarchical).
- [ ] Layer-based coloring + a node detail panel.
- [ ] A search box wired to your retrieval (see graph-search-retrieval).
- [ ] A local dev server with a token gate if the map is sensitive.
- [ ] (Optional) persona state controlling detail density.

## Gotchas
- **Build core before launching** or imports fail.
- Token gate is easy to forget — without it an open localhost port exposes the full code map.
- Big graphs: force layout can thrash; precompute with dagre/elk or cap rendered nodes.
- **Gap (verify before relying):** persona-adaptive mechanics and the exact token-validation path
  are not fully documented in the public skill files; confirm in `packages/dashboard/src` before
  reimplementing those two specifics.

## Origin (reference only)
`understand-anything-plugin/skills/understand-dashboard/SKILL.md`;
`understand-anything-plugin/packages/dashboard/` (package.json, src).
