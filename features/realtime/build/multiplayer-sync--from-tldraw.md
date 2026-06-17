# Multiplayer Sync (build spec) — distilled from tldraw

## Summary
Build server-authoritative real-time collaboration over WebSockets for a diff-producing record
store. Clients edit locally and **optimistically** (instant), stash unconfirmed edits as
**speculative changes**, and push compact **network diffs** tagged with a monotonic **clientClock**.
A server **room** holds the authoritative document with per-record clocks and a room-wide
**serverClock**; on each push it applies, assigns a new serverClock, returns a verdict
(**commit** / **discard** / **rebase-with-diff**), and broadcasts a patch to other sessions. Clients
**rebase**: rewind speculative changes → apply server messages/verdicts → replay remaining
speculative changes. Catch-up on connect uses `lastServerClock` + tombstones (or a full wipe).
Presence (cursors/selections) rides the same socket but is synced-not-persisted. Cross-version gaps
are bridged by up/down [[schema-migrations]]. Reference deployment = Cloudflare Durable Object per
room; also runs on Node + SQLite.

## Core logic (inlined)

### Wire protocol (current protocolVersion = 8)
```ts
// CLIENT -> SERVER
type TLSocketClientSentEvent<R> =
  | { type: 'connect'; connectRequestId: string; protocolVersion: number
      schema: SerializedSchema; lastServerClock: number }
  | { type: 'push'; clientClock: number
      diff?: NetworkDiff<R>                                   // document changes
      presence?: [RecordOpType.Put, R] | [RecordOpType.Patch, ObjectDiff] }
  | { type: 'ping' }

// SERVER -> CLIENT
type TLSocketServerSentEvent<R> =
  | { type: 'connect'; connectRequestId: string; protocolVersion: number
      schema: SerializedSchema; hydrationType: 'wipe_all' | 'wipe_presence'
      diff: NetworkDiff<R>; serverClock: number; isReadonly: boolean }
  | { type: 'data'; data: TLSocketServerSentDataEvent<R>[] }  // batched
  | { type: 'incompatibility_error'; reason: TLIncompatibilityReason }
  | { type: 'pong' }
  | { type: 'custom'; data: any }

type TLSocketServerSentDataEvent<R> =
  | { type: 'patch'; diff: NetworkDiff<R>; serverClock: number }    // someone else's change
  | { type: 'push_result'; clientClock: number; serverClock: number
      action: 'commit' | 'discard' | { rebaseWithDiff: NetworkDiff<R> } }

enum TLIncompatibilityReason {
  ClientTooOld, ServerTooOld, InvalidRecord, InvalidOperation, RoomNotFound, ... }
```

### Diff format (bandwidth-optimized; see [[reactive-record-store]] for RecordsDiff)
```ts
enum RecordOpType { Put = 'put', Patch = 'patch', Remove = 'remove' }
enum ValueOpType  { Put = 'put', Append = 'append', Patch = 'patch', Delete = 'delete' }

type RecordOp<R> = [RecordOpType.Put, R] | [RecordOpType.Patch, ObjectDiff] | [RecordOpType.Remove]
type NetworkDiff<R> = { [id: string]: RecordOp<R> }

type ValueOp =
  | [ValueOpType.Put, unknown]
  | [ValueOpType.Append, array_or_string: unknown[] | string, offset: number]  // grow arrays cheaply (freehand strokes)
  | [ValueOpType.Patch, ObjectDiff]                                            // nested object
  | [ValueOpType.Delete]
type ObjectDiff = { [key: string]: ValueOp }

function getNetworkDiff<R>(d: RecordsDiff<R>): NetworkDiff<R> | null   // null if empty
//   added/updated -> Put or Patch(diffRecord(from,to)); removed -> Remove
function diffRecord(prev: object, next: object): ObjectDiff | null      // 'props'/'meta' treated as nested
function applyObjectDiff<T>(obj: T, diff: ObjectDiff): T                // returns new obj (or same if no-op)
function applyNetworkDiffToRecordsDiff<R>(state, diff: NetworkDiff<R>): RecordsDiff<R> | null
```

