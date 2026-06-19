# Dispatcher & Concurrency Control — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

When you call `arun_many()` to crawl multiple URLs simultaneously, crawl4ai uses a **dispatcher** to manage the concurrency — how many pages get fetched at once, how fast, and in what order. The `MemoryAdaptiveDispatcher` (the default) continuously monitors system RAM and automatically throttles the crawl if memory pressure builds up. The simpler `SemaphoreDispatcher` caps concurrency to a fixed number. Both support optional rate limiting per domain.

## Why it exists

Naive parallel crawling at full speed causes two problems: it crashes your machine when RAM fills up from hundreds of open browser pages, and it gets you IP-banned from servers you're hammering with rapid requests. The dispatcher layer solves both — it's the concurrency governor that keeps mass crawling viable.

## How it actually works

**MemoryAdaptiveDispatcher** is the intelligent default. It runs a background monitoring task that polls system memory every second. Three thresholds define behavior: normal operation, "pressure" mode (default 90% memory use), and "critical" mode (default 95%). 

In normal mode, it greedily fills available concurrency slots from a priority queue of pending tasks — up to `max_session_permit` concurrent crawls (default 20). When memory exceeds the pressure threshold, intake slows down: the dispatcher stops launching new tasks until memory recovers below the `recovery_threshold` (default 85%). If memory stays in pressure mode longer than a configurable timeout, it raises a `MemoryError`.

The priority queue uses scoring to prevent starvation: tasks that have been waiting longer than `fairness_timeout` (default 10 minutes) get boosted priority, so no URL gets stuck at the back of the queue indefinitely.

**SemaphoreDispatcher** is simpler: a standard `asyncio.Semaphore` with a configurable count (default 5). All URLs are launched as tasks immediately and must acquire the semaphore before executing. No memory monitoring, no priority queue — just a fixed ceiling. Better for situations where you know the memory will be fine and just want to limit courtesy to the target server.

**Rate Limiting** integrates into both dispatchers via a `RateLimiter` object. The rate limiter enforces domain-level delays between requests, with configurable base delay (mean ± jitter), maximum delay (for exponential backoff), and max retries before giving up. Rate limiting is applied per domain, not globally — so crawling two different domains in parallel is unaffected by the per-domain rate limit.

**URL-to-config matching:** When `arun_many()` receives a list of `CrawlerRunConfig` objects (one per URL), the dispatcher calls `select_config(url, configs)` to match each URL to the right config. Configs can have a `url_matcher` function or pattern that selects which URLs they apply to. The first matching config wins.

## The non-obvious parts

**The dispatcher doesn't control the browser pool directly.** It controls how many crawl tasks run concurrently, but each task uses the shared browser process. The real concurrency bottleneck is Playwright's page management within one browser context.

**Memory pressure causes task requeuing, not cancellation.** When memory hits critical, pending tasks aren't dropped — they're pushed back into the queue with an incremented retry count. The crawler keeps trying as memory frees up. This makes the system resilient to temporary spikes.

**`fairness_timeout` is the anti-starvation mechanism.** Without it, a continuously-replenishing queue (from deep crawls) would always have fresh high-priority tasks, and low-priority tasks (e.g., less-relevant URLs) might never run. The fairness boost ensures old-waiting tasks eventually get their turn.

**The rate limiter uses domain-level jitter.** `base_delay=(0.5, 1.5)` means each request to a domain waits a random time between 0.5 and 1.5 seconds. This mimics human browsing patterns and avoids the regular timing signature of robotic crawlers.

## Related
- [[async-web-crawler--from-crawl4ai]] (the engine each dispatched task calls)
- [[deep-crawl-traversal--from-crawl4ai]] (BFS level-parallel crawling uses the dispatcher under the hood)
