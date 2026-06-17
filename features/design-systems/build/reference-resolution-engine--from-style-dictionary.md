# Reference Resolution Engine (build spec) — distilled from style-dictionary

## Summary

Build the engine that resolves `{dotted.path}` references inside design-token values: chains (A→B→C), multiple references in one string, references to objects/arrays, number-type preservation, circular-reference detection, and an `outputReferences` mode that keeps references in output only when safe. Two variants exist — a nested-object resolver and a flat-`Map` resolver — sharing one algorithm.

## Core logic (inlined)

### Reference syntax (the regexes)
```js
// Default — capture group 1 = INNER text (no braces). Used by resolveObject/usesReferences/getReferences.
const regexDefault = /\{([^}]+)\}/g;
// Capture-groups variant — capture group 1 = FULL match WITH braces. Used by the Map resolver.
const regexCaptureGroups = /(\{[^}]+\})/g;
```
- `[^}]+` ⇒ one or more non-`}` chars; **no nesting**.
- Path separator is `.` (hard-coded): `getPathFromName("color.brand.500")` → `["color","brand","500"]`; `getName(path)` is the inverse.

### Entry point — nested object (`resolveObject`)
```
resolveObject(object, opts = { ignoreKeys:['original'], ignorePaths:[], usesDtcg:false }):
  obj = structuredClone(object)
  traverseObj(obj):                              # recursive walk, tracks current_context = path[]
     for each key:
        if key in opts.ignoreKeys: skip          # default ['original'] — never resolve the snapshot
        if value is string && value.indexOf('{') > -1:    # fast guard before regex
           value = _resolveReferences(value, obj, {...opts, warnImmediately:false, current_context, foundCirc})
  return obj
```

### Core resolver (`_resolveReferences`, nested-object version)
```
_resolveReferences(value, tokens, { usesDtcg, warnImmediately, ignorePaths,
                                    current_context=[], stack=[], foundCirc={}, firstIteration=true }):
  if firstIteration: stack.push(getName(current_context))   # seed cycle detector with own name
  to_ret = value
  value.replace(regexDefault, (match, variable) => {        # called once per {...} occurrence
     variable = variable.trim()                              # inner path text
     # cycle checks BEFORE resolving:
     if Object.hasOwn(foundCirc, variable): return            # already known circular → skip silently
     if stack.indexOf(variable) !== -1:                       # cycle!
        circ = stack.slice(stack.indexOf(variable))
        circ.forEach(n => foundCirc[n] = true)
        error "Circular definition cycle: " + [...circ, variable].join(', ')
        (throw if warnImmediately, else queue in GroupMessages.PropertyReferenceWarnings)
        return
     stack.push(variable)
     path = getPathFromName(variable)
     ref  = getValueByPath(path, tokens)        # nested: tokens[p0][p1]...  |  Map: tokens.get('{'+path.join('.')+'}')
     # DTCG alias: if path does NOT end in value/$value but ref has .value/.$value, drill in
     if ref is string|number:
        to_ret = to_ret.replace(match, String(ref))
        if usesReferences(to_ret): to_ret = _resolveReferences(to_ret, tokens, {...opts, stack, foundCirc, firstIteration:false})  # transitive
        if typeof ref === 'number' && to_ret === ref.toString(): to_ret = ref   # number preservation
     else if ref !== undefined:
        to_ret = ref                            # object/array — whole value becomes ref
     else:
        warn "<current_context> tries to reference <variable>, which is not defined."  (throw or queue)
     stack.pop()
  })
  return to_ret
```

### Map variant (`resolveReferencesMap.js`) — differences only
- Uses `regexCaptureGroups` (full match incl. braces).
- Lookup: `tokenMap.get(trimmedMatch)?.[valProp]` — Map keyed by full `"{color.brand.500}"` string.
- `ignorePaths` is a `Set<string>`; `current_context` is a `string`.
- Extra option `objectsOnly`: only resolve references whose target is an object.
- Type preservation: if `to_ret === match` (value is *exclusively* the reference), return the ref as-is (preserves object/array/boolean/number). Otherwise stringify into surrounding text.
- Cycle error text: `"Circular definition cycle for <context> => a, b, c, a"`.

### `usesReferences(value)` → boolean
True if a string contains `{...}`, or (recursively) if any string leaf of an object does.

### `getReferences(value, tokens, opts, references=[])` → Token[]
For each `{...}` match: strip trailing `.value`/`.$value`, look up the token by path, push the *full token object* (with an added `.ref` = path array). If not in the filtered set, fall back to `unfilteredTokens` and queue a `FilteredOutputReferences` warning. Used by formats for `outputReferences`.

