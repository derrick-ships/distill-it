# Declarative (Low-Code) CDK (build spec) — distilled from airbyte

## Summary

Define a connector entirely in a YAML **manifest** that is an instance of a formal JSON-schema of
component types; a runtime **interprets** it: resolve `$ref`s → propagate `$parameters` → validate
against the schema → instantiate live components via a model-to-component factory. One manifest runs on
a synchronous or a concurrent engine (worker pool sized by a declared `concurrency_level`). Normalization
+ migration keep old manifests working.

## Core logic (inlined)

### Load pipeline (`manifest_declarative_source.py`)

```python
class ManifestDeclarativeSource(DeclarativeSource):
    def __init__(self, source_config, component_factory=None, ...):
        self._declarative_component_schema = _get_declarative_component_schema()   # the big JSON-schema YAML
        self._source_config = self._preprocess_manifest(source_config)
        self._constructor = component_factory or ModelToComponentFactory(...)
        self._message_repository = self._constructor.get_message_repository()
        self._validate_source()                      # jsonschema.validate(resolved_manifest, component_schema)
        # spec built from the manifest's `spec:` block:
        self._spec_component = self._constructor.create_component(SpecModel, spec, dict()) if spec else None

    def _preprocess_manifest(self, manifest):
        resolved   = ManifestReferenceResolver().preprocess_manifest(manifest)              # expand $ref / *ref()
        propagated = ManifestComponentTransformer().propagate_types_and_parameters(resolved) # push $parameters down
        return propagated

    def streams(self, config):
        # for each `streams:` entry -> factory builds a DeclarativeStream (with retriever/cursor/etc.)
        return [ self._constructor.create_component(DeclarativeStreamModel, s, config) for s in self._stream_configs ]
```

`_get_declarative_component_schema()` loads `sources/declarative/declarative_component_schema.yaml` (the
formal spec of every component: `DeclarativeStream`, `HttpRequester`, `DefaultPaginator`,
`RecordSelector`, `DpathExtractor`, `DatetimeBasedCursor`, auth types, etc.).

### Interpreter = ModelToComponentFactory

`create_component(Model, definition_dict, config)`: maps a manifest dict → its Pydantic model (generated
from the JSON-schema) → the real Python object. It recurses: a `DeclarativeStream` model contains a
`retriever` which contains a `requester`/`paginator`/`record_selector`, each built the same way.

### Concurrent engine (`concurrent_declarative_source.py`)

```python
class ConcurrentDeclarativeSource(Source):
    _LOWEST_SAFE_CONCURRENCY_LEVEL = 1
    def __init__(self, source_config, ...):
        cl = source_config.get("concurrency_level")
        concurrency_level = (self._constructor.create_component(ConcurrencyLevelModel, cl, ...).get_concurrency_level()
                             if cl else self._LOWEST_SAFE_CONCURRENCY_LEVEL)
        initial = max(concurrency_level // 2, 1)                      # reserve half for partition generation
        self._concurrent_source = ConcurrentSource.create(num_workers=concurrency_level, initial_number_of_partitions_to_generate=initial, ...)
    def read(self, ...):
        concurrent_streams, synchronous_streams = self._group_streams(...)   # some streams run concurrently, some not
        if concurrent_streams: yield from self._concurrent_source.read(selected_concurrent_streams)
        # synchronous streams fall back to the classic AbstractSource read
```

### Reference resolution + parameter propagation (the repetition-killers)

- `ManifestReferenceResolver.preprocess_manifest(manifest)`: resolves `"$ref": "#/definitions/base_requester"` and inline `"*ref(definitions.x)"`.
- `ManifestComponentTransformer.propagate_types_and_parameters(...)`: any component's `$parameters` (e.g. `{url_base: "https://api.x.com"}`) are merged into all nested children, so leaf components can interpolate `{{ parameters['url_base'] }}`.

## Data contracts

- **manifest.yaml (top level):** `{ version, type: DeclarativeSource, check:{stream_names}, definitions:{...$ref targets...}, streams:[DeclarativeStream...], spec:{connection_specification: <JSONSchema for config>}, concurrency_level?, metadata? }`.
- **DeclarativeStream:** `{ type, name, primary_key, retriever:{ type:SimpleRetriever, requester, record_selector, paginator?, partition_router? }, incremental_sync?:DatetimeBasedCursor, schema_loader, transformations? }`.
- **Component schema:** `declarative_component_schema.yaml` — JSON-schema; Pydantic models are generated from it (`models/declarative_component_schema.py`).
- **config:** validated against `spec.connection_specification` (user-supplied credentials/options).

## Dependencies & assumptions

- **Python**, `pydantic` (generated models), `jsonschema` (validation), `PyYAML`, `dpath`, `Jinja2`-style
  interpolation (`InterpolatedString`). The Airbyte protocol I/O layer ([[airbyte-protocol--from-airbyte]]).
- Swappable: the interpreter pattern (schema → model → component factory) is domain-agnostic; the
  components are HTTP-API-oriented but the architecture isn't.

## To port this, you need:

- [ ] A formal **component JSON-schema** enumerating every node type and its fields.
- [ ] A **manifest** format (YAML/JSON) that is an instance of that schema.
- [ ] A loader that **resolves refs**, **propagates shared params**, and **validates** before building.
- [ ] A **model-to-component factory** that recursively turns the validated manifest into live objects.
- [ ] An **interpolation** layer so manifest strings can reference config/params/state at runtime.
- [ ] (optional) a concurrent execution engine whose worker count is declared in the manifest.
- [ ] Normalization/migration so manifests survive schema evolution.

## Gotchas

- **Validate the *resolved* manifest, not the raw one** — refs/params must be expanded first or validation lies.
- **Propagate `$parameters` before building** — leaf components interpolate them; skip it and base URLs/paths are empty.
- **The interpreter runs every sync** — keep component construction cheap; it's not a one-time codegen.
- **Schema is the source of truth for tooling** — generate the Pydantic models and the Builder UI from it, don't hand-maintain parallel copies.
- **Reserve workers for partition generation** (half the concurrency level) or stream-slicing starves the readers.
- **Migrations must be idempotent** — old manifests load through them every run.

## Origin (reference only)

airbyte CDK lives in `airbytehq/airbyte-python-cdk` @ `main`:
`airbyte_cdk/legacy/sources/declarative/manifest_declarative_source.py` (load pipeline — inlined),
`airbyte_cdk/sources/declarative/concurrent_declarative_source.py` (concurrent engine — inlined),
`airbyte_cdk/sources/declarative/declarative_component_schema.yaml` (the component JSON-schema),
`.../parsers/{manifest_reference_resolver,manifest_component_transformer,model_to_component_factory}.py`.

**Gaps to verify (cost-capped):** the full `ModelToComponentFactory.create_component` dispatch table;
exact `$parameters`/`$ref` syntax edge cases; manifest normalizer/migration rules; `_group_streams` concurrency split criteria.
