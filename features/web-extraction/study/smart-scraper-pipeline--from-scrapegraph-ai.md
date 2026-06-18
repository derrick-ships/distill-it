# SmartScraper Pipeline — from [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)

> Domain: [[_domain]] · Source: https://github.com/ScrapeGraphAI/Scrapegraph-ai · NotebookLM: <add link>

## What it does
This is the library's flagship: the one-liner that most people come for. You write `SmartScraperGraph("List all the attractions in Chioggia", "https://en.wikipedia.org/wiki/Chioggia", {"llm": {"model": "openai/gpt-4o"}})` and call `.run()`, and you get back a structured answer extracted from that page — no selectors, no XPath, just a prompt and a URL. Optionally hand it a Pydantic schema and the answer comes back shaped to it. Under the hood it's a small assembled pipeline: fetch the page → clean and chunk it → ask the LLM to answer your prompt against the content → return the answer.

## Why it exists
It's the product. Everything else in the library (search, multi-page, script generation, speech) is a remix of this core flow. Its job-to-be-done is "turn a page + a question into structured data," and its design goal is to make the *common* case trivial while keeping the *hard* cases reachable through config flags. The clever part isn't any single node — it's how the pipeline reshapes itself based on three boolean options without any of the nodes knowing.

## How it actually works
`SmartScraperGraph` extends an `AbstractGraph` base that, on construction, does three things: builds the LLM client from your config, builds the node graph, and pushes shared params (the model, headless flag, timeout) into every node. Then `.run()` seeds the shared state with `{user_prompt, url-or-local_dir}` and hands it to the [[graph-execution-engine--from-scrapegraph-ai]].

The default graph is three nodes in a line:
1. **Fetch** ([[multi-source-fetch-node--from-scrapegraph-ai]]) — grabs the page (or local file) and writes `doc` into state, usually converting HTML to Markdown for the LLM.
2. **Parse** — splits `doc` into token-sized chunks (sized to the model's context window) and writes `parsed_doc`.
3. **Generate Answer** ([[map-reduce-answer-generation--from-scrapegraph-ai]]) — reads the prompt and the chunks, runs the LLM per chunk in parallel, merges into one answer, and writes `answer`.

The interesting bit is that this exact pipeline has **eight variants**, selected by three boolean config flags: `html_mode`, `reasoning`, and `reattempt`. The class holds a lookup table keyed by the `(html_mode, reasoning, reattempt)` tuple, and each entry is a different node list + edge list over the *same* node objects:
- `html_mode=True` skips the Parse node — the raw HTML/markdown goes straight to the LLM (no chunking), trading cost for fidelity on small pages.
- `reasoning=True` inserts an extra "reasoning" node before answering, to think before extracting.
- `reattempt=True` appends a **conditional node + a regenerate node**: after the first answer, the conditional checks `not answer or answer == "NA"`; if the extraction failed, it routes to a second LLM pass primed with "you just failed, try again and fill the gaps"; otherwise it stops. This is a self-healing retry loop built purely from the engine's conditional-node mechanism.

A nice escape hatch: if you set the model to the magic string `"scrapegraphai/smart-scraper"`, the whole graph is bypassed and the call is forwarded to ScrapeGraphAI's hosted API instead — same interface, their servers do the work. That's how the open-source library doubles as a client for the paid product.

## The non-obvious parts
- **The pipeline is data, not code.** Eight pipeline shapes are eight entries in a dict. The nodes don't know which variant they're in; the graph just wires them differently. This is the payoff of the node/edge engine — feature flags become edge-list swaps.
- **The retry loop is the headline robustness feature and it's free.** No special framework — it's one conditional node returning the next node's name. The condition string `'not answer or answer=="NA"'` is evaluated against state. If the model says "NA" (its instructed value for "couldn't find it"), the pipeline gets a second, more aggressive attempt.
- **`html_mode` is a cost/fidelity dial.** Off (default): clean → chunk → map-reduce, cheap and scalable to big pages. On: send the page whole, fewer LLM calls, better at cross-section reasoning, but blows up on large pages and costs more per call.
- **Input key auto-detection.** `input_key` is `"url"` if the source starts with `http`, else `"local_dir"`. The same class scrapes the live web and local HTML with no API difference.
- **The base class is provider-agnostic by construction** ([[provider-agnostic-model-layer--from-scrapegraph-ai]]) — the `{"llm": {"model": "..."}}` config is parsed into the right client, and the model's token limit is what sizes the chunks. So your model choice silently changes chunk size.
- **The schema rides along untouched.** If you pass a Pydantic schema, it's handed to the answer node which converts it to format instructions / structured output. The pipeline shape doesn't change; only the answer node's prompting does.

## Related
- [[graph-execution-engine--from-scrapegraph-ai]] — the engine this pipeline is assembled on; the variation matrix is its showcase.
- [[multi-source-fetch-node--from-scrapegraph-ai]] — step 1.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — step 3, where the LLM extraction happens.
- [[provider-agnostic-model-layer--from-scrapegraph-ai]] — how `{"llm": {...}}` becomes a client and sets chunk size.
- [[search-driven-scraping--from-scrapegraph-ai]] — wraps this pipeline N times across search results.
- See also: [[schema-driven-extraction--from-llm-scraper]] — the same "prompt + page → typed object" idea in TypeScript, but a single LLM call instead of a node pipeline. Good contrast: SDK-structured-output vs. chunk-and-merge prompting.
