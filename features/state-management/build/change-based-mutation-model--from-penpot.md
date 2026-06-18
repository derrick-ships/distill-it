# Change-Based Document Mutation Model (build spec) — distilled from penpot

## Summary
Never mutate the document directly. Represent every edit as a serializable **change** (a map tagged
with `:type`), apply changes via a dispatch table, and **build each forward change together with its
inverse** so undo/redo, incremental persistence, and realtime collaboration all reduce to "replay a
list of changes (forward or backward)." This is event-sourcing / the command pattern applied to a
design file. Language here is Clojure, but the model is language-agnostic.

## Core logic (inlined)

### 1. The change vocabulary (dispatch on `:type`)
~40 change types. Object/page level:
`:add-obj :mod-obj :del-obj :fix-obj :mov-objects :reorder-children :reg-objects`,
`:add-page :mod-page :del-page :mov-page :set-option :set-guide :set-flow :set-default-grid`,
`:set-plugin-data :set-comment-thread-position :set-base-font-size`. Library:
`:add-color/:mod-color/:del-color`, `:add-media/...`, `:add-component/:mod-component/:del-component/:restore-component/:purge-component`,
`:add-typography/...`. Tokens: `:set-tokens-lib :set-token :set-token-set :set-token-theme
:set-active-token-themes :rename-token-set-group :move-token-set :move-token-set-group`.

### 2. Applying changes — a multimethod fold (`changes.cljc`)
```clojure
(defmulti process-change (fn [_ change] (:type change)))

(defn process-changes
  ([data items] (process-changes data items true))
  ([data items verify?]
   (reduce #(or (process-change %1 %2) %1) data items)))   ; fold each change into file data

(defmethod process-change :add-obj
  [data {:keys [id obj page-id component-id frame-id parent-id index ignore-touched]}]
  (let [update-container #(ctst/add-shape id obj % frame-id parent-id index ignore-touched)]
    (if page-id
      (d/update-in-when data [:pages-index page-id] update-container)
      (d/update-in-when data [:components component-id] update-container))))

(defmethod process-change :mod-obj
  [data {:keys [page-id component-id] :as change}]
  (if page-id
    (d/update-in-when data [:pages-index page-id :objects] process-operations change)
    (d/update-in-when data [:components component-id :objects] process-operations change)))

;; :mod-obj payload is itself a list of fine-grained operations:
(defmulti process-operation (fn [_ op] (:type op)))   ; :set | :set-touched | :set-remote-synced | :assign
;; :set => (ctn/set-shape-attr shape (:attr op) (:val op) :ignore-touched .. :ignore-geometry ..)

(defmethod process-change :del-obj
  [data {:keys [id page-id component-id ignore-touched]}] ...)   ; inverse of :add-obj
(defmethod process-change :mov-objects [data change] ...)        ; reparent + reindex
```
A single shape edit is therefore: `{:type :mod-obj :page-id .. :id .. :operations [{:type :set :attr :fills :val ...}]}`.

### 3. Building changes WITH inverses — the dual track (`changes_builder.cljc`)
```clojure
(defn empty-changes []
  {:redo-changes []        ; vector: cheap append, forward order
   :undo-changes '()})     ; list:  cheap prepend, reverse order

;; attach a snapshot so inverses can capture OLD values
(defn with-objects [changes objects]
  (let [fdata (-> (ctf/make-file-data (uuid/next) uuid/zero)
                  (assoc-in [:pages-index uuid/zero :objects] objects))]
    (vary-meta changes assoc ::file-data fdata ::applied-changes-count 0)))

(defn add-object [changes obj {:keys [index ignore-touched] :as opts}]
  (let [add-change {:type :add-obj :id (:id obj) :obj obj :page-id .. :parent-id .. :index index}
        del-change {:type :del-obj :id (:id obj) :page-id ..}]      ; the inverse
    (-> changes
        (update :redo-changes conj add-change)
        (update :undo-changes conj del-change)                     ; prepend -> auto-reverses
        (apply-changes-local))))                                   ; keep builder's snapshot current

;; attribute updates: compute paired forward/backward operations from old vs new shape
(defn update-shapes [changes ids update-fn {:keys [attrs] :as opts}]
  ;; for each shape: old-obj -> new-obj = (update-fn old-obj)
  (let [[rops uops] (-> (or attrs (d/concat-set (keys old-obj) (keys new-obj)))
                        (generate-operations old-obj new-obj))]    ; rops=new vals, uops=old vals
    (cond-> changes
      (seq rops) (update :redo-changes conj (assoc change :operations rops))
      (seq uops) (update :undo-changes conj (assoc change :operations (vec uops))))))
```
`generate-operations` diffs old vs new and emits `:set` ops for the redo (new values) and matching
`:set` ops for the undo (prior values). Undo is just `process-changes(data, undo-changes)`.

