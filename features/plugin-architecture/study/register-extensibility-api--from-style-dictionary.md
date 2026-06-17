# Register / Extensibility API — from [style-dictionary](https://github.com/style-dictionary/style-dictionary)

> Domain: [[_domain]] · Source: https://github.com/style-dictionary/style-dictionary · NotebookLM: <link once added>

## What it does

Style Dictionary ships with a pile of built-in transforms, formats, and so on — but its real power is that you can add your own. The Register API is the plugin surface: a set of `registerX` methods (and a newer declarative `hooks` config) that let you teach the tool new behavior without touching its source. There are eight extension points:

- **transforms** — mutate a token's name/value/attributes
- **transform groups** — named ordered bundles of transforms
- **formats** — turn resolved tokens into an output file's contents
- **filters** — decide which tokens go into a given file
- **actions** — arbitrary side-effects after files are written (and how to undo them)
- **parsers** — read non-standard token file formats into the token tree
- **preprocessors** — massage the whole token tree before processing
- **file headers** — the comment block at the top of generated files

## Why it exists

No fixed set of built-ins can cover every team's platform, naming convention, or weird in-house file format. Rather than fork the tool, you register a plugin. The contract is small and stable: each `registerX` validates the shape you hand it and files it into a central registry keyed by name. Later, when your config references that name as a string (`format: "my-custom-format"`), the build looks it up. This name-indirection is what lets a plain JSON config describe a fully custom pipeline.

## How it actually works

**A single `hooks` object holds everything.** Internally there's one object with eight buckets: `hooks.transforms`, `hooks.transformGroups`, `hooks.formats`, `hooks.filters`, `hooks.actions`, `hooks.parsers`, `hooks.preprocessors`, `hooks.fileHeaders`. Every registration writes into the matching bucket under the name you give.

**Each `registerX` validates, then stores.** For example, `registerTransform` checks that `type` is one of `value`/`name`/`attribute`, that `name` is a string, that `filter` (if present) and `transform` are functions — throwing a specific error otherwise — then stores `{ type, filter, transitive, transform }` under that name. `registerParser` insists `pattern` is a real RegExp. `registerAction` requires a `do` function and treats `undo` as optional. The validation is the contract.

**What's stored differs by type.** Transforms, actions, and parsers are stored as structured objects (multiple properties). Formats, filters, preprocessors, and file headers are stored as *bare functions*. A small but easy-to-trip-on inconsistency.

**Global vs per-instance — the clever part.** Registration can happen two ways. Call it *statically* (`StyleDictionary.registerTransform(...)`) and it writes into a class-level registry shared by every instance — past and future. Call it on an *instance* (`sd.registerTransform(...)`) and it writes into that instance's private `_hooks`. When the build reads the registry, it deep-merges the class-level hooks with the instance-level ones, with the instance winning. So you get global defaults plus per-instance overrides, for free.

**The modern declarative path.** Instead of imperative `registerX` calls, you can pass a `hooks` object right in the config: `new StyleDictionary({ hooks: { parsers: { myParser: {...} } } })`. This goes through the instance path. The `registerX` methods are the older imperative surface; the inline `hooks` config is the newer declarative one.

**Lookup at build time.** When resolving a platform config, the engine maps string names to the stored objects: `hooks.transformGroups[groupName]` gives the ordered name list, `hooks.transforms[name]` gives each transform. Unknown names throw with a list of what's missing. Parsers are special — they're opt-in: only parsers whose names appear in the config's `parsers` array actually run.

## The non-obvious parts

- **Static registration mutates global state shared across all instances.** Register a transform statically and it silently affects every StyleDictionary you create anywhere in the process. Convenient, but a footgun in tests or multi-tenant code.
- **Name collisions overwrite silently.** Before each registration the engine deletes any existing entry with that name — no warning. Re-registering clobbers.
- **`registerTransformGroup` validates its members at *registration* time.** Every transform named in the group must already be registered when you call it — not lazily at build time.
- **Mixed storage shapes.** Transforms/actions/parsers are objects; formats/filters/preprocessors/fileHeaders are bare functions. If you build a generic "register anything" helper, you have to special-case these.
- **`registerPreprocessor` uses `instanceof Function`** for its check while everything else uses `typeof x !== 'function'` — functionally the same, but a telltale inconsistency.
- **Parsers are opt-in by name.** A registered parser that isn't listed in the config's `parsers` array never runs — unlike transforms, which apply wherever a group includes them.

## Related

- [[transforms-and-transform-groups--from-style-dictionary]] — the most-used registration target; the lookup interface this feeds
- [[token-pipeline-orchestration--from-style-dictionary]] — consumes the registry when resolving each platform config
- [[reference-resolution-engine--from-style-dictionary]] — formats registered here decide whether to keep references in output
- [[plugin-system--from-markitdown]] — a different extensibility model (Python entry-point discovery vs. in-process name registry)
- [[plugin-ecosystem--from-open-design]] — another take on host-plus-plugins composition
