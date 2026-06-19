# Async Web Crawler Engine (build spec) — distilled from crawl4ai

## Summary

A Playwright-based async web crawler that fetches URLs through a real browser, applies content filtering and extraction, and returns a rich structured result. Designed as a reusable async context-manager class with caching, proxy rotation, anti-bot retry logic, and pluggable processing strategies.

## Core logic (inlined)

```python
# Lifecycle — always use as context manager
async with AsyncWebCrawler(config=BrowserConfig(...)) as crawler:
    result = await crawler.arun(url, config=CrawlerRunConfig(...))

# arun() pseudocode
async def arun(url, config):
    cache_ctx = CacheContext(url, config.cache_mode)
    if cache_ctx.should_read():
        cached = await db.aget_cached_url(url)
        if cached:
            valid = await CacheValidator().validate(url, cached.etag, cached.last_modified, cached.head_fp)
            if valid == FRESH:
                return CrawlResultContainer(cached)  # "hit_validated"

    # Anti-bot retry loop
    for attempt in range(config.max_retries):
        proxy = await config.proxy_rotation_strategy.get_next_proxy()
        html, status, headers = await crawler_strategy.crawl(url, config, proxy)
        blocked, reason = is_blocked(status, html)
        if not blocked:
            break

    if blocked and config.fallback_fetch_function:
        html, status, headers = await config.fallback_fetch_function(url, config)

    # Process HTML
    crawl_result = await self.aprocess_html(url, html, config, ...)

    if cache_ctx.should_write():
        await db.acache_url(crawl_result)

    return CrawlResultContainer(crawl_result)
```

**CrawlResult shape:**
```python
@dataclass
class CrawlResult:
    url: str
    html: str                        # raw HTML
    cleaned_html: str                # HTML after scraping strategy
    markdown: MarkdownGenerationResult  # .raw_markdown, .fit_markdown, .references_markdown
    extracted_content: str           # JSON string (if ExtractionStrategy set)
    media: dict                      # {"images": [...], "videos": [...], "audio": [...]}
    tables: List[dict]               # extracted tables
    links: dict                      # {"internal": [...], "external": [...]}
    metadata: dict                   # page title, description, etc.
    screenshot: bytes | None
    pdf: bytes | None
    success: bool
    status_code: int
    error_message: str
    cache_status: str                # "hit", "miss", "hit_validated"
    redirected_url: str | None
    response_headers: dict
    session_id: str | None
    head_fingerprint: str | None
```

**MarkdownGenerationResult shape:**
```python
@dataclass
class MarkdownGenerationResult:
    raw_markdown: str           # full page markdown
    fit_markdown: str           # noise-filtered version
    fit_html: str               # pruned HTML behind fit_markdown
    references_markdown: str    # citation-style links section
    markdown_with_citations: str  # inline numbered citations
```

## Data contracts

**BrowserConfig (constructor kwargs):**
```python
BrowserConfig(
    browser_type="chromium",     # "chromium" | "firefox" | "webkit"
    headless=True,
    enable_stealth=False,        # playwright-stealth anti-bot
    use_managed_browser=False,   # advanced CDP control
    user_agent=None,             # override user agent
    user_agent_mode="random",    # or explicit string
    proxy_config=None,           # ProxyConfig(server=..., username=..., password=...)
    cookies=[],                  # [{"name":..., "value":..., "domain":...}]
    storage_state=None,          # path or dict with cookies+localStorage
    user_data_dir=None,          # path for persistent profile
    use_persistent_context=False,
    viewport_width=1080,
    viewport_height=600,
    text_mode=False,             # disable images for speed
    light_mode=False,
    memory_saving_mode=False,
    ignore_https_errors=True,
    java_script_enabled=True,
    headers={},
    extra_args=[],               # extra Playwright launch args
    verbose=False,
)
```

**CrawlerRunConfig (per-crawl kwargs):**
```python
CrawlerRunConfig(
    # Scope
    css_selector=None,           # restrict extraction to CSS selector
    word_count_threshold=10,     # min words to include a block

    # Extraction
    extraction_strategy=None,    # LLMExtractionStrategy | JsonCssExtractionStrategy | ...
    chunking_strategy=None,      # ChunkingStrategy
    markdown_generator=None,     # DefaultMarkdownGenerator(...)
    content_filter=None,         # BM25ContentFilter | PruningContentFilter | ...

    # Caching
    cache_mode=CacheMode.ENABLED, # BYPASS | ENABLED | WRITE_ONLY | READ_ONLY
    check_cache_freshness=False,
    cache_validation_timeout=2.0,

    # Anti-bot
    max_retries=3,
    proxy_config=None,
    proxy_rotation_strategy=None, # RoundRobinProxyStrategy([ProxyConfig(...)])
    proxy_session_id=None,
    fallback_fetch_function=None, # async (url, config) -> (html, status, headers)

    # Output
    screenshot=False,
    pdf=False,
    stream=False,                 # for arun_many streaming
    verbose=False,
    semaphore_count=10,
    mean_delay=0,
    max_range=0,
)
```

## Dependencies & assumptions

- `playwright` (or `patchright` for stealth) — must call `playwright install chromium` at setup
- `aiosqlite` — local cache DB at `~/.crawl4ai/cache/`
- `beautifulsoup4`, `lxml`, `cssselect` — HTML parsing
- `rank-bm25` — BM25 content filter
- `xxhash` — cache key hashing
- Python 3.10+ (uses modern async patterns)
- Optional: `pytorch`, `transformers`, `sentence-transformers` for cosine/semantic extraction

## To port this, you need:
- [ ] Install Playwright and run `playwright install chromium`
- [ ] Create a `BrowserConfig` with your target browser settings
- [ ] Create a `CrawlerRunConfig` with your extraction and caching preferences
- [ ] Wire up an `ExtractionStrategy` if you need structured JSON output
- [ ] Wire up a `ContentFilterStrategy` if you need noise filtering
- [ ] Handle `CrawlResult.success == False` cases (check `error_message`)
- [ ] Decide on `CacheMode` — `BYPASS` for always-fresh, `ENABLED` for dev speed
- [ ] For parallel crawls, use `arun_many()` with `MemoryAdaptiveDispatcher`

## Gotchas

**Context manager is required.** Calling `arun()` without `start()` (or the context manager) raises — the browser process isn't running. Always use `async with AsyncWebCrawler(...) as c:`.

**`extracted_content` is a JSON string, not a dict.** If you set an `ExtractionStrategy`, `result.extracted_content` is a JSON string — call `json.loads()` on it.

**`fit_markdown` vs `raw_markdown`:** `raw_markdown` is everything; `fit_markdown` is the noise-filtered version via your `ContentFilterStrategy`. If no filter is set, they're identical.

**Proxy exhaustion is silent.** When all proxies in rotation fail, the crawler doesn't raise — it returns a failed `CrawlResult`. Check `result.success`.

**`stream=True` changes the return type of `arun_many`.** It returns an `AsyncGenerator` instead of a `List`. Your caller must `async for result in crawler.arun_many(...):`.

**Thread safety is opt-in.** Pass `thread_safe=True` to wrap operations in an `asyncio.Lock`. Required if sharing one crawler across multiple coroutines.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key files: `crawl4ai/async_webcrawler.py`, `crawl4ai/async_configs.py`, `crawl4ai/models.py`
