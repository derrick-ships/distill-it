# Transforms & Transform Groups (build spec) — distilled from style-dictionary

## Summary

Build the per-token mutation layer: small composable transforms of three types (name/value/attribute), each with an optional `filter` predicate, run in a fixed order over every token. Named transform *groups* bundle ordered transform-name lists per platform. A `transitive` flag lets a value transform run after reference resolution. Transforms are async and integrate with the orchestrator's transform↔resolve convergence loop via a deferral signal.

## Core logic (inlined)

### Transform object shape
```ts
type Transform = {
  type: 'name' | 'value' | 'attribute';   // required
  name: string;                            // injected by config resolution from the registry key
  transitive?: boolean;                    // value transforms only: run AFTER ref resolution
  filter?: (token: Token, options: Config) => boolean;   // optional; replaces deprecated `matcher`
  transform: (token: Token, config: PlatformConfig, options: Config, vol?: Volume) => any;  // required, async-capable
}
```

### Token setup (once per token, before transforms)
```
tokenSetup(token, name /* last path segment */, path /* full ancestor array */):
  if token.original exists: return        # idempotent
  token.original   = structuredClone(token) minus {filePath, isSource}   # pre-transform snapshot
  token.name       = token.name || name
  token.attributes = token.attributes || {}
  token.path       = structuredClone(path)
```

### Apply all transforms to one token (`transformToken`, async, returns a NEW object)
```
transformToken(token, config, options, vol):
  token = structuredClone(token)                 # pure: never mutate input
  for transform in config.transforms:            # in array order
     if transform.filter && !transform.filter(token, options): continue
     switch transform.type:
        'name':
           token.name = await transform.transform(token, config, options, vol)
        'value':
           valProp = options.usesDtcg ? '$value' : 'value'
           if usesReferences(token[valProp]): continue          # current value still a ref → skip this pass
           originalHadRef = usesReferences(token.original[valProp])
           if !originalHadRef || transform.transitive === true:
              result = await transform.transform(token, config, options, vol)
              if result === undefined: return undefined          # SIGNAL: defer this token to next loop pass
              token[valProp] = result
        'attribute':
           token.attributes = { ...token.attributes, ...await transform.transform(token, config, options, vol) }
  return token
  # on a thrown transform error: collect into GroupMessages 'TransformErrors', return safe fallback
  #   (existing token.attributes / .name / .value) so the build continues and reports all errors at once
```

### Map iteration + deferral (`transformMap`, called repeatedly by the orchestrator)
```
transformMap(tokenMap, config, options, ctx /* {transformedPropRefs, deferredPropValueTransforms} */, vol):
  await Promise.all(for each [key, token] of tokenMap):
     if transformedPropRefs.has(key): continue
     tokenSetup(token, lastSegment(token.path), token.path)
     valProp = options.usesDtcg ? '$value' : 'value'
     if usesReferences(token[valProp]):
        deferredPropValueTransforms.add(key); continue          # blocked on a ref — try next pass
     result = await transformToken(token, config, options, vol)
     if result === undefined:
        deferredPropValueTransforms.add(key)                    # value transform asked to defer
     else:
        tokenMap.set(key, result)
        transformedPropRefs.add(key)
        deferredPropValueTransforms.delete(key)
  # orchestrator then runs resolveMap, and loops until deferredPropValueTransforms stops shrinking
```

### Config resolution (group name → ordered Transform[])
```
transformConfig(platformConfig, dictionary, platformName):
  names = (dictionary.hooks.transformGroups[platformConfig.transformGroup] ?? [])  # throws if group unknown
            .concat(platformConfig.transforms ?? [])
  config.transforms = names.map(name => {
     t = dictionary.hooks.transforms[name]    # throws if name not registered
     return { ...t, name }
  })
  # ...also resolves fileHeaders/filters/formats/actions (see orchestration + register features)
```

## Concrete built-in transforms (verbatim behavior)

```js
// attribute/cti — maps path[0..4] onto category/type/item/subitem/state; existing attrs win
transform(token) {
  const attrNames = ['category','type','item','subitem','state'];
  const out = {};
  for (let i=0; i<token.path.length && i<attrNames.length; i++) out[attrNames[i]] = token.path[i];
  return Object.assign(out, token.attributes || {});
}

// name/kebab — join optional platform prefix + full path → kebab-case
transform(token, config) { return kebabCase([config.prefix].concat(token.path).join(' ')); }

// color/hex — value, filter: isColor. #rrggbb, or #rrggbbaa when alpha<1
filter: isColor,
transform(token, _, options) {
  const c = getColor(token, options);
  return c.getAlpha() === 1 ? c.toHexString() : c.toHex8String();
}

// size/rem — value, filter: isDimension || isFontSize
transform(token, _, options) {
  const v = options.usesDtcg ? token.$value : token.value;
  const { value, unit } = getTokenDimensionValue(v);
  const n = parseFloat(`${value}`);
  if (isNaN(n)) throwSizeError(...);
  if (unit !== undefined) return `${value}${unit}`;
  if (n === 0) return value;       // 0 stays unitless
  return `${n}rem`;
}

// font-family/css — value, TRANSITIVE: true (operates on composed/resolved value)
// shadow/css/shorthand — value, TRANSITIVE: true (stringifies to CSS box-shadow shorthand)
```

