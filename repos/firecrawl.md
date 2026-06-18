# Firecrawl — origin index

- **Source:** https://github.com/firecrawl/firecrawl
- **What it is:** A web-data API that turns any URL (or whole site, or search query) into clean
  LLM-ready output — markdown, structured JSON, screenshots. Endpoints: scrape, crawl, map, search,
  extract, agent/deep-research, generate-llms.txt. "Covers 96% of the web including JS-heavy pages."
- **Author:** Firecrawl (Mendable) · **License:** AGPL-3.0
- **Stack:** TypeScript/Node + Express API (`apps/api`, v0/v1/v2 generations) · BullMQ + Redis (queues,
  crawl state, concurrency) · Playwright + a hosted "fire-engine" browser service · SearXNG/DuckDuckGo
  search · structured-output LLMs (Gemini) for extract/agent · Supabase (billing, caches) · x402 EVM payments.
- **Date distilled:** 2026-06-18
- **Architecture in one line:** request → capability-driven engine fallback chain → fixed transformer
  stack → formats; crawl/search/extract/map/research/llms.txt are queue- and LLM-orchestrated fan-outs
  over that one scraper, all behind credit metering + concurrency queues + keyless/x402 access tiers.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Scrape Engine + Fallback Pipeline | web-extraction | [study](../features/web-extraction/study/scrape-engine-fallback-pipeline--from-firecrawl.md) | [build](../features/web-extraction/build/scrape-engine-fallback-pipeline--from-firecrawl.md) |
| Queue-Backed Crawl | pipeline-orchestration | [study](../features/pipeline-orchestration/study/queue-backed-crawl--from-firecrawl.md) | [build](../features/pipeline-orchestration/build/queue-backed-crawl--from-firecrawl.md) |
| LLM Extract (map-reduce) | structured-extraction | [study](../features/structured-extraction/study/llm-extract-map-reduce--from-firecrawl.md) | [build](../features/structured-extraction/build/llm-extract-map-reduce--from-firecrawl.md) |
| Web Search (+ optional scrape) | web-extraction | [study](../features/web-extraction/study/web-search-with-scrape--from-firecrawl.md) | [build](../features/web-extraction/build/web-search-with-scrape--from-firecrawl.md) |
| Site URL Map | web-extraction | [study](../features/web-extraction/study/site-url-map--from-firecrawl.md) | [build](../features/web-extraction/build/site-url-map--from-firecrawl.md) |
| Agentic Browser Actions (smart-scrape) | web-extraction | [study](../features/web-extraction/study/agentic-browser-actions--from-firecrawl.md) | [build](../features/web-extraction/build/agentic-browser-actions--from-firecrawl.md) |
| Deep Research Loop | research-automation | [study](../features/research-automation/study/deep-research-loop--from-firecrawl.md) | [build](../features/research-automation/build/deep-research-loop--from-firecrawl.md) |
| Generate llms.txt | content-synthesis | [study](../features/content-synthesis/study/generate-llms-txt--from-firecrawl.md) | [build](../features/content-synthesis/build/generate-llms-txt--from-firecrawl.md) |
| Credit Billing & Concurrency | payments | [study](../features/payments/study/credit-billing-and-concurrency--from-firecrawl.md) | [build](../features/payments/build/credit-billing-and-concurrency--from-firecrawl.md) |
| Keyless & x402 Paid Access | credential-management | [study](../features/credential-management/study/keyless-and-x402-access--from-firecrawl.md) | [build](../features/credential-management/build/keyless-and-x402-access--from-firecrawl.md) |

## Verification gaps flagged in build docs (check before transplant)
- `buildFeatureFlags`/engine `quality` weighting, `coerceFieldsToFormats` — scrape build.
- Worker link-filter/child-enqueue, sitemap lifecycle, status cursor — crawl build.
- `analyzeSchemaAndPrompt` multi-entity decision, prompts, reranker — extract build.
- `executeSearch` shouldScrape/credit logic, provider request shapes — search build.
- `MAX_MAP_LIMIT`, fireEngineMap cache TTL — map build.
- fire-engine smart-scrape action-loop internals, cost cap — agentic-browser-actions build.
- deep-research prompts + `shouldContinue`; v2 agent.ts vs v1 — deep-research build.
- llms.txt description prompt, Supabase cache schema — generate-llms-txt build.
- Supabase billing RPC, plan→maxConcurrency, key TTLs — credit-billing build.
- keyless day-counter keys/TTL, x402 settle handshake — keyless-and-x402 build.

> Distill note: traced inline (no agent fan-out) under a session cost cap; all spines confirmed from raw
> source via targeted fetch + grep, with per-doc "gaps to verify" lists where files weren't deep-read.
