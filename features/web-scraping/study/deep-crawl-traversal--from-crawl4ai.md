# Deep Crawl / Multi-Page Traversal — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

The deep crawl system extends `AsyncWebCrawler` to traverse entire websites or link graphs — not just single pages. You give it a start URL and a strategy (BFS, DFS, or Best-First), configure depth limits, URL filters, and quality scorers, and it automatically discovers and crawls linked pages, returning a stream of `CrawlResult` objects. It supports crash recovery through state checkpointing and a "prefetch" mode that discovers URLs 5-10x faster by reading link metadata without full rendering.

## Why it exists

Most real AI data collection tasks require more than one page. A researcher wants all articles on a blog; an agent wants the full documentation of a library; a data pipeline wants all product pages on a site. Deep crawling automates the traversal and deduplication logic that would otherwise be manual.

## How it actually works

**Architecture:** Deep crawling is implemented as a decorator on top of `AsyncWebCrawler.arun()`. When `CrawlerRunConfig.deep_crawl_config` is set, a `DeepCrawlDecorator` intercepts the `arun()` call and runs the chosen traversal strategy instead. The strategy then calls the underlying `arun()` for each discovered URL.

**BFS (Breadth-First Search):** Processes all URLs at depth 0 first, then all at depth 1, and so on. Maintains a `visited` set for deduplication. Each level is processed as a batch through the crawler's dispatcher, so BFS naturally supports parallelism within a level. Link discovery happens after each page loads: the `CrawlResult.links` dict provides internal and external links, which are filtered through the `FilterChain` and optionally scored by the `URLScorer`. URLs below a score threshold or above `max_depth` are dropped.

**DFS (Depth-First Search):** Follows one branch deep before backtracking. Implemented with a stack. Useful when a site's deepest pages are the most valuable and you want to reach them quickly.

**Best-First Search:** Scores all candidate URLs before crawling any of them, then always picks the highest-scoring uncrawled URL next. The `URLScorer` can combine multiple scoring signals: keyword relevance (BM25 against query terms in the URL/path), domain authority, content freshness, and URL path depth. This is the most intelligent strategy for targeted research.

**FilterChain:** Every discovered link passes through a chain of composable filters before being queued:
- `URLPatternFilter` — glob or regex patterns (e.g., `*.html`, `/blog/*`)
- `DomainFilter` — whitelist/blacklist domains
- `ContentTypeFilter` — only HTML pages, skip images/PDFs
- `SEOFilter` — skip low-quality pages (uses BM25 on page head metadata)
- `ContentRelevanceFilter` — BM25 against a query, applied to head metadata

Filters run concurrently for performance. The first filter to reject a URL short-circuits the chain.

**Checkpointing and recovery:** The BFS/DFS strategies expose an `on_state_change` callback that fires after each URL is processed. The state snapshot contains `visited` URLs, `pending` queue, and depth map — enough to resume a crashed crawl exactly where it stopped. Call `strategy.export_state()` to get the snapshot and pass it as `resume_state` to restart.

## The non-obvious parts

**The `DeepCrawlDecorator` wraps `arun()` transparently.** You don't call a different method — deep crawling is activated by setting `deep_crawl_config` in `CrawlerRunConfig`. The same crawler can do single-page or multi-page depending on that config.

**Streaming is critical at scale.** By default, `arun()` in deep-crawl mode returns a `List[CrawlResult]` — all pages held in memory. With `stream=True` in the config, it returns an `AsyncGenerator`, and you process each page as it arrives. For large sites, always stream.

**URL scoring happens before crawling.** When using Best-First, all discovered links are scored using URL-level signals (path, domain) before any page is fetched. This avoids fetching pages to evaluate them, but it means the scorer is working from URL structure alone until the first page of each branch is loaded.

**`max_pages` and `max_depth` are independent limits.** Hitting either one stops traversal. A DFS with `max_depth=5` on a deep site might hit a branch that's only 3 levels deep — `max_pages` then becomes the binding constraint.

## Related
- [[async-web-crawler--from-crawl4ai]] (the engine each page goes through)
- [[adaptive-crawler--from-crawl4ai]] (smarter: stops when coverage is sufficient, not just at depth limit)
- [[dispatcher-concurrency-control--from-crawl4ai]] (BFS parallelism uses the dispatcher)
