# Queue-Backed Crawl — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Hand it one starting URL and it scrapes a whole site — discovering pages as it goes, scraping each one,
following their links, respecting your include/exclude path rules and page limit, all in the background.
You get a crawl id back instantly and then poll for status (or stream results over a WebSocket) as
pages roll in. You can cancel mid-flight.

## Why it exists

Scraping one page is easy; scraping a site reliably at scale is not — you need concurrency control, you
must not re-visit the same URL twice, you must know when you're actually *done*, and you must survive
worker crashes and partial failures. Crawl is the orchestration layer that turns the single-page scraper
into a site-wide operation without melting under thousands of jobs.

## How it actually works

A crawl is a pile of **Redis state** plus a **job queue**. When you POST a crawl, the server (optionally
asking an LLM to turn a natural-language `prompt` into crawl options), clamps your `limit` to your
remaining credits, saves a `StoredCrawl` record in Redis, marks the crawl active, and enqueues a single
**kickoff** job. The kickoff job seeds the frontier — typically by reading the site's `sitemap.xml`
and/or scraping the start page — and enqueues a scrape job per discovered URL.

Each scrape job runs the page through the normal scrape pipeline, then extracts the page's links and,
for any link that passes the include/exclude globs and depth/limit checks and *hasn't been seen before*,
enqueues a child scrape job. "Hasn't been seen" is enforced with a Redis set: `lockURL` does a `SADD`
and treats a return of 0 (already present) as "skip." There's an optional similar-URL collapse that
treats `http`/`https`/`www`/`index.html` permutations of a URL as the same page.

The crawl's bookkeeping lives in a family of Redis keys per crawl id: the `StoredCrawl` JSON
(`crawl:{id}`, 24h TTL), the set of all job ids (`:jobs`), the set of finished jobs (`:jobs_done`) plus
a time-ordered sorted-set for paging results in order, the visited-URL dedup sets (`:visited`,
`:visited_unique`), sitemap-job sets, and a `:kickoff:finish` marker. **The crawl is "done"** when every
job is finished *and* the kickoff finished *and* every sitemap job finished — i.e. `jobs_done` size ==
`jobs` size, the kickoff-finish key exists, and sitemap jobs are all done. There are also global indexes
(`active_crawls`, `crawls_by_team_id:{team}`) so the system can see all in-flight crawls.

Status (`/crawl/{id}`) reads the done-jobs sorted set to page through completed documents; the WebSocket
variant streams each document as its job completes; cancel flips the crawl inactive so workers stop
enqueuing children. Concurrency is bounded per team so one big crawl can't starve everyone.

## The non-obvious parts

- **Redis is the source of truth, not a DB.** All crawl state — frontier, visited, done, ordering — is
  Redis sets/sorted-sets with a 24h TTL. Crash-tolerant and fast, but ephemeral.
- **Dedup is a `SADD` return value.** No separate "have I seen this?" lookup; the atomic set-add *is* the
  check (`lockURL` returns false when SADD returns 0). Cheap and race-safe.
- **"Done" is a three-way condition**, not a counter hitting zero — jobs done AND kickoff done AND
  sitemap done. Forgetting any one gives you crawls that finish early or never finish.
- **Kickoff is its own job type.** The first enqueue is a single `mode:"kickoff"` job; it fans out the
  rest. Keeps the POST handler instant.
- **Natural-language crawl prompts** are turned into structured options by an LLM at submit time.
- **A separate ordered sorted-set** (`jobs_donez_ordered`, score=timestamp) exists purely so status can
  return results in completion order with paging.

## Related
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (each crawled page goes through the scraper)
- [[web-search-with-scrape--from-firecrawl]] (a sibling fan-out-then-scrape pattern, no recursion)
- See also: [[multi-source-research-engine--from-last30days-skill]] and other queue/fan-out orchestrations.
