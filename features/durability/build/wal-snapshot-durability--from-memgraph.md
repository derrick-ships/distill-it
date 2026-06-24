# WAL + Snapshot Durability (build spec) — distilled from memgraph

## Summary

Crash-safety for an in-memory store via two cooperating disk mechanisms: an append-only **WAL** of per-operation delta records framed in transactions (with a deferred commit-flag patch for atomicity and per-transaction CRC), and periodic **full snapshots** with a section offset-table for seek-based loading. Recovery = load newest snapshot, replay WALs whose timestamps exceed it. A versioned on-disk format (current kVersion=36) with composable version-dependent decoders keeps old files loadable.

## Core logic (inlined)

### WAL: per-operation delta records (40+ variants)

Each committed change encodes to one record. The decoded form is a tagged variant:

```cpp
struct WalDeltaData {
  std::variant<
    WalVertexCreate, WalVertexDelete, WalVertexAddLabel, WalVertexRemoveLabel,
    WalVertexSetProperty, WalEdgeSetProperty, WalEdgeCreate, WalEdgeDelete,
    WalTransactionStart, WalTransactionEnd,
    WalLabelIndexCreate/Drop, WalLabelPropertyIndexCreate/Drop, WalEdgeTypeIndexCreate/Drop,
    WalPointIndexCreate/Drop, WalTextIndexCreate/Drop,
    WalVectorIndexCreate, WalVectorIndexDrop, WalVectorEdgeIndexCreate,
    WalExistenceConstraintCreate/Drop, WalUniqueConstraintCreate/Drop, WalTypeConstraintCreate/Drop,
    WalEnumCreate, WalEnumAlterAdd, WalEnumAlterUpdate, WalTtlOperation, WalDescriptionSet/Delete, ...
  > data_;
};
// e.g.  struct WalVertexCreate { Gid gid; };
//       struct WalVertexSetProperty { Gid gid; string property; ExternalPropertyValue value; };
//       struct WalEdgeCreate { Gid gid; string edge_type; Gid from_vertex; Gid to_vertex; };
```

### Transaction framing + the atomicity trick

```cpp
// WalFile is the append handle. Pseudocode of a committed transaction's WAL frame:
pos = AppendTransactionStart(timestamp, commit=false, access_type)  // returns byte offset of the commit flag
for delta in txn.deltas: AppendDelta(delta, owner, timestamp, storage)  // EncodeDelta serializes the op
endpos = AppendTransactionEnd(timestamp)   // returns {crc_wal_pos, stored_crc}
Sync()                                      // fsync the deltas
// ... only AFTER the storage engine confirms commit:
UpdateCommitStatus({commit_flag_wal_position = pos, crc_wal_pos, stored_crc})  // patches the flag to TRUE in place
```
**Why:** if the process dies before `UpdateCommitStatus`, recovery reads the start frame's commit flag as false and discards the entire transaction. The commit flag flipping is the atomic "this transaction is durable" point. `WalTransactionEnd` carries a `uint32 txn_crc` (since kCrcProtection=36) covering the transaction's bytes, checked on replay.

### WAL file metadata + recovery entry points

```cpp
struct WalInfo { uint64 offset_metadata, offset_deltas; string uuid, epoch_id;
                 uint64 seq_num, from_timestamp, to_timestamp, num_deltas; };

WalInfo  ReadWalInfo(path);                         // header: which timestamp range this file covers
uint64   ReadWalDeltaHeader(decoder);               // returns the delta's timestamp
WalDeltaData ReadWalDeltaData(decoder, version);    // decode one record (version-aware)
bool     SkipWalDeltaData(decoder, version);        // skip without decoding
// Replay everything in a file into the live skip-lists:
optional<RecoveryInfo> LoadWal(path, indices_constraints, last_applied_ts,
                               vertices, edges, name_id_mapper, edge_count, items,
                               enum_store, schema_info, find_edge_fn, ttl, description_store);
```

### Snapshot: sectioned dump with an offset table

```cpp
struct SnapshotInfo {
  // offset table: byte position of each section (0/kInvalidOffset => absent)
  uint64 offset_edges, offset_vertices, offset_indices, offset_edge_indices,
         offset_constraints, offset_mapper, offset_enums, offset_epoch_history,
         offset_metadata, offset_edge_batches, offset_vertex_batches, offset_ttl, offset_descriptions;
  string uuid, epoch_id;
  uint64 start_timestamp, durable_timestamp, edges_count, vertices_count, num_committed_txns;
};

SnapshotInfo  ReadSnapshotInfo(path);   // read header + offset table (seek targets)
RecoveredSnapshot LoadSnapshot(path, vertices, edges, edges_metadata, epoch_history,
                               name_id_mapper, edge_count, config, enum_store, schema_info,
                               ttl, description_store, snapshot_observer);
// Create concurrently with serving, abortable, progress-observable:
optional<path> CreateSnapshot(storage, txn, snapshot_dir, wal_dir, vertices, edges,
                              uuid, epoch_id, epoch_history, file_retainer,
                              abort_snapshot /*atomic_bool*/, progress, trigger="periodic");
```

