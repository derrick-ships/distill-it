# Airbyte Protocol (build spec) — distilled from airbyte

## Summary

A universal source↔destination contract: a connector is a CLI emitting newline-delimited JSON
`AirbyteMessage`s (a tagged union) over stdout. Four commands — `spec`, `check`, `discover`, `read`.
`read` streams `RECORD` + `STATE` (checkpoints) interleaved with `LOG`/`TRACE`/`CONTROL`. Destinations
consume the stream; the platform persists `STATE` for resumable syncs. Language-agnostic (Docker image
+ stdout).

## Core logic (inlined)

### Message envelope (`models/airbyte_protocol.py`)

```python
class Type(Enum): RECORD; STATE; LOG; SPEC; CONNECTION_STATUS; CATALOG; TRACE; CONTROL

@dataclass
class AirbyteMessage:                     # tagged union — exactly one payload set per `type`
    type: Type
    record: Optional[AirbyteRecordMessage] = None
    state:  Optional[AirbyteStateMessage]  = None
    log:    Optional[AirbyteLogMessage]    = None
    trace:  Optional[AirbyteTraceMessage]  = None
    catalog: Optional[AirbyteCatalog]      = None
    spec:   Optional[ConnectorSpecification] = None
    connectionStatus: Optional[AirbyteConnectionStatus] = None
    control: Optional[AirbyteControlMessage] = None

@dataclass
class AirbyteRecordMessage:
    stream: str
    data: Dict[str, Any]
    emitted_at: int            # ms epoch
    namespace: Optional[str] = None

@dataclass
class AirbyteStateMessage:      # the resumable checkpoint
    type: AirbyteStateType      # STREAM | GLOBAL | LEGACY
    stream: Optional[AirbyteStreamState] = None    # {stream_descriptor:{name,namespace}, stream_state:{...}}
    global_: Optional[AirbyteGlobalState] = None
    data: Optional[Dict[str, Any]] = None          # legacy whole-state blob
```

### Catalog (discover output) + configured catalog (read input)

```python
@dataclass
class AirbyteStream:
    name: str
    json_schema: Dict[str, Any]
    supported_sync_modes: List[SyncMode]           # full_refresh | incremental
    source_defined_cursor: Optional[bool] = None
    default_cursor_field: Optional[List[str]] = None
    source_defined_primary_key: Optional[List[List[str]]] = None
    namespace: Optional[str] = None

@dataclass
class AirbyteCatalog: streams: List[AirbyteStream]

@dataclass
class ConfiguredAirbyteStream:                       # user's choices for a stream
    stream: AirbyteStream
    sync_mode: SyncMode
    destination_sync_mode: DestinationSyncMode        # append | overwrite | append_dedup
    cursor_field: Optional[List[str]] = None
    primary_key: Optional[List[List[str]]] = None

@dataclass
class ConfiguredAirbyteCatalog: streams: List[ConfiguredAirbyteStream]
```

### The four commands (connector CLI)

```
spec                                  -> AirbyteMessage(type=SPEC, spec=ConnectorSpecification{connectionSpecification: <JSONSchema>})
check     --config c.json             -> AirbyteMessage(type=CONNECTION_STATUS, connectionStatus={status: SUCCEEDED|FAILED, message?})
discover  --config c.json             -> AirbyteMessage(type=CATALOG, catalog=AirbyteCatalog)
read      --config c --catalog cc --state s.json
          -> stream of: RECORD..., STATE (checkpoint), LOG, TRACE(error/estimate), CONTROL(config update)
```

Serialization: dedicated serializers (`airbyte_protocol_serializers.py`) (de)serialize messages
fast; everything is newline-delimited JSON on stdout (stderr is ignored/aux).

## Data contracts

- **Sync modes:** `SyncMode = full_refresh | incremental`; `DestinationSyncMode = append | overwrite | append_dedup`.
- **TRACE:** `{type: ERROR|ESTIMATE|STREAM_STATUS, error?:{message, internal_message, stack_trace, failure_type}, estimate?, emitted_at}`.
- **CONTROL:** `{type: CONNECTOR_CONFIG, connectorConfig:{config}}` — connector asks platform to persist new config (e.g. refreshed token).
- **ConnectorSpecification:** `{connectionSpecification: JSONSchema, supportsIncremental?, advanced_auth?, documentationUrl?}`.

## Dependencies & assumptions

- Just JSON + stdout; connectors ship as Docker images, any language. Serializers for speed.
- The platform/worker reads the message stream, routes RECORDs to the destination, persists STATE.
- Swappable nothing — this IS the contract; everything else conforms.

## To port this, you need:

- [ ] A tagged-union `AirbyteMessage` envelope + the payload types (record/state/log/trace/catalog/spec/status/control).
- [ ] A connector CLI with `spec`/`check`/`discover`/`read` emitting newline-delimited JSON on stdout.
- [ ] A `discover` → catalog and a `ConfiguredCatalog` input that selects streams + sync/dest modes + cursor/pk.
- [ ] `read` interleaving RECORD + STATE, with the consumer checkpointing on STATE.
- [ ] TRACE for structured errors/estimates; CONTROL for config write-back.

## Gotchas

- **STATE is interleaved, not final** — emit checkpoints during read so a crash resumes mid-stream; emitting only at the end defeats incremental.
- **stdout is the only data channel** — anything a connector prints to stdout that isn't a valid message corrupts the stream (route logs to LOG/stderr).
- **`emitted_at` is milliseconds** — destinations dedup/order on it.
- **Catalog negotiation is two-step** — `discover` advertises, the configured catalog decides; honor the configured cursor/pk, not the defaults.
- **TRACE ERROR vs LOG** — put real failures in TRACE so the platform can classify them; free text goes to LOG.

## Origin (reference only)

`airbytehq/airbyte-python-cdk` @ `main`: `airbyte_cdk/models/airbyte_protocol.py` (inlined),
`airbyte_cdk/models/airbyte_protocol_serializers.py`. Canonical spec: the `airbyte-protocol` schema in
`airbytehq/airbyte` docs (`docs/understanding-airbyte/airbyte-protocol.md`).

**Gaps to verify (cost-capped):** exact GLOBAL vs STREAM state nesting; full TRACE/CONTROL subtypes;
`advanced_auth` (OAuth) spec shape; serializer field-name casing (camelCase on the wire).
