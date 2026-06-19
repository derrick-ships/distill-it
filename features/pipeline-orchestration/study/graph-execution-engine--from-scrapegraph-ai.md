# Graph Execution Engine — from [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)

> Domain: [[_domain]] · Source: https://github.com/ScrapeGraphAI/Scrapegraph-ai · NotebookLM: <add link>

## What it does
This is the little engine the whole library is built on. You give it a list of "nodes" (each a small object that does one job) and a list of edges saying which node leads to which, point it at a starting node, and call `execute`. It walks the graph node by node, handing each one a shared "state" — a plain dictionary — that accumulates results as it goes. The first node might drop the fetched HTML into the state under `"doc"`; the next reads `"doc"`, splits it into chunks, and writes `"parsed_doc"`; the last reads that and writes `"answer"`. At the end you get the final state back, plus a per-node report of how long each step took and how many tokens/dollars it burned.

## Why it exists
ScrapeGraphAI's pitch is "scraping pipelines built from graph logic." That promise needs a substrate: something that can express "fetch, then parse, then ask the LLM, then merge" as data you can rearrange — not as hard-coded function calls. The engine is that substrate. By making the pipeline a *list of nodes and edges* instead of a method that calls `fetch(); parse(); generate()` in sequence, every pipeline in the library (single-page scrape, multi-page search, script generation, speech) becomes the same engine with a different node list. Add a feature and you add a node; change the flow and you edit an edge. It also gives you for free the things product teams actually need: timing, token accounting, cost, and a clean failure report saying *which* node blew up.

## How it actually works
There are two cooperating pieces: `BaseGraph` (the engine) and `BaseNode` (the contract every step implements).

**Setting up the graph.** You construct `BaseGraph(nodes=[...], edges=[(a,b),(b,c)], entry_point=a)`. Internally it turns the edge list into a simple lookup table: "after node a, go to node b." Edges are deduplicated and stored as a dict mapping a node's name → the next node's name. One node type is special — a *conditional node* — and its edges aren't stored in that table; instead the engine reads the two outgoing edges and remembers a "true" target and a "false" target on the node itself.

**Running it.** Execution is a `while` loop. Start at the entry point. Look up the current node by name, call its `execute(state)`, get back the mutated state. Then ask "what's next?": for a normal node, look up the next node in the edge table; for a conditional node, the node's own return value *is* the name of the next node to jump to (or `None` to stop). When there's no next node, the loop ends and the final state is returned. That's the entire control flow — maybe 15 lines of actual logic.

**The shared state is the only communication channel.** Nodes never hold references to each other. A node reads what it needs from the dict and writes what it produces back into the dict. This is the "blackboard" pattern: the dict is a shared whiteboard everyone reads and scribbles on. It's why you can yank a node out, drop a different one in, or reorder them — as long as the keys line up, the pipeline still runs.

**Each node declares its data dependencies as a tiny boolean expression.** Rather than positional arguments, a node is configured with an `input` string like `"user_prompt & (relevant_chunks | parsed_doc | doc)"`. At run time the node parses this against whatever keys currently exist in the state and resolves it to a concrete list of keys to read. The `&` means "I need both," the `|` means "whichever of these is present, preferring the first." So the answer-generation node says "I need the user's prompt, AND the best available content — relevant chunks if some earlier node produced them, otherwise the parsed doc, otherwise the raw doc." This is what lets one node slot into several different pipeline shapes without code changes: it adapts to whatever upstream nodes happened to run.

**Observability is baked in.** Every node call is wrapped in a callback that captures wall-clock time and, via LangChain's token-counting callback, the prompt/completion/total tokens, successful request count, and estimated USD cost. These are summed across nodes into a "TOTAL RESULT" row. If a node raises, the engine logs a structured execution record (graph name, source, prompt, schema, model, *which node failed*, the exception) before re-raising — so failures are diagnosable, not silent.

## The non-obvious parts
- **The engine is deliberately not a real DAG executor.** There's no topological sort, no parallel branches, no join nodes. It's a single cursor walking one path. "Parallelism" in the library (multi-page scraping) is done *inside* a node (a node that runs N sub-graphs), not by the engine forking. Keeping the engine a simple linear/branching walk is what keeps it ~100 lines and trivially debuggable.
- **Conditional nodes invert who decides the next step.** For normal nodes the *graph* decides routing (via the edge table). For conditional nodes the *node* decides, by returning a node name. This one inversion is what enables retry loops (`generate → conditional → regenerate` or `→ done`) without giving the engine any notion of loops.
- **The input-key DSL is a real micro-parser, not a regex.** It validates balanced parentheses, rejects adjacent operators and adjacent bare keys, then evaluates OR-segments left to right and returns the first AND-group whose every key is present in state. It's overkill for the handful of expressions actually used — but it makes nodes genuinely portable across pipelines.
- **The state dict has no schema.** It's just `dict`. Power and footgun in one: any node can read or clobber any key. The library leans on naming conventions (`doc`, `parsed_doc`, `relevant_chunks`, `answer`) rather than types. Reusing this engine, you'd want to write those conventions down somewhere, because nothing enforces them.
- **`append_node` mutates the graph after construction.** You can tack a node onto the end and it auto-wires an edge from the current last node. Convenient for dynamic pipelines, but it assumes a linear tail.
- **An optional "Burr" backend can replace the standard loop entirely** for state-machine tracing/observability — the same node list, executed by a different runner. Evidence that the node/edge model is the real abstraction and the loop is swappable.

## Related
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — the canonical pipeline assembled on this engine; shows the variation-matrix trick of reusing nodes under different edge lists.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — a node built to this contract that does the real LLM work.
- [[multi-source-fetch-node--from-scrapegraph-ai]] — the entry-point node that seeds the shared state.
- [[search-driven-scraping--from-scrapegraph-ai]] — a pipeline that runs *other* graphs inside a node, the library's answer to parallelism.
- See also: [[reactive-store-architecture--from-xyflow]] and the node-graph model in [[graph-editing]] — a UI-side cousin of "everything is nodes + edges."
