# LLM Extract (map-reduce) — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

You give it a prompt (and optionally a JSON schema) and one or more URLs — even a whole domain — and it
returns one clean structured object that answers your prompt, pulled from across all those pages. "Get
the pricing tiers and features from stripe.com" becomes a tidy JSON object, whether the answer lives on
one page or is scattered across twenty.

## Why it exists

Scraping gives you text; you usually want *data*. Doing that well across many pages is the hard part:
pages are too big for one LLM call, the answer might be one fact (single-answer) or a list of many
entities (every product, every team member), and you have to merge partial answers without losing or
duplicating anything. Extract is the map-reduce engine that handles all of that.

## How it actually works

It runs as an **async job** (you get an extract id, then poll status), updating a Redis record through
named steps so the UI can show progress.

First it **understands the task**: an LLM optionally rephrases your prompt, then `analyzeSchemaAndPrompt`
decides the crucial thing — is this a **single-answer** extraction (one object) or a **multi-entity** one
(a list of many similar objects)? — and identifies which schema keys are the "multi-entity" arrays.

Then it **gathers sources**: `processUrl` expands your input into a concrete set of pages to scrape
(following a map/discovery step when you point it at a domain rather than exact URLs), and scrapes each.

Then the split:
- **Single-answer path**: feed the relevant document content to one completion against your schema and
  get the object back.
- **Multi-entity path**: `spreadSchemas` splits your schema into the single-answer part and the
  per-entity part. The scraped documents are processed **in chunks of 50**, each chunk extracted
  concurrently (`batchExtract`) with its own session id, and the per-entity results are merged. Empty
  fields are reconciled with `mergeNullValObjs` (so a null from one page doesn't clobber a real value
  from another), arrays are deduplicated, and the single-answer fields are filled by a separate
  completion. A reranker scores document/section relevance so the LLM spends its budget on the pages
  that actually matter.

Finally the pieces are **merged into one object** matching your schema and returned. Every stage writes
a status update to Redis so `/extract/{id}/status` reflects where it is.

## The non-obvious parts

- **Single-answer vs multi-entity is the pivotal decision.** The whole pipeline forks on it, decided up
  front by an LLM analyzing your schema + prompt. Get it wrong and you either collapse a list into one
  row or explode one answer into a fake list.
- **Schemas are split, not used whole.** `spreadSchemas` separates "one value for the whole extraction"
  fields from "one per entity" fields so they can be extracted by different strategies and merged.
- **Null-aware merging.** `mergeNullValObjs` is the unsung hero: when the same entity appears on two
  pages, you take the non-null fields from each rather than letting a later empty overwrite an earlier
  value.
- **Chunking at 50 docs** with concurrent batch extraction is how it scales to large domains without
  blowing the context window — classic map (per-chunk extract) then reduce (merge).
- **A reranker** (relevance scoring) keeps the LLM focused on pages likely to contain the answer instead
  of paying to read everything.
- **It's a status-stepped async job**, not a request/response — built for long multi-page runs.
- There's a whole parallel **`fire-0`** implementation in the tree (the previous generation of this
  engine) kept alongside the current one.

## Related
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (extract scrapes each source through the scraper; the per-page `json` format is the single-page version of this)
- [[queue-backed-crawl--from-firecrawl]] (domain-wide extract reuses crawl/map to find the pages)
- [[smart-scraper-pipeline--from-scrapegraph-ai]] (the LLM-driven "prompt → structured data" cousin at single-page scale)
- See also: [[structured-extraction]] domain peers.
