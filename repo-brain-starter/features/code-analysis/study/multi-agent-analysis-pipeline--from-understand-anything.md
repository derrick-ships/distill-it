# Multi-Agent Analysis Pipeline — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
When you run `/understand` on a codebase, this is the conductor. It doesn't read the whole repo
itself — it dispatches a relay team of specialized sub-agents, each doing one job, handing its
output to the next. The result is a single knowledge-graph JSON file describing every file,
function, class, dependency, architectural layer, and a guided tour — built far faster and more
reliably than one model trying to hold the whole repo in its head.

## Why it exists
A large repo doesn't fit in one context window, and a single mega-prompt that tries to "analyze
everything" is slow, expensive, and inconsistent run-to-run. Splitting the work lets each step be
narrow (so it's accurate), lets the file-analysis step run **5 files in parallel** (so it's
fast), and lets re-runs touch **only changed files** (so it's cheap). The pipeline is the thing
that makes whole-repo understanding economically viable.

## How it actually works
It's a seven-phase assembly line, each phase a dedicated agent or script:

1. **Pre-flight** — find the project root, detect git worktrees, build the plugin, resolve the
   output language, check whether a graph already exists (to offer an incremental run).
2. **Scan** (`project-scanner`) — inventory every file, detect languages and frameworks, classify
   each file (code / config / docs / infra / data / script / markup), and resolve the internal
   import map. This is mostly deterministic scripts, not guesswork.
3. **Batch** (`compute-batches.mjs`) — group files into *semantic* batches (related files
   together, with their imports pre-resolved and a "neighbor map" of exported symbols), so each
   analyzer has the context it needs without re-parsing.
4. **Analyze** (`file-analyzer` ×5 concurrent) — each agent takes one batch and emits a partial
   graph (`batch-0.json`, `batch-1.json`, …). A merge script (`merge-batch-graphs.py`) stitches
   them into one `assembled-graph.json`.
5. **Assemble review** (`assemble-reviewer`) — validate the merged graph against the import data;
   catch dropped nodes/edges.
6. **Architecture** (`architecture-analyzer`) — group nodes into 3–10 named layers (API, Service,
   Data, UI, Utility…).
7. **Tour** (`tour-builder`) — build a dependency-ordered learning walkthrough.
8. **Review + Save** — fix dangling references and missing fields, then write
   `.understand-anything/knowledge-graph.json`, generate structural fingerprints, write
   `meta.json`, clean up intermediates, optionally launch the dashboard.

The clever part is the **division of labor**: deterministic scripts own anything that must be
reproducible (file lists, line counts, imports, batching, merging, fingerprints), and LLM agents
own only the interpretation (summaries, layer names, tour narrative). The scripts are the skeleton
the agents are forbidden from re-deriving.

## The non-obvious parts
- **Strict output-file naming is load-bearing.** Analyzer outputs must be exactly
  `batch-<n>.json` (or `batch-<n>-part-<k>.json`); any other name (e.g. `batch-fused-8-13.json`)
  makes the merge script *silently drop* those nodes and edges. A naming slip looks like data loss
  with no error.
- **Parallelism is capped at 5** analyzers — enough to be fast, low enough to avoid rate limits
  and context thrash.
- **Incremental mode** uses `git diff <lastCommit>..HEAD --name-only`, removes old nodes/edges for
  changed files, re-analyzes only those, then re-runs architecture on the *whole* set (because one
  changed file can shift layer assignments). See [[diff-impact-analysis--from-understand-anything]]
  for the per-change blast-radius variant.
- **Language is a directive, not a translation pass** — a `$LANGUAGE_DIRECTIVE` is injected into
  every sub-agent prompt so summaries/tours are generated in the target language from the start.
- The split between deterministic structure and LLM semantics is the same idea as
  [[hybrid-static-semantic-extraction--from-understand-anything]], applied at the orchestration
  level.

## Related
- [[hybrid-static-semantic-extraction--from-understand-anything]] — what each `file-analyzer` does inside a batch
- [[knowledge-graph-data-model--from-understand-anything]] — the schema every phase reads/writes
- [[dependency-ordered-guided-tours--from-understand-anything]] — the tour phase
- [[business-domain-mapping--from-understand-anything]] — an optional parallel pipeline (`/understand-domain`)
