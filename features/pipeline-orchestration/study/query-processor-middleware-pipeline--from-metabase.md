# Query Processor Middleware Pipeline — from [metabase](https://github.com/metabase/metabase)

> Domain: [[_domain]] · Source: https://github.com/metabase/metabase · NotebookLM: <link once added>

## What it does

The Query Processor is the assembly line that takes an MBQL query and produces results. It runs the
query through ~40 small **middleware** steps that progressively rewrite it (resolve tables, add implicit
joins, apply permissions and sandboxing, substitute parameters, bucket datetimes, add a default limit…),
compiles the finished MBQL into native SQL for the target database, executes it, and then streams the
result rows back through a second chain of middleware that formats values, applies limits, annotates
columns, and attaches metadata.

## Why it exists

A real query needs dozens of independent concerns handled in a precise order: security, parameter
injection, implicit joins, timezone handling, row limits, value formatting. Cramming that into one
function would be unmaintainable. So Metabase made each concern a **composable middleware** — a function
that wraps the next — so the pipeline is a readable, reorderable list, and each step is small,
testable, and ignorant of the others. It's the same pattern as Ring/Express middleware, applied to
queries instead of HTTP.

## How it actually works

There are really three phases, and the middleware is split across them:

**Preprocess (transform the query).** A list of ~40 middleware functions is threaded over the query
map, each one a pure-ish `query → query` transform. They run in order: normalize the query, strip
permission keys, validate, resolve source cards/tables, expand macros and metrics, substitute
parameters, apply impersonation/sandboxing (enterprise), add implicit clauses and joins, resolve
fields, desugar high-level filters into primitives, bucket datetimes, wrap literal values, add the
default limit, check feature support. The output is a fully-resolved, canonical MBQL query.

**Compile + execute.** The resolved MBQL is handed to the driver via the `mbql->native` multimethod,
which turns it into native SQL (or whatever the database speaks). Execution uses a **reducible** design:
a dynamic `*run*` calls `*execute*` (which calls the driver's `execute-reducible-query`), which calls
back with a result-metadata + a *reducible* sequence of rows; `*reduce*` then reduces those rows
through a **reducing function (`rff`)**. This streams rows instead of materializing them all — crucial
for big result sets — and supports **cancellation** via a `*canceled-chan*` that's checked before
expensive steps.

**Postprocess (transform the results).** As rows come back, a second middleware chain — implemented as
reducing-function transformers — runs in order: pivot grouping, format rows, record results metadata,
limit result rows, add "rows truncated" info, attach timezone info, annotate columns. There's also an
**"around" middleware** layer that wraps the whole thing for userland queries: catch exceptions into a
friendly error shape, save a QueryExecution record, add running-time. The pipeline function is *built
once* by reducing the middleware list into a single function, and rebuilt automatically if any
middleware var changes (live reload in dev).

## The non-obvious parts

- **Middleware is a list you can read top-to-bottom.** The entire query lifecycle is a literal vector of
  function vars — to understand or change behavior, you reorder/add/remove an entry. That legibility is
  the whole point.
- **Pre-processing threads the *query*; post-processing threads the *rows*.** Two different shapes:
  query-map transforms going in, reducing-function transforms coming out.
- **Reducible + rff = streaming.** Results are never fully realized; rows flow through a reducing
  function, so a billion-row scan doesn't OOM and can be aggregated on the fly.
- **Cancellation is cooperative** via a core.async channel checked at each stage — closing the HTTP
  connection cancels the database query.
- **Order is load-bearing.** Sandboxing must run before joins resolve; default limit late; desugar
  before compile. The list *is* the contract.
- **The compiled function is cached and hot-reloaded** — built by `reduce`-ing middleware, rebuilt on
  var change so dev edits take effect without restart.
- **Enterprise concerns slot in as middleware** (impersonation, sandboxing, download limits) — same
  mechanism, no forks.

## Related
- [[mbql-query-ast--from-metabase]] (the query the pipeline rewrites)
- [[multimethod-driver-abstraction--from-metabase]] (compile + execute delegate to driver multimethods)
- [[pdf-ingestion-pipeline--from-openpaper]] (a different pipeline shape: stages over jobs, not middleware over a map)
- See also: Ring/Express middleware — same composition pattern.
