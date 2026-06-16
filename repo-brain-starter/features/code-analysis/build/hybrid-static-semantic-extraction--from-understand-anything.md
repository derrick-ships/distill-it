# Hybrid Static + Semantic Extraction (build spec) — distilled from Understand-Anything

## Summary
Per file: (1) deterministically extract structure (functions, classes, imports, exports, call
sites, line ranges) with Tree-sitter (regex fallback for unsupported langs; format parsers for
non-code), then (2) have an LLM add summary/tags/complexity by reading the structure + source.
Strict node-ID prefixes and an "emit ALL import edges" rule keep the graph consistent.

## Core logic (inlined)
```
extract-structure.mjs(input = batch of {path,language,sizeLines,fileCategory}):
  for each file:
    if language in {ts,js,py,go,rust,java,ruby,php,c,cpp,c#}:
        tree = treeSitter.parse(source)
        functions = query(tree, function_defs) -> [{name, lineRange:[s,e], exported?}]
        classes   = query(tree, class_defs)    -> [{name, lineRange, exported?}]
        calls     = query(tree, call_sites)
        exports   = query(tree, exports)
    elif language in {swift,kotlin,powershell,bash,batch}:
        regex top-level defs
    else (config/docs/infra/data):
        format-specific parse -> sections/endpoints/services/steps/resources
    metrics = {importCount, functionCount, classCount}
  emit structured JSON report (per-file metrics + arrays of defs w/ line ranges)

LLM enrichment (reads extract-structure output + source):
  for each candidate node:
    summary  = specific one-liner (purpose + where used)
    tags     = 3..5 hyphenated keywords (entry-point/test/api-handler/...)
    complexity = nonEmptyLines<50?simple : <=200?moderate : complex   (also weigh nesting)
    languageNotes = optional, only if notable pattern

Node creation rules:
  - every FILE -> one node (type from fileCategory: file|config|document|service|pipeline|schema|resource|...)
  - function/class -> node ONLY if (lineCount>=10 OR exported)   # significance filter
  - skip trivial one-liners / generated boilerplate

Edge emission rules:
  - imports: emit EXACTLY one edge per entry in batchImportData[path] (ALL of them).
             total imports edges == sum(len(batchImportData[*])).  imports may cross batches.
  - contains: file -> its function/class nodes
  - calls/exports/etc per extracted relations
  - non-code edges must target nodes verified in neighborMap/known neighbors
```

## Data contracts
Node (required): `{ id, type, name, filePath, summary, tags[3-5], complexity }`; function/class add
`lineRange:[start,end]`; optional `languageNotes`.
ID format (exact): `file:<path>` · `function:<path>:<name>` · `class:<path>:<name>`.
Edge: `{ source, target, type, direction:"forward", weight }`. Edge types incl.
`imports, exports, contains, calls, inherits, implements, depends_on, tested_by, configures,
documents, deploys, migrates, triggers, defines_schema, serves, provisions, routes, related`.
Output splitting: if a batch yields >60 nodes or >120 edges, split into
`batch-<i>-part-<k>.json`, partitioning edges by source-node membership.

## Dependencies & assumptions
- Tree-sitter + grammars for the supported languages (the deterministic core; swappable for
  another AST lib but you lose multi-language uniformity).
- An LLM for enrichment (model-agnostic; prompt asks for specific, non-generic summaries).
- Pre-resolved `batchImportData` and `neighborMap` from the batching step (so the analyzer never
  re-parses imports).

## To port this, you need:
- [ ] Tree-sitter (or AST) extraction emitting functions/classes/imports/exports + line ranges.
- [ ] A regex fallback path for languages without a grammar.
- [ ] Format parsers for config/docs/infra/data files.
- [ ] An LLM enrichment prompt producing summary/tags/complexity per node.
- [ ] The significance filter (>=10 lines OR exported) and the "every file is a node" rule.
- [ ] The "emit all import edges; count must match" invariant + a post-check that verifies it.

## Gotchas
- **The import-edge count invariant is the #1 silent corruptor.** If you "tidy" imports, fan-in/
  fan-out breaks and tours/architecture degrade with no error. Assert the count.
- ID prefix typos break everything downstream — validate against a regex.
- Don't let the LLM invent or drop functions; it only annotates what the script found.
- Complexity/tag heuristics are intentionally mechanical — keep them deterministic for stable diffs.

## Origin (reference only)
`understand-anything-plugin/agents/file-analyzer.md` + bundled `extract-structure.mjs`.
