# Knowledge Graph Data Model (build spec) — distilled from Understand-Anything

## Summary
A single versioned JSON document = the shared IR for a code-understanding system. Typed nodes +
typed edges + layers + tour, with strict deterministic IDs and standardized edge weights. Stored
at `.understand-anything/knowledge-graph.json`, git-committable, merged from independent batches.

## Core logic (inlined)
Top-level shape:
```json
{
  "version": "1.0.0",
  "project": { "name": "", "languages": [], "frameworks": [], "description": "",
               "analyzedAt": "ISO-8601", "gitCommitHash": "" },
  "nodes":  [ { "id": "file:src/index.ts", "type": "file", "name": "index.ts",
               "summary": "", "tags": [], "filePath": "src/index.ts",
               "complexity": "simple|moderate|complex" } ],
  "edges":  [ { "source": "file:src/index.ts", "target": "file:src/utils.ts",
               "type": "imports", "weight": 0.8, "confidence": 0.9 } ],
  "layers": [ { "id": "layer:api", "name": "API", "description": "",
               "nodeIds": ["file:..."] } ],
  "tour":   [ { "order": 1, "title": "", "description": "", "nodeIds": ["..."],
               "languageLesson": "" } ]
}
```
ID conventions (deterministic, joinable):
```
file:<path>            function:<path>:<name>      class:<path>:<name>
config:<path>          document:<path>             service:<name>          layer:<kebab>
domain:<kebab>  flow:<kebab>  step:<kebab>     (domain graph variant)
```
Node types (13): file, function, class, module, concept, config, document, service, table,
endpoint, pipeline, schema, resource.
Edge types (~26): imports, exports, contains, calls, reads_from, writes_to, deploys, tested_by,
configures, inherits, implements, depends_on, documents, migrates, triggers, defines_schema,
serves, provisions, routes, related, … .
Standardized weights: contains=1.0, inheritance=0.9, calls/imports=0.8, default=0.5.

Merge model (why the schema is shaped this way):
```
analysis runs as independent batches -> each emits nodes/edges with global IDs ->
merge-batch-graphs.py concatenates + dedups by id (last-writer / union edges) ->
deterministic IDs guarantee cross-batch edges resolve.
incremental: delete nodes where filePath in changed[] and edges referencing them,
             then merge freshly-analyzed batches back in.
```

## Data contracts
As above. Companion files in `.understand-anything/`: `meta.json` (`gitCommitHash`, fingerprint
baseline, analyzedAt) and `intermediate/` (scan-result.json, batch-*.json, assembled-graph.json —
deleted after save). Persist `knowledge-graph.json`; gitignore `intermediate/`.

## Dependencies & assumptions
- JSON storage only; no DB required.
- Deterministic ID generation at extraction time (path + name) — non-negotiable for clean merges.
- Optional git-lfs for very large graphs.

## To port this, you need:
- [ ] Adopt the exact ID prefix scheme (or your merge/joins break).
- [ ] A closed node-type and edge-type vocabulary + weight table.
- [ ] Full-coverage `layers[].nodeIds` (every file node assigned).
- [ ] A merge routine that dedups by id and unions edges.
- [ ] `meta.json` with `gitCommitHash` for incremental gating; gitignore intermediates.

## Gotchas
- ID format drift is fatal to merges and to every consumer; validate with a regex on write.
- Keep edge weights standardized globally — ranking/tours assume it.
- `version` field: bump it when the schema changes so old graphs trigger a rebuild.
- Don't commit `intermediate/`; do commit the final graph.

## Origin (reference only)
`understand-anything-plugin/skills/understand/SKILL.md` (schema + save phase);
`@understand-anything/core` types; `merge-batch-graphs.py`, `build-fingerprints.mjs`.
