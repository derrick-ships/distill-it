# Scrape Engine + Fallback Pipeline — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Give it one URL and it returns clean LLM-ready output — markdown, cleaned HTML, a screenshot, the
links, or structured JSON — no matter how hostile the page is. A static blog and a heavily
JavaScript-gated SPA behind a bot-wall both come back as tidy markdown. This single transform is the
atom every other firecrawl feature (crawl, search, extract) is built on.

## Why it exists

"Covering 96% of the web, including JS-heavy pages" is the whole pitch. Real pages fight you: some need
a full headless browser, some block datacenter IPs, some are just a PDF. Firecrawl's answer is to keep
a *stable* of fetching engines and try them in order until one works, then run the raw result through a
fixed chain of transformers that shape it into whatever output formats you asked for.

## How it actually works

Two stages: **get the bytes** (engines, with fallback), then **shape the bytes** (transformers).

**Engines.** Firecrawl has a roster: `fetch` (plain HTTP, fastest), `playwright` (self-hosted headless
browser), several `fire-engine` variants (its hosted browser service — chrome-cdp and tlsclient flavors,
each with optional `stealth` and `retry` modes), `pdf` and `docx` (document parsers), `index` (serve a
recently-cached copy), and special-case engines like `wikipedia` and `x-twitter`. Each engine declares
which *feature flags* it supports — screenshots, `actions` (click/scroll/type), stealth proxy, waiting,
etc. The request's options get turned into a set of required feature flags; `buildFallbackList`
produces the ordered list of engines that can satisfy them. The loop tries each engine in turn: if one
throws an `EngineError` (or times out), it moves to the next, until something succeeds or it runs out
(`NoEnginesLeftError`). A hard per-request timeout aborts the whole thing via an AbortManager. One nice
detail: if you request `actions`, the list is checked up front — actions only work on fire-engine, so
it fails fast with a clear message rather than silently dropping them.

**Transformers.** Once an engine returns raw HTML (or a file), a *fixed-order* transformer stack runs:
derive cleaned HTML from raw HTML → derive markdown from HTML → extract links → extract metadata (title,
description, og: tags, status code) → run the LLM extraction if a `json` format was requested → strip
base64 images → finally `coerceFieldsToFormats`, which keeps only the formats you actually asked for and
shapes the response. Each transformer takes the document and returns the document, so it's a clean pipe.

**Caching.** A `maxAge` lets a scrape return a recently-indexed copy instead of re-fetching (search,
for instance, uses a 3-day maxAge on the pages it scrapes), which is what keeps p95 latency low.

## The non-obvious parts

- **Engines are chosen by capability, not by name.** You don't pick "use playwright"; you ask for
  screenshots+actions and the fallback builder figures out which engines qualify and in what order.
- **Fallback is the reliability story.** "96% of the web" isn't one magic scraper — it's `fetch` →
  browser → stealth-browser → retry, each catching what the previous couldn't.
- **`stealth` and `retry` are modes layered onto an engine**, encoded right in the engine name
  (`fire-engine(retry);chrome-cdp;stealth`), not separate engines.
- **Transformer order is fixed and matters** — markdown is derived *from* the cleaned HTML, links and
  metadata from the raw HTML, LLM-extract runs after markdown exists, and format-trimming is dead last.
- **Actions require the hosted browser.** Self-hosters without fire-engine can't use click/scroll/type.
- **The index engine** can short-circuit the whole thing by serving a cached scrape — fast and cheap,
  the backbone of the latency claims.

## Related
- [[queue-backed-crawl--from-firecrawl]] (crawl calls this scraper once per discovered page)
- [[web-search-with-scrape--from-firecrawl]] (search scrapes each result through this same pipeline)
- [[llm-extract-map-reduce--from-firecrawl]] (the `json` format is the LLM-extract transformer; multi-page extract scrapes via this engine)
- See also: [[page-format-pipeline--from-llm-scraper]] and [[multi-source-fetch-node--from-scrapegraph-ai]] — same "one page → many formats" idea at smaller scale.
