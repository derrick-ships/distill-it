# MBQL — the Metabase Query AST (build spec) — distilled from metabase

## Summary

A database-agnostic query **as a typed, nested data structure** (EDN/JSON), formally specified by a
Malli schema. A query is `{:database, :type, :query|:native}`; clauses are tagged vectors
(`[:field id opts]`, `[:= lhs rhs]`, `[:sum field]`). Everything downstream rewrites the query *as
data*; only the driver compiles it to a dialect. Two generations (legacy + MBQL 5) normalized to one.

## Core logic (inlined)

### Top-level shape

```clojure
;; MBQL question
{:database 1
 :type     :query
 :query    {:source-table 2                ; or :source-query {...} for nested
            :aggregation  [[:sum [:field 7 nil]] [:count]]
            :breakout     [[:field 4 {:temporal-unit :month}]]
            :filter       [:and [:= [:field 5 nil] "active"]
                                [:> [:field 7 nil] 100]]
            :order-by     [[:asc [:aggregation 0]]]   ; positional ref to the :sum above
            :joins        [{:source-table 9 :condition [...] :alias "u" :fields :all}]
            :expressions  {"profit" [:- [:field 7 nil] [:field 8 nil]]}
            :limit        100}}
;; Native question
{:database 1 :type :native :native {:query "SELECT ..." :template-tags {...}}}
```

### Clause grammar (tagged vectors)

```clojure
[:field   <id-or-name> <opts>]      ; opts: {:temporal-unit :month, :binning {...}, :join-alias "u", :base-type :type/Text}
[:aggregation <index> <opts>]       ; positional reference to the Nth :aggregation
[:value   <literal> <type-info>]    ; literal + {:base_type ..., :semantic_type ...}; lets compiler cast correctly
[:= [:field 5 nil] [:value "..." {...}]]   ; filter clause
[:sum [:field 7 nil]] [:count] [:distinct field] [:metric id]   ; aggregations
[:expression "profit"]              ; reference a named expression
[:relative-datetime -7 :day] [:interval 1 :month] [:absolute-datetime t :day]
```

### Schema definition via `defclause` (Malli)

```clojure
;; from legacy_mbql/schema.cljc — every clause is declared, validated, and documented:
(defclause field   id-or-name [:schema ...] opts [:maybe FieldOptions])
(defclause* aggregation ...)          ; defclause* = lower-level variant
(def datetime-bucketing-units #{:default :minute :hour :day :week :month :quarter :year ...})
(def aggregations #{:sum :count :distinct :avg :min :max :cum-sum :cum-count :share
                    :count-where :sum-where :distinct-where :metric :measure :aggregation-options :offset})
;; a top-level ::Query schema validates the whole map; mu/defn fns are spec'd against it.
```

The schema is the single source of truth: queries are validated against it (the QP's `validate-query`
middleware), and tooling (builder, autocomplete, error messages) is generated from it.

### Normalization

Incoming queries (legacy MBQL, MBQL 5, snake_case from JSON) are normalized to one canonical shape
(`normalize-query` is the first QP middleware), so all downstream transforms see consistent data.

## Data contracts

- **Query:** `{:database int, :type :query|:native, :query MBQLInner | :native {:query str, :template-tags map}, :parameters? [...], :middleware? {...}, :info? {...}}`.
- **MBQLInner:** `{:source-table int | :source-query MBQLInner, :aggregation [clause...], :breakout [field...], :filter clause, :order-by [[:asc|:desc ref]...], :joins [...], :expressions {name clause}, :fields [field...], :limit int, :page {...}}`.
- **Field ref:** `[:field (int id | str name) {:base-type, :temporal-unit, :binning, :join-alias, :source-field}]`.
- **Field options carry type info** so compilation and display are correct without re-querying metadata.

## Dependencies & assumptions

- A schema/validation lib (Metabase uses **Malli**; equally a JSON-Schema or zod in other stacks).
- A normalization step at the boundary. Consumers that walk/rewrite the AST (the QP middleware).
- Swappable: the *idea* (typed query AST + schema) is language-agnostic; the clause set is BI-specific.

## To port this, you need:

- [ ] A nested data structure for queries with **tagged-vector clauses** (uniform `[:tag ...args opts]`).
- [ ] A **formal schema** of every clause (validate at the boundary; generate tooling from it).
- [ ] A normalization pass to one canonical shape (handle multiple input dialects/casings).
- [ ] Type-carrying literals (`:value`) and field options so the compiler can cast/format correctly.
- [ ] Positional references where useful (order-by → aggregation index).

## Gotchas

- **Validate the normalized query**, not the raw input — normalize first or the schema rejects legitimate variants.
- **Keep clauses uniform** (`[:tag ...]`) — irregular shapes break the generic walkers that power rewriting.
- **Put type info in the AST** (`:value`, field `:base-type`) — pushing type decisions to the dialect re-introduces per-dialect hacks (UUID-vs-text).
- **Two-version drift** — if you evolve the schema, add a migration/normalization so old queries still load.
- **Positional refs are fragile to reordering** — `[:aggregation 0]` must track aggregation order through rewrites.

## Origin (reference only)

metabase/metabase @ `master`: `src/metabase/legacy_mbql/schema.cljc` (legacy clause schema — grepped),
`src/metabase/legacy_mbql/schema/{helpers,macros}.clj(c|s)` (`defclause`), `src/metabase/lib/{core,query,schema}.cljc`
(MBQL 5 / the new `lib`), normalization in `query_processor/middleware/normalize_query.clj`.

**Gaps to verify (cost-capped):** the full clause inventory + exact option maps; MBQL-5 stage model vs
legacy differences; join/expression schema details; the normalization rules between versions.
