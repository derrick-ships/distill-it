# Query Processor Middleware Pipeline (build spec) — distilled from metabase

## Summary

Three-phase query engine. **Preprocess**: thread the MBQL query through ~40 `query→query` middleware
(normalize, validate, resolve tables/joins/fields, permissions+sandboxing, parameter substitution,
desugar, bucketing, default limit). **Compile + execute**: driver `mbql->native` → native SQL; a
**reducible** runner streams rows through a reducing function (`rff`) with cooperative cancellation.
**Postprocess**: thread result rows through reducing-fn middleware (format, limit, annotate, metadata).
An "around" layer adds userland behavior (catch-exceptions, save execution, timing).

## Core logic (inlined)

### Entry + around-middleware (`query_processor.clj`)

```clojure
(def around-middleware            ; wraps the whole pipeline (userland concerns). (f qp) -> qp
  [#'qp.middleware.enterprise/handle-audit-app-internal-queries-middleware
   #'qp.process-userland-query/process-userland-query-middleware   ; save QueryExecution, add running_time
   #'qp.catch-exceptions/catch-exceptions])                         ; userland: friendly error shape

(defn- process-query** [query rff]
  (let [preprocessed (qp.preprocess/preprocess query)
        compiled     (qp.compile/attach-compiled-query preprocessed)   ; mbql->native
        rff          (qp.postprocess/post-processing-rff preprocessed rff)]
    (qp.execute/execute compiled rff)))

;; build the pipeline fn ONCE by reduce-ing around-middleware over process-query**:
(defn- rebuild-process-query-fn! []
  (alter-var-root #'process-query*
    (constantly (reduce (fn [qp mw] (if mw (mw qp) qp)) process-query** around-middleware))))
(rebuild-process-query-fn!)
;; add-watch on each middleware var -> rebuild on change (dev hot-reload)

(defn process-query
  ([query] (process-query query nil))
  ([query rff] (qp.setup/with-qp-setup [query query]
                 (process-query* query (or rff qp.reducible/default-rff)))))
```

### Preprocess: ~40 query→query middleware, IN ORDER (`preprocess.clj`)

```clojure
[#'normalize/normalize-preprocessing-middleware        ; canonicalize MBQL shape FIRST
 #'qp.perms/remove-permissions-key #'qp.perms/remove-source-card-keys #'qp.perms/remove-sandboxed-table-keys
 #'qp.constraints/maybe-add-default-userland-constraints
 #'validate/validate-query                              ; schema-validate
 #'prefetch-metadata/prefetch-metadata
 #'fetch-source-query/resolve-source-cards
 #'expand-aggregations/expand-aggregations #'metrics/adjust #'measures/adjust #'expand-macros/expand-macros
 #'qp.resolve-referenced/resolve-referenced-card-resources
 #'parameters/substitute-parameters                    ; inject dashboard/native params
 #'qp.resolve-source-table/resolve-source-tables
 #'qp.auto-bucket-datetimes/auto-bucket-datetimes #'reconcile-bucketing/...
 #'qp.middleware.enterprise/apply-impersonation #'qp.middleware.enterprise/apply-sandboxing   ; SECURITY before joins
 #'qp.persistence/substitute-persisted-query
 #'qp.add-implicit-clauses/add-implicit-clauses
 #'resolve-joins/resolve-joins #'qp.add-remaps/add-remapped-columns #'qp.resolve-fields/resolve-fields
 #'binning/update-binning-strategy #'desugar/desugar    ; high-level filters -> primitives
 #'qp.add-default-temporal-unit/add-default-temporal-unit #'qp.add-implicit-joins/add-implicit-joins
 #'qp.cumulative-aggregations/rewrite-cumulative-aggregations #'qp.wrap-value-literals/wrap-value-literals
 #'validate-temporal-bucketing/... #'optimize-temporal-clauses/...
 #'limit/add-default-limit                              ; default limit LATE
 #'check-features/check-features]                       ; verify driver supports what's used
;; preprocess = thread the query map through each (transform-fn query)
```

### Compile (`compile.clj`) — delegate to driver

```clojure
(defn- compile* [preprocessed-query]
  (driver/mbql->native driver/*driver*                  ; multimethod -> native SQL/query
    (set/rename-keys (lib/query-stage preprocessed-query -1) {:native :query})))
;; attach-compiled-query assoc's {:qp/compiled <native>} onto the query
```

