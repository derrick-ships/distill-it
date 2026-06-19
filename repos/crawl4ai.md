# crawl4ai — origin index

- **Source:** https://github.com/unclecode/crawl4ai
- **What it is:** Open-source LLM-friendly web crawler and scraper. Turns any URL into clean, structured Markdown or typed JSON — built for RAG pipelines, AI agents, and data collection at scale.
- **Author:** Unclecode (unclecode@kidocode.com) · **License:** Apache-2.0
- **Stack:** Python 3.10+ · Playwright + patchright (browser automation) · FastAPI (Docker server) · aiosqlite (cache) · LiteLLM (multi-provider LLM) · BeautifulSoup4 + lxml (HTML parsing) · rank-bm25 (content filtering) · NLTK (NLP chunking) · Pydantic v2 (schemas) · psutil (memory monitoring) · Redis (optional, for state)
- **Date distilled:** 2026-06-19
- **Architecture in one line:** URL → AsyncWebCrawler (Playwright fetch + cache + anti-bot retry) → HTML processing pipeline (filter → markdown → extract) → CrawlResult; multi-page via deep crawl strategies (BFS/DFS/adaptive) dispatched through MemoryAdaptiveDispatcher; structured extraction via CSS schemas or LLM.

## Features extracted

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Async Web Crawler Engine | web-scraping | [study](../features/web-scraping/study/async-web-crawler--from-crawl4ai.md) | [build](../features/web-scraping/build/async-web-crawler--from-crawl4ai.md) |
| LLM-Based Structured Extraction | structured-extraction | [study](../features/structured-extraction/study/llm-structured-extraction--from-crawl4ai.md) | [build](../features/structured-extraction/build/llm-structured-extraction--from-crawl4ai.md) |
| CSS/XPath/Lxml Schema Extraction | structured-extraction | [study](../features/structured-extraction/study/css-xpath-schema-extraction--from-crawl4ai.md) | [build](../features/structured-extraction/build/css-xpath-schema-extraction--from-crawl4ai.md) |
| Content Filtering Strategies | web-scraping | [study](../features/web-scraping/study/content-filtering-strategies--from-crawl4ai.md) | [build](../features/web-scraping/build/content-filtering-strategies--from-crawl4ai.md) |
| Deep Crawl / Multi-Page Traversal | web-scraping | [study](../features/web-scraping/study/deep-crawl-traversal--from-crawl4ai.md) | [build](../features/web-scraping/build/deep-crawl-traversal--from-crawl4ai.md) |
| Browser Stealth & Anti-Detection | browser-automation | [study](../features/browser-automation/study/browser-stealth-anti-detection--from-crawl4ai.md) | [build](../features/browser-automation/build/browser-stealth-anti-detection--from-crawl4ai.md) |
| Adaptive Crawler | web-scraping | [study](../features/web-scraping/study/adaptive-crawler--from-crawl4ai.md) | [build](../features/web-scraping/build/adaptive-crawler--from-crawl4ai.md) |
| Dispatcher & Concurrency Control | infrastructure | [study](../features/infrastructure/study/dispatcher-concurrency-control--from-crawl4ai.md) | [build](../features/infrastructure/build/dispatcher-concurrency-control--from-crawl4ai.md) |
| Chunking Strategies | structured-extraction | [study](../features/structured-extraction/study/chunking-strategies--from-crawl4ai.md) | [build](../features/structured-extraction/build/chunking-strategies--from-crawl4ai.md) |

## Verification gaps to check before transplanting
- `agenerate_schema()` validation loop and XML-block response parsing — llm-structured-extraction build.
- `JsonLxmlExtractionStrategy` nth-child fallback and `_resolve_source()` sibling logic — css-xpath build.
- `BestFirstCrawlingStrategy` scorer weights and link-preview fetch mechanism — deep-crawl build.
- `AdaptiveCrawler.digest()` return shape and embedding strategy paraphrase LLM call — adaptive-crawler build.
- `MemoryAdaptiveDispatcher` priority queue drain/refill cycle and fairness recalculation — dispatcher build.
- patchright vs playwright behavioral differences with `browser_mode="dedicated"` — stealth build.
