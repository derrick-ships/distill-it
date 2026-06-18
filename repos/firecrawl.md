# Firecrawl — origin index

- **Source:** https://github.com/firecrawl/firecrawl
- **What it is:** A web-data API that turns any URL (or whole site, or search query) into clean
  LLM-ready output — markdown, structured JSON, screenshots. Headline endpoints: scrape, crawl, map,
  search, extract, plus agent/deep-research. "Covers 96% of the web including JS-heavy pages."
- **Author:** Firecrawl (Mendable) · **License:** AGPL-3.0
- **Stack:** TypeScript/Node + Express API (`apps/api`), v0/v1/v2 endpoint generations · BullMQ + Redis
  (queues & crawl state) · Playwright + a hosted "fire-engine" browser service · SearXNG/DuckDuckGo
  search backends · structured-output LLMs for extract.
- **Date distilled:** 2026-06-18
- **Architecture in one line:** request → capability-driven engine fallback chain → fixed transformer
  stack → formats; crawl/search/extract are queue- and LLM-orchestrated fan-outs over that one scraper.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Scrape Engine + Fallback Pipeline | web-extraction | [study](../features/web-extraction/study/scrape-engine-fallback-pipeline--from-firecrawl.md) | [build](../features/web-extraction/build/scrape-engine-fallback-pipeline--from-firecrawl.md) |
| Queue-Backed Crawl | pipeline-orchestration | [study](../features/pipeline-orchestration/study/queue-backed-crawl--from-firecrawl.md) | [build](../features/pipeline-orchestration/build/queue-backed-crawl--from-firecrawl.md) |
| LLM Extract (map-reduce) | structured-extraction | [study](../features/structured-extraction/study/llm-extract-map-reduce--from-firecrawl.md) | [build](../features/structured-extraction/build/llm-extract-map-reduce--from-firecrawl.md) |
| Web Search (+ optional scrape) | web-extraction | [study](../features/web-extraction/study/web-search-with-scrape--from-firecrawl.md) | [build](../features/web-extraction/build/web-search-with-scrape--from-firecrawl.md) |

## Not yet distilled (candidates)
- **Map (URL discovery)** — instant enumerate all URLs on a site → domain: `web-extraction`
- **Browser interaction / actions** — AI-driven click/scroll/type before scrape → domain: `web-extraction`
- **Deep research / Agent** — autonomous multi-step gathering without known URLs → domain: `research-automation`
- **generate-llms.txt** — auto-build an llms.txt for a site → domain: `content-synthesis`
- **Credit/billing + concurrency limits** — API-key auth, credit usage, rate/concurrency gating → domain: `payments`
- **x402 / keyless eligibility** — pay-per-call + keyless access → domain: `credential-management`

## Verification gaps flagged in build docs (check before transplant)
- `buildFeatureFlags` rules, engine `quality` weighting, `coerceFieldsToFormats` mapping — scrape build.
- Worker link-filter/child-enqueue code, sitemap-job lifecycle, status cursor — crawl build.
- `analyzeSchemaAndPrompt` multi-entity decision, prompts, LLM provider, reranker — extract build.
- `executeSearch` shouldScrape/credit logic, provider request shapes — search build.

> Distill note: traced inline (no agent fan-out) under a session cost cap; scrape/crawl/extract/search
> spines confirmed from raw source, with per-doc "gaps to verify" lists where files weren't deep-read.