### CLIENT (TLSyncClient)
```ts
class TLSyncClient<R> {
  store: Store<R>
  isConnectedToRoom = false
  clientClock = 0
  lastServerClock = 0
  speculativeChanges: RecordsDiff<R> = empty()            // applied locally, not yet server-confirmed
  pendingPushRequests: { request: TLPushRequest<R>; sent: boolean }[] = []   // in-flight, ordered by clientClock
  private incomingDiffBuffer: TLSocketServerSentDataEvent<R>[] = []
  private unsentChanges?: { nextDiff?: RecordsDiff<R>; nextPresence?: RecordOp<R> }
  presenceState?: Signal<R | null>

  // 1) wire local store changes into sync (listen to store 'user' diffs only)
  constructor() {
    store.listen(({ changes }) => this.push(changes), { source: 'user', scope: 'document' })
    react('push presence', () => this.pushPresence(this.presenceState?.get()))
  }

  push(diff: RecordsDiff<R>) {
    squashRecordDiffsMutable(this.speculativeChanges, [diff])   // remember as unconfirmed
    if (!this.isConnectedToRoom) return                          // offline: keep stashed only
    this.unsentChanges ??= {}
    this.unsentChanges.nextDiff = squash(this.unsentChanges.nextDiff, diff)
    this.sendUnsentChanges()                                     // throttled to sync fps
  }

  sendUnsentChanges = throttle(() => {
    if (!this.unsentChanges) return
    const netDiff = this.unsentChanges.nextDiff && getNetworkDiff(this.unsentChanges.nextDiff)
    const req: TLPushRequest<R> = { type: 'push', clientClock: ++this.clientClock,
                                    diff: netDiff ?? undefined, presence: this.unsentChanges.nextPresence }
    this.socket.send(req); this.pendingPushRequests.push({ request: req, sent: true })
    this.unsentChanges = undefined
  }, 1000 / SYNC_FPS)

  // 2) connect / reconnect
  sendConnectMessage() {
    this.socket.send({ type: 'connect', connectRequestId: uuid(), protocolVersion: 8,
                       schema: this.store.schema.serialize(), lastServerClock: this.lastServerClock })
  }
  onConnect(e) {                                  // server 'connect' reply
    if (e.connectRequestId !== this.latestConnectRequestId) return
    this.store.mergeRemoteChanges(() => {
      if (e.hydrationType === 'wipe_all') this.store.clear()
      else this.store.removeAllPresence()                       // wipe_presence
      else /* undo speculative first if not wiping all */ this.applyInverse(this.speculativeChanges)
      this.applyNetworkDiff(e.diff, /*runCallbacks*/ false)     // server's initial state
    })
    this.isConnectedToRoom = true
    this.lastServerClock = e.serverClock
    // re-apply stashed speculative changes -> generate fresh pushes
    this.push(this.speculativeChanges)
    this.onAfterConnect?.(e.isReadonly)
  }

  // 3) handle batched server data: buffer then rebase once
  onData(e) { this.incomingDiffBuffer.push(...e.data); this.scheduleRebase() }

  rebase() {                                       // THE CORE RECONCILIATION
    this.store.mergeRemoteChanges(() => {
      this.store.applyDiff(reverseRecordsDiff(this.speculativeChanges))   // (1) rewind unconfirmed
      for (const evt of this.incomingDiffBuffer) {                         // (2) apply server truth
        if (evt.type === 'patch') { this.applyNetworkDiff(evt.diff, false); this.lastServerClock = evt.serverClock }
        else /* push_result */ {
          const front = this.pendingPushRequests[0]
          assert(front?.request.clientClock === evt.clientClock)          // results arrive in order
          this.pendingPushRequests.shift()
          if (evt.action === 'discard') {/* drop: change was a no-op */}
          else if (evt.action === 'commit') {/* my optimistic diff is already correct */}
          else this.applyNetworkDiff(evt.action.rebaseWithDiff, false)    // (3) use server's actual result
          this.lastServerClock = evt.serverClock
        }
      }
      this.incomingDiffBuffer = []
      // (4) recompute speculative = (still-pending pushes) + (unsent) replayed onto server truth
      this.speculativeChanges = this.store.extractingChanges(() => {
        for (const p of this.pendingPushRequests) this.applyNetworkDiff(p.request.diff, false)
        if (this.unsentChanges?.nextDiff) this.store.applyDiff(this.unsentChanges.nextDiff)
      })
    })
  }

  applyNetworkDiff(diff: NetworkDiff<R>, runCallbacks: boolean) {
    const changes = applyNetworkDiffToRecordsDiff(this.store, diff)        // value-eq checks; skip no-ops
    if (changes) this.store.applyDiff(changes, { runCallbacks })
  }

  // 4) health
  // ping every 5s; if no server message for 10s -> reset(): clear presence, isConnectedToRoom=false,
  //   empty buffers, restart socket. On next 'online' -> sendConnectMessage() -> onConnect catch-up.
}
```

