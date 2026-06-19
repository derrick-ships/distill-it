# Dispatcher & Concurrency Control (build spec) — distilled from crawl4ai

## Summary

Two dispatcher classes (`MemoryAdaptiveDispatcher` and `SemaphoreDispatcher`) that control parallel URL crawling concurrency in `arun_many()`. The adaptive one monitors RAM in real-time and throttles when memory is tight; the semaphore one caps at a fixed count. Both support domain-level rate limiting.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai import MemoryAdaptiveDispatcher, SemaphoreDispatcher, RateLimiter

# Option A: Memory-adaptive (recommended for large batches)
dispatcher = MemoryAdaptiveDispatcher(
    max_session_permit=20,          # max concurrent crawls
    memory_threshold_percent=90.0,  # start throttling at 90% RAM
    critical_threshold_percent=95.0,
    recovery_threshold_percent=85.0,
    check_interval=1.0,             # memory polling interval (seconds)
    fairness_timeout=600,           # boost priority after 10 min wait
    memory_timeout=300,             # raise MemoryError if pressure > 5 min
    rate_limiter=RateLimiter(
        base_delay=(0.5, 1.5),      # (min, max) seconds between requests per domain
        max_delay=60.0,
        max_retries=3,
    ),
)

# Option B: Simple semaphore
dispatcher = SemaphoreDispatcher(
    semaphore_count=5,              # max concurrent crawls
    rate_limiter=RateLimiter(base_delay=(1.0, 2.0)),
)

# Batch crawl with dispatcher
urls = ["https://example.com/page1", "https://example.com/page2", ...]
config = CrawlerRunConfig(stream=True)

async with AsyncWebCrawler(config=BrowserConfig()) as crawler:
    async for result in await crawler.arun_many(urls, config=config, dispatcher=dispatcher):
        print(f"{result.url}: {result.success}")

# Per-URL configs (matched by URL pattern)
configs = [
    CrawlerRunConfig(url_matcher=lambda u: "/api/" in u, css_selector=".response"),
    CrawlerRunConfig(url_matcher=lambda u: "/blog/" in u, css_selector="article"),
    CrawlerRunConfig(),  # fallback: no pattern = matches anything
]
async for result in await crawler.arun_many(urls, config=configs, dispatcher=dispatcher):
    ...
```

**MemoryAdaptiveDispatcher task scheduling pseudocode:**
```python
class MemoryAdaptiveDispatcher:
    async def _memory_monitor(self):
        while True:
            usage = psutil.virtual_memory().percent
            if usage >= self.critical_threshold:
                self._in_critical = True
            elif usage >= self.memory_threshold:
                self._in_pressure = True
            elif usage < self.recovery_threshold:
                self._in_pressure = False
                self._in_critical = False
            await asyncio.sleep(self.check_interval)

    async def run(self, tasks):
        queue = PriorityQueue()
        for task in tasks:
            queue.put((0, time.time(), task))  # priority=0, enqueue_time, task

        semaphore = asyncio.Semaphore(self.max_session_permit)
        active = 0

        async def worker(task):
            nonlocal active
            # Rate limit: wait domain-specific delay
            await self.rate_limiter.wait_for_domain(task.url)
            async with semaphore:
                if self._in_critical:
                    await asyncio.sleep(1)  # back off
                    queue.put(...)          # requeue
                    return
                active += 1
                result = await task.execute()
                active -= 1
                return result

        # Update priorities periodically for fairness
        async def priority_updater():
            while queue:
                now = time.time()
                items = drain(queue)
                for priority, enqueue_time, task in items:
                    age = now - enqueue_time
                    new_priority = -age if age > self.fairness_timeout else priority
                    queue.put((new_priority, enqueue_time, task))
                await asyncio.sleep(30)
```

## Data contracts

**RateLimiter:**
```python
RateLimiter(
    base_delay: tuple[float, float] = (0.5, 1.0),  # (min, max) jitter range
    max_delay: float = 60.0,       # cap on exponential backoff
    max_retries: int = 3,          # retries before marking domain as failed
)
# Internally tracks per-domain last-request timestamps
```

**MemoryAdaptiveDispatcher:**
```python
MemoryAdaptiveDispatcher(
    max_session_permit: int = 20,
    memory_threshold_percent: float = 90.0,
    critical_threshold_percent: float = 95.0,
    recovery_threshold_percent: float = 85.0,
    check_interval: float = 1.0,
    fairness_timeout: int = 600,
    memory_timeout: int = 300,
    rate_limiter: RateLimiter | None = None,
    monitor: CrawlerMonitor | None = None,
)
```

**SemaphoreDispatcher:**
```python
SemaphoreDispatcher(
    semaphore_count: int = 5,
    max_session_permit: int = 10,
    rate_limiter: RateLimiter | None = None,
)
```

**arun_many() signature:**
```python
async def arun_many(
    urls: List[str],
    config: CrawlerRunConfig | List[CrawlerRunConfig],
    dispatcher: BaseDispatcher | None = None,  # defaults to MemoryAdaptiveDispatcher
    **kwargs
) -> List[CrawlResult] | AsyncGenerator[CrawlResult, None]
# Returns List when config.stream=False, AsyncGenerator when config.stream=True
```

## Dependencies & assumptions

- `psutil` — system memory monitoring (MemoryAdaptiveDispatcher only)
- `asyncio` — standard library, Python 3.10+
- Both dispatchers: part of `crawl4ai` core

## To port this, you need:
- [ ] Import `MemoryAdaptiveDispatcher` or `SemaphoreDispatcher` from `crawl4ai`
- [ ] Choose based on environment: adaptive for long/large jobs, semaphore for quick/controlled batches
- [ ] Set `max_session_permit` based on your RAM and browser page overhead (~50-150MB per page)
- [ ] Wire in `RateLimiter` if crawling public-facing sites (avoid ban)
- [ ] Always use `stream=True` for large URL lists — prevents holding all results in memory
- [ ] Pass `dispatcher=` explicitly to `arun_many()`; default is fine but explicit is clearer

## Gotchas

**Memory thresholds are system-wide, not process-level.** `psutil.virtual_memory().percent` counts all processes. If you're running other memory-heavy apps, the dispatcher will throttle earlier than expected.

**`semaphore_count=5` is conservative.** Each Playwright page uses significant memory. On a machine with 16GB RAM running nothing else, `max_session_permit=15` is typically safe. Profile your page overhead before pushing higher.

**Rate limiter delay is per-domain, not per-URL.** Two URLs on the same domain share one rate limit bucket. Two URLs on different domains can crawl in parallel at full speed.

**`arun_many` with `stream=False` returns ALL results at once.** For 1000 URLs, this means 1000 `CrawlResult` objects in memory simultaneously. Always use `stream=True` for large batches.

**Requeuing on memory critical adds retries to the task.** Each requeue increments the retry counter. If you set a low `max_retries` globally, memory-triggered requeues count against it and can cause tasks to be abandoned. Set generous retries when using the adaptive dispatcher under heavy load.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key file: `crawl4ai/async_dispatcher.py`
