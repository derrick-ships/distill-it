# memgraph

> Source: https://github.com/memgraph/memgraph · Distilled: 2026-06-24

## What it is

Memgraph is a high-performance, in-memory graph database (C++) built for real-time graph analytics and AI context (GraphRAG, agentic memory) — sub-millisecond multi-hop traversals, Cypher query language, MAGE algorithm library, vector + text indexes, Raft-based HA, streaming ingestion. Records live in RAM; durability is layered on via WAL + snapshots.

**Stack:** C++ (CMake, Conan), Python (query modules / MAGE), Cypher, USearch (vector ANN), tantivy/mgcxx (text search), Raft (HA).

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| In-Memory MVCC Storage Engine | storage-engine | [study](../features/storage-engine/study/mvcc-inmemory-storage-engine--from-memgraph.md) | [build](../features/storage-engine/build/mvcc-inmemory-storage-engine--from-memgraph.md) |
| WAL + Snapshot Durability | durability | [study](../features/durability/study/wal-snapshot-durability--from-memgraph.md) | [build](../features/durability/build/wal-snapshot-durability--from-memgraph.md) |
| USearch Vector Index | vector-search | [study](../features/vector-search/study/usearch-vector-index--from-memgraph.md) | [build](../features/vector-search/build/usearch-vector-index--from-memgraph.md) |

## Not yet distilled (candidates)

- Cypher query engine + rule-based planner (parse → AST → logical/physical plan → operators)
- Raft-based HA & coordinator failover (`src/coordination`, `src/replication`)
- Deep-path traversal operators (BFS/DFS/WSP/all-shortest-paths)
- Streaming ingestion (Kafka/Pulsar/RedPanda transformation modules)
- Query modules / MAGE plugin system (loadable C++/Python/CUDA procedures)
- Text/point indices, multi-tenancy, RBAC/auth/audit