### SERVER (TLSyncRoom)
```ts
interface RoomSnapshot {
  clock?: number                  // room-wide serverClock
  documentClock?: number          // clock at last document (non-presence) change
  documents: Array<{ state: UnknownRecord; lastChangedClock: number }>
  tombstones?: Record<string, number>            // deleted id -> clock at deletion
  tombstoneHistoryStartsAtClock?: number         // oldest deletion still remembered
  schema?: SerializedSchema
}

class TLSyncRoom<R, Meta> {
  private clock: number
  private documentClock: number
  private state: { documents: Record<id, { state: R; lastChangedClock: number }>
                   tombstones: Record<id, number>; tombstoneHistoryStartsAtClock: number }
  private sessions = new Map<sessionId, RoomSession>()        // each holds socket, presenceId, clocks, isReadonly
  private documentTypes: Set<string>     // typeNames with scope==='document'
  private presenceType?: RecordType      // the presence record type (scope==='presence')
  static MAX_TOMBSTONES = 3000

  // --- connect ---
  handleConnect(session, msg: connect) {
    if (msg.protocolVersion !== 8) return reject(ClientTooOld/ServerTooOld)
    const migrationsOk = this.schema.getMigrationsSince(msg.schema)        // can we bridge?
    if (!migrationsOk.ok || lacksRequiredDownMigrations) return reject(ClientTooOld)

    const sinceClock = msg.lastServerClock
    const tooOld = sinceClock < this.state.tombstoneHistoryStartsAtClock || sinceClock === 0
    const hydrationType = tooOld ? 'wipe_all' : 'wipe_presence'

    let diff: NetworkDiff<R> = {}
    if (tooOld) for (const id in this.state.documents) diff[id] = [Put, this.state.documents[id].state]
    else {
      for (const id in this.state.documents)                                // changed since client's clock
        if (this.state.documents[id].lastChangedClock > sinceClock) diff[id] = [Put, doc.state]
      for (const id in this.state.tombstones)                               // deletions since
        if (this.state.tombstones[id] > sinceClock) diff[id] = [Remove]
      // include other sessions' current presence; EXCLUDE this session's own presence
    }
    diff = migrateDiffDownToClientSchema(diff, msg.schema) // or reject if impossible
    session.send({ type: 'connect', connectRequestId: msg.connectRequestId, protocolVersion: 8,
                   schema: this.schema.serialize(), hydrationType, diff,
                   serverClock: this.clock, isReadonly: session.isReadonly })
  }

  // --- push ---
  handlePush(session, msg: push) {
    const proposed = msg.diff ?? {}
    const actual: NetworkDiff<R> = {}          // what really happened (may differ -> rebase)
    let changed = false
    this.transaction(txn => {
      // presence (independent store, ignores readonly)
      if (msg.presence && this.presenceType) applyPresenceOp(session.presenceId, msg.presence)
      // document ops
      if (!session.isReadonly) for (const [id, op] of Object.entries(proposed)) {
        if (op[0] === Put) {
          if (!this.documentTypes.has(typeNameOf(id))) return reject(InvalidRecord)
          const migrated = migrateRecordUpFromClientSchema(op[1], session.schema)  // up to server schema
          const validated = this.schema.validateRecord(...)
          const prev = this.state.documents[id]
          if (!prev || !equals(prev.state, validated)) {
            this.state.documents[id] = { state: validated, lastChangedClock: this.clock + 1 }
            actual[id] = prev ? [Patch, diffRecord(prev.state, validated)] : [Put, validated]; changed = true
          }
        } else if (op[0] === Patch) {
          const prev = this.state.documents[id]; if (!prev) continue          // patch to missing -> skip
          let rec = downIfNeeded(prev.state, session.schema)
          rec = applyObjectDiff(rec, op[1]); rec = upIfNeeded(rec); rec = validate(rec)
          this.state.documents[id] = { state: rec, lastChangedClock: this.clock + 1 }
          actual[id] = [Patch, diffRecord(prev.state, rec)]; changed = true
        } else /* Remove */ {
          if (!this.state.documents[id]) continue
          delete this.state.documents[id]
          this.state.tombstones[id] = this.clock + 1; this.pruneTombstones()
          actual[id] = [Remove]; changed = true
        }
      }
      if (changed) { this.clock++; this.documentClock = this.clock }
    })

    // verdict to the pusher
    let action: 'commit' | 'discard' | { rebaseWithDiff: NetworkDiff<R> }
    if (!changed) action = 'discard'
    else if (deepEqual(actual, proposed)) action = 'commit'
    else action = { rebaseWithDiff: migrateDiffDownToClientSchema(actual, session.schema) }
    session.send({ type: 'data', data: [{ type: 'push_result',
                   clientClock: msg.clientClock, serverClock: this.clock, action }] })

    // broadcast to everyone ELSE (per-session schema migration of the diff)
    if (changed) for (const other of this.sessions.values()) if (other !== session)
      other.send({ type: 'data', data: [{ type: 'patch',
                   diff: migrateDiffDownToClientSchema(actual, other.schema), serverClock: this.clock }] })
  }

  pruneTombstones() {  // keep only newest MAX_TOMBSTONES; advance tombstoneHistoryStartsAtClock
    const ids = Object.keys(this.state.tombstones)
    if (ids.length > TLSyncRoom.MAX_TOMBSTONES) { /* drop oldest, raise tombstoneHistoryStartsAtClock */ }
  }

  // sessions pruned on a throttle: connected w/ idle>sessionIdleTimeout or closed socket;
  //   awaiting-connect older than SESSION_START_WAIT_TIME; awaiting-removal older than SESSION_REMOVAL_WAIT_TIME.
  // on session removal: delete its presence + broadcast a Remove patch for that presence record.
}
```

