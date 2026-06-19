# Multimethod Driver Abstraction (build spec) — distilled from metabase

## Summary

One interface, N databases, via **Clojure multimethods + an `isa?` hierarchy**. Drivers `register!`
with a parent (`:postgres` → `:sql-jdbc` → `:sql`); multimethods (`mbql->native`,
`execute-reducible-query`, `describe-database`, `can-connect?`, `database-supports?`, …) dispatch on the
driver keyword and fall through the hierarchy. SQL databases inherit one shared MBQL→**HoneySQL**→string
compiler (itself per-clause multimethods) and override only dialect quirks. A dynamic `*driver*` threads
the current driver.

## Core logic (inlined)

### The hierarchy + dispatch (`driver.clj`)

```clojure
(p/import-vars [driver.impl hierarchy register! initialized?])   ; shared hierarchy
(def ^:dynamic *driver* nil)                                      ; current driver, threaded through calls

(defn the-driver [driver] ...)        ; keyword -> registered driver
(defn dispatch-on-initialized-driver [driver] (the-driver driver))

;; a driver registers with a PARENT -> single inheritance via isa?:
(register! :sql-jdbc :parent :sql)
(register! :postgres :parent :sql-jdbc)
;; now: (isa? hierarchy :postgres :sql)  => true

;; every capability is a multimethod dispatching on the driver keyword:
(defmulti mbql->native            {:arglists '([driver query])}  dispatch-on-initialized-driver :hierarchy #'hierarchy)
(defmulti execute-reducible-query {:arglists '([driver query context respond])} ... :hierarchy #'hierarchy)
(defmulti can-connect?            ... :hierarchy #'hierarchy)
(defmulti describe-database       ...)   ; -> {:tables #{{:name ... :schema ...}}}
(defmulti describe-table          ...)   ; -> {:fields #{{:name ... :base-type ...}}}
(defmulti database-supports?      {:arglists '([driver feature database])} (fn [driver feature _] [driver feature]) :hierarchy #'hierarchy)
(defmulti connection-properties   ...)   ; the config form fields for the admin UI
;; Postgres need only implement what differs; the rest resolves up the hierarchy to :sql-jdbc/:sql.
```

### Shared SQL compiler = more multimethods (`driver/sql/query_processor.clj`)

```clojure
;; :sql implements mbql->native ONCE: MBQL -> HoneySQL (SQL-as-data) -> SQL string.
;; The compiler dispatches per [driver clause]:
(defmulti ->honeysql {:arglists '([driver x])} (fn [driver x] [(dispatch-on-driver driver) (mbql-clause-tag x)]) :hierarchy #'driver/hierarchy)
(defmethod ->honeysql [:sql :field]   [driver [_ id-or-name opts]] ...)
(defmethod ->honeysql [:sql :=]       [driver [_ a b]] [:= (->honeysql driver a) (->honeysql driver b)])
(defmethod ->honeysql [:sql Number]   [_ n] n)
(defmethod ->honeysql [:sql nil]      [_ _] nil)

;; focused dialect hooks a new DB overrides instead of the whole compiler:
(defmulti quote-style ...)                         ; :ansi | :mysql | :sqlserver
(defmulti current-datetime-honeysql-form ...)      ; NOW() vs CURRENT_TIMESTAMP vs ...
(defmulti date {:arglists '([driver unit expr])})  ; date_trunc dialect
(defmulti unix-timestamp->honeysql ...)
(defmulti add-interval-honeysql-form ...)          ; INTERVAL arithmetic
(defmulti apply-top-level-clause {:arglists '([driver top-level-clause honeysql-form query])})  ; :breakout/:filter/:order-by
;; final: honeysql -> SQL string via the dialect's quote-style
```

### Execution

```clojure
(defmethod execute-reducible-query :sql-jdbc [driver query context respond]
  ;; open connection, prepare+run native SQL, then:
  (respond {:cols [...metadata...]} reducible-rows))   ; respond SYNCHRONOUSLY with metadata + lazy rows
;; the QP's *execute* calls this; *reduce* streams the reducible rows through the rff.
```

## Data contracts

- **Driver:** a keyword registered with `:parent`; capabilities are multimethod implementations.
- **`mbql->native` ->** `{:query "SELECT ..." :params [...]}` (native query + params).
- **`describe-database` ->** `{:tables #{{:name, :schema}}}`; **`describe-table` ->** `{:name, :schema, :fields #{{:name, :database-type, :base-type, :database-position}}}`.
- **`execute-reducible-query`:** `(driver query context respond)`, `respond` = `(metadata reducible-rows)`.
- **`database-supports?`:** `[driver feature database] -> bool` (feature detection, e.g. `:nested-queries`, `:window-functions`).
- **`connection-properties` ->** vector of admin-form field specs.

## Dependencies & assumptions

- A language with **open multimethods + a runtime hierarchy** (Clojure here; emulate with a dispatch
  table + prototype chain, or registry + interface inheritance, elsewhere). HoneySQL (SQL-as-data).
- The QP calls these multimethods; `*driver*` carries the current driver.
- Swappable: the *pattern* (capability interface + inheritance + per-clause compiler dispatch) ports to
  any extensible-connector system.

## To port this, you need:

- [ ] A capability **interface** (connect / describe / compile / execute / supports?) dispatched by driver id.
- [ ] An **inheritance hierarchy** so related drivers share a base (one SQL base for all SQL DBs).
- [ ] A shared compiler that turns the query AST into an **intermediate (SQL-as-data)** then a string, dispatched **per [driver, clause]** so dialects override surgically.
- [ ] Focused dialect hooks (quoting, date functions, intervals, current-timestamp) instead of full-compiler overrides.
- [ ] **Feature detection** (`supports?`) so the core adapts rather than assumes.
- [ ] A streaming `execute` that responds with metadata + a reducible row source.

## Gotchas

- **Inherit, don't copy** — without a base SQL driver, every DB reimplements MBQL→SQL; the hierarchy is the whole economy.
- **Dispatch the compiler per clause** — overriding the entire compiler per dialect forks thousands of lines; `[driver clause]` dispatch keeps overrides to the one date/quoting function that differs.
- **Feature-detect, don't assume** — call `supports?` before emitting window functions/nested queries or you generate SQL the DB rejects.
- **`respond` synchronously** with a reducible (not a realized) row sequence — that's what lets the QP stream.
- **Resolve the driver once** into `*driver*` and let multimethods pick it up — threading it manually everywhere is noise.
- **Register parents correctly** — a wrong parent silently inherits the wrong dialect.

## Origin (reference only)

metabase/metabase @ `master`: `src/metabase/driver.clj` (multimethods + hierarchy — grepped),
`src/metabase/driver/impl.clj` (hierarchy/register!), `src/metabase/driver/sql/query_processor.clj`
(`->honeysql` per-clause compiler — grepped), `src/metabase/driver/sql_jdbc/{execute,connection,sync}.clj`.

**Gaps to verify (cost-capped):** exact `register!`/`the-driver` impl; the full `->honeysql` clause set;
`apply-top-level-clause` for breakout/filter/order-by; `execute-reducible-query` JDBC streaming details.
