# Credit Billing & Concurrency (build spec) — distilled from firecrawl

## Summary

Two metering controls. **Credits:** `checkTeamCredits` (pre-flight, from a cached "chunk" of
remaining/used/price-adjusted credits) gates work; `billTeam` (post, Supabase RPC) decrements,
non-blocking on the hot path; sub-jobs self-bill. **Concurrency:** Redis sorted-sets — a per-team active
set + a queue with timeout-scored entries; over-limit jobs are *parked* and released by
`getNextConcurrentJob` as actives finish, bounded by plan/crawl `maxConcurrency`; expired entries swept.

## Core logic (inlined)

### Billing (`services/billing/credit_billing.ts`)

```ts
export async function billTeam(team_id, subscription_id, credits, api_key_id, billing, logger) {
  return withAuth(async (team_id, subscription_id, credits, ...) => {
    // Supabase RPC that decrements remaining credits and records a usage row { source:"billTeam", value:credits }
    await supabase_rpc("bill_team", { team_id, sub_id: subscription_id, credits, ... });
  })(team_id, subscription_id, credits, api_key_id, billing, logger);
  // CALLED fire-and-forget on hot paths: billTeam(...).catch(e => logger.error(...))
}

export async function checkTeamCredits(chunk, team_id, credits) {
  // chunk = cached snapshot: { remaining_credits, price_credits, adjusted_credits_used, total_credits_sum, ... }
  const totalRemaining = chunk.is_metered ? chunk.remaining_credits + chunk.price_credits : chunk.remaining_credits;
  const willBeUsed = chunk.adjusted_credits_used + credits;
  const limit = (chunk.total_credits_sum ?? 100_000_000) + (chunk.is_metered ? chunk.price_credits : 0);
  return { success: willBeUsed <= limit, remainingCredits: totalRemaining, ... };
}
```

### Concurrency (`lib/concurrency-limit.ts`) — Redis sorted sets

```ts
// keys: concurrency-limiter:{team}        (ZSET active jobs, score = expiry timestamp)
//       concurrency-limit-queue:{team}    (ZSET queued jobs,  score = enqueue/timeout)
//       crawl-concurrency-limiter:{crawl} (ZSET active jobs for a crawl)

export async function pushConcurrencyLimitedJob(team_id, job, timeout, now=Date.now()) {
  await redis.zadd(`concurrency-limit-queue:${team_id}`, now /*score*/, JSON.stringify({ job, timeout }));
}
export async function cleanOldConcurrencyLimitEntries(team_id, now=Date.now()) {
  await redis.zremrangebyscore(`concurrency-limiter:${team_id}`, -inf, now);   // sweep expired/orphaned actives
}
export async function getConcurrencyLimitActiveJobsCount(team_id, now=Date.now()) {
  return redis.zcount(`concurrency-limiter:${team_id}`, now, "+inf");           // only non-expired count
}
export async function getNextConcurrentJob(teamId) {
  const maxConcurrency = sc?.maxConcurrency ?? planDefault;          // per-crawl override else plan default
  const active = await getConcurrencyLimitActiveJobsCount(teamId);
  if (active >= maxConcurrency) return null;
  const next = await redis.zpopmin(`concurrency-limit-queue:${teamId}`);        // pull oldest queued
  // (orphan guard) if the job's own key TTL expired, skip it (already removed)
  return next;
}
export async function concurrentJobDone(job) {
  await redis.zrem(`concurrency-limiter:${job.data.team_id}`, job.id);          // free the slot
  await cleanOldConcurrencyLimitEntries(job.data.team_id);
  const next = await getNextConcurrentJob(job.data.team_id);                    // promote next queued -> active
  if (next) enqueueToWorker(next);
}
```

## Data contracts

- **Credit chunk (cached):** `{ remaining_credits, price_credits, adjusted_credits_used, total_credits_sum, is_metered, sub_id, ... }`.
- **billTeam args:** `(team_id, subscription_id, credits, api_key_id, BillingMetadata{endpoint, jobId})`.
- **Concurrency active entry (ZSET):** member=`jobId`, score=expiry ts. **Queue entry:** member=`{job, timeout}` JSON, score=enqueue ts.
- **maxConcurrency:** number from plan, overridable per-crawl (`StoredCrawl.maxConcurrency`).

## Dependencies & assumptions

- **Redis** (sorted sets) for concurrency; **Supabase** (RPC) for credit ledger — swap the ledger for any transactional store.
- A cached credit "chunk" per team (ACUC) refreshed out-of-band.
- A worker/queue that calls `getNextConcurrentJob`/`concurrentJobDone` around each job.

## To port this, you need:

- [ ] A pre-flight `checkTeamCredits` against a cached balance snapshot, and a post `billTeam` decrement (non-blocking on the hot path).
- [ ] Self-billing per sub-job in composite endpoints.
- [ ] Per-team active ZSET (expiry-scored) + queue ZSET; `pushConcurrencyLimitedJob` when at limit.
- [ ] `concurrentJobDone` → free slot, sweep expired, promote next; `getNextConcurrentJob` bounded by `maxConcurrency`.
- [ ] A per-crawl active set + per-crawl concurrency override.

## Gotchas

- **Score actives by expiry** so a crashed worker's slot is swept (`zremrangebyscore`), not leaked forever.
- **Queue, don't reject** over-limit jobs — backpressure keeps the API usable under load.
- **Bill off the hot path** (`.catch(log)`) — never make a scrape wait on the billing write.
- **Self-bill sub-jobs** so partial failures still attribute cost correctly and crawls bill per page.
- **Layer maxConcurrency** (plan vs per-crawl) or you can't give a big crawl more lanes without raising the whole team.
- **Guard orphaned queue entries** (job-key TTL expired) when popping, or you promote ghosts.

## Origin (reference only)

firecrawl/firecrawl @ `main`: `apps/api/src/services/billing/credit_billing.ts` (inlined),
`apps/api/src/lib/concurrency-limit.ts` (inlined), `apps/api/src/services/billing/{batch_billing,types}.ts`,
`apps/api/src/controllers/v2/credit-usage.ts`.

**Gaps to verify (cost-capped):** exact Supabase RPC name/columns; the ACUC chunk refresh; plan→maxConcurrency
mapping; `batch_billing` semantics; exact key names/TTLs.
