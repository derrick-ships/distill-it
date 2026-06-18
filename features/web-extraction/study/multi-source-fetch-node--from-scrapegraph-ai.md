# Multi-Source Fetch Node — from [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)

> Domain: [[_domain]] · Source: https://github.com/ScrapeGraphAI/Scrapegraph-ai · NotebookLM: <add link>

## What it does
This is the front door of every scraping pipeline: the step that turns "a thing the user pointed at" into "clean text in the shared state." That thing can be a live URL, a local HTML string, a PDF, a CSV, a JSON file, an XML or Markdown file, or a whole directory of those. The node figures out what kind of source it is and dispatches to the right loader, then — for web/HTML content destined for an LLM — converts the messy HTML into clean Markdown so the model isn't drowning in tags. It writes the result into state as a list of `Document` objects under the key `doc`.

## Why it exists
Every downstream node assumes "there is content in `doc`." Someone has to produce that content from wildly different inputs, and do it in a way that's friendly to an LLM. The job-to-be-done is **input normalization**: hide the difference between "scrape a JS-heavy site through a headless browser" and "read a local PDF" behind one node so the rest of the pipeline never branches on source type. The second job is **noise reduction** — raw HTML is mostly markup; converting to Markdown can cut tokens dramatically while preserving the readable content and links.

## How it actually works
The node reads its single input key (`"url | local_dir"` — whichever is present) and the source value, then routes on the *input key name*, not the content:

- **File types** (`pdf`, `csv`, `json`, `xml`, `md`) → a file loader. PDFs go through PyPDFLoader; CSVs through pandas (stringified); JSON is loaded and stringified; XML/MD are read as raw text. Each becomes a `Document` with a `source` metadata tag.
- **Directory types** (`*_dir`) → the source is wrapped as-is into a one-element list (the directory contents are assumed pre-collected).
- **`local_dir`** (a local HTML string) → optionally converted to Markdown, wrapped as a `Document`.
- **`url`** (the main path) → fetched through one of several backends, then converted to Markdown.

The web path is where the real engineering is. There are *four* ways to fetch a URL, chosen by config:
1. **Plain `requests`** (`use_soup=True`) — simple GET, optional HTML cleanup.
2. **BrowserBase** — a hosted headless-browser service (for JS-heavy or bot-protected sites).
3. **Scrape.do** — a proxy/scraping API with geo and super-proxy options.
4. **ChromiumLoader** (default) — a real headless Chromium via Playwright, with optional saved browser session (`storage_state`) for authenticated scraping.

Whichever backend runs, the result is checked for emptiness (raising if the page came back blank), then — when the LLM is an OpenAI-family model and we're not in script-creation mode — the HTML is run through `convert_to_md`. Both the raw fetched document and the cleaned/compressed document are written to state (`doc` gets the raw, the output key gets the compressed one), so later nodes can choose fidelity vs. cleanliness.

## The non-obvious parts
- **Dispatch is on the input *key name*, not content sniffing.** Because the engine's input DSL already resolved which key is present (`url` vs `pdf` vs `local_dir`…), the node trusts that name to pick a handler. The "what kind of source is this" decision was effectively made upstream by how the pipeline seeded the state.
- **Four fetch backends behind one node** is a portability story: free/simple (`requests`), real-browser (Chromium), and two commercial anti-bot services (BrowserBase, Scrape.do). You opt into heavier machinery only when a site fights back, without changing the pipeline.
- **HTML→Markdown conversion is gated on model family.** It only auto-converts for OpenAI/Azure-OpenAI models (and respects `force`/`script_creator`/`openai_md_enabled` flags). The assumption: those models do better on Markdown; other paths may want raw HTML. It's a quietly load-bearing heuristic.
- **`storage_state` enables authenticated scraping.** Pass a saved Playwright session (cookies/localStorage) and Chromium loads the page as a logged-in user. This is the difference between scraping public pages and scraping behind a login.
- **It writes two representations.** `state["doc"]` = the raw fetched document; `state[output[0]]` = the compressed/markdown version. Downstream nodes' input expressions (`relevant_chunks | parsed_doc | doc`) can fall back to `doc` if no parsing happened.
- **Blank-page detection is explicit.** If the loader returns nothing or whitespace, it raises rather than silently feeding an empty page to the LLM — a real failure mode for JS sites that didn't finish rendering.

## Related
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — the pipeline this node leads.
- [[graph-execution-engine--from-scrapegraph-ai]] — the node contract and the input-key DSL that pre-selects the source type.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — consumes the `doc`/`parsed_doc` this node produces.
- See also: [[html-cleanup--from-llm-scraper]] and [[page-format-pipeline--from-llm-scraper]] — the TS library's take on the same "reduce a page to LLM-friendly text" problem; and [[html-web-conversion--from-markitdown]] for generic HTML→Markdown with platform specializations.
