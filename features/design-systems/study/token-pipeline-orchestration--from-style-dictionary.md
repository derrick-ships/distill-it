# Token Pipeline Orchestration — from [style-dictionary](https://github.com/style-dictionary/style-dictionary)

> Domain: [[_domain]] · Source: https://github.com/style-dictionary/style-dictionary · NotebookLM: <link once added>

## What it does

Style Dictionary takes one set of design tokens — colors, sizes, spacing, fonts, written once as JSON or JS — and spits out ready-to-use style files for every platform you target: CSS custom properties, SCSS variables, JS objects, iOS Swift, Android XML, Flutter, React Native, and so on. The orchestration engine is the conveyor belt that makes this happen. You hand it a config that says "here are my token files, and here are the platforms I want output for," call `buildAllPlatforms()`, and it writes all the files.

The job-to-be-done: **define a style once, use it everywhere, and never hand-sync the same hex code across five codebases again.**

## Why it exists

Design teams keep drifting out of sync with engineering. A designer picks "brand blue = #1473E6," and that value gets retyped — slightly wrong — into a CSS file, an iOS asset catalog, an Android colors.xml, and a JS theme. Multiply by hundreds of tokens and you get a slow, error-prone mess. Style Dictionary makes the token files the single source of truth and turns "generate every platform's style files" into one deterministic build step you can run in CI.

## How it actually works

The whole thing is a pipeline with a strict order of operations, and the orchestration layer (the `StyleDictionary` class) is the conductor.

**1. Construction and initialization.** You create an instance with `new StyleDictionary(config)` or, more commonly, `StyleDictionary.extend(config)`. Initialization is asynchronous, but cleverly so: the instance exposes a promise called `hasInitialized`, and every public method begins by awaiting it. So you can call `buildAllPlatforms()` the instant after construction and it just waits for setup to finish. No race conditions, no manual "is it ready yet" checks.

**2. Loading and merging tokens.** During init, the engine pulls tokens from three places and merges them in a fixed priority: tokens written inline in the config (lowest priority), then `include` files, then `source` files (highest priority — source wins). Each layer is deep-merged so later files can override individual nested values without wiping the rest. If two source files define the same token, you get a collision warning.

**3. Preprocessing and normalization.** Registered preprocessors run over the merged tree. If the tokens use the DTCG standard format (the Design Tokens Community Group spec, with `$value`/`$type` fields), the engine auto-detects that and normalizes accordingly.

**4. Three synchronized representations.** Here's a key design move: the engine keeps the tokens in *three* shapes at once — a nested object tree (for humans and formats that want structure), a flat array (for iteration), and a `Map` keyed by token path (for fast lookup). Any time one changes, the engine immediately re-derives the other two so they never drift apart.

**5. Per-platform build.** `buildAllPlatforms()` fires off every platform concurrently. For each platform, the engine: resolves the platform's config (turning string names like `"css"` into the actual transform functions), takes a *deep clone* of the global tokens so platform processing never corrupts the shared state, runs the transform-and-resolve loop (transform each token's name/value/attributes, resolve `{references}`, repeat until stable), then formats and writes the output files. After files are written, it runs any "actions" (arbitrary side-effects like copying asset files).

**6. The transform/resolve loop.** This is the cleverest part. Some token values can't be transformed until the references inside them are resolved, and some references can't resolve until other tokens are transformed. So the engine loops: transform what it can, resolve what it can, and track the tokens it had to "defer." It keeps looping until the count of deferred tokens stops shrinking, then does one final resolution pass to flush everything. It converges instead of trying to compute a perfect dependency order up front.

## The non-obvious parts

- **`hasInitialized` is a promise, not a boolean.** This is what makes "construct then immediately build" safe. It's an elegant alternative to callback hell or a manual ready-state.
- **Every platform gets its own `structuredClone` of the tokens.** This is why platforms can run concurrently without stepping on each other — there's no shared mutable token state during the per-platform phase. The one shared thing is the global warning collector, so warnings from parallel platforms interleave.
- **Filtering happens at format time, not build time.** The transformed token set is computed once per platform; then each *file* within that platform independently filters it. So the same token can appear in one output file and be excluded from another, in the same build.
- **It runs in the browser by default.** The filesystem is abstracted, defaulting to an in-memory virtual filesystem (memfs). The Node build swaps in the real `node:fs`. That's how the online playground works with the exact same code.
- **`.extend()` re-reads everything.** Calling `extend()` doesn't inherit already-loaded tokens — it builds a fresh instance and re-runs the whole load/merge/preprocess pipeline. Surprising if you expected it to be cheap.

## Related

- [[reference-resolution-engine--from-style-dictionary]] — the `{token.path}` resolver the loop calls every pass
- [[transforms-and-transform-groups--from-style-dictionary]] — the per-token mutation step the loop drives
- [[register-extensibility-api--from-style-dictionary]] — how the string names in a platform config map to real functions
- [[design-systems-library--from-open-design]] — a different take on the design-system-as-source-of-truth idea (markdown specs injected into agents vs. tokens compiled to code)
