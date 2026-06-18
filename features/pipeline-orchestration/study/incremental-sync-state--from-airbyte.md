# Incremental Sync & State — from [airbyte](https://github.com/airbytehq/airbyte)

> Domain: [[_domain]] · Source: https://github.com/airbytehq/airbyte · NotebookLM: <link once added>

## What it does

After the first full pull, you don't want to re-download everything every time — you want *only what
changed*. This is the machinery that makes that work: a **cursor** (usually a timestamp like
`updated_at`) tracks how far you've synced, the sync emits **state checkpoints** as it goes, and the
next run resumes from the saved cursor instead of from the beginning. It also slices a big date range
into chunks so a multi-year backfill is done in safe, resumable windows.

## Why it exists

Re-syncing a giant table every hour is wasteful and slow, and a sync that crashes at 90% shouldn't
start over. Incremental sync solves both: only fetch new/changed records, and checkpoint progress so
failures resume. For any real data pipeline this is the difference between viable and unusable.

## How it actually works

The declarative cursor is the `DatetimeBasedCursor`. You give it a `start_datetime`, an optional
`end_datetime`, a `cursor_field` (the record field it watches, e.g. `updated_at`), a datetime format,
and optionally a `step` (window size, as an ISO-8601 duration like `P30D`) with a matching
`cursor_granularity`, and a `lookback_window`.

- **Slicing**: it partitions the range `[start - lookback, end]` into windows of size `step`, producing
  a `stream_slice` per window (`{start_time, end_time}`). The retriever runs the request once per slice,
  injecting those bounds into the URL/params via interpolation. This bounds memory and makes a backfill
  resumable window-by-window.
- **Observing**: as records flow by, the cursor watches each record's `cursor_field` and tracks the
  **highest value seen** so far.
- **State**: at slice boundaries it emits state `{<cursor_field>: <highest datetime>}`. That state is
  persisted (via the protocol's STATE message). On the next run, it becomes the new effective start —
  so you only pull records newer than last time.
- **Lookback** re-reads a little before the last cursor to catch late-arriving/updated rows; the
  `cursor_granularity` ensures consecutive slices don't overlap or skip a tick.

`should_be_synced` lets it skip records outside the configured window. The newer CDK runs cursors
**concurrently** across partitions, but the state semantics are the same.

## The non-obvious parts

- **Slicing and cursoring are the same component.** The thing that windows the date range is also the
  thing that tracks progress — because the window bounds *are* the state.
- **Track the highest observed value, emit it as state.** State isn't "where the loop is," it's "the
  newest record we've safely seen," so resume is correct even if records arrive out of order.
- **Lookback trades dupes for completeness.** Re-reading a window catches late updates at the cost of
  re-emitting some rows — destinations dedup on primary key.
- **`step` + `cursor_granularity` must agree** — granularity is what keeps slice N+1 from overlapping
  slice N by one tick; the cursor enforces you set both or neither.
- **State is emitted at slice boundaries, interleaved with records**, so a crash resumes from the last
  completed window, not from zero.
- **Concurrent cursors** keep per-partition state and reconcile — same contract, parallel execution.

## Related
- [[airbyte-protocol--from-airbyte]] (state travels as STATE messages defined there)
- [[declarative-http-stream-stack--from-airbyte]] (slices feed `stream_slice` into request interpolation)
- [[declarative-low-code-cdk--from-airbyte]] (the cursor is declared in the manifest)
- [[queue-backed-crawl--from-firecrawl]] (a different resumable-progress model: Redis sets vs cursor state)
