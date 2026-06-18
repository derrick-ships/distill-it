# Map-Reduce Answer Generation — from [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)

> Domain: [[_domain]] · Source: https://github.com/ScrapeGraphAI/Scrapegraph-ai · NotebookLM: <add link>

## What it does
This is the node that actually turns "a big pile of page content + your question" into a structured answer. The catch it solves: a real web page is often far bigger than a model's context window. So instead of one giant call, it runs the model **once per chunk in parallel** ("here's chunk 3 of the page, answer the question from just this"), then makes a **final merge call** that stitches the per-chunk answers into one deduplicated result. If the content fits in a single chunk, it skips straight to one call. If you supplied a Pydantic schema, the output is coerced to that schema; otherwise it's parsed as JSON.

## Why it exists
The whole "scrape with an LLM" promise dies on large pages: you either truncate (and miss data) or exceed the context limit (and error). Map-reduce is the standard escape — split, answer each piece, combine. The job-to-be-done is **extract a complete, schema-shaped answer from content of any size**, while keeping latency reasonable (the per-chunk calls run concurrently, not in sequence) and the output reliably parseable (schema-constrained, with explicit "no backticks, valid JSON" instructions hammered into the prompt).

## How it actually works
The node figures out three things up front: which prompt templates to use, how to enforce output shape, and whether it's a one-chunk or many-chunk job.

**Output shaping.** If a Pydantic schema was passed: for OpenAI it builds a Pydantic output parser and asks for those exact fields; for most others, same; for Bedrock specifically it skips the parser (lets the model's native structured output handle it). If no schema: a plain JSON output parser is used, with an instruction to return `{"content": ...}`.

**Template choice.** There are two families of prompt templates — one for Markdown-converted content, one for raw HTML — each with three variants: "no chunks" (single call), "chunks" (per-chunk), and "merge" (combine). The node picks the Markdown family by default (since the fetch node usually converts to Markdown). Every template carries the same hard rules: *if you can't find the answer, return "NA"; output valid JSON; do not wrap in ```json fences* (because the fences break downstream parsing).

**The one-chunk fast path.** If there's a single chunk, it builds one prompt (`content` + `question` + `format_instructions`), pipes it through the model and the output parser, invokes with a timeout, and returns the answer. Done.

**The many-chunk map-reduce.** For N chunks it builds N separate chains — one per chunk, each with that chunk baked in as a partial variable and labelled `chunk{i}` — and bundles them into a `RunnableParallel`. One `.invoke({"question": ...})` fires all N model calls concurrently and returns a dict of per-chunk answers. Then a **merge chain** takes that dict of partial answers as its `content`, plus the original question, and asks the model to merge them into one coherent answer "without repetitions" and "respecting any maximum-items limit." That merged result is the final answer written to state.

Every model call goes through an `invoke_with_timeout` helper that wraps the chain and raises if it runs long, and timeouts / JSON-decode errors are caught and turned into a structured `{"error": ..., "raw_response": ...}` value rather than crashing the pipeline.

## The non-obvious parts
- **Map-reduce is the headline robustness move.** It's what lets the library claim "scrape any page" — content size stops mattering because chunks are answered independently and merged. The cost is N+1 model calls and the risk that a fact split across two chunks gets half-answered in each (the merge step is supposed to reconcile, but it's not guaranteed).
- **Per-chunk calls run in parallel via `RunnableParallel`.** This is the difference between "10 chunks = 10× latency" and "10 chunks ≈ 1× latency." It's a deliberate latency optimization that also multiplies your rate-limit pressure.
- **Chunks are injected as *partial* prompt variables, not runtime inputs.** Each chunk's chain has its chunk pre-bound, so the single parallel invoke only needs to pass `question`. Clean trick for fanning one question across many fixed contexts.
- **"Do not start with ```json" is a real, repeated instruction.** Models love wrapping JSON in Markdown fences; that breaks naive parsers. Rather than strip fences after the fact, the prompt forbids them up front (belt-and-suspenders with the output parser).
- **`"NA"` is the contract for "not found."** Every template instructs the model to use it. This sentinel is what the SmartScraper retry loop keys off to decide whether to try again — so this node and the conditional retry node share a vocabulary.
- **Ollama gets schema set on the model object itself.** For Ollama, the node sets `llm_model.format` to either `"json"` or the schema's JSON schema — using Ollama's native structured-output instead of a parser. Provider-specific structured-output handling is baked in per backend.
- **Failures degrade to data, not exceptions.** A timeout or bad JSON becomes `{"error": ..., "raw_response": ...}` in the answer slot, so the graph completes and the caller can inspect what went wrong instead of catching an exception.

## Related
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — the pipeline this is the final node of; its retry loop reads this node's `"NA"` output.
- [[multi-source-fetch-node--from-scrapegraph-ai]] / parse step — produce the chunks this consumes.
- [[provider-agnostic-model-layer--from-scrapegraph-ai]] — supplies the model and the token budget that decides how many chunks there are.
- See also: [[schema-driven-extraction--from-llm-scraper]] — the contrasting design: lean on the SDK's structured-output in ONE call instead of chunk-and-merge with hand-written JSON instructions. And [[streaming-partial-objects--from-llm-scraper]] for progressive output.
