# Transforms & Transform Groups — from [style-dictionary](https://github.com/style-dictionary/style-dictionary)

> Domain: [[_domain]] · Source: https://github.com/style-dictionary/style-dictionary · NotebookLM: <link once added>

## What it does

A raw token says `color.background.primary = "#1473E6"`. But CSS wants a kebab-case name (`--color-background-primary`), iOS wants a `UIColor`, Android wants an 8-digit hex, and a rem-based design system wants `16px` rewritten as `1rem`. Transforms are the small, composable functions that mutate each token — its **name**, its **value**, or its **attributes** — to fit a target platform. Transform *groups* are named, ordered bundles of these transforms ("give me the standard `css` set," "give me the `ios-swift` set") so you don't hand-list a dozen transforms per platform.

## Why it exists

The same logical token has a different *physical* form on every platform. Hardcoding "for CSS do X, for iOS do Y" into the build would make the system rigid and unextensible. Instead, Style Dictionary breaks platform-fitting into tiny single-purpose functions and lets you compose them. Want a custom naming scheme? Write one name transform and slot it in. Want px→rem? There's a value transform for that. The platform output is just "which ordered list of transforms do I run." That composability is the whole reason the tool can target so many platforms without bloating.

## How it actually works

**Three kinds of transform.** Every transform declares a `type`:
- **name** — rewrites `token.name` (e.g. `name/kebab` joins the prefix + path into kebab-case).
- **value** — rewrites the token's value (e.g. `color/hex` turns a color into `#rrggbb`, `size/rem` turns dimensions into rem).
- **attribute** — adds metadata under `token.attributes` (e.g. `attribute/cti`).

**The CTI convention.** This is the backbone. `attribute/cti` reads the token's *path* and labels each segment: position 0 = **c**ategory, 1 = **t**ype, 2 = **i**tem, 3 = subitem, 4 = state. So `color.background.primary` becomes `{ category: "color", type: "background", item: "primary" }`. Lots of other transforms and filters key off these attributes — which is exactly why `attribute/cti` is the *first* transform in nearly every built-in group.

**Filters decide what each transform touches.** A transform can carry a `filter` predicate (older code calls it `matcher`). `color/hex` only runs on tokens that look like colors; `size/rem` only on dimensions. No filter means "apply to every token."

**Each token, each transform, in order.** For one token, the engine walks the platform's ordered transform list and applies each that passes its filter. Order is the contract — there's no dependency graph. `attribute/cti` goes first so later transforms can rely on `category` being set; name transforms generally use the raw path rather than CTI, so they're more order-independent, but value transforms that operate on assembled/compound values often need to run late.

**Transform groups are just name lists.** A group like `css` is literally an ordered array of transform names. At build time the engine expands the group into the real transform objects and appends any extra `transforms` you listed. The built-in `css` group, for instance, runs: `attribute/cti`, `name/kebab`, `time/seconds`, `html/icon`, `size/rem`, `color/css`, `asset/url`, `font-family/css`, `cubic-bezier/css`, and several `*/shorthand` transforms for stroke, border, typography, transition, and shadow.

**The `transitive` escape hatch.** By default, a value transform is *skipped* if the token's original value was a reference like `{some.token}` — the idea being "resolve the reference first, then transform the real value on a later pass." But some transforms need to run on values that were *assembled from* references (a shadow built out of `{color}` + `{blur}` + `{offset}`). Marking a transform `transitive: true` opts it into running after resolution, on the composed value. This is why the transform and reference-resolution steps are interleaved in a loop rather than run once each.

## The non-obvious parts

- **`attribute/cti` first, always.** The category/type/item labels it produces are depended on by downstream transforms and filters. Reorder it and things silently misbehave.
- **`matcher` was renamed to `filter`, silently.** The current code only reads `filter`. An old transform written with `matcher` won't error — it'll just apply to *every* token, which is a quiet, nasty behavior change.
- **Order is the only dependency mechanism.** There's no topological sort. The author of a transform group hand-orders the list, and getting it wrong produces wrong output, not an error.
- **Value transforms read the *original* value to decide whether to defer.** They check the original (pre-transform) value for references, but write to a clone — so a transform never sees a half-transformed input.
- **Transforms are async.** Each transform function is awaited, so a value transform can do I/O (e.g. read an asset file to inline or base64 it).
- **A value transform returning `undefined` signals "defer me."** That's how a token blocked on an unresolved reference gets pushed to the next loop pass instead of being written with a broken value.

## Related

- [[token-pipeline-orchestration--from-style-dictionary]] — drives the transform→resolve loop and calls `transformMap` each pass
- [[reference-resolution-engine--from-style-dictionary]] — the reason `transitive` exists; transforms and resolution interleave
- [[register-extensibility-api--from-style-dictionary]] — how you register a custom transform or transform group
