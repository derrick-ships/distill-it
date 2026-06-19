# Site URL Map — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Point it at a domain and it hands back, almost instantly, a list of (nearly) every URL on that site —
no scraping of page bodies, just the link inventory. Add a `search` term and the list comes back ranked
by how well each URL matches it ("give me all the /docs pages about billing").

## Why it exists

Before you crawl or extract a whole site, you often just want to *see its shape* — what pages exist,
which ones matter. Map is the cheap, fast reconnaissance step: it skips the expensive per-page scrape
and returns URLs in seconds, which is what makes "discover all URLs instantly" possible.

## How it actually works

Map pulls links from two sources and merges them: the site's **sitemap.xml** (parsed directly; in
`sitemap: "only"` mode it returns *just* sitemap links, with the limit cranked way up), and
**fire-engine's index/search** (`fireEngineMap`), which returns up to 100 known URLs for the domain and
is cached per-URL (`fireEngineMap:{url}`) so repeat maps are instant. The combined link set is
deduplicated and filtered by `includeSubdomains` / `allowExternalLinks` and a `limit` (capped at
`MAX_MAP_LIMIT`).

If you passed a `search` query, the URLs are **reranked by cosine similarity** — each link is embedded,
compared against the embedded query, and sorted by score (`performCosineSimilarityV2`). So the result
isn't just "all URLs," it's "all URLs, most relevant first." The controller also emits a soft warning
when a map returns ≤1 result (likely a misconfigured or JS-only site) unless you explicitly asked for
`limit=1`.

## The non-obvious parts

- **Two sources, merged** — sitemap (authoritative but often incomplete) + fire-engine's index (broad
  but external). Neither alone covers a site; together they approximate it.
- **Cached fire-engine results** keyed by URL are why repeat maps feel instant.
- **`search` makes it semantic, not just a filter** — links are embedded and cosine-ranked against the
  query, not substring-matched.
- **`sitemap: "only"`** is a distinct fast path: skip fire-engine entirely, return sitemap links with a
  huge limit.
- **It never scrapes page bodies** — that's the whole point and the reason it's fast and cheap.

## Related
- [[queue-backed-crawl--from-firecrawl]] (crawl uses the same sitemap discovery to seed its frontier)
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (map finds URLs; scrape reads them)
- [[llm-extract-map-reduce--from-firecrawl]] (domain-wide extract uses map to enumerate sources)
- [[generate-llms-txt--from-firecrawl]] (llms.txt generation starts by mapping the site)
