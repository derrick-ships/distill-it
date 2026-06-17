# Schema & Migrations (build spec) — distilled from tldraw

## Summary
Build a versioned, bidirectional migration system for evolving a record-store's data format over
time and across client/server version gaps. Migrations are identified by namespaced ids
(`sequenceId/version`, e.g. `com.app.shape/3`), grouped into ordered **sequences**, and have a
**scope** (`record` | `store` | `storage`). Cross-sequence ordering is expressed with `dependsOn`
and resolved by topological sort. A tiny **SerializedSchema** (`{schemaVersion:2, sequences:{id→version}}`)
travels with every snapshot; on load (or cross-version sync) the system diffs persisted-vs-current,
collects the missing migrations, sorts them, and runs them **up** (upgrade) or **down** (downgrade,
for talking to older peers). Pairs with [[reactive-record-store]] and [[multiplayer-sync]].

## Core logic (inlined)

### Migration types
```ts
type MigrationId = `${string}/${number}`          // 'com.app.shape/3'

type Migration = {
  readonly id: MigrationId
  readonly dependsOn?: readonly MigrationId[]
} & (
  | { readonly scope: 'record'
      readonly filter?: (r: UnknownRecord) => boolean              // run only on matching records
      readonly up:   (r: UnknownRecord) => void | UnknownRecord    // mutate in place OR return new
      readonly down?: (r: UnknownRecord) => void | UnknownRecord }
  | { readonly scope: 'store'
      readonly up:   (s: SerializedStore) => void | SerializedStore // whole {id→record} map
      readonly down?: (s: SerializedStore) => void | SerializedStore }
  | { readonly scope: 'storage'
      readonly up:   (storage: SynchronousRecordStorage) => void
      readonly down?: never }
)

interface MigrationSequence {
  sequenceId: string       // 'com.app.shape'
  retroactive: boolean     // true = apply even to snapshots saved before this sequence existed
  sequence: Migration[]    // in ascending version order
}
interface StandaloneDependsOn { readonly dependsOn: readonly MigrationId[] }  // ordering-only node, no transform
```

### Factories + id helpers
```ts
function createMigrationIds<const ID extends string, const V extends Record<string, number>>(
  sequenceId: ID, versions: V): { [K in keyof V]: `${ID}/${V[K]}` }
// e.g. createMigrationIds('com.app.shape', { AddOpacity: 1, RenameColor: 2 })
//   => { AddOpacity: 'com.app.shape/1', RenameColor: 'com.app.shape/2' }

function createMigrationSequence(opts: {
  sequenceId: string; retroactive?: boolean   // default true
  sequence: Array<Migration | StandaloneDependsOn>
}): MigrationSequence
// validateMigrations() runs here: versions must be 1..N contiguous & ascending within the sequence.

function createRecordMigrationSequence(opts: {
  sequenceId: string; recordType: string; retroactive?: boolean
  filter?: (r: UnknownRecord) => boolean
  sequence: Array<Omit<Extract<Migration,{scope:'record'}>, 'scope'|'id'> & { id: MigrationId }>
}): MigrationSequence
// sugar: injects scope:'record' and a typeName filter into every entry.

function parseMigrationId(id: MigrationId): { sequenceId: string; version: number } {
  const i = id.lastIndexOf('/'); return { sequenceId: id.slice(0,i), version: +id.slice(i+1) }
}
```

### Topological sort (global execution order)
```ts
function sortMigrations(migrations: Migration[]): Migration[] {
  // Build edges:
  //   implicit: within a sequence, version N depends on version N-1
  //   explicit: each migration.dependsOn[] adds an edge
  // Kahn's algorithm (repeatedly emit zero-in-degree nodes). Tie-break to MINIMIZE total distance,
  // i.e. prefer emitting a node whose dependents are "closest", keeping related migrations adjacent.
  // Throws on cycles or references to unknown migration ids.
}
```

