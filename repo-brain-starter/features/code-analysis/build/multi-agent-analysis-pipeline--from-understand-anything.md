# Multi-Agent Analysis Pipeline (build spec) — distilled from Understand-Anything

## Summary
Orchestrate whole-repo analysis as a sequence of single-purpose agents and deterministic scripts
that read/write a shared knowledge-graph JSON. Deterministic scripts own all reproducible facts
(file list, imports, batching, merge, fingerprints); LLM agents own only interpretation. File
analysis fans out to 5 concurrent workers over pre-computed batches; results merge by strict
filename convention. Supports incremental re-analysis of only git-changed files.

## Core logic (inlined)
Phase order (driver = the `/understand` command/skill):

```
phase 0  pre-flight: resolve PROJECT_ROOT; detect git worktree; build plugin;
         resolve --language (persist to config.json); if knowledge-graph.json exists,
         offer (a) full rebuild (b) LLM review only (c) nothing.
phase 1  scan:    dispatch project-scanner -> .understand-anything/intermediate/scan-result.json
phase 1.5 batch:  run compute-batches.mjs  -> batch specs (file list + pre-resolved imports +
                  neighborMap of exported symbols per batch)
                  (incremental: compute-batches.mjs --changed-files=<list>)
phase 2  analyze: for each batch, dispatch file-analyzer agent. RUN UP TO 5 CONCURRENTLY.
                  each writes batch-<i>.json (split to batch-<i>-part-<k>.json if
                  nodes>60 or edges>120, edges partitioned by source-node membership).
                  then run merge-batch-graphs.py -> assembled-graph.json
phase 3  assemble-review: dispatch assemble-reviewer -> validate merged graph vs import data
phase 4  architecture:    dispatch architecture-analyzer(lang,framework ctx) -> layers[]
phase 5  tour:            dispatch tour-builder -> tour[]
phase 6  review:          inline deterministic validation (or --review => graph-reviewer agent);
                          fix dangling edge refs + missing required fields
phase 7  save:            write .understand-anything/knowledge-graph.json;
                          build-fingerprints.mjs -> structural fingerprints; write meta.json;
                          delete intermediate/; optionally launch dashboard
```

Incremental path (changed commit hash):
```
changed = git diff <meta.lastCommitHash>..HEAD --name-only
compute-batches.mjs --changed-files=changed
remove nodes/edges whose filePath in changed from existing graph
analyze changed batches; merge into untouched remainder
re-run architecture-analyzer on FULL merged node set (layers may shift)
```

Agent roster (each is a separate subagent prompt/definition):
| agent | input | output |
|-------|-------|--------|
| project-scanner | root path, optional `.understandignore` | scan-result.json (files, languages, frameworks, importMap) |
| file-analyzer (×5) | one batch spec | batch-<i>.json (nodes+edges) |
| assemble-reviewer | assembled-graph.json + import data | validation/fixes |
| architecture-analyzer | graph + lang/framework | layers[] |
| tour-builder | graph + layers | tour[] |
| graph-reviewer (opt) | full graph | dangling-ref + field fixes |
| domain-analyzer (separate cmd) | graph or domain-context | domain-graph.json |

## Data contracts
- `scan-result.json`: `{ name, description, languages[], frameworks[], files[{path,language,sizeLines,fileCategory}], totalFiles, filteredByIgnore, estimatedComplexity, importMap{ path: [internalDepPath] } }`
- Batch spec (per analyzer): `{ batchIndex, files[{path,language,sizeLines,fileCategory}], batchImportData{ path:[dep] }, neighborMap{ path:[exportedSymbol] } }`
- Final graph: see [[knowledge-graph-data-model--from-understand-anything]] (version, project, nodes, edges, layers, tour).
- `meta.json`: includes `gitCommitHash` (lastCommitHash) used to drive incremental runs; plus fingerprint baseline reference.

## Dependencies & assumptions
- A subagent dispatch primitive that supports **concurrency** (run N agents in parallel) — in
  Claude Code this is the Task/subagent mechanism. Swappable for any job runner that can run N
  prompts concurrently and collect their JSON.
- Node.js for bundled scripts (`scan-project.mjs`, `extract-import-map.mjs`, `compute-batches.mjs`,
  `extract-structure.mjs`, `build-fingerprints.mjs`); Python for `merge-batch-graphs.py`.
- `git` (for file listing + incremental diffs); works on non-git repos via recursive walk.
- Tree-sitter grammars for the 10–12 supported languages (used inside scanner + file-analyzer).

## To port this, you need:
- [ ] A shared graph schema + on-disk JSON location.
- [ ] Deterministic scanner (files/langs/frameworks/categories/import map).
- [ ] A batching step that pre-resolves imports + neighbor exports per batch.
- [ ] A concurrent agent dispatcher (cap ~5) writing strictly-named partial outputs.
- [ ] A merge step keyed on the exact `batch-<i>[-part-<k>].json` filename regex.
- [ ] Post-merge validators (assemble-review, architecture, tour, final review).
- [ ] A fingerprint + meta.json baseline to enable incremental re-runs by git diff.

## Gotchas
- **Filename convention is silent-failure-prone**: merge only ingests files matching
  `batch-(\d+)(?:-part-(\d+))?\.json`. Anything else is dropped without error. Validate counts.
- **Re-run architecture on the full set** after incremental merges, not just changed nodes —
  layer membership is global.
- **Don't let agents re-derive deterministic facts** (imports, line counts, batching). They must
  consume script output verbatim or the graph stops being reproducible.
- Concurrency >5 tends to hit model rate limits and degrade batch quality; 5 is the tuned cap.

## Origin (reference only)
Repo: github.com/Egonex-AI/Understand-Anything. Key files:
`understand-anything-plugin/skills/understand/SKILL.md` (orchestration);
`understand-anything-plugin/agents/{project-scanner,file-analyzer,assemble-reviewer,architecture-analyzer,tour-builder,graph-reviewer}.md`;
bundled scripts under the plugin (scan-project.mjs, extract-import-map.mjs, compute-batches.mjs,
merge-batch-graphs.py, build-fingerprints.mjs).
