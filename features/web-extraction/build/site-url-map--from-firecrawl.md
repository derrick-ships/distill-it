# Site URL Map (build spec) — distilled from firecrawl

## Summary

Fast URL discovery for a domain (no page-body scraping): merge **sitemap.xml** links + **fire-engine
index** results (≤100, cached per-URL), dedup, filter by subdomain/external/limit, and — if a `search`
query is given — **rerank by embedding cosine similarity**. Returns an ordered URL list in seconds.

## Core logic (inlined)

### `getMapResults` (`lib/map-utils.ts`)

```ts
const MAX_FIRE_ENGINE_RESULTS = 100;
export async function getMapResults({ url, search, limit = MAX_MAP_LIMIT, includeSubdomains,
  crawlerOptions, allowExternalLinks, maxFireEngineResults = MAX_FIRE_ENGINE_RESULTS, ... }) {
  let links: string[] = [];

  // 1) sitemap
  if (crawlerOptions.sitemap === "only") {
    const sitemap = await crawler.tryGetSitemap(/* limit */ 10000000);   // sitemap-only fast path
    return sitemapLinks;
  }
  const sitemapLinks = await crawler.tryGetSitemap(limit);
  links.push(...sitemapLinks);

  // 2) fire-engine index (cached per URL)
  const cacheKey = `fireEngineMap:${mapUrl}`;
  const feResults = await fireEngineMap(mapUrl, {
    numResults: Math.min(maxFireEngineResults, limit),
  });   // cached read/write around this
  links.push(...feResults);

  // 3) dedup + filter (subdomains / external / limit)
  links = dedup(links).filter(l => allowed(l, { includeSubdomains, allowExternalLinks, hostname }));

  // 4) optional semantic rerank by `search`
  if (search) links = performCosineSimilarityV2(links, search);   // embed links + query, sort by score

  return links.slice(0, limit);
}
```

### Cosine rerank (`lib/map-cosine.ts`)

```ts
export function performCosineSimilarityV2(links: string[], searchQuery: string) {
  const cosine = (a:number[], b:number[]) => dot(a,b)/(norm(a)*norm(b));
  const linkVecs = links.map(embed);
  const q = embed(searchQuery);
  return links
    .map((link, i) => ({ link, score: cosine(linkVecs[i], q) }))
    .sort((a, b) => b.score - a.score)
    .map(x => x.link);
}
```

### Controller (`controllers/v2/map.ts`)

```ts
const links = await getMapResults({ url, search, limit, includeSubdomains,
  crawlerOptions:{ sitemap, ... }, allowExternalLinks });
// soft warning if links.length <= 1 && limit !== 1 && url is not the base domain
return res.json({ success:true, links, /* or {url,title,description}[] */ });
```

## Data contracts

- **Request:** `{ url, search?, limit?(<=MAX_MAP_LIMIT), includeSubdomains?:bool, allowExternalLinks?:bool, sitemap?:"include"|"only"|"skip", timeout? }`.
- **Response:** `{ success, links: string[] }` (v2 can return `{url,title,description}[]` when enriched).

## Dependencies & assumptions

- A **sitemap parser** (`crawler.tryGetSitemap`), **fire-engine** index/search (`fireEngineMap`) — swap for any URL-index source.
- An **embeddings** provider for cosine rerank (only when `search` is set).
- A cache (Redis) for `fireEngineMap:{url}`. **Env:** `FIRE_ENGINE_BETA_URL`, embeddings key.

## To port this, you need:

- [ ] A sitemap fetcher + an index/search source for the domain; merge + dedup their links.
- [ ] Subdomain/external/limit filtering.
- [ ] (optional) embedding-based cosine rerank when a `search` query is supplied.
- [ ] A per-domain cache so repeat maps are instant.

## Gotchas

- **Don't scrape bodies** — map's value is speed; the moment you fetch pages it becomes a crawl.
- **Merge two sources** — sitemap alone misses unlisted pages; index alone drifts; together they approximate coverage.
- **Cache the index lookup** keyed by URL or every map re-hits the index service.
- **`sitemap:"only"`** must skip the index path and lift the limit, or you cap a sitemap that has 10k URLs.
- **Cosine rerank needs embeddings** — degrade to unranked links if the embeddings call fails rather than erroring.

## Origin (reference only)

firecrawl/firecrawl @ `main`: `apps/api/src/controllers/v2/map.ts`,
`apps/api/src/lib/map-utils.ts` (`getMapResults` — inlined), `apps/api/src/lib/map-cosine.ts` (rerank — inlined),
`apps/api/src/search/fireEngine.ts` (`fireEngineMap`), `apps/api/src/scraper/crawler/sitemap.ts`.

**Gaps to verify (cost-capped):** exact `MAX_MAP_LIMIT`, `tryGetSitemap` internals, fireEngineMap request/cache TTL, the index-at-split-level query variants.