### Retention (snapshots + the WALs that bridge them)

```cpp
// Keep N newest snapshots; keep exactly the WAL files needed to bridge from the oldest retained snapshot.
EnsureRetentionCountSnapshotsExist(snapshot_dir, uuid, current_snapshot_path, file_retainer, storage) -> OldSnapshotFiles
DeleteOldSnapshotFiles(old, snapshot_retention_count, file_retainer)
EnsureNecessaryWalFilesExist(wal_dir, uuid, old_snapshot_files, transaction, file_retainer)  // do NOT delete bridging WALs
```

### Versioned format + forward-compatible decoding

```cpp
constexpr uint64 kOldestSupportedVersion = 14;
// changelog-as-constants (excerpt):
//   kVectorIndex=22, kDurableTS=23, kCompositeIndicesForLabelProperties=24, kNestedIndices=25,
//   kVectorIndexWithScalarKind=26, kTxnStart=28, kTextIndexWithProperties=29, kTtlSupport=30,
//   kVectorIndexId=32, kDescriptionAndDescIndexSupport=34, kVectorIndexMultiLabel=35, kCrcProtection=36
constexpr uint64 kVersion = kCrcProtection;  // 36
const string kSnapshotMagic = "MGsn", kWalMagic = "MGwl";
bool IsVersionSupported(v) { return v >= kOldestSupportedVersion && v <= kVersion; }

// Type-level upgraders compose to read old fields:
template <auto MIN_VER, typename T> struct VersionDependant {};            // field absent below MIN_VER
template <auto MIN_VER, typename Before, typename After, auto Upgrader>
struct VersionDependantUpgradable {};   // read Before-shape for old files, apply Upgrader -> After
// e.g. a pre-v35 vector filter was a single label name; UpgradeForVectorMultiLabel promotes it to
//      {mode=SINGLE, ids={name}}.
```

## Data contracts

- **WAL file:** magic "MGwl", header (`WalInfo`: uuid, epoch, seq_num, from/to timestamp, num_deltas), then framed transactions: `TransactionStart{commit flag, access_type}` → deltas → `TransactionEnd{crc}`.
- **Snapshot file:** magic "MGsn", header + `SnapshotInfo` offset table, then sections (vertices, edges, indices, constraints, mapper, enums, epoch history, …) each at its recorded offset.
- **Timestamps:** every record/transaction carries a commit timestamp; recovery replays WAL deltas with `timestamp > snapshot.durable_timestamp`.

## Dependencies & assumptions

- A binary encoder/decoder (`BaseEncoder`/`BaseDecoder`) over an output file with in-place patch capability (to flip the commit flag and write CRC at a saved offset).
- `fsync`/`Sync()` for ordering: deltas durable before the commit flag is patched.
- The storage engine ([[mvcc-inmemory-storage-engine--from-memgraph]]) to source a consistent snapshot view and the committed deltas.
- A `FileRetainer` to safely delete files not in use, and a name↔id mapper persisted alongside.

## To port this, you need:
- [ ] An append-only log with per-record encode/decode and transaction framing.
- [ ] A deferred-commit-flag scheme: write start-frame with commit=false, fsync deltas, then patch the flag true. Recovery discards transactions whose flag is false.
- [ ] A full-dump format with a section offset table so recovery seeks instead of scans.
- [ ] A recovery routine: newest snapshot → replay WALs with timestamp beyond it.
- [ ] A retention policy that keeps N snapshots AND the WALs bridging them.
- [ ] A version constant + version-dependent decoders if the format must evolve without breaking old files.

## Gotchas

- **Order is everything: deltas fsynced BEFORE the commit flag flips.** Reverse it and a crash can leave a "committed" flag pointing at unsynced deltas.
- **A false commit flag means discard the whole transaction.** Don't partially apply; recovery must skip start→end as a unit.
- **Snapshot retention must preserve bridging WALs.** Deleting a WAL that connects a retained snapshot to "now" creates an unrecoverable gap.
- **`kInvalidOffset` (0) marks absent sections.** Newer sections (enums, ttl, descriptions) are absent in old snapshots — guard every offset before seeking.
- **CRC is per-transaction and only since v36.** Older files have no integrity check; don't assume it.
- **Version-dependent decode is mandatory for old files.** A field added at version N must be read as defaulted for files < N (via `VersionDependant`/`VersionDependantUpgradable`), or old snapshots fail to load.

## Origin (reference only)

Repo: https://github.com/memgraph/memgraph — `src/storage/v2/durability/wal.hpp` (WalDeltaData variants, WalFile, EncodeTransactionStart/End, LoadWal, UpdateCommitStatus), `durability/snapshot.hpp` (SnapshotInfo, CreateSnapshot, LoadSnapshot, retention helpers), `durability/version.hpp` (version constants, magic, IsVersionSupported), `durability/metadata.hpp`, `durability/serialization.hpp`.
