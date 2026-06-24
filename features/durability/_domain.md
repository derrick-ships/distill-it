# Domain: durability

Making an in-memory database survive process crashes and restarts: write-ahead logging of every change, periodic full snapshots, and a recovery procedure that replays them to reconstruct state. Sits below [[storage-engine]] (which produces the changes) and is distinct from app-level [[persistence]].

## What this domain is about

An in-memory engine loses everything on a crash unless it also writes to disk. The canonical solution is two cooperating mechanisms: a **WAL (write-ahead log)** that appends every committed change as a compact, replayable delta, and **snapshots** that periodically dump the entire dataset so recovery doesn't have to replay the log from the beginning of time. Recovery = load the newest snapshot, then replay WAL deltas committed after it. The hard parts are a versioned on-disk format that can evolve without breaking old files, crash-atomicity (a half-written transaction must not be replayed), and integrity checking.

## Features in this domain

- [[wal-snapshot-durability--from-memgraph]] — Memgraph's WAL + snapshot subsystem: a 40+-variant delta format with version-dependent decoding (kVersion 36), CRC-protected transaction framing, a deferred commit-flag patch for atomicity, snapshot files with an offset table for sectioned loading, and retention of N snapshots + the WALs needed to bridge them.
