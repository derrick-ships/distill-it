# Native Design Tokens (build spec) — distilled from penpot

## Summary
A design-tokens system embedded in the document: **tokens** (typed named values) live in ordered
**token sets**, and **themes** select which sets are active. The *resolved* token map you actually
use is derived by **merging the active sets in order (later overrides earlier), then resolving
`{path}` references**. Theming = switching the active theme (which swaps sets). All token mutations
ride the file's change/undo system. W3C-flavored token shape for interop.

## Core logic (inlined)

### Token + type validation (`common/.../files/tokens.cljc`)
```clojure
;; Token attrs: :name (1-255), :type, :value, :description (<=2048)
;; schema:token = (merge cto/schema:token-attrs { :name .. :type .. :value .. :description .. })

;; value validation dispatches on :type
(defn make-token-value-schema [token-type] ...)
;; :opacity      -> number in [0,1]
;; :font-size    -> number
;; :font-weight  -> known weight | text
;; :font-family  -> [string...] | reference
;; :typography   -> {:font-family :font-size :font-weight :line-height
;;                   :letter-spacing :paragraph-spacing :text-decoration :text-case}
;; :shadow       -> [{:offset-x :offset-y :blur :spread :color (:inset?)} ...]
;; :color / default -> string (may be a reference or formula)

;; alias / reference detection — intentionally simple
(defn is-reference? [token]
  (str/includes? (:value token) "{"))     ; "{colors.primary.blue}" => reference
```
Resolution (conceptual — follow the chain until concrete):
```clojure
(defn resolve-token-value [tokens token]
  (loop [v (:value token) seen #{}]
    (if-let [ref (extract-ref v)]                 ; ref = the "colors.primary.blue" inside {…}
      (do (assert (not (seen ref)) "cycle")
          (recur (:value (get tokens ref)) (conj seen ref)))
      v)))                                         ; concrete value
```

### Library structure (`common/.../types/tokens_lib.cljc`)
```clojure
(defrecord Token [id name type value description modified-at])           ; INamedItem
(deftype   TokenSet [id name description modified-at tokens])            ; tokens = ordered-map name->Token
(defrecord TokenTheme [id name group description is-source external-id
                       modified-at sets])                               ; sets = #{set-name ...}
(deftype   TokensLib [sets themes active-themes])
;; sets:          nested ordered map of groups -> sets (internal prefixes "S-" set, "G-" group)
;; themes:        {group -> {theme-name -> TokenTheme}}
;; active-themes: #{"group/theme-name" ...}   (+ a hidden uuid/zero temp theme always present)
```

### The resolution chain — active themes → active sets → merged tokens (override by order)
```clojure
(get-active-theme-paths      this) ; -> the active-themes set
(get-active-themes           this) ; -> the TokenTheme records for those paths
(get-active-themes-set-names this) ; -> (into #{} (mapcat :sets) (get-active-themes this))

(get-tokens-in-active-sets [this]
  (let [theme-set-names  (get-active-themes-set-names this)
        all-set-names    (get-set-names this)              ; full ORDER of sets
        active-set-names (filter theme-set-names all-set-names)  ; keep order, keep active
        tokens (reduce (fn [tokens set-name]
                         (let [set (get-set-by-name this set-name)]
                           (merge tokens (get-tokens- set))))     ; later set overrides earlier
                       (d/ordered-map)
                       active-set-names)]
    tokens))
```
So "dark mode" = an active theme whose `:sets` includes `dark` instead of `light`; `merge` order
(driven by the global set ordering, filtered to active) gives override semantics. Resolved values are
derived on demand, never stored.

### Token edits are change types (see change-based-mutation-model build spec)
`:set-tokens-lib :set-token :set-token-set :set-token-theme :set-active-token-themes
:rename-token-set-group :move-token-set :move-token-set-group` — so token mutations get undo /
autosave / realtime sync for free.

## Data contracts
- **Token:** `{id, name (dot/slash path), type, value, description, modified-at}`.
- **value by type:** color→string; opacity→0..1; dimension/spacing/font-size→number;
  typography→map; shadow→list of shadow maps; font-family→string[]; any may be `"{ref.path}"`.
- **TokenSet:** `{id, name (slash hierarchy), tokens: ordered-map<name, Token>}`.
- **TokenTheme:** `{id, name, group, sets: Set<setName>}`.
- **TokensLib:** `{sets: ordered nested map, themes: {group->{name->theme}}, active-themes: Set<"group/name">}`.
- **Resolved view:** `ordered-map<name, Token>` = merge(active sets, in global order) then ref-resolve.

## Dependencies & assumptions
- Ordered maps (insertion order matters for both display and override). No external lib otherwise.
- A reference resolver with cycle detection. (For a richer one, see the style-dictionary build spec.)
- Assumes tokens + sets + themes live inside the document and mutate via your change/undo system.
- Swappable: serialize to the W3C Design Tokens JSON format for import/export interop.

## To port this, you need:
- [ ] A typed Token shape (`name`/`type`/`value`/`description`) with per-type value validation.
- [ ] Ordered token sets and themes that select active set names.
- [ ] A derive step: active themes → active set names (filtered to global order) → merge → resolve refs.
- [ ] `{path}` reference detection (cheap: contains "{") + a resolver with cycle detection.
- [ ] Token mutations wired through your existing change/undo/persistence path (don't build a second one).

## Gotchas
- **Merge order is the theming contract** — sets must merge in a *stable global order* filtered to
  active, not in active-set arbitrary order, or overrides become nondeterministic.
- **Reference cycles** (`a -> b -> a`) must be detected or resolution loops forever. Track a `seen` set.
- Multi-reference / formula values (`"{a} {b}"`, `"{x} * 2"`) need a richer resolver than single-ref;
  `is-reference?` only flags presence — the resolver must handle the composite case.
- Resolved values are derived; if you cache them for perf, invalidate on any token/set/theme/active
  change — or just recompute (penpot recomputes).
- Typography/shadow tokens are *composite* — their sub-fields can themselves be references; resolve recursively.
- The always-present hidden theme (`uuid/zero`) is a base layer; forget it and the merge has no floor.

## Origin (reference only)
`common/src/app/common/files/tokens.cljc` (token schema, types, `is-reference?`),
`common/src/app/common/types/tokens_lib.cljc` (Token/TokenSet/TokenTheme/TokensLib,
`get-tokens-in-active-sets` resolution). Token change types in
`common/src/app/common/files/changes.cljc`.
