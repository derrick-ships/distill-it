# Register / Extensibility API (build spec) — distilled from style-dictionary

## Summary

Build an in-process plugin registry with eight extension points (transforms, transformGroups, formats, filters, actions, parsers, preprocessors, fileHeaders). Each `registerX(cfg)` validates the shape and files it into a single `hooks` object keyed by name. Supports two scopes: static (class-level, shared by all instances) and instance-level (`_hooks`), merged at read time with instance winning. A declarative `hooks` config key is the modern equivalent of the imperative `registerX` methods. Config references everything by string name; build-time lookup resolves names → objects/functions.

## Core logic (inlined)

### The registry
```
hooks = {
  transforms:      {},   // { [name]: { type, filter?, transitive?, transform } }
  transformGroups: {},   // { [name]: string[] }
  formats:         {},   // { [name]: fn }        ← bare function
  filters:         {},   // { [name]: fn }        ← bare function
  actions:         {},   // { [name]: { do, undo? } }
  parsers:         {},   // { [name]: { pattern, parser } }
  preprocessors:   {},   // { [name]: fn }        ← bare function
  fileHeaders:     {},   // { [name]: fn }        ← bare function
}
```

### Static vs instance dispatch
```
// static:   StyleDictionary.registerTransform(cfg)  → __registerTransform(cfg, target=THE CLASS)  → class-level hooks
// instance: sd.registerTransform(cfg)               → constructor.__registerTransform(cfg, target=THE INSTANCE) → this._hooks
// All registerX share one private __registerX(cfg, target); only `target` differs.

deleteExistingHook(target, hookBucket, name):   // called before EVERY registration
  delete target.hooks[hookBucket][name]          // silent overwrite, no collision warning

get hooks():  return deepmerge(constructor.hooks /* class-level */, this._hooks ?? {})  // instance wins
set hooks(v): this._hooks = v                                                            // never touches class-level
```

### Each registerX — signature, validation, storage
```
registerTransform({ name, type, filter?, transitive?, transform }):
  if typeof type !== 'string'                → "type must be a string"
  if type not in ['value','name','attribute']→ "<type> type is not one of: value, name, attribute"
  if typeof name !== 'string'                → "name must be a string"
  if filter && typeof filter !== 'function'  → "filter must be a function"
  if typeof transform !== 'function'         → "transform must be a function"
  store: hooks.transforms[name] = { type, filter, transitive, transform }

registerTransformGroup({ name, transforms /* string[] */ }):
  if typeof name !== 'string'                → "transform name must be a string"
  if !Array.isArray(transforms)              → "transforms must be an array of registered value transforms"
  for t in transforms: if !hooks.transforms[t] → same array error   // MEMBERS MUST ALREADY BE REGISTERED
  store: hooks.transformGroups[name] = transforms

registerFormat({ name, format /* fn */ }):
  if typeof name !== 'string'                → "Can't register format; format.name must be a string"
  if typeof format !== 'function'            → "Can't register format; format.format must be a function"
  store: hooks.formats[name] = format        // bare fn. Signature: async ({dictionary, options, file, platform}) => string

registerFilter({ name, filter /* fn */ }):
  if typeof name !== 'string'                → "Can't register filter; filter.name must be a string"
  if typeof filter !== 'function'            → "Can't register filter; filter.filter must be a function"
  store: hooks.filters[name] = filter        // bare fn. (token) => boolean

registerAction({ name, do /* fn */, undo? /* fn */ }):
  if typeof name !== 'string'                → "name must be a string"
  if typeof do !== 'function'                → "do must be a function"
  store: hooks.actions[name] = { do, undo }  // undo optional; orchestrator warns at config-resolve time if missing

registerParser({ name, pattern /* RegExp */, parser /* fn */ }):
  if typeof name !== 'string'                → "Can't register parser; parser.name must be a string"
  if !(pattern instanceof RegExp)            → "Can't register parser; parser.pattern must be a regular expression"
  if typeof parser !== 'function'            → "Can't register parser; parser.parser must be a function"
  store: hooks.parsers[name] = { pattern, parser }   // parser(contents, filePath) => tokenTreeObject
  // OPT-IN: only run if name ∈ config.parsers[]

registerPreprocessor({ name, preprocessor /* fn */ }):
  if typeof name !== 'string'                → "Cannot register preprocessor; Preprocessor.name must be a string"
  if !(preprocessor instanceof Function)     → "Cannot register preprocessor; Preprocessor.preprocessor must be a function"
  store: hooks.preprocessors[name] = preprocessor    // async (dictionary, config) => dictionary

registerFileHeader({ name, fileHeader /* fn */ }):
  if typeof name !== 'string'                → "Can't register file header; options.name must be a string"
  if typeof fileHeader !== 'function'        → "Can't register file header; options.fileHeader must be a function"
  store: hooks.fileHeaders[name] = fileHeader        // (defaultMessage) => string[]
```

