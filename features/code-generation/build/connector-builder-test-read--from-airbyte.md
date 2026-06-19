# Connector Builder Test-Read (build spec) — distilled from airbyte

## Summary

Backend for the no-code Connector Builder: run a **bounded, instrumented test read** of an in-progress
manifest using the SAME declarative engine as production, and return a rich `StreamRead` (records +
captured HTTP request/response pairs + pages + slices + inferred schema) wrapped in an Airbyte protocol
RECORD message. Plus `resolve_manifest`/`full_resolve_manifest` to show the expanded manifest.

## Core logic (inlined)

### Handler (`connector_builder/connector_builder_handler.py`)

```python
MAX_PAGES_PER_SLICE_KEY = "max_pages_per_slice"
MAX_SLICES_KEY = "max_slices"
MAX_RECORDS_KEY = "max_records"

@dataclass
class TestLimits:
    DEFAULT_MAX_RECORDS = 100
    DEFAULT_MAX_PAGES_PER_SLICE = 5
    DEFAULT_MAX_SLICES = 5
    max_records: int; max_pages_per_slice: int; max_slices: int

def get_limits(command_config) -> TestLimits:
    return TestLimits(
        max_records=command_config.get(MAX_RECORDS_KEY, TestLimits.DEFAULT_MAX_RECORDS),
        max_pages_per_slice=command_config.get(MAX_PAGES_PER_SLICE_KEY, TestLimits.DEFAULT_MAX_PAGES_PER_SLICE),
        max_slices=command_config.get(MAX_SLICES_KEY, TestLimits.DEFAULT_MAX_SLICES))

def create_source(config, limits) -> ConcurrentDeclarativeSource:
    # build the SAME production source from the manifest, but pass the caps so the read is bounded
    return ConcurrentDeclarativeSource(source_config=config["__injected_declarative_manifest"], limits=limits, ...)

def read_stream(source, config, configured_catalog, stream_name, state, limits) -> AirbyteMessage:
    test_read_handler = TestReader(limits.max_pages_per_slice, limits.max_slices, limits.max_records)
    stream_read = test_read_handler.run_test_read(source, config, configured_catalog, stream_name, state, limits.max_records)
    return AirbyteMessage(type=RECORD, record=AirbyteRecordMessage(
        data=asdict(stream_read), stream=stream_name, emitted_at=_emitted_at()))   # rich result rides a RECORD

def resolve_manifest(source) -> AirbyteMessage:
    return AirbyteMessage(type=RECORD, record=AirbyteRecordMessage(
        data={"manifest": source.resolved_manifest}, stream="resolve_manifest", emitted_at=_emitted_at()))

def full_resolve_manifest(source, limits) -> AirbyteMessage:
    # like resolve, but ALSO materialize dynamic streams (run a tiny read to discover them)
    ...
```

### TestReader (the instrumentation)

`run_test_read(...)` runs the real read but: (1) stops at `max_records`, and per-slice at
`max_pages_per_slice`, and overall at `max_slices`; (2) captures every HTTP request↔response (via the
HttpClient's logging hook); (3) a **MessageGrouper** groups emitted messages by slice→page→records;
(4) infers a JSON-schema from the sampled records. Output `StreamRead`:

```python
@dataclass
class StreamRead:
    logs: List[...]
    slices: List[StreamReadSlices]      # each: { pages:[{request, response, records}], slice_descriptor, state }
    test_read_limit_reached: bool
    inferred_schema: Optional[dict]
    inferred_datetime_formats: Optional[dict]
    latest_config_update: Optional[dict]
    auxiliary_requests: Optional[list]
```

## Data contracts

- **Command config:** `{ __injected_declarative_manifest: <manifest>, __command: "test_read"|"resolve_manifest"|"full_resolve_manifest", __test_read_config?: {max_records, max_pages_per_slice, max_slices} }`.
- **test_read result:** `AirbyteRecordMessage.data = asdict(StreamRead)` (records + grouped pages + captured req/resp + inferred schema + `test_read_limit_reached`).
- **resolve result:** `{ manifest: <fully ref/param-resolved manifest> }`.

## Dependencies & assumptions

- The declarative engine ([[declarative-low-code-cdk--from-airbyte]]) + its HTTP stack with a
  request/response logging hook; the Airbyte protocol RECORD message ([[airbyte-protocol--from-airbyte]]).
- A MessageGrouper + a schema-inference util. Swappable: the caps/instrumentation wrap any read engine
  that can emit per-request traces.

## To port this, you need:

- [ ] Build the real connector from the in-progress manifest (no separate preview engine).
- [ ] A `TestLimits{max_records, max_pages_per_slice, max_slices}` cap threaded into the read.
- [ ] HTTP request/response capture during the read.
- [ ] A grouper that nests messages by slice → page → records, plus schema inference.
- [ ] Return the rich result over your existing transport (here: a protocol RECORD).
- [ ] `resolve`/`full-resolve` endpoints to show the expanded (and dynamic-stream-materialized) manifest.

## Gotchas

- **Cap on all three axes** — records alone won't bound a multi-slice paginating stream; pages-per-slice and slices matter.
- **Run the production engine, not a mock** — the whole value is zero preview/prod drift.
- **Capture requests at the HTTP-client layer** so the trace is exactly what hit the API (headers, final URL, body).
- **`test_read_limit_reached`** must be surfaced so the UI says "showing first N", not "this is everything".
- **full-resolve actually runs a little** (to materialize dynamic streams) — it's not pure string expansion.
- **Schema is inferred from a sample** — present it as a starting point, not ground truth.

## Origin (reference only)

`airbytehq/airbyte-python-cdk` @ `main`: `airbyte_cdk/connector_builder/connector_builder_handler.py`
(inlined), `airbyte_cdk/connector_builder/test_reader/*` (TestReader + MessageGrouper),
`airbyte_cdk/connector_builder/models.py` (StreamRead). Driven by `connector_builder/main.py`.

**Gaps to verify (cost-capped):** exact `TestReader.run_test_read` capture mechanism; `MessageGrouper`
grouping rules; `StreamRead` full field list; how dynamic streams are materialized in full-resolve.