### Schema object
```ts
class StoreSchema<R extends UnknownRecord, Props = unknown> {
  readonly types: Record<R['typeName'], RecordType<any, any>>
  readonly migrations: Record<string, MigrationSequence>   // sequenceId -> sequence
  private sortedMigrations: Migration[]                     // sortMigrations(all sequences flattened)

  static create<R, P>(types, options?: {
    migrations?: MigrationSequence[]
    onValidationFailure?: (info: { error: unknown; record: R; phase: string; recordBefore: R|null }) => R
    createIntegrityChecker?: (store: Store<R>) => () => void
  }): StoreSchema<R, P>

  // current serialized fingerprint (travels with snapshots / connect handshake)
  serialize(): SerializedSchema {
    return { schemaVersion: 2,
             sequences: mapValues(this.migrations, seq => highestVersion(seq)) }
  }

  // which migrations are needed to bridge persistedSchema -> current?
  getMigrationsSince(persisted: SerializedSchema): Result<Migration[], string> {
    const out: Migration[] = []
    for (const seq of Object.values(this.migrations)) {
      const have = versionOf(persisted, seq.sequenceId)        // 0 / undefined if absent
      const knowsSequence = sequencePresentIn(persisted, seq.sequenceId)
      if (have === undefined && !knowsSequence && !seq.retroactive) continue  // skip non-retroactive unknown seq
      for (const m of seq.sequence)
        if (parseMigrationId(m.id).version > (have ?? 0)) out.push(m)
    }
    // if any needed migration is BELOW persisted version but we're going down and it lacks `down` -> Err
    return Ok(sortMigrations(out))
  }

  migratePersistedRecord(record: R, persisted: SerializedSchema, direction: 'up'|'down' = 'up'): MigrationResult<R> {
    const migrations = direction === 'up'
      ? getMigrationsSince(persisted)            // missing ones, ascending
      : getMigrationsToGoDownTo(persisted)       // ones to undo, descending; FAIL if any lacks `down`
    let rec = record
    for (const m of migrations) {
      if (m.scope !== 'record') continue
      if (m.filter && !m.filter(rec)) continue
      const fn = direction === 'up' ? m.up : m.down
      if (!fn) return { type: 'error', reason: MigrationFailureReason.MigrationError }
      const res = fn(rec); if (res) rec = res as R         // up/down may mutate or return
    }
    return { type: 'success', value: rec }
  }

  migrateStoreSnapshot(snapshot: StoreSnapshot<R>, opts?: { mutateInputStore?: boolean }): MigrationResult<SerializedStore<R>> {
    const migrations = getMigrationsSince(snapshot.schema).unwrap()  // ascending, mixed scopes, topo-sorted
    let store = opts?.mutateInputStore ? snapshot.store : structuredClone(snapshot.store)
    for (const m of migrations) {
      if (m.scope === 'store') { const r = m.up(store); if (r) store = r }
      else if (m.scope === 'record') {
        for (const id in store) {
          const rec = store[id]; if (m.filter && !m.filter(rec)) continue
          const r = m.up(rec); if (r) store[id] = r as R
        }
      } // 'storage' scope handled by the persistence layer, not here
    }
    return { type: 'success', value: store }
  }

  validateRecord(store: Store<R>, record: R, phase: 'initialize'|'createRecord'|'updateRecord'|'tests', before: R|null): R {
    try { return this.types[record.typeName].validate(record, before ?? undefined) }
    catch (error) { if (this.options.onValidationFailure)
      return this.options.onValidationFailure({ error, record, phase, recordBefore: before }); throw error }
  }
}
```

### SerializedSchema shapes
```ts
type SerializedSchema = SerializedSchemaV1 | SerializedSchemaV2
interface SerializedSchemaV2 { schemaVersion: 2; sequences: { [sequenceId: string]: number } }
interface SerializedSchemaV1 {                       // legacy, still readable
  schemaVersion: 1; storeVersion: number
  recordVersions: Record<string, { version: number } |
    { version: number; subTypeVersions: Record<string, number>; subTypeKey: string }>
}
// upgradeSchema(v1): translate per-record versions into the sequence model before diffing.

type MigrationResult<T> = { type: 'success'; value: T } | { type: 'error'; reason: MigrationFailureReason }
enum MigrationFailureReason { IncompatibleSubtype, UnknownType, TargetVersionTooNew, TargetVersionTooOld, MigrationError, UnrecognizedSubtype }
```

