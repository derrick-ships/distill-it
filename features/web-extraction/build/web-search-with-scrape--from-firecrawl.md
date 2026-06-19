# Web Search (+ optional scrape) (build spec) — distilled from firecrawl

## Summary

`/search` = query a web-search provider (fallback chain) → normalized `{web,news,images}` results →
optionally scrape every result concurrently through the existing scrape pipeline (3-day cache) →
merge scraped content back onto results by URL. Search bills search credits; scrape jobs self-bill;
a keyless reserve/reconcile path meters anonymous callers.

## Core logic (inlined)

### Provider fallback (`search/v2/index.ts`)

```ts
export async function search({ query, num_results=5, tbs, filter, lang="en", country="us", location, type, enterprise, ... }) {
  try {
    if (config.FIRE_ENGINE_BETA_URL)                // 1) hosted fire-engine search
      return await fire_engine_search_v2(query, { numResults:num_results, tbs, filter, lang, country, location, type, enterprise });
    if (config.SEARXNG_ENDPOINT) {                  // 2) SearXNG (self-host default)
      const r = await searxng_search(query, { num_results, tbs, filter, lang, country, location });
      if (r.web && r.web.length > 0) return r;      // only accept if it returned web results
    }
    const ddg = await ddgSearch(query, num_results, { tbs, lang, country, proxy, timeout });  // 3) DuckDuckGo
    if (ddg.web && ddg.web.length > 0) return ddg;
    return {};                                      // soft-empty
  } catch (e) { logger.error(...); return {}; }     // never throws
}
// Normalized SearchV2Response: { web?: Result[], news?: Result[], images?: Result[] }
```

### Controller flow (`controllers/v2/search.ts`)

```ts
req.body = searchRequestSchema.parse(req.body);
// keyless: project credits up front, reserve, 429 if insufficient
const projected = projectSearchTotalCredits({ limit, enterprise, scrapeOptions }, flags, zdr);
if (projected > 0) { const r = await reserveKeylessCredits(teamId, projected); if (!r.ok) return 429; }

const result = await executeSearch({ query, limit, tbs, filter, lang, country, location,
  sources, categories, includeDomains, excludeDomains, scrapeOptions, highlights, timeout }, ctx, logger);

// bill: search credits here; scrape jobs bill themselves
if (shouldBill) billTeam(teamId, subId, result.searchCredits, apiKeyId, billing);
if (reservedKeyless) adjustKeylessCredits(teamId, result.totalCredits - reserved);

return res.json({ success:true, data: result.response, creditsUsed: result.totalCredits, id: jobId });
```

### Scrape-of-results (`search/scrape.ts`)

```ts
// 1) which results to scrape (drop blocked URLs), tagged by type
export function getItemsToScrape(searchResponse, flags, ctx): ScrapeItem[] {
  const items = [];
  for (const bucket of ["web","news","images"])
    for (const item of (searchResponse[bucket] ?? []))
      if (item.url && !isUrlBlocked(item.url, flags, ctx))
        items.push({ item, type: bucket, scrapeInput:{ url:item.url, title:item.title??"", description:item.description??item.snippet??"" }});
  return items;
}

// 2) scrape ALL concurrently, reusing the scrape worker directly (skipNuq, 3-day cache)
export async function scrapeSearchResults(items, options, logger, flags) {
  if (!items.length) return [];
  const jobPriority = await getJobPriority({ team_id: options.teamId, basePriority: 10 });
  return Promise.all(items.map(it => scrapeSearchResultDirect(it, options, logger, flags, jobPriority)));
}
async function scrapeSearchResultDirect(searchResult, options, logger, flags, jobPriority) {
  const job = { id: uuidv7(), status:"active", priority:jobPriority, data:{
    url: searchResult.url, mode:"single_urls", team_id: options.teamId,
    scrapeOptions: { ...options.scrapeOptions, maxAge: 3*24*60*60*1000 },   // 3-day cache
    internalOptions: { teamId, bypassBilling: options.bypassBilling ?? true, ... },
    skipNuq: true, is_scrape:false, ... }};
  try { const doc = await processJobInternal(job);   // SAME worker as a normal scrape
        return { document: { title, description, url, ...doc, metadata: doc?.metadata ?? {statusCode:200} }, costTracking };
  } catch (error) {                                   // soft failure -> stub doc with 500
        return { document: { title, description, url, metadata:{ statusCode:500, error:error.message } }, costTracking }; }
}

// 3) merge scraped docs back onto results by URL
export function mergeScrapedContent(searchResponse, items, docs) {
  const byUrl = new Map(items.map((it,i) => [it.scrapeInput.url, docs[i].document]));
  for (const bucket of ["web","news","images"])
    if (searchResponse[bucket]?.length)
      searchResponse[bucket] = searchResponse[bucket].map(it => ({ ...it, ...(it.url ? byUrl.get(it.url) : {}) }));
}
```

