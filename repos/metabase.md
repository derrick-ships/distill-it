# Metabase — origin index

- **Source:** https://github.com/metabase/metabase
- **What it is:** Open-source Business Intelligence + embedded analytics. A visual query builder, 50+
  database drivers, dashboards, and charts that let non-engineers ask questions of their data without SQL.
- **Author:** Metabase · **License:** AGPL / commercial (enterprise)
- **Stack:** Clojure backend (`src/`, query processor + drivers + MBQL), React/TypeScript frontend
  (`frontend/`, query builder + visualizations), Malli schemas, HoneySQL, core.async; enterprise in `enterprise/`.
- **Date distilled:** 2026-06-18
- **Architecture in one line:** the UI emits MBQL (a typed query AST); the Query Processor threads it
  through ~40 middleware, compiles it to native via per-driver multimethods (SQL DBs share one
  MBQL→HoneySQL compiler), streams rows back through post-processing middleware, and the frontend
  auto-selects a sensible visualization from a registry.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| MBQL — Metabase Query AST | data-structures | [study](../features/data-structures/study/mbql-query-ast--from-metabase.md) | [build](../features/data-structures/build/mbql-query-ast--from-metabase.md) |
| Query Processor Middleware Pipeline | pipeline-orchestration | [study](../features/pipeline-orchestration/study/query-processor-middleware-pipeline--from-metabase.md) | [build](../features/pipeline-orchestration/build/query-processor-middleware-pipeline--from-metabase.md) |
| Multimethod Driver Abstraction | plugin-architecture | [study](../features/plugin-architecture/study/multimethod-driver-abstraction--from-metabase.md) | [build](../features/plugin-architecture/build/multimethod-driver-abstraction--from-metabase.md) |
| Visualization Auto-Selection | rendering | [study](../features/rendering/study/visualization-auto-selection--from-metabase.md) | [build](../features/rendering/build/visualization-auto-selection--from-metabase.md) |

## Not yet distilled (candidates)
- **X-rays** (automatic dashboards/insights from a table or question) → domain: `ai-automation`
- **Permissions + data sandboxing** (row/column access enforced as QP middleware) → domain: `agent-guardrails`
- **Signed embedding** (JWT-signed embedded dashboards with locked params) → domain: `credential-management`
- **Query Builder notebook UI** (the no-SQL visual editor) → domain: `canvas-interaction`
- **Result caching** (QP cache middleware + backends) → domain: `infrastructure`

## Verification gaps flagged in build docs (check before transplant)
- Full clause inventory/options, MBQL-5 stage model, normalization rules — mbql build.
- `qp.execute`/`reducible` wiring, `with-qp-setup`, sandboxing/parameter middleware internals — query-processor build.
- `register!`/`the-driver` impl, full `->honeysql` clause set, JDBC streaming — driver build.
- Per-chart `isSensible` heuristics, `transformSeries`, default-display choice — visualization build.

> Distill note: traced inline (no agent fan-out) under high session cost; QP/driver/MBQL spines confirmed
> from raw source via targeted fetch + grep, with per-doc "gaps to verify" lists where files weren't deep-read.