## Built-in transform groups (exact ordered contents)

| Group | Ordered transform names |
|---|---|
| `web` | attribute/cti, name/kebab, size/px, color/css |
| `js` | attribute/cti, name/pascal, size/rem, color/hex |
| `css` | attribute/cti, name/kebab, time/seconds, html/icon, size/rem, color/css, asset/url, font-family/css, cubic-bezier/css, stroke-style/css/shorthand, border/css/shorthand, typography/css/shorthand, transition/css/shorthand, shadow/css/shorthand |
| `scss` | identical to `css` |
| `less` | same as `css` but `color/hex` instead of `color/css` |
| `html` | attribute/cti, attribute/color, name/human |
| `android` | attribute/cti, name/snake, color/hex8android, size/rem/to/sp, size/rem/to/dp |
| `compose` | attribute/cti, name/camel, color/composeColor, size/compose/em, size/compose/rem/to/sp, size/compose/rem/to/dp |
| `ios` | attribute/cti, name/pascal, color/UIColor, content/objc/literal, asset/objc/literal, size/rem/to/float |
| `ios-swift` | attribute/cti, name/camel, color/UIColorSwift, content/swift/literal, asset/swift/literal, size/swift/rem/to/CGFloat |
| `ios-swift-separate` | identical to `ios-swift` |
| `flutter` | attribute/cti, name/camel, color/hex8flutter, size/flutter/rem/to/double, content/flutter/literal, asset/flutter/literal |
| `flutter-separate` | identical to `flutter` |
| `react-native` | name/camel, color/css, size/object |
| `assets` | attribute/cti |

## Data contracts

- Input: a `Map<string, Token>` keyed by `"{dotted.path}"`. `Token` has `value`/`$value`, `name`, `path: string[]`, `attributes`, `original` (post-`tokenSetup`).
- Output: same Map with each token's `name`/`value`/`attributes` mutated; ready for formats.
- `hooks.transforms`: `{ [name]: Transform }`. `hooks.transformGroups`: `{ [name]: string[] }`.
- Errors batched into `GroupMessages` groups `TransformErrors` / `MissingRegisterTransformErrors`.

## Dependencies & assumptions

- `structuredClone` (pure transform application + token snapshot).
- A `usesReferences(value)` predicate (from the references feature) — gates value-transform deferral.
- Case helpers (`kebabCase`, `pascalCase`, `camelCase`, `snakeCase` — `change-case` in the original).
- Color lib for color transforms (`tinycolor2`/`colorjs.io` in the original); dimension parsing helper.
- The orchestrator's convergence loop (calls `transformMap` then `resolveMap` repeatedly).

## To port this, you need:

- [ ] The three transform types and the `{type,name,filter?,transitive?,transform}` shape.
- [ ] `tokenSetup` to stamp `original`/`name`/`path`/`attributes` once per token, idempotently.
- [ ] CTI attribute mapping (or your own attribute convention) registered first in each group.
- [ ] Ordered group→names registry, expanded to Transform objects at build time (throw on unknown names).
- [ ] The deferral protocol: value transform returns `undefined` ⇒ token re-queued for the next loop pass.
- [ ] `transitive` handling so compound/assembled-from-reference values transform after resolution.
- [ ] Batched error collection so one bad transform doesn't abort the whole build.

## Gotchas

- **`attribute/cti` (or your attribute transform) MUST run first.** Downstream transforms/filters read `attributes.category` etc. No dependency resolver enforces this — order is the only contract.
- **`matcher` is deprecated in favor of `filter` and the change is silent.** Code reads only `filter`; a transform written with `matcher` applies to *every* token. Normalize on read if you support legacy.
- **Value transforms skip when the *current* value still has a reference**, and check the *original* value to decide whether deferral is permanent vs. transitive. Read original, write clone.
- **Returning `undefined` from a value transform is meaningful** — it's the defer signal, not "no change." Don't return `undefined` to mean "leave as-is."
- **Transforms are awaited** — they may be async (asset I/O). Don't assume synchronous.
- **`size/rem` keeps `0` unitless and preserves an explicit unit if present** — don't blindly append `rem`.
- **Some group entries are aliases** (`scss`≡`css`, `ios-swift-separate`≡`ios-swift`, `flutter-separate`≡`flutter`). `react-native` notably omits `attribute/cti`.

## Origin (reference only)

Repo: https://github.com/style-dictionary/style-dictionary (branch `main`). Files: `lib/transform/{token,tokenSetup,config,map}.js`, `lib/common/transforms.js` (built-in transform registry), `lib/common/transformGroups.js` (group definitions). Transform/group names are exported as enums from `lib/enums/`. `shadow/css/shorthand` and `size/object` full bodies were not captured verbatim — verify before relying on their exact output format.
