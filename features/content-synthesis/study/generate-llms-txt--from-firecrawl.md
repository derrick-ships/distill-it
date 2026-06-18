# Generate llms.txt — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Point it at a site and it produces that site's `llms.txt` — the emerging convention for a single file
that tells AI tools what a site contains: a titled list of its important pages, each with a one-line
description. It can also emit `llms-full.txt`, the same but with the full cleaned text of every page
inlined.

## Why it exists

`llms.txt` is to LLMs what `robots.txt` is to crawlers — a curated, machine-friendly map of a site's
content. Hand-writing one is tedious and goes stale. This generates it automatically from the live site,
so any site can have an LLM-ready index without manual effort. It's also a neat showcase that chains
firecrawl's own primitives (map → scrape → summarize).

## How it actually works

Three steps, all reusing other firecrawl features. First it **maps** the site to get the list of URLs
(`getMapResults`). Then it **scrapes** those pages for clean markdown. Then, per page, it runs an LLM
against a tiny schema that just asks for a one-sentence `description`. It assembles two artifacts: the
short `llms.txt` (a header/title plus one `- [page](url): description` line per page) and the long
`llms-full.txt` (every page's full markdown, with each page delimited by a marker like
`<|firecrawl-page-N-lllmstxt|>`). Helper functions cap the output — `limitLlmsTxtEntries` trims to a max
number of entries, `limitPages` trims the full-text version to a max number of pages.

It runs as an async job with Redis status, and results are cached (Supabase) so re-generating a site is
cheap. A `showFullText` flag decides whether the full version is produced.

## The non-obvious parts

- **It's a composition, not new machinery** — map + scrape + a one-line-summary LLM call, glued. The
  value is the assembly and the format, not novel tech.
- **Two outputs, one run** — the concise index (`llms.txt`) and the full corpus (`llms-full.txt`), the
  latter using page-delimiter markers so consumers can split it back into pages.
- **Per-page summarization against a one-field schema** keeps the LLM cheap and the descriptions
  uniform.
- **Capping helpers** (`limitPages`, `limitLlmsTxtEntries`) keep big sites from producing enormous files.
- **Cached in Supabase** — regeneration is mostly free, which matters because it scrapes a whole site.

## Related
- [[site-url-map--from-firecrawl]] (step 1 — enumerate the site's URLs)
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (step 2 — get each page's markdown)
- [[llm-extract-map-reduce--from-firecrawl]] (sibling: also map+scrape+LLM, but for structured data)
- See also: [[content-synthesis]] peers.
