# meilisearch

- **Source:** https://github.com/meilisearch/meilisearch
- **What it is:** A fast, typo-tolerant, open-source search engine (Rust). The `milli` crate is the search/indexing core; `index-scheduler` is the write task queue. Known for relevance-out-of-the-box, search-as-you-type, and a tunable ranking pipeline.
- **Distilled:** 2026-06-24

## Features extracted

| Domain | Feature | Study | Build |
|--------|---------|-------|-------|
| search-relevance | Ranking-Rules Bucket Sort | [study](../features/search-relevance/study/ranking-rules-bucket-sort--from-meilisearch.md) | [build](../features/search-relevance/build/ranking-rules-bucket-sort--from-meilisearch.md) |
| fuzzy-search | Length-Gated Typo Tolerance | [study](../features/fuzzy-search/study/length-gated-typo-tolerance--from-meilisearch.md) | [build](../features/fuzzy-search/build/length-gated-typo-tolerance--from-meilisearch.md) |
| task-scheduling | Auto-Batching Write Scheduler | [study](../features/task-scheduling/study/auto-batching-write-scheduler--from-meilisearch.md) | [build](../features/task-scheduling/build/auto-batching-write-scheduler--from-meilisearch.md) |

## Why these three
The ranking cascade and typo tolerance are Meilisearch's signature relevance features (and fill a search gap in the brain); the autobatcher is a clean, reusable write-coalescing scheduler. The typo derivations feed the ranking pipeline; both sit behind the autobatched index writes.
