# Search-Driven Scraping — from [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)

> Domain: [[_domain]] · Source: https://github.com/ScrapeGraphAI/Scrapegraph-ai · NotebookLM: <add link>

## What it does
This is the "I don't have a URL, just answer my question from the web" mode. You give it only a question — `SearchGraph("What is Chioggia famous for?", {...})` — and it: turns your question into a good search query, runs a real web search, takes the top N results, **scrapes every one of them with the full SmartScraper pipeline**, and then merges all those per-page answers into one consolidated answer. You can also ask it which URLs it ended up considering.

## Why it exists
SmartScraper answers "what's on *this* page." But most real questions don't come with a URL attached — they come with an information need. The job-to-be-done is **research, not scraping**: go find the relevant pages yourself, read them all, and synthesize. It's the difference between "extract data from this page" and "go figure this out from the internet." Architecturally it's also a demonstration that the node-graph engine composes — a graph whose middle step is *running other graphs*.

## How it actually works
It's a three-node pipeline on the same [[graph-execution-engine--from-scrapegraph-ai]], but the nodes operate at a higher level:

1. **Search the internet.** A node takes your prompt and asks the LLM to rewrite it as a concise search query (a tight prompt: "return only the query string, nothing else; e.g. for 'What is the capital of France?' return 'capital of France'"). It runs that query through a pluggable search backend (DuckDuckGo by default, or Google via a Serper API key) and collects the top `max_results` URLs (default 3). Those URLs go into state.

2. **Scrape each result.** A "graph iterator" node takes the list of URLs and, for each, instantiates a fresh `SmartScraperGraph` with the original prompt and runs it — producing one structured answer per URL. This is where the parallelism actually lives in the library: not in the engine, but in a node that fans out N sub-graphs. The per-page answers collect into a `results` list.

3. **Merge the answers.** A final node takes the list of per-page answers plus the original question and asks the LLM to merge them into a single coherent answer, respecting the schema if one was given.

The config is deep-copied before being handed to the sub-graphs (so each scrape gets a clean, independent config), and after the run you can call `get_considered_urls()` to see exactly which pages fed the answer — useful for citations and debugging.

## The non-obvious parts
- **Graphs compose: a node runs other graphs.** The middle node's whole job is to spin up and execute `SmartScraperGraph` instances. The engine never needed a "sub-pipeline" primitive — composition falls out of "a node can do anything, including run a graph." This is the cleanest evidence that the node/edge model scales up.
- **LLM-rewritten search query, not the raw prompt.** Feeding a chatty question straight to a search engine gives bad results; the search node first distills it to keywords. The prompt is almost comically strict ("if you return something else, you will get a really bad grade") because reliability of that one short output matters a lot.
- **Pluggable search backend with a free default.** DuckDuckGo needs no API key (good for getting started / no-cost); Serper/Google is opt-in for quality. Same "free path by default, pay for power" pattern as the fetch node's backends.
- **`max_results` is the cost/coverage dial.** Three results = three full SmartScraper runs (each itself possibly map-reducing). Bump it for thoroughness, but cost scales linearly with a multiplier per page.
- **Config is deep-copied for the sub-graphs.** Each scrape gets its own config/schema copy so concurrent runs don't stomp shared mutable state — a subtle but necessary correctness move when fanning out.
- **It returns its sources.** `considered_urls` is captured from the final state. Most LLM "research" tools treat sourcing as an afterthought; here it's a first-class output, which is what makes the answer auditable.

## Related
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — the per-page worker this fans out across search results.
- [[graph-execution-engine--from-scrapegraph-ai]] — the engine; this shows graphs composing inside nodes.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — the same merge-many-into-one idea, one level up (merging page answers instead of chunk answers).
- See also: [[multi-source-research-engine--from-last30days-skill]] — a non-LLM-scraping research pipeline that fans out across 10+ APIs in parallel; and [[engagement-signal-ranking--from-last30days-skill]] for ranking the gathered results rather than merging them.
