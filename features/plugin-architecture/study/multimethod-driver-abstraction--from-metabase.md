# Multimethod Driver Abstraction — from [metabase](https://github.com/metabase/metabase)

> Domain: [[_domain]] · Source: https://github.com/metabase/metabase · NotebookLM: <link once added>

## What it does

It's how Metabase talks to 50+ different databases through **one interface**. Each database driver
(Postgres, MySQL, BigQuery, Mongo, …) implements a set of named operations — "can you connect?",
"describe this table", "turn this MBQL into your native query", "execute and stream rows" — and Metabase
calls those operations without knowing or caring which database it's talking to. Adding a new database
means implementing the interface, not touching the core.

## Why it exists

A BI tool's value is breadth: the more databases it supports, the more useful it is. But the core engine
(query processor, sync, permissions) must stay database-agnostic or it'd collapse under per-database
special cases. The driver abstraction draws a hard line: the core speaks one vocabulary; each driver
translates. And crucially, drivers can **inherit** from each other, so the dozens of SQL databases share
one big SQL implementation and only override the handful of things they do differently.

## How it actually works

The mechanism is Clojure **multimethods** with a **hierarchy**. A multimethod (like `mbql->native`,
`execute-reducible-query`, `describe-database`, `can-connect?`, `database-supports?`,
`connection-properties`) dispatches on the driver keyword (`:postgres`, `:mysql`, …). Drivers
`register!` themselves and declare a **parent** in a hierarchy: `:postgres` derives from `:sql-jdbc`,
which derives from `:sql`. Multimethod dispatch then uses `isa?` against that hierarchy — so if Postgres
doesn't define `mbql->native`, the call falls through to the `:sql-jdbc`/`:sql` implementation. This is
single-inheritance polymorphism via data, not class hierarchies.

The big win is the shared **SQL implementation**. The `:sql` driver implements `mbql->native` once, as a
compiler from MBQL to **HoneySQL** (a Clojure data representation of SQL) and then to a SQL string. That
compiler is itself built from multimethods — `->honeysql` dispatches per MBQL clause *and* per driver,
so a database that formats dates differently overrides just `->honeysql` for the date clause (or one of
the focused multimethods like `current-datetime-honeysql-form`, `date`, `unix-timestamp->honeysql`,
`quote-style`). Everything else — joins, filters, the overall query shape — is inherited. A new SQL
database is often a few dozen lines: connection details plus a handful of dialect overrides.

A dynamic `*driver*` var carries the current driver through the call stack, and `the-driver` resolves a
keyword to its registered driver, so code deep in the query processor can call a multimethod and get the
right database's behavior automatically.

## The non-obvious parts

- **Polymorphism through a data hierarchy, not classes.** `isa?`-based dispatch means a driver is just a
  keyword with a parent and a bag of method implementations — open for extension, no inheritance
  ceremony.
- **Inheritance is the scaling trick.** 30 SQL databases share `:sql`/`:sql-jdbc`; each overrides only
  its quirks. Without inheritance you'd reimplement MBQL→SQL per database.
- **The compiler is *also* multimethods.** `->honeysql` dispatches on `[driver clause]`, so dialect
  differences are surgical overrides at the clause level, not forks of the whole compiler.
- **HoneySQL as an intermediate.** MBQL → HoneySQL (SQL-as-data) → string. Manipulating SQL as data
  (like MBQL itself) keeps the compiler composable and the final string-rendering swappable per dialect.
- **`database-supports?`** lets the core ask a driver "do you do window functions / nested queries?" and
  adapt — feature detection instead of assumptions.
- **One dynamic `*driver*`** threads the current database through everything, so middleware doesn't pass
  it around explicitly.

## Related
- [[query-processor-middleware-pipeline--from-metabase]] (calls `mbql->native` and `execute-reducible-query`)
- [[mbql-query-ast--from-metabase]] (the input the driver compiles)
- [[declarative-low-code-cdk--from-airbyte]] (a different connector-pluggability model: YAML manifest vs multimethods)
- See also: [[plugin-architecture]] peers.
