# Domain: web-extraction

Turning web resources — HTML pages, YouTube videos, RSS feeds, Wikipedia articles — into clean Markdown by combining HTTP fetching, DOM parsing, and platform-specific API calls.

## What this domain is about

Web content is messy: it mixes layout markup, scripts, ads, and navigation chrome with the actual content. Web extraction is the practice of fetching a URL, stripping the noise, and preserving the signal as structured Markdown. Specialized extractors outperform generic HTML-to-Markdown when the platform has a known structure (YouTube metadata JSON, Wikipedia content divs, RSS item schema).

## Common patterns

- **Generic path**: fetch → BeautifulSoup parse → strip scripts/styles → markdownify body
- **Specialized path**: detect URL pattern → call platform-specific API or scrape known JSON structure → format result
- **Fallback**: if specialized extraction fails, fall through to generic HTML path

## Features in this domain

- [[html-web-conversion--from-markitdown]] — generic HTML→Markdown with Wikipedia/RSS/Bing specializations
- [[youtube-extraction--from-markitdown]] — YouTube metadata scraping + transcript API
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — prompt + URL → structured answer, as a 3-node pipeline (fetch→parse→generate) that reshapes itself via feature flags; the LLM-driven alternative to selector scraping.
- [[multi-source-fetch-node--from-scrapegraph-ai]] — input normalization: any of {URL via Chromium/requests/BrowserBase/Scrape.do, local HTML/PDF/CSV/JSON/XML/MD} → clean Markdown `Document`s.
- [[corpus-and-academic-search--from-openpaper]] — two non-merging search subsystems: an internal `ILIKE` substring scan over a paper corpus (no embeddings, recency-ranked) and external academic discovery via OpenAlex (with inverted-index abstract reconstruction) + Exa. The 'search my library AND the web of papers' counterpart to the page-extraction nodes here, plus a 3-pass metadata-hydration fallback (CrossRef/OpenAlex → agentic Exa+Firecrawl).
- [[scrape-engine-fallback-pipeline--from-firecrawl]] — the production-grade version of this domain's 'one page → many formats' idea: a capability-driven engine fallback chain (fetch → playwright → hosted stealth browser → pdf) chosen by feature flags, then a fixed transformer stack. The reliability ('96% of the web') comes from the fallback ladder, not one magic scraper.
- [[web-search-with-scrape--from-firecrawl]] — fuses web search (fire-engine → SearXNG → DuckDuckGo fallback) with concurrent scraping of every result through that same pipeline, merged by URL. The general-web counterpart to [[corpus-and-academic-search--from-openpaper]]'s domain-specific search+scrape.
- [[site-url-map--from-firecrawl]] — fast URL discovery for a domain (sitemap + fire-engine index, dedup, optional cosine-rerank by a search query) WITHOUT scraping page bodies. The reconnaissance step before a crawl/extract.
- [[agentic-browser-actions--from-firecrawl]] — an AI agent drives a hosted browser from a natural-language goal (click/scroll/type/wait) before capture, returning post-interaction HTML/markdown. The interactive-web answer to JS-gated content, as a scrape-pipeline transformer.
- [[declarative-http-stream-stack--from-airbyte]] — the four-component REST-pull engine (requester → paginator → extractor → selector) wired by a retriever loop, all driven by string interpolation. The API-record-oriented counterpart to the page-scraping pipelines in this domain; pagination splits how-to-compute-the-token from where-to-inject-it.

## Cross-domain links
- The scrapegraph-ai features above are built on [[graph-execution-engine--from-scrapegraph-ai]] (the node/edge engine) and feed [[map-reduce-answer-generation--from-scrapegraph-ai]] (the LLM extraction step).
