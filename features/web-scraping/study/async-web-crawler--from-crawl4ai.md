# Async Web Crawler Engine — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

`AsyncWebCrawler` is the central engine of crawl4ai — it fetches any URL using a real Chromium/Firefox/WebKit browser, applies configurable processing to the response (content filtering, markdown generation, structured extraction), and returns a rich `CrawlResult` object with cleaned HTML, markdown, extracted JSON, screenshots, links, and media. It is async-first and supports both single-URL and batch crawling via `arun_many()`.

## Why it exists

Web pages written for humans are hostile to machines: JavaScript renders content dynamically, bot-detection blocks naive HTTP clients, lazy-loading hides content, and raw HTML is full of noise. crawl4ai exists to bridge that gap — producing LLM-ready, clean output from any URL, at any scale, without the caller having to manage browsers directly.

## How it actually works

**Initialization:** The crawler is built from two config objects — `BrowserConfig` (browser type, headless/visible, stealth mode, proxy, user agent) and `CrawlerRunConfig` (per-crawl options like CSS selectors, extraction strategy, caching mode, screenshot). You either use it as an async context manager (preferred — auto-starts and closes the browser) or call `start()`/`close()` manually.

**arun() pipeline (one URL):**

1. *Cache check:* A `CacheContext` evaluates whether the URL already has a valid cached result. If `CacheMode.ENABLED` (the default), it hits a local aiosqlite database. Freshness is validated via ETag, Last-Modified headers, and a "head fingerprint" — an HTTP HEAD request that detects if the server's version has changed.

2. *Live fetch with anti-bot retry:* If no valid cache hit, the crawler tries to load the page through Playwright. It runs a retry loop: for each attempt, it tries each proxy in the rotation (if configured). After loading, it checks if the page was blocked by anti-bot systems (via HTTP status codes and HTML pattern signatures). If blocked and retries remain, it tries the next proxy.

3. *HTML processing:* The raw HTML is passed through a scraping strategy (`LXMLWebScrapingStrategy` by default) which: applies the `css_selector` to limit scope, computes word count, runs the `ContentFilterStrategy` (BM25, Pruning, or LLM-based), generates clean and "fit" Markdown via `DefaultMarkdownGenerator`, and runs the `ExtractionStrategy` if one is configured.

4. *Cache write:* The result is stored to the local cache if `cache_mode.should_write()` and the crawl succeeded.

5. *Return:* A `CrawlResultContainer` wrapping the `CrawlResult` is returned.

**arun_many() for batches:** Takes a list of URLs (and optionally a list of `CrawlerRunConfig` objects — one per URL, matched by URL pattern). Dispatches all URLs through a `MemoryAdaptiveDispatcher` (or a custom one), which controls concurrency based on system memory pressure. Results can be streamed (yielded as they complete) or collected.

## The non-obvious parts

**Cache validation is smarter than most people expect.** The cache doesn't just store a TTL — it validates freshness via an actual HTTP HEAD request and ETag comparison. "Hit validated" means the server confirmed the page hasn't changed, avoiding a re-render while ensuring data freshness.

**Fallback fetch function is the escape hatch.** If all proxies are exhausted and the page is still blocked, `config.fallback_fetch_function` is called — a fully custom async function the caller provides. This is the hook for things like residential proxy services or manual CAPTCHA solving.

**The browser is a singleton, not a pool.** Despite marketing language about "browser pools," the default strategy uses one Playwright browser process and manages pages within it. True parallelism comes from running multiple `AsyncWebCrawler` instances behind the `MemoryAdaptiveDispatcher`.

**"raw:" URLs bypass browser rendering.** Pass `raw:` as a URL prefix with HTML content and the crawler skips fetching entirely — useful for testing extraction pipelines on static HTML.

## Related
- [[deep-crawl-traversal--from-crawl4ai]] (multi-page version wrapping this engine)
- [[dispatcher-concurrency-control--from-crawl4ai]] (how arun_many() manages parallel crawls)
- [[browser-stealth-anti-detection--from-crawl4ai]] (stealth and proxy options used by this engine)
- [[content-filtering-strategies--from-crawl4ai]] (applied inside aprocess_html)
