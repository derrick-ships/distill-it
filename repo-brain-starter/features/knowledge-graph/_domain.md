# Domain: Knowledge Graph

Features about the *data structure* at the center of a code-understanding system: a typed
node/edge graph that everything else (search, tours, diff, dashboard) reads from and writes to.
The common thread: a single, versioned JSON document with strict ID conventions, a closed
vocabulary of node and edge types, and weights/confidence — designed to be committed to git and
shared so a team skips re-analysis.

## Features in this domain
- [[knowledge-graph-data-model--from-understand-anything]] — the node/edge/layer/tour schema,
  ID conventions (`file:`, `function:path:name`), 13 node types, 26 edge types, storage at
  `.understand-anything/knowledge-graph.json`, and the batch-merge + fingerprint flow. (from
  Understand-Anything)

## Why this domain matters
The schema *is* the contract. Every downstream feature depends on the ID format and the edge
vocabulary being exact. A well-designed graph schema is what lets analysis be parallel
(independent batches merge cleanly), incremental (delete + re-add by file), and portable
(commit the JSON, render it anywhere). When studying a new repo, the persisted intermediate
representation is usually the most reusable artifact in the whole system.
