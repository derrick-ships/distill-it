# Domain: research-automation

Patterns for building automated research pipelines: parallel multi-source retrieval, entity resolution before search, engagement-based ranking, and graceful degradation when sources fail.

## What this domain is about

Research automation is the practice of replacing manual tab-by-tab research with an orchestrated pipeline that hits multiple sources simultaneously, ranks by real engagement signals, and synthesizes results into a coherent output. The key insight: most information silos (Reddit, X, YouTube, GitHub) have public or semi-public access patterns that can be automated without official API deals.

## Core patterns

- **Pre-search entity resolution**: Identify who/what to search for before searching (handles, subreddits, repos)
- **Parallel source retrieval**: ThreadPoolExecutor across heterogeneous APIs with per-source error isolation
- **Depth profiles**: quick/default/deep tiers controlling result volume vs latency
- **Supplemental phases**: Entity-targeted follow-up after initial retrieval to go deeper on signals found

## Features in this domain

- [[multi-source-research-engine--from-last30days-skill]] — parallel retrieval pipeline across 10+ sources
- [[entity-resolution--from-last30days-skill]] — pre-search handle/subreddit/repo discovery
- [[engagement-signal-ranking--from-last30days-skill]] — reciprocal-rank fusion + LLM reranking by engagement
- [[search-driven-scraping--from-scrapegraph-ai]] — question-only research: LLM rewrites prompt → web search → scrape top-N results with the full SmartScraper pipeline → merge per-page answers into one. Composition trick: a node runs other graphs; returns `considered_urls` for citations.
- [[deep-research-loop--from-firecrawl]] — autonomous depth-bounded research: from a topic, loop search+scrape → analyze → pick the next query until maxDepth/timeLimit, then synthesize a report. The feedback loop (analyze→next-topic) is the whole value; reuses the search+scrape path.
