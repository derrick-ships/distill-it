# MBQL — the Metabase Query AST — from [metabase](https://github.com/metabase/metabase)

> Domain: [[_domain]] · Source: https://github.com/metabase/metabase · NotebookLM: <link once added>

## What it does

MBQL ("Metabase Query Language") is the **data structure** every question in Metabase becomes — a
database-agnostic description of a query as plain nested EDN/JSON: which table, which columns, which
filters, which aggregations, grouped how, ordered how. It's not SQL; it's a normalized *intermediate
representation* that the rest of the system reads, rewrites, and finally compiles down to SQL (or a
Mongo query, or an API call) for whatever database you're pointed at.

## Why it exists

If the query builder emitted SQL directly, every feature — filtering, drill-downs, permissions,
caching, "view the SQL" — would have to parse and rewrite SQL strings for a dozen dialects. Instead
Metabase made the query a **typed data structure**: the UI produces MBQL, dozens of transforms operate
on MBQL as data, and only the very last step turns it into a dialect. A data structure you can
`assoc`/`update` is infinitely easier to manipulate than a string you have to parse. MBQL is the spine
the entire product hangs on.

## How it actually works

A query is a map: `{:database <id>, :type :query | :native, :query {...} | :native {...}}`. The `:query`
(for MBQL questions) is itself a map of clauses: `:source-table` (or `:source-query` for nested
queries), `:aggregation`, `:breakout` (group-by), `:filter`, `:order-by`, `:limit`, `:joins`,
`:expressions`, `:fields`. Each clause is a **vector with a keyword tag** — the classic Lisp "tagged
list" shape: a field reference is `[:field <id-or-name> <opts>]`, a filter is `[:= [:field 5 nil]
"x"]`, an aggregation is `[:sum [:field 7 nil]]`, and you can reference the Nth aggregation positionally
with `[:aggregation 0]`.

The whole language is **formally specified as a schema** (using Malli). A library of `defclause` macros
declares every legal clause — its tag, its argument types, its options — so a query can be *validated*
and so tools (autocomplete, the query builder, error messages) can be generated from the spec. There
are bucketing units for datetimes (day/week/month/quarter…), string/numeric/boolean function clauses,
relative and absolute datetime literals, and an explicit `:value` clause that carries a literal plus
type info (so the compiler knows a string is really a UUID, say).

There are two generations: **legacy MBQL** (the historical schema) and **MBQL 5** (the newer `lib`
version, normalized and stage-based). The query processor normalizes incoming queries to the canonical
form first, so everything downstream sees one consistent shape.

## The non-obvious parts

- **The query is data, not a string.** This single decision is why Metabase can manipulate queries so
  freely — permissions, sandboxing, drill-through, parameterization are all just map transforms.
- **Tagged vectors are the grammar.** `[:tag arg1 arg2 opts]` everywhere — fields, filters,
  aggregations, expressions. Uniform shape means uniform walking/rewriting.
- **The schema is the source of truth.** MBQL is *defined by* its Malli schema, so queries validate and
  the spec drives tooling. Invalid queries fail loudly at the edge.
- **Positional aggregation references** (`[:aggregation 0]`) let order-by point at a computed column
  without naming it.
- **`:value` carries type info** so the eventual SQL casts correctly (the UUID-vs-text gotcha is handled
  in the AST, not the dialect).
- **Two schemas, normalized to one.** Legacy MBQL and MBQL 5 coexist; normalization collapses them so
  downstream code is version-agnostic.

## Related
- [[query-processor-middleware-pipeline--from-metabase]] (the pipeline that rewrites and compiles MBQL)
- [[multimethod-driver-abstraction--from-metabase]] (drivers compile MBQL → their dialect)
- [[airbyte-protocol--from-airbyte]] (a different "normalized contract" — messages vs query AST)
- See also: [[data-structures]] peers.
