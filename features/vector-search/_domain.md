# Domain: vector-search

Approximate-nearest-neighbour (ANN) similarity search over high-dimensional embeddings, embedded inside a primary datastore so semantic retrieval lives next to the records it indexes. The retrieval half of GraphRAG and AI-memory systems.

## What this domain is about

Embeddings turn text/images into vectors; finding "similar" items means nearest-neighbour search in that vector space. Exact search is O(n) per query, so production systems use ANN structures (HNSW being dominant) for sub-linear, approximately-correct results. The interesting engineering is when this lives *inside* another database: the vector index must stay consistent with the primary records (add/remove/relabel), survive recovery, respect the host's memory accounting, and expose search through the host's query language — all while ANN libraries assume they own their data.

## Features in this domain

- [[usearch-vector-index--from-memgraph]] — Memgraph's node/edge vector index over the USearch HNSW library: per-index HNSW with configurable metric/dimension/scalar-kind/capacity, a SINGLE/WILDCARD/ANY_OF/ALL_OF label membership filter, copy-on-write index container for stable read snapshots, READ_UNCOMMITTED isolation, undo-able drop, and serialization into the DB's snapshots.
