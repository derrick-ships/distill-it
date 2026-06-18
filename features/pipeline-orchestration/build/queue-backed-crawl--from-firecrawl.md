# Queue-Backed Crawl (build spec) — distilled from firecrawl

## Summary

Recursive site crawl built on a **job queue + Redis crawl-state**. POST /crawl saves a `StoredCrawl`,
marks it active, and enqueues one `kickoff` job; kickoff seeds the frontier (sitemap + start page) and
enqueues a scrape job per URL; each scrape job extracts links, filters by include/exclude globs +
depth + limit, dedups via a Redis `SADD` set (`lockURL`), and enqueues children. Completion is a
three-part condition (all jobs done AND kickoff done AND sitemap jobs done). Status pages a time-ordered
sorted-set; a WebSocket streams docs; cancel flips the crawl inactive. Per-team concurrency bound.

## Core logic (inlined)

### Submit (`controllers/v2/crawl.ts`)

```ts
// 1) optional: LLM turns natural-language `prompt` into crawler options
// 2) merge options; clamp limit to remaining credits
const sc: StoredCrawl = { originUrl, crawlerOptions, scrapeOptions, team_id, createdAt: Date.now(), ... };
await saveCrawl(id, sc);          // crawl:{id} JSON, 24h TTL
await markCrawlActive(id);        // active_crawls SADD + crawls_by_team_id:{team} SADD
await _addScrapeJobToBullMQ({ ...kickoffJobData, mode: "kickoff" }, id);  // ONE kickoff job
return { id, url: `/crawl/${id}` };
```

### Redis state schema (`lib/crawl-redis.ts`)

```
crawl:{id}                       JSON StoredCrawl, TTL 24h
crawl:{id}:jobs                  SET  - all enqueued job ids
crawl:{id}:jobs_done             SET  - finished job ids
crawl:{id}:jobs_donez_ordered    ZSET - finished jobs, score = completion timestamp (for ordered paging)
crawl:{id}:jobs_qualified        SET  - jobs that passed filters (billable/qualified)
crawl:{id}:visited               SET  - dedup of normalized+permuted URLs
crawl:{id}:visited_unique        SET  - canonical URLs
crawl:{id}:kickoff:finish        KEY  - set when kickoff completes
crawl:{id}:sitemap_jobs          SET  / crawl:{id}:sitemap_jobs_done  SET
active_crawls                    SET  - global in-flight crawls
crawls_by_team_id:{team_id}      SET  - per-team crawls
```

### URL dedup = atomic SADD (`lockURL`)

```ts
async function lockURL(id, sc, url): Promise<boolean> {
  let urls = [url];
  if (sc.crawlerOptions?.deduplicateSimilarURLs)
    urls = deduplicateSimilarURLs(url);   // collapse www/http/https/index.html permutations
  const added = await redis.sadd(`crawl:${id}:visited`, ...urls);
  return added !== 0;   // false => already visited, skip
}
// canonical tracking:
async function lockURLUnique(id, url) { return (await redis.sadd(`crawl:${id}:visited_unique`, normalize(url))) !== 0; }
```

### Per-page worker step (conceptual, from queue-worker)

```ts
// for a scrape job in a crawl:
const doc = await scrapeURL(job.url, job.scrapeOptions);     // the scrape pipeline (see scrape-engine doc)
await redis.sadd(`crawl:${id}:jobs_done`, job.id);
await redis.zadd(`crawl:${id}:jobs_donez_ordered`, Date.now(), job.id);
for (const link of doc.links) {
  if (!passesIncludeExclude(link, opts)) continue;
  if (depthOf(link) > opts.maxDepth) continue;
  if (jobsCount >= opts.limit) break;
  if (!(await lockURL(id, sc, link))) continue;             // dedup
  const childId = await addScrapeJob({ url: link, crawl_id: id, ... });
  await redis.sadd(`crawl:${id}:jobs`, childId);
}
```

### Completion check + cancel

