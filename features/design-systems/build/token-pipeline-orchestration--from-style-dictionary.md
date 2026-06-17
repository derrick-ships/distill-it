# Token Pipeline Orchestration (build spec) — distilled from style-dictionary

## Summary

Build the orchestration engine that turns a set of design-token source files plus a multi-platform config into written output files. The engine: loads + deep-merges tokens, preprocesses, maintains three synchronized token representations, then for each platform runs a transform↔resolve convergence loop, filters per-file, formats to strings, and writes files — followed by post-write "actions." Build runs entirely on an abstracted filesystem so it works in-browser or in Node.

## Core logic (inlined)

### Instance state
```
this.config            // raw config (object or path string)
this.tokens   = {}     // nested object tree (source of truth for structure)
this.allTokens = []     // flat array of token objects
this.tokenMap = Map()  // Map<string, Token> keyed by "{dotted.path}"
this.usesDtcg          // bool, auto-detected
this.platforms = {}    // { [name]: PlatformConfig }
this.source = []       // glob patterns (highest merge priority)
this.include = []      // glob patterns (lower priority)
this.volume            // filesystem volume; defaults to in-memory (memfs)
this._dictionaries = {}      // per-platform processed-token cache
this._platformConfigs = {}   // per-platform resolved-config cache
this.hasInitialized          // Promise — resolved at end of extend()
```

### Initialization (`init` → `extend`)
```
extend(config, opts):
  if typeof config === 'string': config = await loadFile(config, volume)   // JSON or JS module
  if !opts.mutateOriginal:        # user-facing path
     newSD = new StyleDictionary(deepmerge(this.options, options), {init:false})
     return newSD.init(opts)      # NB: re-runs the WHOLE pipeline on a fresh instance
  # mutating path (used by init):
  Object.entries(this.options).forEach(([k,v]) => this[k] = v)   # copy config onto instance
  if tokens non-empty and usesDtcg===undefined: usesDtcg = detectDtcgSyntax(tokens)
  # --- load + merge in priority order (source wins) ---
  inline  = deepExtend([{}, this.tokens])
  include = await combineJSON(this.include, /*deep*/true, /*no collision warn*/)
  source  = await combineJSON(this.source,  true, collisionCallback)   # warns on dup tokens
  merged  = deepExtend([{}, inline, include, source])
  merged  = await preprocess(merged, this.preprocessors, this.hooks.preprocessors, this.options)
  if usesDtcg: merged = typeDtcgDelegate(merged)     # normalize $value/$type inheritance
  # --- sync the three representations ---
  this.tokens    = merged
  this.allTokens = convertTokenData(this.tokens,    {output:'array'})
  this.tokenMap  = convertTokenData(this.allTokens, {output:'map'})
  if shouldRunExpansion(this.expand): expandTokens(this.tokenMap, options); re-sync all three
  this.hasInitializedResolve(null)   # unblock everything awaiting hasInitialized
```

### Build all platforms
```
buildAllPlatforms(opts):
  await this.hasInitialized
  await Promise.all(Object.keys(this.platforms).map(k => this.buildPlatform(k, opts)))
```

### Build one platform
```
buildPlatform(platform, opts):
  await this.hasInitialized
  platformConfig = getPlatformConfig(platform, opts)       # resolves names→functions, cached
  dictionary     = await getPlatformTokens(platform, opts) # transform+resolve, cached
  files          = await formatPlatform(platform, opts)    # array of {output, destination}
  await Promise.all(files.map(f => f.output is string ? writeFile(f.destination, f.output)
                                                       : warn("non-string output, skipped")))
  await performActions(dictionary, platformConfig, this.options, this.volume)

writeFile(dest, output):
  dir = dirname(dest)
  try await volume.promises.access(dir) catch await volume.promises.mkdir(dir,{recursive:true})
  return volume.promises.writeFile(dest, output)
```