### 4. Versioning + migrations (`migrations.cljc`, `validate.cljc`, `repair.cljc`)
File carries a `:version`. On load, run the ordered migration chain `migrate(data, from→current)`;
then `validate` structural invariants and `repair` malformed data. Same "ordered replayable list"
discipline, applied to the format itself.

## Data contracts
- **Change:** `{:type keyword, :page-id|:component-id uuid, :id uuid, ...type-specific...}`.
- **Operation (inside `:mod-obj`):** `{:type :set, :attr keyword, :val any}` (or `:set-touched` /
  `:set-remote-synced` / `:assign`).
- **Changes bundle:** `{:redo-changes [change...], :undo-changes (change...)}` + metadata snapshot.
- **File data:** `{:version int, :pages-index {uuid -> page}, :components {uuid -> comp}, :colors,
  :typographies, :tokens-lib, ...}`; a page has `:objects {uuid -> shape}`.
- **Apply:** `process-changes(file-data, [change...]) -> file-data'` (pure fold).

## Dependencies & assumptions
- Pure data + a dispatch mechanism (multimethod / switch / map of handlers keyed by type). No libs required.
- Persistent/immutable data structures help (cheap structural sharing for snapshots + undo) but aren't mandatory.
- An ordered-map for `:objects` if z-order/insertion order matters.
- Swappable: serialize changes as JSON/MessagePack for the wire; the model is identical.

## To port this, you need:
- [ ] A closed set of change types covering every mutation your document allows (resist ad-hoc mutation).
- [ ] A `process-change(data, change) -> data` handler per type, and a `reduce` to apply a list.
- [ ] A builder that, for each edit, emits the forward change **and** its inverse while the old value is in scope.
- [ ] Two accumulators: redo (append/forward) and undo (prepend/reverse).
- [ ] Fine-grained `:set`-style operations for partial-object edits (don't resend whole objects).
- [ ] A `:version` field + ordered migration chain for format evolution; a validate/repair pass.

## Gotchas
- **Inverses must be captured at build time** from the pre-edit state. Compute them later (after
  applying) and you've lost the old values — the single most common way to get this wrong.
- Undo list order: prepend (or reverse before replaying). Append to both and undo runs backwards-wrong.
- `:add-obj` must record enough (`parent-id`, `index`, `frame-id`) for its `:del-obj` inverse to
  fully restore position — partial inverses corrupt z-order/hierarchy on undo.
- Component overrides need a "touched" flag carried as an operation, or a later sync silently
  overwrites local edits.
- Concurrent edits: replaying remote changes is fine for independent objects; truly conflicting edits
  to the same attribute still need a resolution policy (last-write-wins or operational transform) —
  the change model makes conflicts *visible* but doesn't auto-resolve them.
- Keep handlers total/forgiving: an unknown or stale change type should no-op (return data), not throw,
  or one bad change breaks the whole fold (note `(or (process-change ..) data)`).

## Origin (reference only)
`common/src/app/common/files/changes.cljc` (process-change multimethod + all types),
`common/src/app/common/files/changes_builder.cljc` (empty-changes, with-objects, add-object,
update-shapes — the redo/undo pairing), `common/src/app/common/files/page_diff.cljc`,
`migrations.cljc`, `validate.cljc`, `repair.cljc`.