### Declarative path (modern)
```
new StyleDictionary({ hooks: { parsers: {...}, transforms: {...}, formats: {...}, ... } })
  → goes through the `hooks` SETTER → this._hooks → merged via getter at read time (instance-level scope)
```

### Build-time lookup (consumers)
```
hooks.transformGroups[groupName]   → string[]   (throws/aggregates missing names)
hooks.transforms[transformName]    → Transform  (optional chaining; missing → aggregated error)
hooks.formats[file.format]         → fn
hooks.filters[file.filter]         → fn (when filter is a string)
hooks.actions[name]                → { do, undo }
hooks.parsers filtered by config.parsers[]  → only enabled parsers run
hooks.preprocessors / hooks.fileHeaders by name
```

## Data contracts

```ts
type Hooks = {
  transforms:      Record<string, { type:'value'|'name'|'attribute'; filter?:Function; transitive?:boolean; transform:Function }>;
  transformGroups: Record<string, string[]>;
  formats:         Record<string, Function>;   // ({dictionary,options,file,platform}) => string
  filters:         Record<string, Function>;   // (token) => boolean
  actions:         Record<string, { do:Function; undo?:Function }>;
  parsers:         Record<string, { pattern:RegExp; parser:Function }>;  // parser(contents, filePath) => object
  preprocessors:   Record<string, Function>;   // (dictionary, config) => dictionary
  fileHeaders:     Record<string, Function>;   // (defaultMessage) => string[]
}
```
Two storage shapes: **objects** (transforms, actions, parsers) vs **bare functions** (formats, filters, preprocessors, fileHeaders).

## Dependencies & assumptions

- `deepmerge` for the class+instance hooks merge (instance wins).
- A class with both static methods and instance methods sharing private `__registerX(cfg, target)` implementations.
- Built-in hooks pre-loaded into the class-level registry at construction (`getBuiltinHooks()` — exact merge point not fully confirmed; see gaps).
- Consumers: the platform-config resolver (transforms/groups/formats/filters/actions/fileHeaders) and the loader (parsers/preprocessors).

## To port this, you need:

- [ ] A single `hooks` registry with one bucket per extension point.
- [ ] Per-type validators that throw specific messages (the contract).
- [ ] Two scopes — a shared/global registry and a per-instance one — merged on read with instance precedence (if you need overrides; otherwise one scope is fine).
- [ ] A `deleteExistingHook` step (or decide to warn instead of silently overwriting).
- [ ] String-name indirection so config can reference plugins by name; build-time lookup that aggregates unknown-name errors.
- [ ] Opt-in semantics for parsers (only run those listed in config).
- [ ] Decide whether to support a declarative `hooks` config key in addition to imperative `registerX`.

## Gotchas

- **Static registration is process-global** — shared across all instances, including ones created later. Great for defaults, dangerous in tests/multi-tenant. Prefer instance-level (`hooks` config) for isolation.
- **Silent overwrite on name collision** (`deleteExistingHook`). If you want safety, warn or throw on re-register.
- **`registerTransformGroup` requires members already registered** at call time — order your registrations.
- **Two storage shapes** (object vs bare fn). A generic register helper must special-case this; consumers must know which bucket returns what.
- **`instanceof Function` vs `typeof === 'function'`** — preprocessor uses the former; functionally equal but inconsistent. `instanceof Function` fails across realms/iframes — prefer `typeof`.
- **Parsers are opt-in**; a registered-but-unlisted parser silently never runs. Transforms are not — they run wherever a group includes them.
- **Validation of the inline `hooks` config key** may differ from the `registerX` methods' explicit validation — not confirmed; validate yourself if porting.

## Origin (reference only)

Repo: https://github.com/style-dictionary/style-dictionary (branch `main`). Files: `lib/Register.js` (all registration methods + `hooks` getter/setter + `deleteExistingHook`), `lib/StyleDictionary.js` (extends Register), `lib/transform/config.js` (build-time lookup of transforms/groups), `lib/enums/transformTypes.js` (the `value`/`name`/`attribute` enum), built-in hook sources under `lib/common/{transforms,transformGroups,formats,actions,filters}.js`. Exact `getBuiltinHooks()` body and the inline-`hooks`-config validation path were not fully traced — verify before relying on them.
