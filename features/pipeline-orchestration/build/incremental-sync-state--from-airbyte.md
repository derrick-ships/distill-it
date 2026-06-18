# Incremental Sync & State (build spec) — distilled from airbyte

## Summary

Cursor-based incremental reads with resumable state. `DatetimeBasedCursor` slices `[start-lookback, end]`
into `step`-sized windows → one `stream_slice{start_time,end_time}` per window (injected into the request
via interpolation); observes each record's `cursor_field`, tracks the **highest value seen**, and emits
state `{cursor_field: highest_datetime}` at slice boundaries. Next run resumes from saved state. Lookback
catches late updates (destinations dedup on PK). State rides the protocol's STATE messages.

## Core logic (inlined)

### DatetimeBasedCursor (`incremental/datetime_based_cursor.py`)

```python
@dataclass
class DatetimeBasedCursor(DeclarativeCursor):
    start_datetime: Union[MinMaxDatetime, str]
    cursor_field: Union[InterpolatedString, str]
    datetime_format: str
    end_datetime: Optional[...] = None
    step: Optional[str] = None              # ISO-8601 duration, e.g. "P30D"; window size
    cursor_granularity: Optional[str] = None  # smallest tick; required iff step is set (no overlap)
    lookback_window: Optional[...] = None
    _highest_observed_cursor_field_value: Optional[str] = None   # the value that becomes state

    def __post_init__(self, parameters):
        if bool(self.step) != bool(self.cursor_granularity):
            raise ValueError("If step is defined, cursor_granularity must be too, and vice-versa.")
        self._start_datetime = MinMaxDatetime.create(self.start_datetime, parameters)
        self._end_datetime   = MinMaxDatetime.create(self.end_datetime, parameters) if self.end_datetime else None

    def stream_slices(self) -> Iterable[StreamSlice]:
        start = self._start - self._lookback                      # apply lookback
        end   = self._end or now()
        for win_start, win_end in self._partition_daterange(start, end, self._step, self._cursor_granularity):
            yield {"start_time": fmt(win_start), "end_time": fmt(win_end)}   # consumed via interpolation

    def observe(self, stream_slice, record):                      # called per record
        val = record[self.cursor_field]
        if self._highest_observed is None or val > self._highest_observed:
            self._highest_observed = val                          # track MAX, not last

    def close_slice(self, stream_slice):                          # at slice boundary
        self._cursor = max(self._cursor or self._start, self._highest_observed or self._start)

    def get_stream_state(self) -> Mapping:
        return {self.cursor_field: self._cursor}                  # {"updated_at": "2026-06-01T00:00:00Z"}

    def set_initial_state(self, stream_state):                    # resume
        self._cursor = stream_state.get(self.cursor_field) or self._start

    def should_be_synced(self, record) -> bool:                   # skip out-of-window records
        return self._start <= record[self.cursor_field] <= (self._end or now())
```

### How it threads through the retriever

- `stream_slices()` → the retriever loops once per slice; the slice's `{start_time,end_time}` are
  available in the interpolation context, so the manifest's request params can do
  `{{ stream_slice['start_time'] }}` / `{{ stream_slice['end_time'] }}`.
- The selector/retriever calls `observe(record)` for each record; `close_slice()` at the end of each
  window; the source emits an `AirbyteStateMessage{ stream_state: get_stream_state() }` after each slice.
- Next run: `set_initial_state(prev_state)` makes the saved cursor the effective start.

## Data contracts

- **Manifest cursor:** `incremental_sync: { type: DatetimeBasedCursor, cursor_field, datetime_format, start_datetime, end_datetime?, step?, cursor_granularity?, lookback_window? }`.
- **stream_slice:** `{ start_time, end_time }`.
- **stream_state:** `{ <cursor_field>: <datetime string> }` (per-stream; GLOBAL for shared cursors).
- **STATE message:** `AirbyteStateMessage{type:STREAM, stream:{stream_descriptor:{name}, stream_state:{cursor_field: value}}}`.

## Dependencies & assumptions

- A datetime lib (ISO-8601 durations), the interpolation layer, the protocol STATE emission, a
  retriever that calls `stream_slices`/`observe`/`close_slice`. Destinations must dedup on primary key.
- Swappable: cursor type (datetime is the common one; there are incrementing-id and custom cursors too).

## To port this, you need:

- [ ] A cursor that slices a range into `step` windows and yields `stream_slice` bounds for the request.
- [ ] Per-record `observe` tracking the MAX cursor value; `close_slice` to advance state.
- [ ] State get/set so the next run resumes from the saved cursor.
- [ ] State emitted at slice boundaries (interleaved with records).
- [ ] A `lookback_window` (and PK dedup downstream) for late/updated rows.
- [ ] A `should_be_synced` window filter.

## Gotchas

- **Emit state per slice**, not once at the end — otherwise a crash loses the whole run.
- **State = MAX observed cursor**, not the loop position — out-of-order records would otherwise corrupt resume.
- **`step` + `cursor_granularity` are a pair** — granularity prevents window N+1 from overlapping/ skipping a tick.
- **Lookback re-emits rows** — only safe if the destination dedups on primary key.
- **Slice bounds must reach the request via interpolation** — the URL/params template needs `stream_slice['start_time']`.
- **Timezones/format** — the cursor compares strings via `datetime_format`; mismatched formats silently mis-slice.

## Origin (reference only)

`airbytehq/airbyte-python-cdk` @ `main`:
`airbyte_cdk/legacy/sources/declarative/incremental/datetime_based_cursor.py` (inlined),
plus `.../incremental/{concurrent cursors, per_partition_cursor}.py` and the protocol STATE models.

**Gaps to verify (cost-capped):** exact `_partition_daterange` arithmetic + granularity handling; concurrent
cursor reconciliation; per-partition (substream) state nesting; `MinMaxDatetime` interpolation.