### Resolve platform config (string names → live functions)
```
getPlatformConfig(platform, opts):
  return cache hit unless opts.cache===false
  cfg = {...this.platforms[platform]}   # SHALLOW spread, NOT structuredClone (config has functions!)
  cfg.transforms = (hooks.transformGroups[cfg.transformGroup] ?? []).concat(cfg.transforms ?? [])
                     .map(name => ({...hooks.transforms[name], name}))   # throws if name unknown
  cfg.fileHeader = resolve via hooks.fileHeaders
  for file in cfg.files:
     file.filter = string→hooks.filters[name] | object→inlineMatcher | function (as-is)
     file.format = hooks.formats[file.format]   # string→function
     merge fileHeader into file.options
  cfg.actions = cfg.actions.map(name => hooks.actions[name])   # warn if action.undo missing
  cache and return cfg
```

### Transform ↔ resolve convergence loop (the heart)
```
_exportPlatform(platform):              # returns the Dictionary, cached in _dictionaries
  await this.hasInitialized
  platformConfig = getPlatformConfig(platform)
  tokens, tokenMap, allTokens = structuredClone(this.tokens / tokenMap / allTokens)  # per-platform copy
  await preprocess(tokens, platformConfig.preprocessors, ...)        # platform-level preprocessors
  if platformConfig.expand: expandTokens(tokenMap, opts, platformConfig)
  transformedPropRefs        = new Set()   # tokens fully transformed
  deferredPropValueTransforms = new Set()   # tokens blocked on unresolved refs
  ctx = { transformedPropRefs, deferredPropValueTransforms }
  finished = false; deferredCount = Infinity
  while (!finished):
     await transformMap(tokenMap, platformConfig, opts, ctx)   # see transforms feature
     resolveMap(tokenMap, { ignorePaths: deferredPropValueTransforms, usesDtcg })  # see references feature
     if deferredPropValueTransforms.size === 0: finished = true
     else if deferredPropValueTransforms.size === deferredCount:        # stuck — no progress
        resolveMap(tokenMap, { usesDtcg })   # final flush, no ignore list
        finished = true
     else: deferredCount = deferredPropValueTransforms.size   # progress, loop again
  flush grouped warnings: PROPERTY_REFERENCE_WARNINGS, TRANSFORM_ERRORS, UNKNOWN_CSS_FONT_PROPS
  allTokens = convertTokenData(tokenMap, {output:'array'})
  tokens    = convertTokenData(allTokens, {output:'object'})
  return { tokenMap, allTokens, tokens }   # = Dictionary
```

### Format a platform's files
```
formatPlatform(platform): Promise.all(platformConfig.files.map(f => formatFile(f, platformConfig, dictionary)))

formatFile(file, platform, dictionary):
  fullDestination = join(platform.buildPath, file.destination)
  filtered = await filterTokens(dictionary, file.filter, options)   # {allTokens, tokens, tokenMap}
  filteredDictionary = {
     tokens: filtered.tokens, allTokens: filtered.allTokens, tokenMap: filtered.tokenMap,
     unfilteredTokens: dictionary.tokens, unfilteredAllTokens: dictionary.allTokens,
     unfilteredTokenMap: dictionary.tokenMap,   # formats need this for outputReferences across filter
  }
  if filtered.tokens empty: warn + return {destination, output: undefined}
  detect name collisions among filtered.allTokens (same .name)
  format = format.bind(file)   # legacy: inside a format, `this` === the File object
  output = await format(createFormatArgs({dictionary: filteredDictionary, platform, options, file}))
  return { output, destination: fullDestination }

createFormatArgs(...) => { dictionary, allTokens, tokens, platform, file,
                            options: {...platform.options, ...file.options} }   # file.options wins
```

### Clean (the inverse, for `cleanAllPlatforms`)
```
cleanPlatform: cleanFiles(unlink each file) → cleanActions(action.undo each) → cleanDirs(rm now-empty dirs upward)
```

## Data contracts

