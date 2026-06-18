# Domain: pipeline-orchestration

Composing a unit of work as a **graph of small, single-purpose nodes that pass a shared mutable state dictionary** between them — a deterministic "blackboard" pipeline rather than an autonomous agent loop.

## What this domain is about

Where [[agent-architecture]] is about agents that *decide* what to do next (tool loops, planning), this domain is about pipelines whose shape is *declared up front*: a fixed set of nodes wired by edges, traversed from an entry point until there are no more edges. Each node reads the keys it needs out of one shared `state` dict, does one thing, and writes its results back into the same dict. The graph engine is tiny and dumb on purpose — all the intelligence lives in the nodes, and the same engine runs a 2-node pipeline or a 6-node one without changing.

The defining moves:
- **Shared-state blackboard**: nodes never call each other directly; they communicate only by reading/writing a dict. This is what makes nodes swappable and pipelines re-composable.
- **Declarative wiring**: the pipeline is a list of nodes + a list of `(from, to)` edges. Variants of a pipeline are just different edge lists over the same node instances.
- **Conditional branching**: a special node type returns the *name* of the next node, turning a linear chain into a branch (retry loops, early exit).
- **Input contracts as data**: each node declares which state keys it needs as a boolean expression string (`"user_prompt & (relevant_chunks | parsed_doc | doc)"`), evaluated against the live state at run time.

## Why it's its own domain

Many LLM products are really just 3-5 deterministic steps (fetch → clean → ask model → merge). Reaching for a full agent framework is overkill. A 100-line node-graph engine gives you observability (per-node timing/token cost), testability (run one node on a fixed state), and recomposition (reorder steps by editing an edge list) without any of the nondeterminism of an agent.

## Features in this domain

- [[graph-execution-engine--from-scrapegraph-ai]] — the ~100-line `BaseGraph` + `BaseNode` core: shared-state traversal, conditional nodes, per-node token/cost accounting, and the boolean input-key DSL that declares each node's data dependencies.
- [[queue-backed-crawl--from-firecrawl]] — recursive site crawl as a BullMQ + Redis orchestration: a single kickoff job seeds the frontier, each scrape job enqueues children, dedup is an atomic Redis `SADD`, and 'done' is a three-part condition (jobs done AND kickoff done AND sitemap done). A canonical fan-out-with-state pattern.
- [[declarative-low-code-cdk--from-airbyte]] — define a whole connector in a YAML manifest that a runtime interprets (resolve $refs → propagate $parameters → validate against a component JSON-schema → factory builds live objects). Config-as-connector at scale; the engine behind 600+ Airbyte connectors and the no-code Builder.
- [[incremental-sync-state--from-airbyte]] — cursor-based incremental reads: a DatetimeBasedCursor slices a date range into resumable windows, tracks the MAX observed cursor value, and emits state at slice boundaries so the next run resumes. A different resumable-progress model than [[queue-backed-crawl--from-firecrawl]]'s Redis sets — here progress IS the cursor value.
- [[query-processor-middleware-pipeline--from-metabase]] — the Ring/Express-style middleware pattern applied to queries: ~40 ordered query→query transforms in, reducible streaming execution, ordered row-transforming middleware out. Order is the contract; the whole lifecycle is a readable list of function vars.
- [[file-rules-engine--from-hazelnut]] — condition→action rules where a Condition is an all-optional struct matched by AND (empty = matches all), with a shared metadata syscall and cap-and-clear compiled-pattern caches. A minimal, serializable 'if-this-then-that' engine; contrast the middleware pipeline above — rules vs transforms.
- [[file-actions-executor--from-hazelnut]] — the 'then do this' half: a tagged Action enum (move/copy/rename/trash/delete/archive/run-script) with overwrite guards, recoverable-trash-vs-permanent-delete, and {name}/{path}/{date} placeholder templating. Making 'run a custom script per file' first-class is what turns a file organizer into general automation.

## Cross-domain links
- Contrast with [[agent-architecture]] — agents choose their path; these pipelines have it pre-wired.
- The nodes built on this engine live in [[web-extraction]], [[structured-extraction]], and [[research-automation]].
