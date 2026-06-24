# Domain: storage-engine

The in-process engine that holds a database's records in memory and governs how concurrent transactions read and mutate them — versioning, visibility, isolation, and garbage collection. Distinct from [[durability]] (getting that state safely to disk) and from app-level [[persistence]] (client-side chat/state storage).

## What this domain is about

A storage engine answers: where do records live, how do many transactions see consistent snapshots without blocking each other, and how is old version data reclaimed. The dominant pattern here is **MVCC (multi-version concurrency control)**: instead of locking a record to write it, you keep a chain of *deltas* describing how to undo recent changes, so a reader can reconstruct the version it's entitled to see. Memory layout (cache-line-sized records, tagged pointers) and lock-free chain maintenance are the hard parts.

## Features in this domain

- [[mvcc-inmemory-storage-engine--from-memgraph]] — Memgraph's in-memory vertex/edge store: 56-byte delta chains, three isolation levels resolved by timestamp comparison, pointer-tagging to pack flags for free, and a "non-sequential delta" relaxation that makes edge-heavy bulk imports fast without violating MVCC.
