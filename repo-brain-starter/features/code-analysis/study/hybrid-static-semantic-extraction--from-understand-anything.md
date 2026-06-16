# Hybrid Static + Semantic Extraction — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
For each file, it produces two kinds of knowledge: the **structural facts** (what functions and
classes exist, what it imports, where each definition starts and ends) and the **meaning** (a
plain-English summary, 3–5 tags, a complexity rating). The first kind comes from a parser and is
identical every run; the second comes from an LLM and captures intent a parser can't see.

## Why it exists
Parsers are precise but dumb — they know a function exists but not *why* it matters. LLMs are
smart but unreliable — ask one to "list all the functions" and it will miss some and invent
others. The fix is to let each do only what it's good at: Tree-sitter extracts the structure
deterministically, then the LLM reads that structure (plus the source) and adds the human-meaning
layer on top. You get a graph that's both complete and meaningful.

## How it actually works
Two phases per file (inside each `file-analyzer`):

1. **Structural extraction** (`extract-structure.mjs`, deterministic): Tree-sitter parses the 10
   supported code languages (TS, JS, Python, Go, Rust, Java, Ruby, PHP, C/C++, C#) into a syntax
   tree and pulls out functions, classes, call sites, exports, and imports with line ranges. For
   languages without a grammar (Swift, Kotlin, PowerShell, Bash, Batch) it falls back to regex on
   top-level definitions. Non-code files (config, docs, infra, data) get format-specific parsing
   (sections, endpoints, services, steps, resources).
2. **Semantic enrichment** (LLM): the model reads the extracted structure and the original source
   and writes, per node, a *specific* summary ("Provides date-formatting helpers used across the
   API layer", not "this is a utility file"), 3–5 hyphenated tags, and a complexity rating.

Significance filtering keeps the graph clean: a function/class only becomes its own node if it's
**10+ lines or exported** — trivial one-liners and boilerplate are skipped. But **every file**
always becomes a node, even empty ones.

## The non-obvious parts
- **Emit every import edge, not the "interesting" ones.** For each file the analyzer must emit one
  `imports` edge per entry in the pre-resolved import data — the total edge count must exactly
  equal the sum of import-list lengths. Filtering to "meaningful" imports silently corrupts the
  graph's fan-in/fan-out math, which the tour and architecture steps depend on.
- **Node ID prefixes are exact and unforgiving**: `file:<path>`, `function:<path>:<name>`,
  `class:<path>:<name>`. A missing or misspelled prefix breaks every downstream consumer.
- **Complexity is mechanical**: simple <50 non-empty lines, moderate 50–200, complex >200 — plus
  nesting depth. It's a heuristic, not a deep judgment, so it's stable.
- **Tags are inferred from structure**: `entry-point` for `index.ts`/`__init__.py` at a root,
  `test` for `*.test.*`/`*_test.*`, `api-handler` for exported classes named `*Handler`/`*Controller`.
- This per-file split is the same philosophy the whole
  [[multi-agent-analysis-pipeline--from-understand-anything]] is built on.

## Related
- [[multi-agent-analysis-pipeline--from-understand-anything]] — runs this 5× in parallel
- [[knowledge-graph-data-model--from-understand-anything]] — the node/edge shapes produced here
- See also: many "AST + LLM" code tools; the discipline here is the strict structure/semantics split
