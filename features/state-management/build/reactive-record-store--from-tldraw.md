# Reactive Record Store (build spec) — distilled from tldraw

## Summary
Build an in-memory, reactive, normalized record database. Records are flat `{id, typeName, ...props}`
objects keyed by a `type:uniqueId` id and held in a reactive map (each entry an atom). Writes go
through `put`/`remove` inside an atomic transaction, are validated, fire before/after side-effects,
and produce a precise `RecordsDiff {added, updated, removed}`. A `history` atom accumulates those
diffs; `listen()` consumers subscribe filtered by `source` (`user`|`remote`) and `scope`. A
`StoreQueries` layer gives reactive, incrementally-maintained indexes and result sets. Built on a
signals engine (see [[signals-reactivity-engine]] build spec) — that dependency is assumed below.

## Core logic (inlined)

### Record + RecordType
```ts
interface BaseRecord<TypeName extends string, Id extends string> { readonly id: Id; readonly typeName: TypeName }
type RecordScope = 'document' | 'session' | 'presence'
// document: persisted + synced. session: this-instance only, never synced/persisted.
// presence: synced to peers but NOT persisted; read-only on other peers (e.g. live cursor).

class RecordType<R extends UnknownRecord, RequiredProps extends keyof R> {
  constructor(public readonly typeName: R['typeName'], private config: {
    createDefaultProperties: () => Omit<R, 'id'|'typeName'|RequiredProps>
    validator?: { validate(r: unknown): R; validateUsingKnownGoodVersion?(prev: R, n: unknown): R }
    scope?: RecordScope
    ephemeralKeys?: { [K in Exclude<keyof R,'id'|'typeName'>]: boolean }  // excluded from snapshot+sync
  }) { this.scope = config.scope ?? 'document' }

  create(props: Pick<R,RequiredProps> & Partial<Omit<R,'id'|'typeName'>>): R {
    return { ...this.config.createDefaultProperties(), ...props,
             id: props.id ?? this.createId(), typeName: this.typeName } as R
  }
  createId(unique = uniqueId()): R['id'] { return `${this.typeName}:${unique}` as R['id'] }   // 'shape:abc123'
  isInstance(r?: UnknownRecord): r is R { return r?.typeName === this.typeName }
  isId(id?: string): id is R['id'] { return !!id && id.startsWith(this.typeName + ':') }
  parseId(id: R['id']): string { return id.slice(this.typeName.length + 1) }
  validate(record: unknown, before?: R): R { /* validator.validate, or validateUsingKnownGoodVersion(before,record) */ }
  clone(r: R): R { return { ...structuredClone(r), id: this.createId() } }
}
function createRecordType<R>(typeName, config: { validator?; scope: RecordScope; ephemeralKeys? }): RecordType<R, never>
// uniqueId(): short collision-resistant string (nanoid-style).
```

### RecordsDiff (the universal change shape)
```ts
interface RecordsDiff<R extends UnknownRecord> {
  added:   Record<IdOf<R>, R>
  updated: Record<IdOf<R>, [from: R, to: R]>
  removed: Record<IdOf<R>, R>
}
function squashRecordDiffsMutable<R>(target: RecordsDiff<R>, diffs: RecordsDiff<R>[]): void
// merges sequentially: added-then-removed cancels; added-then-updated stays added with latest value; etc.
function reverseRecordsDiff<R>(d: RecordsDiff<R>): RecordsDiff<R>  // swap added<->removed, flip updated tuples
type ChangeSource = 'user' | 'remote'
interface HistoryEntry<R> { changes: RecordsDiff<R>; source: ChangeSource }
```