### outputReferences guards (format-time decisions)
```
outputReferencesFilter(token, { dictionary, usesDtcg }) -> boolean:
  refs = getReferences(token.original.value, ...)
  return refs.every(r => dictionary.allTokens includes r)    # all referenced tokens survived the filter?
  # side-effect: clears queued FilteredOutputReferences warnings for refs being resolved anyway

outputReferencesTransformed(token, { dictionary, usesDtcg }) -> boolean:
  return token.value === resolveReferences(token.original.value, dictionary..., { /* refs only, no transforms */ })
  # i.e. emit the reference ONLY if no transform changed the value beyond plain resolution
```
A format calls one of these per token; `true` ⇒ emit original `{...}` syntax, `false` ⇒ emit the resolved (and possibly transformed) value.

## Data contracts

```ts
// tokens passed to the resolver is EITHER the nested tree OR a Map:
type NestedTokens = { [key: string]: NestedTokens | Token }
type FlatTokenMap = Map<string /* "{a.b.c}" */, Token>

type Token = { value?: any; $value?: any; original?: Token; name?: string; path?: string[]; ref?: string[] }

type ResolveOpts = {
  usesDtcg?: boolean;
  warnImmediately?: boolean;        // throw on first error vs queue grouped
  ignoreKeys?: string[];            // default ['original']
  ignorePaths?: string[] | Set<string>;
  current_context?: string[] | string;
  stack?: string[];                 // cycle-detection chain (internal)
  foundCirc?: Record<string,boolean>;
  objectsOnly?: boolean;            // Map variant only
}
```
Reference grammar: `{` + `[^}]+` (dot-separated path) + `}`. Multiple per string allowed. A reference to a token resolves to its `.value`/`.$value` (DTCG alias rule).

## Dependencies & assumptions

- `structuredClone` for the non-destructive walk (nested variant).
- A grouped-warning collector (`GroupMessages` with a `PropertyReferenceWarnings` group) — errors queue here unless `warnImmediately`.
- Helpers: `getPathFromName` (split on `.`), `getName` (join with `.`), `getValueByPath` (walk nested or `Map.get`), `usesReferences`.
- For `outputReferences`: a `dictionary` carrying both filtered `allTokens` and `unfilteredTokens`.

## To port this, you need:

- [ ] A token store addressable by dotted path (nested object walk or a Map keyed by `"{a.b.c}"`).
- [ ] The two regexes (inner-capture and full-capture) — pick per store type.
- [ ] A `stack` + `foundCirc` cycle detector threaded through recursion by reference.
- [ ] A grouped-warning sink so unresolved/circular refs batch instead of throwing on first.
- [ ] If you support `outputReferences`: a filtered/unfiltered dictionary and the two guard predicates.
- [ ] An `.original` (pre-transform) snapshot per token, and the discipline to never resolve inside it.

## Gotchas

- **Skip `.original` (`ignoreKeys`).** Resolving inside the snapshot corrupts the historical value and breaks `outputReferences` (which compares against `token.original.value`).
- **Number type preservation is explicit** — `{size.base}` → `16` must come back as the number `16`, not `"16"`. Only triggers when the whole value is exactly that one reference.
- **Object references can't be embedded in a string.** If a value is `"shadow {x}"` and `{x}` is an object, that's nonsensical; objects only work when the value is *exclusively* the reference.
- **Cycle detection marks the whole cycle in `foundCirc`** so you don't emit N copies of the same error. Don't reset `foundCirc`/`stack` between hops — pass them by reference.
- **DTCG alias drilling**: `{color.brand}` resolves to the token, then auto-extracts `.value`/`.$value`. If you forget this, references resolve to the whole token object instead of its value.
- **Two resolvers, two `ignorePaths` types** (array vs Set) and two regex variants — keep them straight; the public dispatch is `tokens instanceof Map`.
- **`lib/resolve.js` is a red herring** — it's a POSIX/Win32 *path* resolver, unrelated to token references.
- **Unresolved refs default to grouped warnings, not throws.** Make sure the orchestrator actually flushes `PropertyReferenceWarnings` or broken references pass silently.

## Origin (reference only)

Repo: https://github.com/style-dictionary/style-dictionary (branch `main`). Files: `lib/utils/resolveObject.js`, `lib/utils/references/{resolveReferences,resolveReferencesMap,createReferenceRegex,getPathFromName,getName,getValueByPath,usesReferences,getReferences,outputReferencesFilter,outputReferencesTransformed}.js`. (`lib/resolve.js` is a path util, not part of this feature.)
