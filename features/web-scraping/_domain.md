# Domain: web-scraping

Browser-driven web data collection at scale — fetching pages through real browser instances, traversing multi-page site graphs, applying crawl strategies (BFS/DFS/adaptive), and managing the lifecycle of browser sessions. Distinct from [[web-extraction]] (which processes already-fetched HTML) and [[structured-extraction]] (which shapes data into schemas). Here the focus is on *getting* the content: navigation, discovery, traversal, and resilience.

## Features studied

- [[async-web-crawler--from-crawl4ai]] — core `AsyncWebCrawler` engine: Playwright-driven fetch, SQLite caching with ETag validation, anti-bot retry loop, content filtering pipeline, and batch dispatch via `arun_many()`.
- [[content-filtering-strategies--from-crawl4ai]] — three swappable noise-reduction strategies applied during crawl: PruningContentFilter (DOM tree scoring), BM25ContentFilter (query-aware relevance), LLMContentFilter (model-based semantic filtering). Produces `fit_markdown` on every result.
- [[deep-crawl-traversal--from-crawl4ai]] — multi-page site traversal using BFS, DFS, or Best-First strategies; URL filters + scorers; crash-recovery checkpointing; streaming results; activated by `deep_crawl_config` in `CrawlerRunConfig`.
- [[adaptive-crawler--from-crawl4ai]] — query-driven crawl that stops when information coverage saturates; statistical term analysis (or embedding-based) measures how much of the query's information space has been captured; prioritizes links by relevance+novelty+authority.

## Cross-domain links
- Depends on [[browser-automation]] — the stealth and session management layer that makes crawls survivable on bot-protected sites.
- Feeds [[structured-extraction]] — the content that crawl produces is consumed by extraction strategies for structured output.
- Uses [[infrastructure]] — the dispatcher and concurrency control layer manages parallel crawl throughput.