```ts
async function isCrawlFinished(id): Promise<boolean> {
  const done = await redis.scard(`crawl:${id}:jobs_done`);
  const all  = await redis.scard(`crawl:${id}:jobs`);
  const kickoffDone = await redis.exists(`crawl:${id}:kickoff:finish`);
  const smDone = await redis.scard(`crawl:${id}:sitemap_jobs_done`);
  const smAll  = await redis.scard(`crawl:${id}:sitemap_jobs`);
  return done === all && kickoffDone === 1 && smDone === smAll;
}
// cancel: mark crawl inactive (SREM active_crawls) -> workers stop enqueuing children
```

## Data contracts

- **Crawl request:** `{ url, prompt?, crawlerOptions:{ includePaths?:string[], excludePaths?:string[], maxDepth?, limit?, allowBackwardLinks?, allowExternalLinks?, deduplicateSimilarURLs?, ignoreSitemap?, sitemapOnly? }, scrapeOptions:ScrapeOptions }`.
- **StoredCrawl (Redis):** `{ originUrl, crawlerOptions, scrapeOptions, team_id, plan?, createdAt, robots? }`.
- **Status response (`/crawl/{id}`):** `{ status:"scraping"|"completed"|"cancelled"|"failed", total, completed, creditsUsed, expiresAt, next?:cursorUrl, data:Document[] }` — `data` paged from `jobs_donez_ordered`.
- **WebSocket:** emits `{type:"document", data:Document}` per completed job, then `{type:"done"}`.

## Dependencies & assumptions

- A **job queue** (firecrawl uses BullMQ and a custom `nuq`) + **Redis** for both queue and crawl state.
- The scrape pipeline ([[scrape-engine-fallback-pipeline--from-firecrawl]]) as the per-page unit.
- A sitemap parser; an include/exclude glob matcher; a credits/billing service (bill per scraped page).
- **Env:** `REDIS_URL`/`REDIS_RATE_LIMIT_URL`, queue config, per-team concurrency limits.
- Swappable: BullMQ ↔ any queue; Redis sets are the load-bearing primitive — keep them.

## To port this, you need:

- [ ] A queue with a `kickoff` job type that fans out scrape jobs.
- [ ] Redis sets for `jobs`, `jobs_done` (+ an ordered ZSET for paging), `visited` (dedup), and `kickoff:finish` / sitemap markers.
- [ ] `lockURL` = atomic `SADD` returning whether the URL was new (the dedup primitive).
- [ ] Include/exclude glob + maxDepth + limit filtering before enqueuing children.
- [ ] A three-part `isCrawlFinished` check (jobs == done AND kickoff done AND sitemap done).
- [ ] Status (paged from the ZSET), a WebSocket streamer, and a cancel that deactivates the crawl.
- [ ] Per-team concurrency caps and per-page billing.

## Gotchas

- **Done is NOT "queue empty."** Use the three-part condition; a naive empty-queue check finishes a crawl while the kickoff is still enqueuing.
- **Dedup must be atomic** — `SADD` return value, not get-then-set, or concurrent workers double-scrape.
- **Set a TTL** (24h) on all crawl keys or Redis leaks state for abandoned crawls.
- **Clamp limit to credits up front** so a runaway crawl can't overspend.
- **Similar-URL collapse** (`www`/`http`/`https`/`index.html`) prevents the same page being crawled four ways.
- **Cancel races** — flip active off and have workers check it before enqueuing children, or children keep spawning after cancel.
- **Order results via a ZSET** scored by completion time; the plain `jobs_done` set has no order for paging.

## Origin (reference only)

firecrawl/firecrawl @ `main`:
`apps/api/src/controllers/v2/crawl.ts` (submit + kickoff — inlined),
`apps/api/src/lib/crawl-redis.ts` (key schema, `lockURL`, `isCrawlFinished` — inlined),
`apps/api/src/controllers/v2/crawl-status.ts` / `crawl-status-ws.ts` / `crawl-cancel.ts`,
`apps/api/src/services/queue-worker.ts` (per-page worker + child enqueue).

**Gaps to verify (cost-capped; crawl-redis + crawl.ts confirmed by an explorer, worker not deep-read):**
exact worker link-filter code and child-enqueue ordering; sitemap-job lifecycle; the precise status
response cursor/paging; how `maxDepth` is computed per URL.