## Data contracts

- **Search request:** `{ query, limit=5, tbs?, filter?, lang?, country?, location?, sources?:[{type:"web"|"news"|"images"}], categories?, includeDomains?, excludeDomains?, scrapeOptions?:ScrapeOptions, highlights?, timeout? }`.
- **Normalized result (`SearchV2Response`):** `{ web?:Result[], news?:Result[], images?:Result[] }`, `Result = { url, title, description|snippet, ...(scraped Document fields after merge: markdown, html, metadata) }`.
- **Response:** `{ success, data: SearchV2Response, creditsUsed, id }`.
- **executeSearch returns:** `{ response, searchCredits, scrapeCredits, totalCredits, totalResultsCount, shouldScrape }`.

## Dependencies & assumptions

- A search provider: **fire-engine** (hosted) OR **SearXNG** (self-host) OR **DuckDuckGo** (fallback).
- The scrape worker/pipeline ([[scrape-engine-fallback-pipeline--from-firecrawl]]) invoked directly (`processJobInternal`, `skipNuq:true`).
- A billing/credits service + url blocklist (`isUrlBlocked`). **Env:** `FIRE_ENGINE_BETA_URL`, `SEARXNG_ENDPOINT`, proxy creds.
- Swappable: any search backend behind the same `{web,news,images}` shape; the 3-day `maxAge` is tunable.

## To port this, you need:

- [ ] A search provider adapter layer with a fallback chain, each normalized to `{web,news,images}`.
- [ ] An optional, **concurrent** scrape of result URLs reusing your scrape pipeline (with a cache `maxAge`).
- [ ] A url blocklist filter before scraping.
- [ ] Merge-scraped-content-by-URL back onto results.
- [ ] Split billing (search credits + per-page scrape credits) and (optional) keyless reserve/reconcile.

## Gotchas

- **Soft-fail everything** — search errors → empty object; a result that won't scrape → stub doc with 500, not a thrown request.
- **Gate SearXNG on actual web results** before accepting it, or you skip the DuckDuckGo fallback on an empty SearXNG reply.
- **Reuse the scrape pipeline, don't fork it** — invoke the same worker with `skipNuq` so search content == scrape content.
- **Concurrent fan-out costs** — projecting/reserving credits up front (keyless) prevents abuse; `Promise.all` on 50 results is 50 scrapes.
- **Cache the result scrapes** (3-day `maxAge`) or search latency balloons on popular queries.
- **Merge by URL** — if a provider returns the URL differently than the scrape normalizes it, the merge silently misses; normalize both sides.

## Origin (reference only)

firecrawl/firecrawl @ `main`:
`apps/api/src/controllers/v2/search.ts` (controller + billing — inlined),
`apps/api/src/search/v2/index.ts` (provider fallback — inlined),
`apps/api/src/search/scrape.ts` (getItemsToScrape / scrapeSearchResults / mergeScrapedContent — inlined),
`apps/api/src/search/execute.ts` (`executeSearch` orchestration — referenced, not deep-read),
`apps/api/src/search/v2/{fireEngine-v2,searxng,ddgsearch}.ts` (provider adapters).

**Gaps to verify (cost-capped; execute.ts not deep-read):** exact `executeSearch` logic (how it decides
`shouldScrape`, computes `searchCredits`/`scrapeCredits`); the `Result` field names per provider; how
`sources`/`categories`/`highlights` map to provider params; SearXNG/fire-engine request shapes.
