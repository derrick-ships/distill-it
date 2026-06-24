# Auto-Batching Write Scheduler (build spec) — distilled from meilisearch

## Summary
A scheduler that coalesces a stream of write tasks into efficient batches: classify each task by kind, greedily merge the longest compatible prefix of consecutive same-target tasks into one batch, process atomically, and keep durable per-task status.

## Core logic (inlined)

**1. Classify tasks by kind** (`crates/index-scheduler/src/scheduler/autobatcher.rs`, `AutobatchKind`):
```rust
enum AutobatchKind {
    DocumentImport { allow_index_creation: bool, primary_key: Option<String> },
    DocumentEdition,
    DocumentDeletion { by_filter: bool },
    DocumentClear,
    Settings { allow_index_creation: bool },
    IndexCreation, IndexDeletion, IndexUpdate, IndexSwap,
}
// (prioritised / standalone tasks never enter the autobatcher)
```

**2. Greedy "merge the compatible prefix" walk** (`next_autobatch`, conceptually):
```
fn next_autobatch(first_task):
    batch = BatchKind::from(first_task)          // running batch description (kind + accumulated task ids)
    for task in following_tasks_for_same_index:
        match batch.accumulate(task.kind):
            Continue(new_batch) => batch = new_batch        // task joined
            Break(reason)       => return (batch, reason)   // incompatible: stop, take the prefix so far
    return (batch, NothingToProcess)
// accumulate() is the compatibility matrix. Examples of its rules:
//   - consecutive DocumentImport merge (same allow_index_creation; primary_key must not conflict)
//   - DocumentDeletion can join a document-import batch in some cases; by_filter is stricter
//   - Settings { allow_index_creation } may join or may break depending on flags
//   - IndexCreation/Deletion/Update/Swap generally BREAK the batch (can't ride with doc ops)
//   - a task targeting a DIFFERENT index always breaks (batches are per-index)
```
The batcher never reorders; it takes the longest compatible run starting at the first task. ControlFlow `Continue`/`Break` drives the accumulation.

**3. Process atomically + stamp status** (`scheduler/{create_batch,process_batch}.rs`):
```
batch = next_autobatch(...)
open one write transaction
  apply all merged operations (e.g. one index build for all merged DocumentImports)
commit
for task in batch.tasks: task.status = Succeeded | Failed(error attributed to it); persist
```
The queue + batch history live in a persistent store (`queue/{tasks,batches}.rs`) so status survives restarts.

## Data contracts
- Task: `{ id, index_uid, kind: KindWithContent, status: Enqueued|Processing|Succeeded|Failed, ... }`, persisted.
- Batch: `{ id, kind: BatchKind, task_ids: [TaskId], stop_reason }`, persisted.

## Dependencies & assumptions
- A durable queue (Meilisearch uses LMDB/heed). A single-writer processing loop. Tasks are ordered (FIFO per index). The expensive operation (here, index build) benefits from batching.
- Pattern is engine-agnostic; applies to any "many small writes, expensive commit" system.

## To port this, you need:
- [ ] A persisted, ordered task queue with per-task status.
- [ ] A `Kind` classification + an `accumulate(batch, next) -> Continue | Break` compatibility function (your matrix).
- [ ] A greedy "longest compatible prefix" batcher over the next run of same-target tasks.
- [ ] Atomic processing of a batch + per-task status attribution (including on failure).

## Gotchas
- **Per-target batching.** Never merge tasks across different indexes/targets; a different target must break the batch.
- **Attribute failures per task.** If a merged batch fails, each member task must record the right outcome, don't fail the whole queue.
- **Greedy prefix only.** Don't reorder or cherry-pick to maximize batch size; correctness comes from taking the contiguous compatible run.
- Destructive/structural ops (delete/swap index) should break batching by design.
- Persist enqueue + batch state before processing so a crash mid-batch is recoverable.

## Origin (reference only)
`crates/index-scheduler/src/scheduler/{autobatcher.rs,create_batch.rs,process_batch.rs}`, `crates/index-scheduler/src/queue/{tasks.rs,batches.rs}`.