### Store
```ts
class Store<R extends UnknownRecord, Props = unknown> {
  readonly schema: StoreSchema<R, Props>
  private readonly records: AtomMap<IdOf<R>, R>            // each entry reactive
  readonly history: Atom<number, RecordsDiff<R>>          // value=clock, diff-buffer=RecordsDiff, historyLength≈1000
  readonly query: StoreQueries<R>
  private readonly sideEffects: StoreSideEffects<R>
  private historyAccumulator = new HistoryAccumulator<R>() // batches diffs between flushes
  private isMergingRemoteChanges = false

  get(id): R | undefined { return this.records.get(id) }            // reactive
  unsafeGetWithoutCapture(id): R | undefined { return this.records.__unsafeGetWithoutCapture(id) }
  allRecords(): R[] { return [...this.records.values()] }

  put(records: R[], phaseOverride?: 'initialize'): void {
    this.atomic(() => {
      const diff: RecordsDiff<R> = { added:{}, updated:{}, removed:{} }
      for (const r of records) {
        const prev = this.records.__unsafeGetWithoutCapture(r.id)
        const phase = phaseOverride ?? (prev ? 'updateRecord' : 'createRecord')
        let next = this.schema.validateRecord(this, r, phase, prev ?? null)
        if (prev) {
          next = this.sideEffects.handleBeforeChange(prev, next, 'user')   // before-update hook may transform
          if (prev === next) continue
          this.records.set(r.id, next); diff.updated[r.id] = [prev, next]
        } else {
          next = this.sideEffects.handleBeforeCreate(next, 'user')
          this.records.set(r.id, next); diff.added[r.id] = next
        }
      }
      this.commitDiff(diff)               // push into history + accumulator; run after-create/after-change hooks
    })
  }

  remove(ids: IdOf<R>[]): void {
    this.atomic(() => {
      const diff = { added:{}, updated:{}, removed:{} as Record<IdOf<R>,R> }
      for (const id of ids) {
        const prev = this.records.__unsafeGetWithoutCapture(id); if (!prev) continue
        this.sideEffects.handleBeforeDelete(prev, 'user')
        this.records.delete(id); diff.removed[id] = prev
      }
      this.commitDiff(diff)               // after-delete hooks fire here
    })
  }

  // apply a precomputed diff (used by sync + undo). Honors current source flag.
  applyDiff(diff: RecordsDiff<R>, opts?: { runCallbacks?: boolean }): void { /* put added/updated, remove removed, atomic */ }

  // run fn; tag all resulting changes as 'remote' (don't echo back, don't enter local undo)
  mergeRemoteChanges(fn: () => void): void {
    if (this.isMergingRemoteChanges) throw Error('cannot nest')
    this.atomic(() => { this.isMergingRemoteChanges = true; try { fn() } finally { this.isMergingRemoteChanges = false } }, 'remote')
  }

  // run fn; return aggregated diff WITHOUT notifying listeners
  extractingChanges(fn: () => void): RecordsDiff<R> { /* swap in a fresh accumulator, run, restore, return collected diff */ }

  listen(onHistory: (e: HistoryEntry<R>) => void, filters?: Partial<{ source: ChangeSource|'all'; scope: RecordScope|'all' }>): () => void
  // filtered, throttled-to-frame delivery; returns unsubscribe.

  private currentSource(): ChangeSource { return this.isMergingRemoteChanges ? 'remote' : 'user' }
  private commitDiff(diff: RecordsDiff<R>) {                      // skip empty diffs
    if (isEmpty(diff)) return
    this.history.set(this.history.get() + 1, diff)               // bump clock, push diff into buffer
    this.historyAccumulator.add({ changes: diff, source: this.currentSource() })
    this.sideEffects.handleAfter(diff, this.currentSource())     // after-create/change/delete
  }
  atomic<T>(fn: () => T, source: ChangeSource = 'user'): T { return transact(fn) }  // signals transaction
}
```

