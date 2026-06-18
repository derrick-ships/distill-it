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

## Cross-domain links
- The scrapegraph-ai features above are built on [[graph-execution-engine--from-scrapegraph-ai]] (the node/edge engine) and feed [[map-reduce-answer-generation--from-scrapegraph-ai]] (the LLM extraction step).
