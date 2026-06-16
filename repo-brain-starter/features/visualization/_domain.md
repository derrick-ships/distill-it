# Domain: Visualization

Features that render a code knowledge graph as something a human can explore — force-directed or
layered layouts, clickable nodes, side panels, search-as-you-type, and UIs that adapt to who is
looking. The common thread: read a static JSON graph and make it *navigable*, locally, with no
backend beyond a dev server.

## Features in this domain
- [[interactive-graph-dashboard--from-understand-anything]] — React 19 + React Flow + d3-force /
  dagre / elkjs layouts + graphology (Louvain community detection), served by Vite with a
  token-gated localhost URL; persona-adaptive complexity and layer grouping. (from
  Understand-Anything)

## Why this domain matters
Analysis is worthless if nobody looks at it. The visualization layer is where comprehension
actually happens — and the design choices (force vs. hierarchical layout, persona-adaptive
detail, layer coloring, local-only token-gated serving) are reusable across any
graph-of-a-system tool, not just code. When studying a repo, anything that turns a data graph
into an explorable map belongs here.