### Side effects (lifecycle hooks)
```ts
class StoreSideEffects<R> {
  registerBeforeCreateHandler(typeName, (record, source) => record): () => void
  registerAfterCreateHandler (typeName, (record, source) => void): () => void
  registerBeforeChangeHandler(typeName, (prev, next, source) => next): () => void
  registerAfterChangeHandler (typeName, (prev, next, source) => void): () => void
  registerBeforeDeleteHandler(typeName, (record, source) => void | false): () => void  // false vetoes delete
  registerAfterDeleteHandler (typeName, (record, source) => void): () => void
  // before-change/create handlers may RETURN a modified record (e.g. clamp values). Disabled during loadSnapshot.
}
```

### StoreQueries (reactive querying)
```ts
type QueryExpression<R> = { [K in keyof R]?: { eq: R[K] } | { neq: R[K] } | { gt: R[K] } }
type RSIndexMap<R>  = Map<unknown, Set<IdOf<R>>>
type RSIndexDiff<R> = Map<unknown, CollectionDiff<IdOf<R>>>   // CollectionDiff = { added?: Set; removed?: Set }

class StoreQueries<R> {
  // reactive Map<propValue, Set<id>>, maintained INCREMENTALLY from the store's filtered history diff
  index<T extends R['typeName']>(typeName: T, property: string): Computed<RSIndexMap, RSIndexDiff> {
    // __uncached_createIndex():
    //   const setConstructors = new Map<value, IncrementalSetConstructor<id>>()
    //   const add = (value, id) => { let c = setConstructors.get(value)
    //                                ?? new IncrementalSetConstructor(prevIndex.get(value) ?? new Set())
    //                                c.add(id); setConstructors.set(value,c) }
    //   const remove = (value, id) => { ...c.remove(id)... }
    //   read filterHistory(typeName).getDiffSince(lastEpoch); for each added/updated/removed apply add/remove
    //   build next index + a per-bucket CollectionDiff; return WithDiff(nextIndex, indexDiff)
  }
  filterHistory<T>(typeName: T): Computed<number, RecordsDiff<Extract<R,{typeName:T}>>>
  // computed over store.history that keeps only records of typeName; reconciles same-epoch add+remove to nothing.

  records<T>(typeName: T, q?: () => QueryExpression, name?): Computed<Extract<R,{typeName:T}>[]>   // shallow-eq guarded
  record <T>(typeName: T, q?: () => QueryExpression, name?): Computed<Extract<R,{typeName:T}> | undefined>
  ids   <T>(typeName: T, q?: () => QueryExpression, name?): Computed<Set<IdOf<R>>, CollectionDiff<IdOf<R>>>
  exec  <T>(typeName: T, q: QueryExpression): Extract<R,{typeName:T}>[]    // one-shot, non-reactive
}
function executeQuery<R>(store, typeName, q: QueryExpression<R>): Set<IdOf<R>>  // uses indexes where possible
```

### Snapshots
```ts
interface StoreSnapshot<R> { store: Record<IdOf<R>, R>; schema: SerializedSchema }
getStoreSnapshot(scope: RecordScope|'all' = 'document'): StoreSnapshot<R>   // omits ephemeralKeys + non-matching scopes
loadStoreSnapshot(snapshot: StoreSnapshot<R>): void
//   migrate snapshot to current schema (see schema-migrations build) → clear store →
//   put all records with side-effects DISABLED → re-enable. Done atomically.
migrateSnapshot(snapshot: StoreSnapshot<R>): StoreSnapshot<R>   // migrate without loading
```

### IncrementalSetConstructor (how indexes stay cheap)
```ts
class IncrementalSetConstructor<T> {
  constructor(private previous: Set<T>) {}
  private nextValues?: Set<T>; private diff?: { added?: Set<T>; removed?: Set<T> }
  add(v: T)    { if (!this.previous.has(v)) { /* record in diff.added, lazily clone set */ } }
  remove(v: T) { if (this.previous.has(v))  { /* record in diff.removed */ } }
  get(): { value: Set<T>; diff?: CollectionDiff<T> } | undefined  // undefined if no net change
}
```