```ts
type Config = {
  tokens?: object;                  // inline tokens
  source?: string[]; include?: string[];   // globs
  platforms: { [name: string]: PlatformConfig };
  parsers?: string[];               // names of registered parsers to enable
  preprocessors?: string[];
  expand?: boolean | ExpandConfig;
  log?: LogConfig; usesDtcg?: boolean;
  hooks?: Hooks;                    // declarative inline registration (see register feature)
}
type PlatformConfig = {
  transformGroup?: string;          // name → ordered transform list
  transforms?: string[];            // extra transform names appended
  files: File[];
  actions?: string[];
  buildPath?: string;               // prefix for every file destination
  preprocessors?: string[];
  expand?: boolean | ExpandConfig;
  options?: object;                 // merged under each file's options
  log?: LogConfig;
}
type File = {
  destination: string;
  format: string;                   // → resolved to format fn
  filter?: string | object | ((token)=>boolean);
  options?: { fileHeader?: string|fn; outputReferences?: boolean|fn; [k:string]:any };
}
type Token = {                       // legacy keys; DTCG uses $value/$type
  value?: any; $value?: any;
  type?: string; $type?: string;
  name?: string;                     // set by name transforms
  path?: string[];                   // ancestor keys, e.g. ['color','brand','500']
  attributes?: Record<string,any>;   // set by attribute transforms (CTI)
  original?: Token;                  // pre-transform snapshot (never resolved)
  filePath?: string; isSource?: boolean;
}
type Dictionary = { tokens: object; allTokens: Token[]; tokenMap: Map<string,Token> }
```

## Dependencies & assumptions

- `deepmerge` / a deep-extend that merges nested objects (source wins). Swappable.
- `structuredClone` (global) — used per-platform to isolate token state. Cannot clone functions (that's why platform-config resolution uses a *shallow* spread instead).
- A filesystem abstraction (`volume`) with `promises.{access,mkdir,writeFile,unlink}` and sync `existsSync/readdirSync/rmSync` for dir cleanup. Defaults to an in-memory FS (memfs) so it runs in browsers; Node entrypoint swaps in `node:fs`.
- A glob library for `source`/`include`.
- A grouped-warning collector singleton (here `GroupMessages`) — accumulates warnings/errors keyed by group and flushes once per phase.
- The transforms, references, and register features (see Related) provide `transformMap`, `resolveMap`, and the `hooks` registry respectively.

## To port this, you need:

- [ ] Three-representation token store with a single `convertTokenData(data, {output:'object'|'array'|'map'})` converter, and the discipline to re-sync after every mutation.
- [ ] An async-safe init gate (a resolved-once promise the public API awaits).
- [ ] A filesystem abstraction with both a real and in-memory backend.
- [ ] A grouped-message collector for deferred/batched warnings.
- [ ] The transform + reference-resolution + hook-registry subsystems wired in.
- [ ] Per-platform `structuredClone` isolation so platforms can run concurrently.

## Gotchas

- **Don't `structuredClone` the platform config** — it has functions after resolution; cloning silently drops them. Shallow-spread it.
- **The convergence loop can terminate with unresolved references** (the "stuck" branch does a final flush and breaks). That's why `PROPERTY_REFERENCE_WARNINGS` is flushed right after — surface those, don't swallow them.
- **`GroupMessages` is a global singleton**; with concurrent platforms its contents interleave. Flushing drains globally, not per-platform — a real correctness wrinkle if you parallelize.
- **Filtering is per-file, after transform.** A token can be in file A and out of file B in the same platform. Formats relying on cross-references must read `unfilteredTokens`, which is why the filtered dictionary always carries both.
- **`format` is `bind`-ed to the File object** for backward compat — inside a format, `this` is the file. Don't rely on it, but don't break it either.
- **`cleanDir` uses *synchronous* fs calls** while everything else is async — would block the event loop on a real FS. Consider making it async if you port it.
- **Non-string format output is silently skipped** with a warning, no file written. Validate your format returns a string.
- **`.extend()` re-runs the full load pipeline** on a fresh instance; it is not a cheap incremental update.

## Origin (reference only)

Repo: https://github.com/style-dictionary/style-dictionary (branch `main`). Key files: `lib/StyleDictionary.js` (class + lifecycle), `lib/transform/config.js` (config resolution), `lib/filterTokens.js`, `lib/performActions.js`, `lib/cleanFile.js`/`cleanDir.js`, `lib/utils/createFormatArgs.js`, `lib/utils/convertTokenData.js`, `lib/utils/combineJSON.js`, `lib/utils/preprocess.js`, `lib/fs.js` + `lib/fs-node.js`.
