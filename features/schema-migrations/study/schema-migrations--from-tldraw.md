# Schema & Migrations — from [tldraw](https://github.com/tldraw/tldraw)

> Domain: [[_domain]] · Source: https://github.com/tldraw/tldraw (`packages/store` + `packages/tlschema`) · NotebookLM: <add link>

## What it does
It's the system that lets a tldraw document saved in 2022 still open in today's app — and lets
today's document still load on a slightly older client during a multiplayer session. Every record
type (and the store as a whole) has an ordered list of **migrations**: tiny functions that transform
data from one version to the next (`up`) and, ideally, back again (`down`). When a document is
loaded or received over the network, the system compares the document's recorded schema version
against the current one and runs exactly the migrations needed to bridge the gap — forward to
upgrade old data, or backward to send modern data to an older peer. It also validates every record
against its type so corrupt or malformed data is caught rather than silently rendered.

## Why it exists
tldraw is a long-lived SDK: documents are saved to disk, embedded in other products, and synced
live between clients that may be on different versions. The data format *will* change — a shape
gains a property, a property is renamed, an enum value is split. Without a migration system, every
such change would break old files and break multiplayer between mismatched clients. The
job-to-be-done: "evolve the data format freely over years, without ever stranding an old document or
breaking a cross-version collaboration session." This is the boring infrastructure that makes a
shippable, backwards-compatible product possible.

## How it actually works
**Migrations are identified by a global, namespaced id.** Each migration has an id like
`com.tldraw.shape/3` — a *sequence id* (`com.tldraw.shape`) plus a *version number* (`3`). A
**migration sequence** is the ordered list for one concern (one record type, or the store
structure). The current schema is just the set of sequences and the latest version reached in each.

**Three scopes of migration.** A migration is one of:
- **record** — transforms a single record (the common case: "shapes gained an `opacity` prop").
- **store** — transforms the whole record map at once (needed for cross-record changes, e.g.
  "split every page into a page + a camera record").
- **storage** — operates on the persistence layer itself (rare, for low-level storage changes).

**Migrations can declare cross-sequence dependencies.** Beyond the implicit "version N comes after
version N-1 in my own sequence," a migration can say `dependsOn: ['com.tldraw.page/2']` to express
"run me only after that other sequence's migration." All migrations across all sequences are then
**topologically sorted** (Kahn's algorithm with a distance-minimizing tie-break) into one correct
global order. This is what lets independent feature teams add migrations without coordinating exact
numbers, while still guaranteeing a safe execution order.

**The serialized schema is tiny.** When you save a document you also save its schema fingerprint.
The modern (v2) form is just `{ schemaVersion: 2, sequences: { 'com.tldraw.shape': 3,
'com.tldraw.page': 2, ... } }` — for each sequence, the highest version this document has been
migrated through. (There's a legacy v1 form with per-record version maps that the system still
reads.) On load, the system diffs "where the document is" against "where the code is," collects the
missing migrations via `getMigrationsSince`, sorts them, and runs them.

**Up and down, forward and backward.** Loading an old document runs the missing migrations *up*.
Critically, the multiplayer server uses the *same* machinery in reverse: to send a modern record to
a client running older code, it runs the relevant migrations *down* to that client's version. This
is why down-migrations matter — and why a sequence that lacks a needed down-migration causes the
server to *reject* an incompatible client rather than corrupt it.

**`retroactive` is a subtle but important flag.** A sequence marked `retroactive: true` (the
default) applies its migrations even to snapshots saved *before that sequence existed* — i.e. to
documents that don't mention the sequence at all. Non-retroactive sequences only run for documents
that already know about them. This controls whether a brand-new migration touches legacy data.

**Validation runs alongside migration.** Each record type carries a validator. After migrating (and
on every write), records are validated; on failure the schema can invoke an `onValidationFailure`
recovery hook rather than throwing outright, so one bad record needn't kill a whole load.

## The non-obvious parts
- **Namespaced ids decouple teams from version numbers.** Because a migration is `sequenceId/version`
  and ordering across sequences is by explicit `dependsOn` + topological sort, two unrelated features
  can each add "version 4" to their own sequence without colliding or having to agree on global
  ordering. This is the key scalability move.
- **The store-scope migration is the escape hatch.** Most format changes are per-record, but some
  are inherently cross-cutting (move data between records, introduce a new record type from existing
  ones). Having a whole-store migration scope means those aren't impossible — they're just a
  different migration kind.
- **Down-migrations are a networking feature, not just an "undo."** Their real job is letting a
  newer server talk to an older client by translating records *down* to the client's schema. Skip
  them and you can't support mixed-version multiplayer; you can only reject the old client.
- **The serialized schema got smaller on purpose.** v2 stores just one version number per sequence,
  not a per-record-type version matrix. Less to store, less to get wrong, and it maps directly onto
  the sequence model.
- **`retroactive` decides whether history gets rewritten.** It's the difference between "this new
  migration also fixes up every old file" and "this only matters going forward" — a real semantic
  choice, defaulted to the more aggressive option.
- **Migration is woven into load and into sync, not a one-off import tool.** The same code path runs
  on every snapshot load *and* on every cross-version connect/push. Migration isn't a batch utility;
  it's continuously in the hot path of opening and collaborating.

## Related
- [[reactive-record-store]] — `loadStoreSnapshot` and `getStoreSnapshot` call this on every load/save.
- [[multiplayer-sync]] — runs migrations *down* to bridge a newer server to an older client, and
  rejects clients whose gap can't be bridged (missing down-migrations).
- [[signals-reactivity-engine]] — the records being migrated live in the signals-backed store.
- See also: Prisma/Rails schema migrations (DB-side, one-directional, server-run) vs. tldraw's
  in-document, bidirectional, client-and-server migrations.
