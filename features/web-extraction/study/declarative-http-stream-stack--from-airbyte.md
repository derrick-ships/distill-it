# Declarative HTTP Stream Stack — from [airbyte](https://github.com/airbytehq/airbyte)

> Domain: [[_domain]] · Source: https://github.com/airbytehq/airbyte · NotebookLM: <link once added>

## What it does

This is the engine that actually pulls records from a REST API, broken into four swappable pieces: a
**requester** (build and send the HTTP call), a **paginator** (figure out the next page), an
**extractor** (pluck the records out of the JSON response), and a **selector** (filter + normalize +
transform them). A **retriever** wires them into a loop: request a page → extract records → get the
next page token → repeat until pages run out. Every Airbyte API connector is some configuration of
these four.

## Why it exists

Almost every REST API sync is the same shape — call, paginate, dig records out of a nested JSON path,
clean them up — differing only in *details*. By making each step a small, declared, swappable
component, Airbyte turns "write a connector" into "configure four components." It's the concrete
machinery the declarative manifest configures.

## How it actually works

The **SimpleRetriever** owns the loop (`_read_pages` / `read_records`): it asks the requester to send a
page, hands the response to the record selector to get clean records, asks the paginator for the next
page token, and stops when the paginator returns `None`.

- **HttpRequester** holds `url_base` + `path` (both `InterpolatedString`s, so they can embed config,
  parameters, stream state, and the page token), plus request params/headers/body and an **error
  handler with backoff strategies**. It delegates the actual send + retry to an `HttpClient`.
- **DefaultPaginator** combines a `pagination_strategy` (OffsetIncrement, PageIncrement, CursorPagination
  — read the next-page cursor out of the response/headers) with a `page_size_option` and
  `page_token_option` that say *where* to inject the page size and token (query param, header, or path).
  When the strategy yields no next token, the page loop ends.
- **DpathExtractor** uses a `field_path` (a list of keys, e.g. `["data", "items"]`, each interpolatable)
  and the `dpath` library to reach into the decoded JSON and yield the record list — `field_path: []`
  means "the whole response is the records."
- **RecordSelector** runs the extractor, then applies an optional **record filter** (a boolean
  expression), **schema normalization** (cast values to the stream's declared types), and a list of
  **transformations** (add/remove/rename fields).

Everything is glued by **string interpolation**: paths, params, and tokens are templates evaluated
against `{config, parameters, stream_state, stream_slice, next_page_token}` at request time.

## The non-obvious parts

- **Four orthogonal jobs.** Request, paginate, extract, select — each is a separate, swappable
  component. Want a weird pagination scheme? Swap the strategy; nothing else changes.
- **Interpolation everywhere.** URLs, params, and the record path are templates, not literals, so a
  single component definition adapts per-stream and per-page.
- **Pagination is two decisions, not one.** *How* to compute the next token (strategy) is separate from
  *where* to put it (token option: query/header/path). That split covers nearly every real API.
- **`field_path: []` = whole response.** The extractor's empty path is the common case for APIs that
  return a bare array.
- **The selector is the cleanup stage** — filter, type-cast to schema, transform — kept distinct from
  extraction so the same extractor feeds different cleanups.
- **Backoff/error handling lives in the requester**, declared, so retry policy is config not code.

## Related
- [[declarative-low-code-cdk--from-airbyte]] (the manifest interpreter that builds these components)
- [[incremental-sync-state--from-airbyte]] (the cursor that feeds `stream_slice`/`stream_state` into interpolation)
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (a different fetch pipeline; airbyte's is API-record-oriented)
- See also: [[multi-source-fetch-node--from-scrapegraph-ai]].