## Data contracts
- **MigrationId:** `` `${sequenceId}/${version}` `` — version is a positive integer, contiguous within a sequence.
- **SerializedSchema v2:** `{ schemaVersion: 2, sequences: { [sequenceId]: latestVersionApplied } }` —
  saved alongside every `StoreSnapshot` and sent in the sync connect handshake.
- **MigrationResult:** discriminated `success | error(reason)` — callers must handle the rejection
  (especially "can't go down: missing down-migration").

## Dependencies & assumptions
- Operates on the record model from [[reactive-record-store]] (`{id, typeName, ...}`, `SerializedStore = {id→R}`).
- Validators are pluggable (tldraw uses `@tldraw/validate`, a small zod-like combinator lib); any
  validator with `validate(record)` works, or no-op for an MVP.
- `up`/`down` functions are author-written and may either mutate in place or return a new object —
  support both. Keep them pure-ish and total.
- Topological sort assumes a DAG; cycles are an authoring bug and should throw at sequence-build time.

## To port this, you need:
- [ ] A namespaced migration id scheme (`sequenceId/version`) + `parseMigrationId`/`createMigrationIds`.
- [ ] Sequences with `retroactive` and per-migration `scope` (`record`/`store`[/`storage`]).
- [ ] `dependsOn` + a topological sort (Kahn) producing one global order; validate contiguity per sequence.
- [ ] A compact `SerializedSchema` carried with every snapshot and connect handshake.
- [ ] `getMigrationsSince(persisted)` diffing persisted-vs-current, honoring `retroactive`.
- [ ] Both directions: `up` for load/upgrade, `down` for sending modern data to older peers.
- [ ] Per-record validation with an `onValidationFailure` recovery hook.
- [ ] A clear failure result when a down-migration is missing (→ reject the peer, don't corrupt).

## Gotchas
- **Down-migrations are mandatory for cross-version multiplayer.** A record-scope migration without
  `down` means a newer server *cannot* serve an older client past that version — it must reject the
  client. Decide this consciously per migration.
- **`retroactive` default = true** means a newly-added sequence will also run against ancient
  snapshots that never heard of it. If a migration should only affect data created after it shipped,
  set `retroactive: false` — easy to get backwards.
- **Topological order ≠ numeric order.** Don't run migrations by sorting ids lexically; `dependsOn`
  edges can force a `page/2` to run before a `shape/2`. Always sort the merged set.
- **Store-scope migrations see the whole map** and can add/remove/retype records — run them at the
  store level, not per-record, and run record-scope migrations on records that *still exist* after them.
- **Mutate-or-return ambiguity:** `up`/`down` may mutate in place and return nothing, or return a new
  object. Always do `const r = fn(x); if (r) x = r`.
- **Validate after migrating, not before** — old data is only guaranteed valid against the *current*
  schema once migrations have run. And disable side-effects in the store while loading migrated data.
- **Version numbers are contiguous and append-only.** Never renumber or delete a shipped migration;
  documents in the wild reference exact versions. Add a new one instead.
- **Clone before mutating snapshots** unless `mutateInputStore` is explicitly set — silently mutating
  a caller's snapshot during a "read" migrate is a nasty bug.

## Origin (reference only)
Repo: https://github.com/tldraw/tldraw — `@tldraw/store` (`packages/store/src/lib/`): `migrate.ts`
(types, `createMigrationSequence`, `createMigrationIds`, `sortMigrations`, `parseMigrationId`),
`StoreSchema.ts` (`getMigrationsSince`, `migratePersistedRecord`, `migrateStoreSnapshot`,
`validateRecord`, `SerializedSchema`). Concrete sequences live in `@tldraw/tlschema`
(`packages/tlschema/src/`) — e.g. `shape/` migrations, `records/` migrations, `createTLSchema.ts`.
Validators in `@tldraw/validate`.
