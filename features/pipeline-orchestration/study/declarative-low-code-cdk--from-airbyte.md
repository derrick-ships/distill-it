# Declarative (Low-Code) CDK — from [airbyte](https://github.com/airbytehq/airbyte)

> Domain: [[_domain]] · Source: https://github.com/airbytehq/airbyte · NotebookLM: <link once added>

## What it does

You describe an entire API connector in a **single YAML file** — base URL, auth, which endpoints
become streams, how to paginate, where the records live in the response, how to sync incrementally —
and Airbyte's runtime *interprets* that YAML into a working connector. No Python, no subclassing. The
same engine powers Airbyte's no-code Connector Builder and a huge share of its 600+ connectors.

## Why it exists

Hand-writing a Python connector per API doesn't scale to "the long tail of data sources." Most REST
APIs differ only in boring, declarable ways — URL, auth header, pagination style, JSON path to the
records. So Airbyte factored all of that into a *declarative schema*: capture the differences as data
(YAML), and let one well-tested interpreter handle the mechanics. A new connector becomes a config
file, not a codebase — which is what makes 600+ connectors maintainable.

## How it actually works

There's a big JSON-schema (`declarative_component_schema.yaml`) that defines every legal component
type: `DeclarativeStream`, `HttpRequester`, `DefaultPaginator`, `DpathExtractor`,
`DatetimeBasedCursor`, the auth types, and so on. A connector's `manifest.yaml` is an instance of that
schema. At startup the source:

1. **Resolves references** — a `ManifestReferenceResolver` expands `$ref`s and `*ref(...)` so shared
   config (defined once, e.g. a base requester) is reused across streams without copy-paste.
2. **Propagates types & parameters** — a `ManifestComponentTransformer` pushes shared `$parameters`
   (like the API base URL) down into every nested component that needs them.
3. **Validates** the resolved manifest against the component JSON-schema — a malformed manifest fails
   loudly here, before any network call.
4. **Builds live objects** — a `ModelToComponentFactory` walks the validated manifest and instantiates
   the actual Python components (the requester, paginator, extractor, cursor) for each stream. This is
   the interpreter: manifest dict → Pydantic model → real component.

Newer connectors use a **concurrent** variant that reads multiple streams (and partitions) in parallel
via a worker pool whose size comes from a `concurrency_level` declared in the manifest; older ones run
synchronously. Either way, the manifest is the single source of truth, and everything else is generated
from it. There's also manifest **normalization** and **migration** machinery so old manifests keep
working as the schema evolves.

## The non-obvious parts

- **The manifest is interpreted, not compiled.** There's no codegen step — the runtime reads the YAML
  and constructs live objects every run. Change the YAML, change the connector.
- **A JSON-schema is the contract.** Every component type and its fields are formally specified, so
  manifests can be validated, and tools (the Builder UI, autocomplete) are generated from the schema.
- **`$ref` + `$parameters` kill repetition.** Define the requester once, reference it per stream;
  declare the base URL once, propagate it everywhere. This is what makes a 20-stream connector readable.
- **Two execution engines, one manifest.** The same YAML runs on the legacy synchronous source or the
  newer concurrent source; concurrency is just another declared field.
- **Normalization + migration** let the schema evolve without breaking the thousands of manifests in
  the wild — old shapes are auto-upgraded at load.
- **The Builder is just a UI over the manifest** — no-code and low-code are the *same* engine.

## Related
- [[declarative-http-stream-stack--from-airbyte]] (the components the factory builds: requester/paginator/extractor)
- [[incremental-sync-state--from-airbyte]] (the `DatetimeBasedCursor` the manifest declares)
- [[airbyte-protocol--from-airbyte]] (what the interpreted connector emits)
- [[connector-builder-test-read--from-airbyte]] (the no-code UI that authors these manifests)
- See also: [[smart-scraper-pipeline--from-scrapegraph-ai]] — config-reshapes-the-pipeline, smaller scale.
