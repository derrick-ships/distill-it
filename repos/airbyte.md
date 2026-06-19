# Airbyte — origin index

- **Source:** https://github.com/airbytehq/airbyte (CDK code lives in https://github.com/airbytehq/airbyte-python-cdk)
- **What it is:** Open-source data-integration platform — moves data from 600+ sources to warehouses/
  lakes/AI apps (ELT) and feeds AI agents real-time data. Connectors are built low-code (a YAML manifest)
  or no-code (the Connector Builder) on a shared Python CDK that speaks the Airbyte Protocol.
- **Author:** Airbyte · **License:** MIT (CDK) / ELv2 + MIT (platform)
- **Stack:** Python CDK (declarative engine, Pydantic, jsonschema, dpath, interpolation) · connectors as
  Docker images speaking newline-delimited JSON over stdout · Gradle/GitHub Actions build.
- **Date distilled:** 2026-06-18
- **Architecture in one line:** a YAML manifest (instance of a component JSON-schema) is interpreted into
  swappable requester/paginator/extractor/cursor components that emit Airbyte-Protocol RECORD+STATE
  messages; the Connector Builder test-runs that same engine, capped + instrumented.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Declarative (Low-Code) CDK | pipeline-orchestration | [study](../features/pipeline-orchestration/study/declarative-low-code-cdk--from-airbyte.md) | [build](../features/pipeline-orchestration/build/declarative-low-code-cdk--from-airbyte.md) |
| Airbyte Protocol | data-portability | [study](../features/data-portability/study/airbyte-protocol--from-airbyte.md) | [build](../features/data-portability/build/airbyte-protocol--from-airbyte.md) |
| Incremental Sync & State | pipeline-orchestration | [study](../features/pipeline-orchestration/study/incremental-sync-state--from-airbyte.md) | [build](../features/pipeline-orchestration/build/incremental-sync-state--from-airbyte.md) |
| Declarative HTTP Stream Stack | web-extraction | [study](../features/web-extraction/study/declarative-http-stream-stack--from-airbyte.md) | [build](../features/web-extraction/build/declarative-http-stream-stack--from-airbyte.md) |
| Connector Builder Test-Read | code-generation | [study](../features/code-generation/study/connector-builder-test-read--from-airbyte.md) | [build](../features/code-generation/build/connector-builder-test-read--from-airbyte.md) |

## Not yet distilled (candidates)
- **Destination/loading CDK** (the bulk-load side: typing+deduping, staging) → domain: `pipeline-orchestration`
- **Partition routers / substreams** (parent-child stream slicing) → domain: `pipeline-orchestration`
- **Auth components** (OAuth2, session-token, API-key declarative authenticators) → domain: `credential-management`
- **Agent SDK** (pydantic-ai/LangChain/FastMCP data access) → domain: `agent-architecture`
- **Concurrent source framework** (the partition/worker engine itself) → domain: `infrastructure`

## Verification gaps flagged in build docs (check before transplant)
- `ModelToComponentFactory` dispatch, $ref/$parameters edge cases, normalizer/migration — declarative-cdk build.
- GLOBAL vs STREAM state nesting, TRACE/CONTROL subtypes, wire casing — protocol build.
- `_partition_daterange` arithmetic, concurrent-cursor reconciliation, substream state — incremental build.
- `send_request`/HttpClient retry, full paginator strategy set, RecordFilter/TypeTransformer — http-stack build.
- `TestReader.run_test_read` capture, MessageGrouper rules, dynamic-stream materialization — connector-builder build.

> Distill note: traced inline (no agent fan-out); CDK lives in airbyte-python-cdk. Spines confirmed from
> raw source via targeted fetch + grep, with per-doc "gaps to verify" lists where files weren't deep-read.
