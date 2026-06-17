# Reference Resolution Engine — from [style-dictionary](https://github.com/style-dictionary/style-dictionary)

> Domain: [[_domain]] · Source: https://github.com/style-dictionary/style-dictionary · NotebookLM: <link once added>

## What it does

Design tokens reference each other. You define `color.brand.500 = "#1473E6"` once, then everywhere else you write `"{color.brand.500}"` instead of repeating the hex. Your button's background is `"{color.brand.500}"`, your link color is `"{color.brand.500}"`, and so on. The reference resolution engine is what turns all those `{...}` placeholders into the real values when the tokens are built — and it handles the hard cases: a reference pointing at another reference (chains), several references mixed into one string (`"1px solid {color.border}"`), references that point at whole objects, and the dreaded circular reference (A points to B points back to A).

## Why it exists

Without references, a token file is just a flat list of literal values — and the moment your brand blue changes, you're find-replacing a hundred places. References let tokens express *relationships*: "this border uses the same color as that text," "this is the base size and that's twice it." Change the base, everything downstream updates. References are what make a token system a system rather than a spreadsheet.

There's also a subtler need: sometimes you *don't* want references resolved away. When you generate CSS custom properties, you'd rather emit `var(--color-brand-500)` than the raw hex, so the cascade still works at runtime. The engine supports keeping references in the output (`outputReferences`) — but only when it's safe.

## How it actually works

**Spotting a reference.** A reference is anything inside curly braces: the engine uses a regex, `\{([^}]+)\}`, that matches `{` followed by any run of non-`}` characters followed by `}`. The text inside is a dot-separated path: `color.brand.500` becomes the path `["color", "brand", "500"]`. There's a fast pre-check (`does the string contain a "{" at all?`) before the regex runs, to skip the vast majority of plain values cheaply.

**Looking up the target.** The path walks the token tree (or, in the newer flat-Map version, a direct `map.get("{color.brand.500}")` keyed by the full reference string). One nicety from the DTCG spec: a reference points at a *token*, not its value field. So `{color.brand.500}` resolves to the token object, and the engine automatically drills into its `.value`/`.$value` for you.

**Substituting.** If the referenced value is a string or number, the engine replaces the `{...}` inside the surrounding string. If the whole value *is* just one reference and it points at a number, the result is cast back to a number (so `16` doesn't become `"16"`). If it points at an object or array (say, a color expressed as `{h, s, l}`), the whole value simply *becomes* that object — you can't splice an object into the middle of a string.

**Chasing chains.** After substituting once, the engine checks: does the result *still* contain `{...}`? If so, it recurses, resolving the next hop. This is how `A → B → C` works — each hop resolves until nothing's left.

**Catching cycles.** As it follows a chain, the engine keeps a stack of the token names it's currently resolving. Before each hop it checks whether the next reference is already on that stack — if it is, that's a cycle, and it throws an error like `Circular definition cycle: a, b, c, a`. Once a cycle is found, every token in it is marked so the engine doesn't re-report the same cycle over and over.

**Keeping references in output, safely.** Two guard functions decide whether a format may emit the original `{...}` instead of the resolved value:
- One checks that *every* token the value references actually survived the platform's filter. If a referenced token was filtered out, emitting `var(--that-token)` would be a dangling reference — so it resolves instead.
- The other checks whether a transform *changed* the value beyond plain resolution. If a px-to-rem transform turned `16px` into `1rem`, emitting the original reference `{size.base}` would throw away that conversion — so again, it resolves instead.

## The non-obvious parts

- **There are two resolvers, not one.** An older one walks a nested object tree; a newer one works on a flat `Map` keyed by the full `{dotted.path}` string. They share the algorithm but differ in details (which regex variant, whether the ignore-list is an array or a Set). The public entry point dispatches based on whether you pass a Map.
- **The `.original` copy is never resolved.** Every token keeps a snapshot of its pre-transform self under `.original`, and the resolver explicitly skips that key. Otherwise it would rewrite the historical record.
- **DTCG alias semantics are baked in.** A reference resolves to the token, and the engine fishes out `.value`/`.$value` itself — matching the community spec where aliases don't spell out the value field.
- **Unresolved references don't crash the build by default.** They're collected as grouped warnings and surfaced together at the end of the phase, rather than throwing on the first one — so you see *all* your broken references at once.
- **`outputReferences` is conditional, not a flag you just flip.** The two guard functions mean the engine will quietly fall back to a resolved value whenever keeping the reference would be wrong (filtered-out target, or a transform changed the value). That safety net is the non-obvious value.

## Related

- [[token-pipeline-orchestration--from-style-dictionary]] — the build loop that calls the resolver each pass, interleaved with transforms
- [[transforms-and-transform-groups--from-style-dictionary]] — `transitive` transforms exist precisely because some values can't be transformed until references resolve
- [[register-extensibility-api--from-style-dictionary]] — formats (which decide whether to use `outputReferences`) are registered here
