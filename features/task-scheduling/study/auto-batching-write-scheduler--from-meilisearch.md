# Auto-Batching Write Scheduler — from [meilisearch](https://github.com/meilisearch/meilisearch)

> Domain: [[_domain]] · Source: https://github.com/meilisearch/meilisearch · NotebookLM: <add link>

## What it does
Takes the constant stream of write requests a search engine receives (add 10k documents, then add 5k more, then change a setting) and quietly groups the ones that can be done together into a single batch, so the engine indexes once instead of many times. Each request still gets its own visible status (enqueued, processing, succeeded/failed), but under the hood compatible requests ride in one transaction.

## Why it exists
Indexing is expensive: every batch rebuilds parts of the inverted index. If a client sends a thousand small "add documents" calls, doing a thousand separate index builds is catastrophic. But you also can't just merge everything blindly, deleting an index can't be batched with adding documents to it. The job is to merge what's safe, automatically, while keeping every individual task's status honest and durable.

## How it actually works
Tasks are enqueued into a persistent queue, each with a kind: add/update documents, edit documents, delete documents (by id or by filter), clear documents, update settings, create/delete/update/swap index. When the scheduler is ready to work, it looks at the next run of tasks for a single index and asks the "autobatcher": starting from the first task, can the next one join this batch? It keeps a running notion of the batch's kind and walks forward, accumulating compatible tasks (many document additions merge; a settings update may or may not join depending on flags like whether index creation is allowed) and stopping the moment it hits an incompatible one, an index deletion, a different index, a primary-key mismatch. The result is one batch describing all the merged tasks.

That batch is then processed as a unit: one write transaction applies all the merged document operations, and on completion the scheduler stamps every task in the batch with its outcome. If the batch fails, the failure is attributed correctly. Some task kinds are never auto-batched (they're prioritized or must run alone). The whole queue and batch history is persisted, so status survives restarts.

## The non-obvious parts
- **A compatibility matrix, not a size timer.** Batching is decided by task kind compatibility (can these two ride together?), not just "wait 50ms and flush." That's what makes it safe.
- **Break on the first incompatible task.** The batcher is greedy-then-stop: it never reorders or skips to find more to merge; it takes the longest compatible prefix. Predictable and correct.
- **Per-task status survives batching.** Clients see their own task's lifecycle even though many were processed together; failures are attributed per task.
- **Some kinds opt out.** Index deletion, swaps, and prioritized tasks break or bypass batching by design.
- **Durable queue.** The task list and batches are persisted, so "processing" state isn't lost on crash/restart.

## Related
- [[multi-source-research-engine--from-last30days-skill]] — a different batching/fan-out of work units (parallel retrieval) for a different job.
- [[wal-snapshot-durability--from-memgraph]] — the durability side: how the work, once batched, is made crash-safe.
