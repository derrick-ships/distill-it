# Credit Billing & Concurrency — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Every API call costs credits, and every team can only run so many scrapes at once. This is the metering
layer: it checks you have enough credits before doing work, deducts them after, and holds a queue so
that a team over its concurrency limit waits its turn instead of hammering the workers.

## Why it exists

A paid web-scraping API lives or dies on two controls: **don't do work people haven't paid for**, and
**don't let one customer's huge crawl starve everyone else**. Credits handle the first; concurrency
limiting handles the second. Together they're what make the service economically and operationally
viable at scale.

## How it actually works

**Credits.** Before billable work, `checkTeamCredits` looks at the team's "chunk" — a cached snapshot of
remaining credits, credits already used, and any price/plan adjustments — and decides if the request
fits. After the work, `billTeam` decrements the balance (ultimately a Supabase RPC) and records usage.
Billing is fire-and-forget on the hot path (errors are logged, not blocking) so metering never adds
latency to the actual scrape. Notably, in composite features each piece bills itself — e.g. in search,
the search bills its credits and each result-scrape job bills its own.

**Concurrency.** This is a Redis sorted-set scheme, not a simple counter. Each team has an *active jobs*
set and a *queue*. When a team is at its limit, a new job is pushed onto the concurrency queue
(`pushConcurrencyLimitedJob`) with a timeout score. As active jobs finish (`concurrentJobDone`), the
system cleans out expired entries and pulls the next queued job (`getNextConcurrentJob` via a
`zpopmin`-style pop) — but only if the team is under its `maxConcurrency` (taken from the plan, or a
per-crawl override). Crawls get their own active-job set so a big crawl's parallelism is tracked
separately. Expired/orphaned entries are swept so a crashed worker doesn't permanently consume a slot.

## The non-obvious parts

- **Concurrency is a queue, not a gate.** Over-limit jobs aren't rejected — they're parked in a Redis
  sorted set and released as slots free up. Backpressure, not failure.
- **Sorted sets with timeout scores** are the trick: the score doubles as an expiry, so orphaned jobs
  from dead workers get swept instead of leaking a slot forever.
- **Billing is async/non-blocking on the hot path** — a scrape never waits on the billing write; failures
  are logged. Throughput over strict accounting.
- **Each sub-job self-bills.** Composite endpoints don't bill once for everything; the search bills
  search credits, each scrape bills itself — clean attribution, and it survives partial failures.
- **`maxConcurrency` is layered** — plan default, with a per-crawl override — so one feature can be given
  more parallelism than the team's baseline.
- **Crawls get a separate active set** so site crawls are throttled independently of one-off scrapes.

## Related
- [[keyless-and-x402-access--from-firecrawl]] (the access tiers that feed into this metering: keyless reserve/reconcile, x402 pay-per-call)
- [[queue-backed-crawl--from-firecrawl]] (crawl jobs flow through the per-team + per-crawl concurrency sets)
- [[web-search-with-scrape--from-firecrawl]] (search self-bills; scrapes self-bill — the split-billing pattern)
- [[secure-payment-webhook--from-pagokit]] (a different payments concern: webhook security vs metering)
