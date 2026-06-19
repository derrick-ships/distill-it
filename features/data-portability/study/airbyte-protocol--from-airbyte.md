# Airbyte Protocol — from [airbyte](https://github.com/airbytehq/airbyte)

> Domain: [[_domain]] · Source: https://github.com/airbytehq/airbyte · NotebookLM: <link once added>

## What it does

It's the **contract** that lets any source talk to any destination. A connector is just a program that
speaks this protocol over stdin/stdout: it emits a stream of typed JSON messages — records, state
checkpoints, logs, the catalog of what it can sync, connection-check results. Because every connector
speaks the same language, Airbyte can wire 600 sources to 100 destinations without either knowing about
the other.

## Why it exists

The whole "any source → any destination" promise rests on a universal interface. If sources and
destinations had to integrate pairwise, you'd need thousands of bespoke adapters. Instead, Airbyte
defines one message protocol: a source emits `RECORD` and `STATE` messages; a destination consumes
them. The protocol *is* the product's core abstraction — everything else plugs into it.

## How it actually works

A connector is a CLI with four commands, each emitting `AirbyteMessage`s as newline-delimited JSON:

- **`spec`** → an `AirbyteСatalog`-adjacent `ConnectorSpecification`: the JSON-schema of the config the
  connector needs (so the UI can render a form).
- **`check`** → an `AirbyteConnectionStatus` (`SUCCEEDED`/`FAILED`): can it reach the source with these
  credentials?
- **`discover`** → an `AirbyteCatalog`: the list of streams it can sync, each with a JSON-schema, its
  supported sync modes, and its default cursor/primary-key.
- **`read`** (given a `ConfiguredAirbyteCatalog` + previous state) → a stream of `RECORD` messages
  (the data), interleaved with `STATE` messages (checkpoints), plus `LOG`, `TRACE` (errors/estimates),
  and `CONTROL` (e.g. config updates) messages.

The key envelope is `AirbyteMessage{type, record?, state?, log?, trace?, catalog?, spec?, connectionStatus?, control?}` — a tagged union. `AirbyteRecordMessage` carries `{stream, data, emitted_at}`; `AirbyteStateMessage` carries the resumable position. Destinations read this stream and write records; the platform persists the state so the next sync resumes from there. Messages are (de)serialized by dedicated serializers for speed.

## The non-obvious parts

- **stdout is the bus.** A connector is just a process emitting newline-delimited JSON. That's why
  connectors can be written in any language and shipped as Docker images — the interface is text.
- **State is a first-class message**, interleaved with records. The destination/platform checkpoints on
  `STATE`, so a sync that dies resumes from the last emitted state, not from zero.
- **The catalog is negotiated.** `discover` offers streams + sync modes; the user configures a
  `ConfiguredAirbyteCatalog` (which streams, which sync mode, which cursor); `read` honors it.
- **TRACE messages carry structured errors and estimates**, separate from free-text LOG — so the
  platform can surface real failure reasons and progress.
- **CONTROL messages let a connector phone home** — e.g. emit an updated OAuth token to persist.
- **Tagged-union envelope** means one stream multiplexes records, state, logs, and metadata cleanly.

## Related
- [[declarative-low-code-cdk--from-airbyte]] (declarative connectors emit this protocol)
- [[incremental-sync-state--from-airbyte]] (produces the STATE messages defined here)
- [[connector-builder-test-read--from-airbyte]] (wraps protocol messages into a test-read result)
- See also: [[data-portability]] peers — this is the canonical "universal data-movement contract."
