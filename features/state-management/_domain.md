# state-management — domain

**What this domain means across repos studied:** how an application holds, mutates, queries, and
observes its in-memory state — especially structured *document* state made of many interrelated
objects. The interesting engineering lives in the *data model* (normalized records vs. nested
trees), *reactive reads* (live queries that recompute surgically), *observable writes* (every change
emitted as a precise diff), and the *lifecycle seams* (validation, side-effects, snapshots) that let
persistence, undo, and sync hang off a single source of truth.

## Features filed here
| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Reactive Record Store | tldraw | [study](study/reactive-record-store--from-tldraw.md) | [build](build/reactive-record-store--from-tldraw.md) |

## Mental model
A reactive document store is a normalized, in-memory database with reactivity built in:
1. **Records** — flat, typed objects (`{id:'type:abc', typeName, ...props}`) keyed by an id that
   encodes the type; relationships are by id reference, not nesting.
2. **Reactive reads** — `get(id)` and queries return *live* values (computeds) that update only when
   relevant records change; indexes are maintained incrementally from change diffs.
3. **Observable writes** — every `put`/`remove` runs in a transaction, validates, fires
   before/after side-effects, and emits a `RecordsDiff {added,updated,removed}` tagged with a
   `source` (`user`|`remote`) — the lingua franca for undo, persistence, and multiplayer.
4. **Snapshots** — serialize/deserialize the whole store, running schema migrations on load.
