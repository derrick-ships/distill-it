# Connector Builder Test-Read — from [airbyte](https://github.com/airbytehq/airbyte)

> Domain: [[_domain]] · Source: https://github.com/airbytehq/airbyte · NotebookLM: <link once added>

## What it does

It's the backend behind Airbyte's no-code Connector Builder UI. As you edit a connector's YAML manifest
in the browser, this runs a **bounded test read** against the real API and streams back not just the
records, but the *whole trace* — the exact HTTP requests and responses, the pages, the slices, the
inferred schema — so you can see why a stream returns what it returns and fix the manifest live.

## Why it exists

Authoring a connector blind is miserable: change a JSON path, re-run a full sync, squint at logs.
The Builder closes that loop to seconds. The magic is that it runs the *same* declarative engine a
production sync uses, but capped and instrumented, so what you see in the preview is exactly what
you'll get in production — there's no separate "preview mode" connector to drift out of sync.

## How it actually works

The handler exposes a few commands over the Airbyte protocol (it returns its results *as* protocol
RECORD messages, cleverly reusing the same transport):

- **`test_read`**: build a real declarative source from the in-progress manifest, then run a read with
  hard **limits** — `max_records`, `max_pages_per_slice`, `max_slices` (defaults exist; the UI can
  override). A `TestReadLimits` object caps the work so hitting "test" never triggers a full sync. The
  read is run through a handler that captures every HTTP request/response pair, groups the emitted
  messages by slice and page (a "message grouper"), infers the record schema from the data, and packages
  it all into a `StreamRead` structure — which is then wrapped in an `AirbyteRecordMessage` and returned.
- **`resolve_manifest`** / **`full_resolve_manifest`**: return the manifest after `$ref`/`$parameters`
  expansion (and, in the full version, after dynamic streams are materialized), so the UI can show the
  "real" manifest the engine actually runs.

Because it constructs the same `ConcurrentDeclarativeSource`/`ManifestDeclarativeSource` as production,
every component — requester, paginator, extractor, cursor — behaves identically; the only difference is
the caps and the request/response capture.

## The non-obvious parts

- **Same engine, capped + instrumented.** Preview isn't a simulation — it's the production interpreter
  with `TestReadLimits` and HTTP capture bolted on. Zero preview/prod drift.
- **Results ride the protocol.** Rather than invent a new channel, it stuffs the rich `StreamRead`
  (requests, responses, slices, pages, schema) into a normal `AirbyteRecordMessage`. One transport for
  everything.
- **Three caps, not one.** Records, pages-per-slice, and slices are bounded separately so a test can't
  run away on any axis (a paginating, multi-slice stream is bounded on all three).
- **Schema is inferred from sampled data**, giving the UI a starting JSON-schema you can refine.
- **Resolve vs full-resolve.** Plain resolve shows refs/params expanded; full-resolve also materializes
  dynamic/derived streams — what the engine *actually* runs.
- **The grouped trace is the teaching tool** — seeing requests↔responses↔records grouped by page/slice
  is what makes the manifest debuggable.

## Related
- [[declarative-low-code-cdk--from-airbyte]] (it test-runs exactly this engine)
- [[declarative-http-stream-stack--from-airbyte]] (the requests/responses it captures come from here)
- [[airbyte-protocol--from-airbyte]] (results are returned as protocol RECORD messages)
- See also: [[interview-driven-scaffolding--from-whatsapp-agentkit]] and other code-generation peers.
