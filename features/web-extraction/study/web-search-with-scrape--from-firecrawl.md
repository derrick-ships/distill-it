# Web Search (+ optional scrape) — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Run a web search and get back results — and, if you ask, the **full scraped content** of each result,
not just a title and snippet. One call: "search for X, give me the top 10 pages as markdown." It can
return web, news, and image result types, with language/country/time filters.

## Why it exists

LLMs and agents constantly need "search the web, then read the pages." Doing that yourself means a
search API plus a scraper plus glue. Firecrawl fuses them: search picks the URLs, the existing scrape
pipeline reads them, and you get LLM-ready content in a single response — the backbone of any
research/agent loop.

## How it actually works

Two layers. The **search layer** queries a provider and returns normalized results. Firecrawl tries
providers in a fixed fallback order: if its hosted **fire-engine** search is configured, use that;
else if a **SearXNG** endpoint is configured, use that (and only accept it if it returned web results);
otherwise fall back to **DuckDuckGo**. Each provider is normalized to a common shape with `web`, `news`,
and `images` buckets. Empty/error responses degrade to an empty object rather than throwing.

The **scrape layer** is optional and only runs if you passed `scrapeOptions`. It takes the result URLs
(after dropping any blocked domains), and scrapes them **all concurrently** (`Promise.all`) by calling
the same internal scrape worker each page would normally use — with a 3-day `maxAge`, so popular pages
come from cache and stay fast. A page that fails to scrape doesn't sink the request: it comes back with
just its title/description and a 500 status in its metadata. The scraped documents are then **merged
back onto** their matching search results by URL, so each result object gains `markdown`/`html`/etc.

Billing is split: the search itself bills search credits; each scrape job bills itself. There's also a
keyless path (reserve projected credits up front, reconcile after) so anonymous/keyless callers are
metered correctly.

## The non-obvious parts

- **Search and scrape are fused but billed separately** — search credits for the query, per-page scrape
  credits for the content. The controller bills search; scrape jobs self-bill.
- **Provider fallback, not a single backend** — fire-engine → SearXNG → DuckDuckGo, each gated on
  actually returning results. Self-hosters typically wire SearXNG.
- **Result-scraping reuses the exact scrape pipeline** (same engine fallback, same transformers), just
  invoked directly with `skipNuq` and a 3-day cache — search isn't a separate scraper.
- **Failures are soft.** A blocked or unscrapeable URL yields a stub document, not an error; the search
  still returns.
- **Three result types** (web/news/images) flow through the same merge-by-URL machinery.
- **Concurrent scrape of all results** — fast, but it's a fan-out you pay for; the credit projection
  exists precisely to gate that for keyless callers.

## Related
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (each result is scraped through this exact pipeline)
- [[llm-extract-map-reduce--from-firecrawl]] (extract can enable web search to find its sources)
- [[corpus-and-academic-search--from-openpaper]] (a domain-specific search+scrape; firecrawl is the general-web version)
- See also: [[smart-scraper-pipeline--from-scrapegraph-ai]].
