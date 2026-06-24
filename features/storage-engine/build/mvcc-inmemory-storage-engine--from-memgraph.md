# In-Memory MVCC Storage Engine (build spec) — distilled from memgraph

## Summary

An in-memory multi-version store for graph objects (vertices/edges). Each object points to the head of a singly-/doubly-linked **delta chain**; readers reconstruct their visible version by walking deltas backward, gated by timestamp comparison against the transaction's isolation level. Writers prepend a new delta after a conflict check. Records are packed tight (Delta == 56 bytes, pointer-tagged), allocated from slabs, trivially destructible. A "non-sequential delta" relaxation lets concurrent edge-creation skip MVCC conflicts during bulk import. Lock-free reads; per-object spin lock only for chain mutation.

## Core logic (inlined)

### Object → delta head

```cpp
struct Vertex {
  const Gid gid;
  small_vector<LabelId> labels;
  Edges in_edges, out_edges;        // tuple<EdgeTypeId, Vertex*, EdgeRef>
  PropertyStore properties;
  mutable RWSpinLock lock;          // taken only to MUTATE the chain / object
  // delta head stored in a PointerPack<Delta,2>: low bits carry flags
  Delta* delta() const;             // head of undo chain (nullptr => no versions)
  bool deleted() const;             // bit 0 of packed pointer
  bool has_uncommitted_non_sequential_deltas() const;  // bit 1
};
// sizeof(Vertex) == 80 (asserted)
```

### Delta record (the undo unit)

```cpp
struct Delta {
  enum class Action { DELETE_OBJECT, RECREATE_OBJECT, SET_PROPERTY,
                      ADD_LABEL, REMOVE_LABEL,
                      ADD_IN_EDGE, ADD_OUT_EDGE, REMOVE_IN_EDGE, REMOVE_OUT_EDGE,
                      DELETE_DESERIALIZED_OBJECT };
  CommitInfo* commit_info;          // shared per-transaction: holds the atomic timestamp
  uint64_t    command_id;           // sub-transaction ordering (statement within txn)
  PreviousPtr prev;                 // tagged: points back to Delta|Vertex|Edge
  std::atomic<Delta*> next;         // older delta (walk this direction for reads)
  union { Action action; /* + per-action payload: label / {PropertyId,value} / {EdgeTypeId,TaggedVertexPtr,EdgeRef} */ };
};
static_assert(sizeof(Delta) <= 56);
static_assert(std::is_trivially_destructible_v<Delta>);   // slab-allocated, bulk-discarded

struct CommitInfo {                  // one per transaction, shared by all its deltas
  std::atomic<uint64_t> timestamp;   // == transaction_id while uncommitted; == commit_ts after commit
  SpinLock lock; NonSeqPropagationState non_seq_propagation;
};
```

A change is **uncommitted** iff `timestamp == transaction_id`. Transaction ids are allocated above `kTransactionInitialId`, which is above every real commit timestamp — so "committed?" is just `timestamp < kTransactionInitialId`, and "committed before me?" is `timestamp < my_start_timestamp`. Commit = atomically store the real commit timestamp into the shared `CommitInfo`, which flips every one of the transaction's deltas visible-as-committed at once.

### Read visibility (the heart) — walk deltas, apply the ones that are too new

```cpp
// For each object read, start at object->delta() and walk `next`, calling back
// with deltas that must be UNDONE to reach the version this txn should see.
ApplyDeltasForRead(txn, delta, view):
  if !delta or txn.isolation == READ_UNCOMMITTED: return        // see latest, undo nothing
  commit_ts = txn.commit_info ? txn.commit_info.timestamp : txn.transaction_id
  while delta:
    ts = delta.commit_info.timestamp           // atomic acquire
    // SNAPSHOT_ISOLATION: stop at changes committed before my start
    // READ_COMMITTED:     stop at any committed change (ts < kTransactionInitialId)
    if (iso==SNAPSHOT_ISOLATION && ts < txn.start_timestamp) ||
       (iso==READ_COMMITTED    && ts < kTransactionInitialId): break (or skip if non-sequential)
    // don't undo my own changes the user asked to SEE (View::NEW) ...
    if view==NEW && ts==commit_ts && delta.command_id <= txn.command_id: break
    // ... and for View::OLD, undo my own older-statement changes
    if view==OLD && ts==commit_ts && delta.command_id <  txn.command_id: break
    callback(delta)            // caller applies the inverse of delta.action
    delta = delta.next
```
(Non-sequential edge deltas are *skipped* rather than *stopping* the walk — they can be interleaved from other txns, so you can't treat them as a chain boundary.)

### Write conflict check + prepend

```cpp
PrepareForWrite(txn, object):                 // returns false => serialization error, abort
  if object->delta()==nullptr: return true
  ts = object->delta()->commit_info->timestamp
  if ts == txn.transaction_id: return true     // my own head, fine (unless it's non-sequential)
  if ts <  txn.start_timestamp: return true     // committed before I started, fine
  txn.has_serialization_error = true; return false   // someone else's uncommitted write => conflict

CreateAndLinkDelta(txn, object, args...):     // prepend new delta, keep chain valid for concurrent GC
  delta = txn.deltas.emplace(args..., txn.commit_info, txn.command_id)
  delta->next.store(object->delta(), release)  // 1. new.next = old head
  delta->prev.Set(object)                       // 2. new.prev = object
  if object->delta(): object->delta()->prev.Set(delta)  // 3. old head.prev = new
  object->SetDelta(delta)                        // 4. object head = new (readers/GC see it now)
```
Order matters: steps 1–4 keep both `next` and `prev` chains traversable at every instant, because GC walks them concurrently. The object lock is held across all four.

### Non-sequential delta optimization (bulk-import fast path)

Problem: importing N edges hammers shared vertices' chains; strict MVCC makes concurrent edge adds to the same vertex conflict. Relaxation: `ADD_IN_EDGE`/`ADD_OUT_EDGE` (and their `REMOVE_*` inverses) may be prepended onto *another in-flight transaction's* chain — "non-sequential" — provided every uncommitted delta in the way is also an edge op (no blocking op like SET_PROPERTY upstream). State is tracked per delta via a 3-state tag packed into the vertex pointer:

```cpp
enum class DeltaChainState { SEQUENTIAL, NON_SEQUENTIAL, FORCED_SEQUENTIAL };
// SEQUENTIAL:        normal MVCC, stops traversal at txn boundaries
// NON_SEQUENTIAL:    may traverse past other txns' uncommitted edge deltas
// FORCED_SEQUENTIAL: a blocking (non-edge) op exists upstream => cannot go non-sequential
```
`PrepareForNonSequentialWrite` returns SUCCESS / NON_SEQUENTIAL / SERIALIZATION_ERROR by scanning the chain: if it finds a non-edge uncommitted delta from another txn before a non-sequential marker, it's a conflict; otherwise the edge op is allowed in non-sequentially. A cross-transaction flag (`NonSeqPropagationState` + the vertex's `has_uncommitted_non_sequential_deltas` bit) coordinates cleanup so the relaxed state is reset once those deltas commit.

