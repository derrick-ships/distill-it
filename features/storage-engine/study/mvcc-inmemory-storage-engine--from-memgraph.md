# In-Memory MVCC Storage Engine — from [memgraph](https://github.com/memgraph/memgraph)

> Domain: [[_domain]] · Source: https://github.com/memgraph/memgraph · NotebookLM: <link once added>

## What it does

This is the beating heart of Memgraph: the part that actually holds every node (vertex) and relationship (edge) in RAM and lets thousands of queries read and write them at the same time without tripping over each other. It's an **MVCC** engine — multi-version concurrency control — which is a fancy way of saying: when you change something, the engine doesn't overwrite the old value, it records *how to undo your change*. That way a query that started before your change can still see the old world, while a query that starts after sees the new one. Nobody waits on a lock to read.

## Why it exists

A graph database lives or dies on read concurrency. If reading a node meant taking a lock that writers also need, every analytical query would stall every update. MVCC removes that contention: readers never block writers and writers never block readers, because each transaction reconstructs exactly the version of the data it's entitled to see from a chain of small "delta" records. The cost is bookkeeping — you have to track versions and eventually garbage-collect the old ones — but for a database whose whole pitch is "sub-millisecond multi-hop traversals," that trade is the entire point.

## How it actually works

Every vertex and edge carries a pointer to the head of its **delta chain** — a linked list of small records, each describing one reversible change ("this property used to be X", "this in-edge didn't used to exist"). When a transaction wants to read a vertex "as of" its own start time, the engine walks that chain applying deltas backward until the object is in the state that transaction should see.

The decision of *which* deltas to apply is pure timestamp arithmetic, and it's where the three isolation levels live:

- **Snapshot isolation:** you see only changes committed *before your transaction started*. Walk back any delta whose commit timestamp is ≥ your start time.
- **Read committed:** you see any change that's *committed at all*. Uncommitted changes are tagged with the writer's transaction id (always a huge number, above any real timestamp), so "is this committed?" is just "is the timestamp below the transaction-id floor?"
- **Read uncommitted:** you see everything; the engine doesn't bother walking deltas at all.

There's also a "new vs old" view distinction so that within a single query, a transaction can choose to see or not see its *own* latest uncommitted edits (important for multi-step operations).

Writing is guarded by a conflict check. Before a transaction writes an object, it peeks at the head delta: if the most recent change is from a still-running *other* transaction, that's a write-write conflict and the writer gets a serialization error and must abort. If the head is old-and-committed, or is the transaction's own, the write proceeds — a brand-new delta is prepended to the chain.

The clever, non-obvious optimization is **non-sequential deltas**. Bulk-importing a graph means creating millions of edges, and every edge creation touches two vertices' delta chains. Under strict MVCC, two transactions both adding edges to the same hot vertex would conflict. Memgraph relaxes the rule *specifically for edge-creation deltas*: those can be prepended onto another in-flight transaction's chain without conflicting, as long as the only uncommitted deltas in the way are also edge creations. This turns a serialization bottleneck into parallel throughput during imports, at the cost of slightly more expensive chain-walking and garbage collection while those deltas are alive.

Two memory tricks keep it fast. First, **pointer tagging**: pointers to 8-byte-aligned objects always have their low 3 bits zero, so those bits are reused to store the pointer's *type* (delta/vertex/edge) and per-vertex flags (deleted? has-uncommitted-non-sequential-deltas?) without spending extra bytes. Second, the whole `Delta` record is deliberately squeezed to **56 bytes** (asserted at compile time) and made trivially destructible, so deltas can be allocated from a slab and discarded en masse without running destructors.

## The non-obvious parts

- **"Don't overwrite, record the undo."** The mental flip that makes MVCC click: the live object is the *newest* version, and the delta chain tells you how to walk *backward* to any older version a reader needs.
- **Commit timestamps double as commit flags.** A change is "uncommitted" by virtue of its timestamp being a transaction id (a number above all real timestamps). Committing means swapping that for the real commit timestamp. So visibility checks and commit checks are the same integer comparison — no separate "is committed" bitmap.
- **Non-sequential deltas trade GC cost for import speed.** A targeted bending of MVCC's rules, only for edge creations, only during the window where it's safe. It's the kind of optimization you'd never guess from the outside but that dominates bulk-load performance.
- **Three bits of a pointer do a lot of work.** Type discrimination and per-object flags ride for free in pointer alignment bits — no struct bloat, which matters when you have hundreds of millions of vertices.
- **The 56-byte budget is religious.** A static_assert fails the build if `Delta` grows past 56 bytes. Cache-line economy is treated as a correctness constraint, not a nicety.

## Related

- [[wal-snapshot-durability--from-memgraph]] (how the deltas this engine produces get written to disk so an in-memory DB survives a crash)
- [[usearch-vector-index--from-memgraph]] (a secondary index over the same vertices, for similarity search)
- See also: other concurrency/versioning approaches in the brain.
