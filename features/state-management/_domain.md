# state-management — domain

**What this domain means across repos studied:** how an application holds, mutates, queries, and
observes its in-memory state — especially structured *document* / *editor* state made of many
interrelated objects that change constantly (often at 60fps during a drag). The interesting
engineering lives in the *data model* (normalized records vs. nested trees; arrays paired with id
keyed lookups), *reactive reads* (live queries / selector subscriptions that recompute surgically
so unrelated updates don't re-render), *observable writes* (every change emitted as a precise diff),
and the *lifecycle seams* (validation, side-effects, snapshots) that let persistence, undo, and sync
hang off a single source of truth.

## Features filed here
| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Reactive Record Store | tldraw | [study](study/reactive-record-store--from-tldraw.md) | [build](build/reactive-record-store--from-tldraw.md) |
| Reactive Store Architecture | xyflow | [study](study/reactive-store--from-xyflow.md) | [build](build/reactive-store--from-xyflow.md) |
| JSON File Store with Async-Mutex | open-carrusel | [study](study/json-mutex-store--from-open-carrusel.md) | [build](build/json-mutex-store--from-open-carrusel.md) |

## Mental model
Two complementary takes on the same problem appear across the repos:

**A normalized reactive document store (tldraw):**
1. **Records** — flat, typed objects (`{id:'type:abc', typeName, ...props}`) keyed by an id that
   encodes the type; relationships are by id reference, not nesting.
2. **Reactive reads** — `get(id)` and queries return *live* values (computeds) that update only when
   relevant records change; indexes are maintained incrementally from change diffs.
3. **Observable writes** — every `put`/`remove` runs in a transaction, validates, fires
   before/after side-effects, and emits a `RecordsDiff {added,updated,removed}` tagged with a
   `source` (`user`|`remote`) — the lingua franca for undo, persistence, and multiplayer.
4. **Snapshots** — serialize/deserialize the whole store, running schema migrations on load.

**A central store + selector subscriptions + framework-agnostic core (xyflow):**
1. **Array + Map duality** — the user gives `nodes: Node[]`; the store derives a
   `nodeLookup: Map<id, InternalNode>` enriched with measured size, absolute position, z-index, and
   parent chain. Hot paths (drag/connect) read the Map; render reads the array.
2. **Selector subscriptions with an equality fn** — each component subscribes to just the slice it
   needs so unrelated state changes don't re-render it.
3. **Imperative actions on the store** — `setNodes`, `updateNodePositions`, `panBy`, … mutate state
   and trigger callbacks; subsystems call these.
4. **Core/adapter split** — all the heavy math lives in a plain-TS core; thin per-framework shells
   (React via Zustand, Svelte via stores) wire that math into their own reactivity.

The shared lesson: keep one authoritative model, let consumers read narrow slices reactively, and
maintain an id-keyed lookup alongside the user-facing arrays for O(1) access on the hot path.
