# USearch Vector Index — from [memgraph](https://github.com/memgraph/memgraph)

> Domain: [[_domain]] · Source: https://github.com/memgraph/memgraph · NotebookLM: <link once added>

## What it does

This is the feature that makes Memgraph useful for AI retrieval: it lets you store an embedding (a list of floats) as a property on a node, build a **vector index** over those embeddings, and then ask "give me the 10 nodes whose embedding is most similar to *this* query vector" — and get an answer in well under a millisecond even over millions of nodes. It's the "R" in GraphRAG: semantic retrieval sitting right next to the graph, so you can find relevant nodes by meaning and then traverse relationships from them.

## Why it exists

Comparing a query embedding against every node's embedding one by one is linear and far too slow at scale. The whole point of a vector index is approximate-nearest-neighbour search — a clever graph structure (HNSW) that finds *almost certainly* the closest vectors while looking at a tiny fraction of them. Memgraph doesn't reinvent that math; it embeds a specialized library (USearch) and does the hard part: keeping that index correct and consistent with a live, transactional graph database that's constantly adding nodes, changing labels, and being snapshotted to disk.

## How it actually works

You create an index with a spec: which **label(s)** and **property** to index, the **distance metric** (cosine, L2, etc.), the embedding **dimension**, a **scalar kind** (e.g. store as float32 or a smaller type to save memory), and a **capacity**. Under the hood each index is a USearch HNSW structure. Memgraph's twist is that the HNSW "key" for each entry is the actual **vertex pointer** — so a search result hands you back the graph node directly, no id-to-node lookup.

When a node gets the right label and has the embedding property, it's added to the index. Searching is a single call into USearch with your query vector and a result-set size; it returns the nearest keys (vertices) with their distances, and Memgraph converts each distance into a similarity score before handing back `(node, distance, similarity)` tuples.

The **label filter** is more expressive than "one label." It has four modes: SINGLE (exactly this label), WILDCARD (all nodes regardless of label), ANY_OF (node has at least one of these labels), and ALL_OF (node has all of these labels). The same filter abstraction works for edge indices too, just keyed on edge-type instead of label.

Keeping it consistent with the transactional graph is where most of the code lives:

- **Adds/removes track label and property changes.** Add the indexed label to a node → it gets inserted. Remove the label → it's pulled out (and its embedding is moved back to being a plain property so no data is lost). Change the embedding property → the index entry updates.
- **Drop is undo-able.** Dropping an index during a transaction that might roll back doesn't just destroy it. The engine captures the evicted index plus the list of nodes whose properties it rewrote, so if the transaction aborts it can reinstall the whole thing exactly. There's careful out-of-memory protection here: rewriting potentially millions of node properties can run out of RAM, so it tracks progress and rolls back cleanly on OOM.
- **Reads are snapshot-stable via copy-on-write.** The set of indices is held behind a shared, copy-on-write pointer. Create/drop swap in a brand-new container, so any query already iterating the old snapshot keeps a consistent view and isn't disturbed mid-flight.
- **It deliberately runs at READ_UNCOMMITTED.** The vector index doesn't do MVCC versioning of its own; it relies on the storage engine's locking discipline (index mutation only happens under an exclusive "unique" storage access that excludes concurrent readers/writers) to stay race-free, which is documented as a hard invariant in the code.
- **It survives recovery.** Indices serialize into the database snapshot (every vector, keyed by node id) and have their own WAL create/drop records, plus a dedicated recovery path that rebuilds the HNSW as nodes are replayed, single- or multi-threaded.

## The non-obvious parts

- **The HNSW key is the vertex pointer itself.** Search returns graph nodes directly — no separate id→node map, and node deletion (which invalidates the pointer) must therefore remove from the index *before* the node is freed, which the GC coordinates.
- **Dropping an index moves embeddings back into properties, reversibly.** A drop isn't destructive: vectors are demoted to plain property values, and a capture object holds everything needed to undo it on abort — including replaying the property rewrites. That's a surprising amount of machinery for "drop index."
- **Four-mode membership filter, shared by node and edge indices.** SINGLE/WILDCARD/ANY_OF/ALL_OF is one generic template parameterized only by id type. The Format method even renders them as `:Label`, `*`, `:A|B`, `:A&B`.
- **Copy-on-write container for lock-free reads.** Instead of locking the index registry, create/drop publish a new immutable snapshot; in-flight readers keep their old one. Mirrors how the text and point indices work.
- **READ_UNCOMMITTED is a deliberate design choice, not a bug.** The index leans entirely on the storage engine's UNIQUE-access invariant for safety, trading MVCC versioning for simplicity and speed — and the code comments are emphatic about why that's safe.
- **OOM is treated as a first-class failure during drop/rewrite.** Converting an index back to properties can exhaust memory, so the rewrite is transactional with explicit rollback on `OutOfMemoryException`.

## Related

- [[mvcc-inmemory-storage-engine--from-memgraph]] (the vertices being indexed; the UNIQUE-access invariant the index relies on for safety; GC coordinates removal before a node pointer is freed)
- [[wal-snapshot-durability--from-memgraph]] (indices serialize into snapshots and have WAL create/drop records and a recovery path)
- See also: other vector-search / retrieval approaches in the brain.