### RoomSession states
```ts
type RoomSession =
  | { state: 'awaiting-connect'; sessionId; socket; sessionStartTime }
  | { state: 'connected'; sessionId; socket; presenceId; schema; isReadonly
      lastInteractionTime; serverClock /* last sent */ }
  | { state: 'awaiting-removal'; sessionId; cancellationTime }
```

## Data contracts
- **Push:** `{ type:'push', clientClock, diff?: NetworkDiff, presence?: RecordOp }`.
- **push_result:** `{ clientClock, serverClock, action: 'commit'|'discard'|{rebaseWithDiff} }`.
- **patch:** `{ diff: NetworkDiff, serverClock }`.
- **connect reply:** `{ hydrationType:'wipe_all'|'wipe_presence', diff, serverClock, isReadonly, schema }`.
- **NetworkDiff:** `{ id: [Put,record] | [Patch,objectDiff] | [Remove] }`; **ObjectDiff** uses
  `Put/Append/Patch/Delete` value ops.
- **RoomSnapshot:** authoritative persisted state (documents + per-record clocks + tombstones + schema).

## Dependencies & assumptions
- A diff-producing record store on the client ([[reactive-record-store]]) with `applyDiff`,
  `mergeRemoteChanges`, `extractingChanges`, and `source: user|remote` listeners. **The `remote`
  source flag is what prevents echo loops** — remote-applied changes must not be re-pushed.
- A migration system ([[schema-migrations]]) for the connect handshake and per-session diff
  translation (up on receive, down on send).
- A WebSocket transport with a client adapter (auto-reconnect, online/offline events) and a server
  adapter. tldraw chunks large messages (`chunk.ts`) since WS frames have practical size limits.