## Data contracts
- **Record:** `{ id: \`${typeName}:${string}\`, typeName: string, ...props }`.
- **RecordsDiff:** `{ added: {id→R}, updated: {id→[from,to]}, removed: {id→R} }` — the lingua franca
  for undo, persistence, and sync.
- **HistoryEntry:** `{ changes: RecordsDiff, source: 'user'|'remote' }`.
- **StoreSnapshot:** `{ store: {id→R}, schema: SerializedSchema }`.
- **QueryExpression:** `{ propName: { eq|neq|gt: value } }`.

## Dependencies & assumptions
- Requires the signals engine ([[signals-reactivity-engine]]): `atom`, `computed`, `transact`,
  history buffers, `WithDiff`. The store is essentially a structured facade over signals.
- `AtomMap`: a reactive map where each key is independently subscribable (so `get(id)` subscribes to
  just that record). Internally an `ImmutableMap` of atoms + an atom tracking the key set.
- Validation via the schema layer (swappable; can be no-op for an MVP).
- Persistence/sync are *external consumers* of `listen()` and snapshots — not part of the store.
- Throttle = one animation frame; swap for a timer in non-DOM environments.

## To port this, you need:
- [ ] The signals engine (atoms/computeds/transactions/diff-history) underneath.
- [ ] A normalized record model with `type:id` ids and a scope enum (document/session/presence).
- [ ] `RecordsDiff` + `squash`/`reverse` helpers — the whole system speaks this shape.
- [ ] A reactive map keyed for per-record subscription (`AtomMap`), not one atom holding a big object.
- [ ] A `source` flag (`user`/`remote`) threaded through writes and exposed on listener entries.
- [ ] Frame-throttled, filterable listeners returning unsubscribers.
- [ ] (For querying) incrementally-maintained indexes via an `IncrementalSetConstructor` reading the
      filtered history diff — not full rebuilds.

## Gotchas
- **Read inside writes with `unsafeGetWithoutCapture`**, not `get`. Using the capturing read inside
  `put`/`remove` would wrongly subscribe the enclosing computation to records it merely wrote.
- **Skip empty diffs.** `commitDiff` must early-return on an empty diff or you tick the history
  clock and notify listeners for nothing — death by a thousand no-ops.
- **`mergeRemoteChanges` must not nest and must not be re-broadcast.** The `source:'remote'` flag is
  the *only* thing preventing an infinite echo between two peers; if a remote-applied change leaks
  out as `user`, you get a feedback loop.
- **Disable side-effects during `loadSnapshot`.** Otherwise loading a 5,000-shape document fires
  5,000 "afterCreate" callbacks and any "beforeCreate" transform corrupts already-valid data.
- **before-change/create handlers can return a *different* record.** Downstream code must use the
  returned value, and `put` must short-circuit if a before-change handler returns the same reference.
- **Indexes: incremental, not rebuilt.** A rebuild-on-every-change index turns querying into the
  bottleneck on large documents. Drive it off `getDiffSince(lastEpoch)` and `IncrementalSetConstructor`.
- **Ephemeral keys + scope are snapshot filters.** Forgetting to strip `ephemeralKeys` or
  session-scoped records from `getStoreSnapshot` leaks transient state into saved/synced data.
- **Listener throttling can reorder relative to synchronous reads.** Listeners see batched diffs on
  the next frame; code that needs the post-write state immediately must read the store directly.

## Origin (reference only)
Repo: https://github.com/tldraw/tldraw — package `@tldraw/store` (`packages/store/src/lib/`):
`Store.ts`, `RecordType.ts`, `BaseRecord.ts`, `RecordsDiff.ts`, `StoreQueries.ts`,
`StoreSchema.ts`, `StoreSideEffects.ts`, `AtomMap.ts`, `AtomSet.ts`, `ImmutableMap.ts`,
`IncrementalSetConstructor.ts`, `executeQuery.ts`, `migrate.ts`.
