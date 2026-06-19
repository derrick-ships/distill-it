# Deep Crawl / Multi-Page Traversal (build spec) — distilled from crawl4ai

## Summary

A decorator-based deep crawl system that wraps `AsyncWebCrawler.arun()` to traverse multi-page websites using BFS, DFS, or Best-First strategies. Activated by setting `deep_crawl_config` in `CrawlerRunConfig`. Supports URL filtering, quality scoring, state checkpointing, and streaming results.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DFSDeepCrawlStrategy, BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import (
    FilterChain, URLPatternFilter, DomainFilter, ContentTypeFilter
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

# Build a filter chain
filter_chain = FilterChain([
    URLPatternFilter(patterns=["*.html", "/blog/*"]),
    DomainFilter(allowed_domains=["docs.example.com"]),
    ContentTypeFilter(allowed_types=["text/html"]),
])

# Build a scorer (optional, for Best-First)
scorer = KeywordRelevanceScorer(keywords=["tutorial", "guide", "api"])

# Choose strategy
strategy = BFSDeepCrawlStrategy(
    max_depth=3,
    max_pages=100,
    filter_chain=filter_chain,
    url_scorer=scorer,          # optional; required for BestFirst
    score_threshold=0.1,
    include_external=False,
    on_state_change=my_save_callback,   # for checkpointing
    resume_state=previous_state_dict,   # to resume from crash
)

# Attach to run config
config = CrawlerRunConfig(
    deep_crawl_config=strategy,
    stream=True,                # strongly recommended for large sites
)

# Run it
async with AsyncWebCrawler(config=BrowserConfig()) as crawler:
    async for result in await crawler.arun("https://docs.example.com", config=config):
        print(result.url, result.markdown.fit_markdown[:200])
```

**BFS traversal pseudocode:**
```python
async def _arun_stream(start_url, crawler, config):
    visited = set()
    depths = {start_url: 0}
    current_level = [(start_url, None)]  # (url, parent_url)

    while current_level:
        next_level = []
        # Crawl all URLs in current level concurrently
        results = await crawl_batch(current_level, crawler, config)
        for result in results:
            visited.add(result.url)
            yield result
            # Discover links
            await link_discovery(result, result.url, depths[result.url],
                                 visited, next_level, depths)
        current_level = next_level

async def link_discovery(result, source_url, current_depth, visited, next_level, depths):
    next_depth = current_depth + 1
    if next_depth > self.max_depth:
        return
    links = result.links.get("internal", []) + (result.links.get("external", []) if include_external else [])
    valid_links = []
    for link in links:
        url = link["href"]
        if url in visited:
            continue
        if not await filter_chain.apply(url):
            continue
        score = url_scorer.score(url) if url_scorer else 0
        if score < score_threshold:
            continue
        valid_links.append((url, score))
    # If too many, keep highest-scored
    if len(valid_links) > remaining_capacity:
        valid_links.sort(key=lambda x: x[1], reverse=True)
        valid_links = valid_links[:remaining_capacity]
    for url, score in valid_links:
        next_level.append((url, source_url))
        depths[url] = next_depth
```

## Data contracts

**DeepCrawlStrategy constructors:**
```python
BFSDeepCrawlStrategy(
    max_depth: int = 3,
    max_pages: int = 100,
    filter_chain: FilterChain | None = None,
    url_scorer: URLScorer | None = None,
    score_threshold: float = 0.0,
    include_external: bool = False,
    should_cancel: Callable[[], bool] | None = None,
    on_state_change: Callable[[dict], None] | None = None,
    resume_state: dict | None = None,
)

DFSDeepCrawlStrategy(...)  # same params

BestFirstCrawlingStrategy(
    max_depth: int = 3,
    max_pages: int = 50,
    filter_chain: FilterChain | None = None,
    url_scorer: URLScorer = None,    # REQUIRED for meaningful prioritization
    score_threshold: float = 0.1,
    ...
)
```

**Checkpoint state shape (from export_state()):**
```python
{
    "visited": ["https://...", ...],          # already-crawled URLs
    "pending": [{"url": "...", "parent_url": "..."}, ...],
    "depths": {"https://...": 0, ...},
    "page_count": 47,
}
```

**FilterChain usage:**
```python
from crawl4ai.deep_crawling.filters import (
    FilterChain, URLPatternFilter, DomainFilter,
    ContentTypeFilter, SEOFilter, ContentRelevanceFilter
)

chain = FilterChain([
    URLPatternFilter(patterns=["*.html"], use_glob=True, reverse=False),
    DomainFilter(allowed_domains=["example.com"], blocked_domains=["ads.example.com"]),
    ContentTypeFilter(allowed_types=["text/html"]),
    SEOFilter(threshold=0.5, keywords=["python", "tutorial"]),
    # ContentRelevanceFilter(query="machine learning", threshold=0.3),  # HEAD peek
])
```

**Available scorers:**
```python
from crawl4ai.deep_crawling.scorers import (
    KeywordRelevanceScorer,     # BM25 on URL path
    DomainAuthorityScorer,      # domain-level authority signals
    FreshnessScorer,            # date patterns in URL
    PathDepthScorer,            # prefer shallow paths
    CompositeScorer,            # weighted combination of the above
)

scorer = CompositeScorer([
    (KeywordRelevanceScorer(keywords=["api", "docs"]), 0.6),
    (PathDepthScorer(max_depth=3), 0.4),
])
```

## Dependencies & assumptions

- `crawl4ai` core + `rank-bm25` (for SEO/relevance filters)
- Deep crawl module: `crawl4ai.deep_crawling` package
- Requires the browser to be running (inside `AsyncWebCrawler` context)

## To port this, you need:
- [ ] Choose a strategy (BFS for broad coverage, DFS for deep branches, BestFirst for targeted)
- [ ] Define a `FilterChain` to prevent crawling irrelevant domains/file types
- [ ] Set `max_depth` and `max_pages` guards — unconstrained crawls can run for hours
- [ ] Use `stream=True` and consume with `async for` — avoid loading all results into RAM
- [ ] Implement `on_state_change` callback that writes state to disk for crash recovery
- [ ] Store the result of `strategy.export_state()` before shutdown for resumability
- [ ] Pass `resume_state=` on restart to continue from where you left off

## Gotchas

**`include_external=False` is the safe default.** Allowing external links can cascade into crawling the entire web. Always explicitly decide on this per-task.

**`result.links` must be populated.** The crawler only discovers links if the scraping strategy extracts them (which it does by default). If you have a custom scraping strategy, ensure it populates `result.links`.

**BFS holds the entire current level in memory.** At depth 2 on a large site, "current level" could be hundreds of URLs. `max_pages` is essential, not optional.

**`ContentRelevanceFilter` and `SEOFilter` make async HTTP HEAD requests.** They peek at page headers before deciding to crawl. This adds latency per link. Use them sparingly in the chain (they should be last, after cheaper filters).

**Cancellation is external.** `should_cancel` is a callback polled between URLs. There's no `asyncio.CancelledError` propagation by default. Wire this to a `threading.Event` or similar if you need graceful shutdown.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key files: `crawl4ai/deep_crawling/bfs_strategy.py`, `crawl4ai/deep_crawling/filters.py`, `crawl4ai/deep_crawling/scorers.py`