- Server authority needs single-threaded-per-room execution. Reference: **Cloudflare Durable
  Object** (one instance per room id + built-in storage). Alternatives: Node process with an
  in-memory room + SQLite/Postgres snapshot, PartyKit, or any actor-per-room runtime.
- Persistence: the room periodically saves a `RoomSnapshot`; on cold start it rehydrates from it.

## To port this, you need:
- [ ] A client store that applies changes optimistically and exposes diffs + a `remote` source flag.
- [ ] NetworkDiff/ObjectDiff encode/decode (`getNetworkDiff`, `diffRecord`, `applyObjectDiff`).
- [ ] Client: `speculativeChanges` buffer, ordered `pendingPushRequests` keyed by `clientClock`,
      throttled sender, and the rewind→apply→replay **rebase** routine.
- [ ] Server room: authoritative doc with per-record `lastChangedClock`, a monotonic room `serverClock`,
      tombstones (capped) + `tombstoneHistoryStartsAtClock`, and the commit/discard/rebase verdict.
- [ ] Connect handshake exchanging `lastServerClock` + schema → targeted diff or `wipe_all`.
- [ ] Presence: a separate store, broadcast-not-persisted, own-presence excluded from hydration,
      removed (and broadcast) on disconnect; readonly sessions allowed presence, denied doc edits.
- [ ] Per-session schema migration of every outgoing/incoming diff; `incompatibility_error` when unbridgeable.
- [ ] Ping + health-check timers and reconnect-resync; large-message chunking.
- [ ] A single-threaded-per-room server runtime + periodic snapshot persistence.

## Gotchas
- **Push results must be matched in order by `clientClock`.** The client assumes the next
  `push_result` corresponds to the front of `pendingPushRequests`; out-of-order handling corrupts the
  speculative buffer. Assert it.
- **The rebase order is exact: rewind speculative → apply server (patches + your verdicts) → replay
  remaining speculative.** Get the order wrong and you either lose in-flight edits or double-apply them.
- **`mergeRemoteChanges` must wrap everything the sync layer writes to the store**, so those writes
  are tagged `remote` and never re-pushed. A leak here = infinite echo between peers.
- **rebase vs commit is decided by comparing the *resulting* diff to the *proposed* diff.** Validation,
  clamping (before-change side-effects), or concurrent edits can make them differ → you must rebase,
  not commit, or clients drift from the server.
- **Tombstones are finite.** Without the cap you leak memory forever; without the "client older than
  tombstone history → wipe_all" fallback, a long-absent client silently misses deletions. Track
  `tombstoneHistoryStartsAtClock`.
- **Exclude the connecting session's own presence from its hydration diff**, or you'll round-trip its
  cursor back to it; it pushes fresh presence right after connecting anyway.
- **Migrate per session, not once.** Different clients can be on different schemas simultaneously;
  every broadcast diff must be migrated *down* to each recipient's version (and pushes migrated *up*).
- **Readonly sessions:** ignore their document ops but still accept their presence — easy to
  accidentally drop both or allow both.
- **WebSocket frame limits:** big initial hydration or a huge paste exceeds practical frame sizes —
  chunk outgoing messages and reassemble on receipt.
- **Clocks are per-room monotonic integers**, persisted in the snapshot. Resetting the server's clock
  (e.g. losing the snapshot) without wiping clients desyncs everyone — on snapshot loss, force `wipe_all`.

## Origin (reference only)
Repo: https://github.com/tldraw/tldraw — package `@tldraw/sync-core` (`packages/sync-core/src/lib/`):
`TLSyncClient.ts`, `TLSyncRoom.ts`, `protocol.ts`, `diff.ts`, `recordDiff.ts`, `RoomSession.ts`,
`TLSocketRoom.ts`, `ClientWebSocketAdapter.ts`, `ServerSocketAdapter.ts`, `chunk.ts`,
`DurableObjectSqliteSyncWrapper.ts`/`NodeSqliteWrapper.ts` (storage). React/transport wrapper in
`@tldraw/sync` (`useSync`, `useSyncDemo`). Reference server template: `templates/sync-cloudflare`.
