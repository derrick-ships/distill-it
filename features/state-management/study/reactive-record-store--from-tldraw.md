# Reactive Record Store — from [tldraw](https://github.com/tldraw/tldraw)

> Domain: [[_domain]] · Source: https://github.com/tldraw/tldraw (`packages/store`, `@tldraw/store`) · NotebookLM: <add link>

## What it does
It's an in-memory, reactive, client-side **database** for normalized records. Everything in a tldraw
document — every shape, the page, the camera, the user's selection, each collaborator's cursor — is
a flat record with an `id` and a `typeName`, and they all live in one Store. You put records in, you
remove them, you query them, and you *subscribe* to changes. Because it's built on the signals
engine, queries are reactive: ask for "all selected shapes" and you get a live value that
recomputes only when something relevant changes. Every change the store makes is also emitted as a
precise **diff** (`{added, updated, removed}`), tagged with whether it came from the local user or
a remote peer — which is exactly what undo/redo, persistence, and multiplayer all feed on.

## Why it exists
A canvas app's state is a graph of thousands of small interrelated objects that change constantly
and need to be: rendered reactively, queried efficiently ("which shapes are on this page?"),
persisted, synced across the network, undone/redone, and migrated as the schema evolves. Holding
that in plain React state or a Redux store would be either too slow (re-render everything) or too
manual (hand-write every selector and every diff). tldraw's answer is a **normalized record store
with first-class reactivity and first-class diffs**. The job-to-be-done: "be the single source of
truth for document state, make reads reactive and surgical, and make every write observable as a
clean patch."

## How it actually works
**Records are flat and typed.** Every record is `{ id: 'shape:abc', typeName: 'shape', ...props }`.
The `id` literally encodes the type as a prefix. Each record type is created from a `RecordType`
factory that knows the type's default properties, its validator, and its **scope** — one of
`document` (persisted and synced), `session` (this browser tab only, never synced), or `presence`
(ephemeral, synced to others but not persisted, like a live cursor). Scope is what lets one store
hold both your saved drawing and your transient cursor without confusing the two.

**The store holds all records in an atom-backed map.** Internally it's an `AtomMap` — a map where
each entry is reactive, so reading one record subscribes you to just that record, not the whole
store. `get(id)` is a reactive read; `unsafeGetWithoutCapture(id)` reads without subscribing.

**Writes go through `put` and `remove`, wrapped in a transaction.** When you put records, the store
validates each one, figures out which are new vs. updates, runs any "before" side-effect callbacks,
applies the change, then runs "after" callbacks. All of this happens inside one atomic transaction
(the signals transaction), so observers see a single coherent batch, not a flicker of intermediate
states.

**Every change becomes a diff in the history.** The store keeps a special `history` atom whose
*value* is just a clock number but whose *diff buffer* accumulates `RecordsDiff` objects
(`{added, updated, removed}`). Listeners registered via `listen()` receive these diffs — and they
can filter by **source** (`user` vs `remote`) and by **scope**. So undo/redo can listen for
user-sourced document changes, persistence can listen for document changes from any source, and the
renderer can just react to the relevant records. Listeners are throttled to a frame so a burst of
changes during a drag collapses into one notification.

**Queries are computeds over the history.** The `StoreQueries` object builds reactive indexes and
result sets. An **index** (e.g. "shapes by parentId") is a computed `Map<value, Set<id>>` that
updates *incrementally*: it reads the store's filtered change-history diff and applies only the
deltas to the previous index, using an `IncrementalSetConstructor` that tracks exactly which ids
entered or left each bucket. A query like `records('shape', () => ({ parentId: { eq: pageId } }))`
returns a live array that recomputes only when matching shapes change. Single-record queries,
id-sets (with their own diffs), and one-shot non-reactive `exec()` are all available.

**Two special write modes** make it network- and tooling-friendly. `mergeRemoteChanges(fn)` runs a
block of writes and tags every resulting change as `source: 'remote'` instead of `'user'` — that's
how incoming sync patches apply without being treated as new user edits (and without being re-sent).
`extractingChanges(fn)` runs a block and hands you back the aggregated diff *without* notifying
listeners — handy for computing a patch you'll apply elsewhere.

**Snapshots** serialize the whole thing: `getStoreSnapshot()` returns `{ store: {id→record},
schema }`, and `loadStoreSnapshot()` clears the store, runs migrations to bring old data up to the
current schema, and replaces everything — with side-effects disabled during the load so it doesn't
fire a thousand "shape created" callbacks.

## The non-obvious parts
- **Normalization + id-encoded types.** Flat records keyed by `type:uniqueId` make every lookup,
  diff, and patch trivial. There's no nested tree to walk — relationships are by id reference
  (a shape has a `parentId`), and indexes make those references fast to traverse.
- **Scope is a three-way switch, not a boolean.** `document`/`session`/`presence` cleanly separates
  "save this," "this is just my tab," and "show this to others live but never save it." One store,
  three lifecycles, decided per record type.
- **Diffs are produced, not reconstructed.** Because the underlying signals carry diff history, the
  store doesn't have to deep-compare snapshots to know what changed — it already has the patch. This
  is the single most important property for everything downstream (undo, sync, persistence).
- **`source: user | remote` is a tiny flag with huge leverage.** It's what stops an infinite echo in
  multiplayer (don't re-send what you just received) and what keeps remote edits out of your local
  undo stack. One enum threaded through the listener system does both jobs.
- **Indexes update incrementally.** A naïve reactive index rebuilds the whole `Map` on any change;
  tldraw's reads the change diff and mutates only the affected buckets, which is what keeps querying
  cheap on documents with thousands of shapes.
- **Listeners are throttled to a frame.** Coalescing a drag's worth of mutations into one
  notification is the difference between 60fps and a stutter.

## Related
- [[signals-reactivity-engine]] — the substrate: records are atoms, queries are computeds, the
  history is an atom with a diff buffer, writes are transactions.
- [[schema-migrations]] — `loadStoreSnapshot` runs these to upgrade old documents on load.
- [[multiplayer-sync]] — consumes the store's diffs and `mergeRemoteChanges`/`source` flags to sync.
- See also: Redux/normalizr (normalized state but no built-in reactivity/diffs), MobX-state-tree,
  Yjs (CRDT — different conflict model; tldraw uses server-authoritative diffs instead).
