# WAL + Snapshot Durability — from [memgraph](https://github.com/memgraph/memgraph)

> Domain: [[_domain]] · Source: https://github.com/memgraph/memgraph · NotebookLM: <link once added>

## What it does

Memgraph keeps the whole database in RAM, which is wonderful for speed and catastrophic for a power cut — RAM forgets everything. This subsystem is the safety net that makes an in-memory database crash-safe. It does it the way serious databases always have: it writes a **log of every change** as it happens (the write-ahead log, WAL) and periodically takes a **full snapshot** of the entire dataset. When the server restarts, it loads the latest snapshot and then replays the WAL entries that came after it, reconstructing the exact state the database was in before it died.

## Why it exists

The job-to-be-done is brutally simple: *don't lose committed data.* If a user runs a transaction and gets "committed," that change must survive a crash one millisecond later. An in-memory engine has no inherent durability, so durability has to be bolted on as an explicit, carefully-ordered disk-writing discipline. And because the format on disk has to be readable by future versions of the software — you can't tell users "upgrade and lose your data" — the whole thing is built around a versioned, forward-compatible encoding.

## How it actually works

**The WAL** is an append-only file. Every committed change becomes a small encoded record — there are 40-plus kinds, one per operation: create vertex, delete vertex, add label, set property, create edge, create an index, create a constraint, create a vector index, and so on. Changes are framed inside transaction boundaries: a "transaction start" marker, then the deltas, then a "transaction end" marker. Crucially, the transaction-start frame contains a **commit flag** that's written as "not yet committed," and only *after* the transaction actually commits does the engine go back and patch that flag to true in place. This is the atomicity trick: if the server dies mid-transaction, recovery sees the commit flag is still false and discards the whole half-written transaction rather than replaying a corrupt partial state. Since a recent format version, each transaction also carries a **CRC checksum** so a torn or corrupted write is detected on replay instead of silently loaded.

**Snapshots** are full dumps. A snapshot file starts with a magic string and a header, then has distinct sections — all the vertices, all the edges, the indices, the constraints, the name↔id mapping, enums, epoch history — and an **offset table** at a known location that records exactly where each section begins. That offset table is what lets recovery seek straight to, say, the edges section without scanning the whole file. Taking a snapshot can run concurrently with the database (there's an abort flag and a progress observer), and the engine keeps a configurable number of recent snapshots plus exactly the WAL files needed to bridge from the oldest retained snapshot forward — older ones are deleted to bound disk use.

**Recovery** on startup is: find the newest valid snapshot, load it section by section using the offsets, then find every WAL file whose timestamp range extends past the snapshot and replay the committed transactions in order. The result is the database exactly as it was.

**Versioning** is the quiet hero. Every snapshot and WAL file records the format version it was written with (current is 36). Old files stay readable through a chain of "version-dependent" decoders: a field that didn't exist before version N is read as absent for older files and upgraded to a default; a field whose shape changed is read in its old shape and transformed forward. There's a whole little type-level machinery (`VersionDependant`, `VersionDependantUpgradable`) that composes these upgrades, so a file written years ago still loads correctly. The named version constants (e.g. "vector index arrived at v22", "CRC protection at v36") double as a changelog of the on-disk format.

## The non-obvious parts

- **The commit flag is written false and patched true later.** That single deferred in-place write is the whole crash-atomicity story: a transaction is only "real" on disk once its start-frame flag flips, so an interrupted commit is invisible to recovery.
- **Snapshots have an offset table, so loading is seek-not-scan.** Recovery jumps directly to each section. Without it, loading a large snapshot would mean parsing everything linearly.
- **Forward-compatible decoding is a first-class subsystem, not an afterthought.** The `VersionDependant`/`VersionDependantUpgradable` templates let new fields and changed shapes coexist with decades-old files. The version-constant list is effectively the documented history of the format.
- **Retention couples snapshots and WALs.** You can't just keep N snapshots — you must keep the WAL files that bridge the gaps, or recovery from the older snapshot would have holes. The engine computes and preserves exactly that set.
- **CRC came late (v36) and only protects per-transaction.** Integrity checking is scoped to the transaction frame, matching the atomicity unit — you detect a torn transaction, not just a torn byte.
- **Snapshotting is concurrent and abortable.** It takes a consistent view (via the storage engine's MVCC) while the database keeps serving, with a progress observer and an abort flag for operational control.

## Related

- [[mvcc-inmemory-storage-engine--from-memgraph]] (produces the deltas the WAL encodes; snapshots take a consistent MVCC view)
- [[usearch-vector-index--from-memgraph]] (vector indices are serialized into snapshots and have their own WAL create/drop records)
- See also: other persistence/state approaches in the brain.