### Pointer tagging (zero-overhead type + flags)

```cpp
// PreviousPtr: stores Delta*/Vertex*/Edge* in one word; low 2 bits = type tag
//   (all are >=8-byte aligned, so low 3 bits are free).
// TaggedVertexPtr: Vertex* + 2-bit DeltaChainState in the same word.
// Vertex::delta_ is a PointerPack<Delta,2>: Delta* + {deleted, has-nonseq} bits.
```

## Data contracts

- **Timestamps:** `start_timestamp` (txn snapshot point), `transaction_id` (> kTransactionInitialId, used as uncommitted marker), `commit_timestamp` (assigned at commit, < kTransactionInitialId). One monotonic counter source.
- **Delta payloads** by action: label deltas carry a `LabelId`; SET_PROPERTY carries `{PropertyId, PropertyValue*}` (+ out_vertex for edge props); edge deltas carry `{EdgeTypeId, TaggedVertexPtr, EdgeRef}`.
- **Vertex:** `{Gid, labels[], in_edges[], out_edges[], PropertyStore, lock, delta head}`. `sizeof==80`. Edge similar but lighter.

## Dependencies & assumptions

- A monotonic timestamp/txn-id allocator with the invariant `commit_ts < kTransactionInitialId <= transaction_id`.
- A slab/arena allocator (`PageSlabMemoryResource`) for trivially destructible deltas; deltas are freed in bulk, never individually destructed.
- Per-object spin/RW lock (cheap, only for mutation). Atomics with acquire/release for lock-free reads of `next`/`timestamp`/head.
- A concurrent garbage collector that walks `prev`/`next` chains to reclaim deltas no longer visible to any live transaction.
- `IN_MEMORY_ANALYTICAL` storage mode short-circuits delta creation entirely (no MVCC, single-writer) — the engine supports a no-versioning fast mode.

## To port this, you need:
- [ ] A versioned record with an atomic head-pointer to a delta chain, and a shared per-transaction commit-info holding the atomic timestamp.
- [ ] The timestamp invariant above (uncommitted == transaction_id, commit flips one shared timestamp).
- [ ] The `ApplyDeltasForRead` walk specialized to your isolation levels.
- [ ] A conflict check (`PrepareForWrite`) on the head delta before mutating.
- [ ] A concurrent GC that respects the "keep both chain directions valid at all times" ordering in `CreateAndLinkDelta`.
- [ ] (Optional) the non-sequential relaxation only if you have an edge-heavy/append-heavy workload worth the GC complexity.

## Gotchas

- **Chain-link order is load-bearing.** `next` then `prev(object)` then `prev(old head)` then `SetDelta` — done under the object lock — so a concurrent GC never sees a half-linked chain. Reordering corrupts traversal.
- **Uncommitted timestamps must sort above all real timestamps.** If a transaction id could be below a commit timestamp, the "committed?" comparison breaks. Allocate ids from a guaranteed-higher range.
- **Commit is a single atomic store** into the shared `CommitInfo.timestamp` — it atomically publishes *all* the transaction's deltas. Don't stamp deltas individually.
- **Non-sequential deltas must be SKIPPED, not treated as chain boundaries, during reads.** They can come from other transactions, so stopping at one would hide later valid versions.
- **Delta size is a compile-time constraint (≤56B) and must stay trivially destructible.** Adding a non-trivial member silently breaks slab bulk-free and blows the cache budget.
- **READ_UNCOMMITTED never walks deltas** — both an optimization and a correctness branch; the vector index deliberately runs at this level.

## Origin (reference only)

Repo: https://github.com/memgraph/memgraph — `src/storage/v2/mvcc.hpp` (ApplyDeltasForRead, PrepareForWrite, PrepareForNonSequentialWrite, CreateAndLinkDelta), `delta.hpp` (Delta, CommitInfo, PreviousPtr, TaggedVertexPtr, DeltaChainState), `vertex.hpp` (Vertex + PointerPack), `transaction.hpp`, `inmemory/storage.hpp`.