### Execute: reducible + rff + cancellation (`pipeline.clj`)

```clojure
(def ^:dynamic *canceled-chan* nil)        ; core.async promise-chan; closing HTTP conn -> cancel
(defn canceled? [] (some-> *canceled-chan* a/poll!))

(defn ^:dynamic *execute* [driver query respond]
  (when-not (canceled?)
    (driver/execute-reducible-query driver query {:canceled-chan *canceled-chan*} respond)))
    ;; driver calls (respond results-metadata reducible-rows) SYNCHRONOUSLY

(defn ^:dynamic *reduce* [rff metadata reducible-rows]
  (when-not (canceled?)
    (let [rf (rff metadata)]                              ; rff builds the reducing fn from result metadata
      (*result* (transduce identity rf reducible-rows))))) ; STREAM rows through rf; never realize all

(defn ^:dynamic *run* [query rff]
  (letfn [(respond [metadata rows] (*reduce* rff metadata rows))]
    (*execute* driver/*driver* query respond)))
```

### Postprocess: reducing-fn middleware over ROWS (`postprocess.clj`)

```clojure
(def middleware                          ; transforms the rff (rows in), IN ORDER
  [#'qp.pivot.middleware/add-pivot-grouping
   #'format-rows/format-rows             ; value formatting per column type/locale
   #'results-metadata/record-and-return-metadata!
   #'limit/limit-result-rows
   #'qp.add-rows-truncated/add-rows-truncated
   #'qp.add-timezone-info/add-timezone-info
   #'annotate/...])                      ; column metadata
;; post-processing-rff wraps the user rff with each of these (they see metadata + each row)
```

## Data contracts

- **Pipeline fn:** `(qp query rff) -> reduced-result`; middleware (preprocess) `(f qp)->qp` where `qp` is `(query rff)`.
- **rff (reducing function factory):** `(fn [results-metadata] -> reducing-fn)`; reducing-fn is a 3-arity transducer-style fn `([],[acc],[acc row])`.
- **respond callback:** `(respond results-metadata reducible-rows)` — called synchronously by the driver.
- **compiled query:** `{:qp/compiled {:query native-sql, :params [...]}}` attached to the query.

## Dependencies & assumptions

- Clojure (vars, dynamic binding, `core.async` for cancellation, transducers/`IReduceInit` for streaming).
  The MBQL AST ([[mbql-query-ast--from-metabase]]); the driver multimethods ([[multimethod-driver-abstraction--from-metabase]]).
- Swappable: the *pattern* (ordered middleware over a query, reducible streaming execution, ordered
  middleware over rows) ports to any language with composable functions + a streaming reducer.

## To port this, you need:

- [ ] An ordered list of **query→query** preprocess middleware (normalize first, validate early, security before joins, default-limit late).
- [ ] A compile step delegating to a per-driver `mbql->native`.
- [ ] A **streaming** execute: driver returns metadata + a reducible row source; reduce through an `rff` (don't realize all rows).
- [ ] An ordered list of **row-transforming** postprocess middleware (format, limit, annotate, metadata).
- [ ] An "around" layer for cross-cutting userland concerns (catch errors, persist execution, timing).
- [ ] Cooperative **cancellation** checked before expensive steps.

## Gotchas

- **Order is the contract** — sandboxing/permissions before join resolution; desugar before compile; default limit late. Reordering silently changes semantics or leaks data.
- **Stream, don't materialize** — the rff/reducible design is what survives huge result sets; collecting rows into a vector defeats it.
- **`respond` must be synchronous** — async responds break the reducing contract.
- **Cancellation is cooperative** — you must check the channel before expensive work, or a closed connection still hammers the DB.
- **Build the pipeline once** (reduce middleware → one fn); rebuilding per query is wasteful — but watch vars for dev reload.
- **Two middleware shapes** — preprocess wraps the query, postprocess wraps the rff; don't mix them.

## Origin (reference only)

metabase/metabase @ `master`: `src/metabase/query_processor.clj` (entry + around — inlined),
`query_processor/{preprocess,compile,postprocess,pipeline,reducible,execute,setup}.clj` (inlined/grepped),
`query_processor/middleware/*.clj` (~40 steps).

**Gaps to verify (cost-capped):** `qp.execute/execute` + `reducible.clj` exact wiring; `with-qp-setup` (driver/db
resolution, store); a few middleware internals (sandboxing, parameters); MBQL-5 `lib/query-stage`.
