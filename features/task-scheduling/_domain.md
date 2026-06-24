# Domain: task-scheduling

Coordinating a stream of write/work tasks: queueing them, deciding which can be combined, and processing them in efficient batches with durable status.

## What this domain is about
When many small write operations arrive (index these documents, change these settings, delete those), processing them one by one is slow and unsafe. This domain is the scheduler that sits in front: it persists a task queue, decides which consecutive tasks can be merged into a single batch, and runs that batch atomically, recording per-task status throughout.

## Key design principle
Coalesce compatible work; stop the batch at the first incompatible task. Classify each task by kind, greedily merge a run of compatible same-target tasks into one batch, and break when a task can't safely join (so one write transaction does the work of many).

## Features in this domain
- [[auto-batching-write-scheduler--from-meilisearch]] — Meilisearch's autobatcher: combines consecutive same-index tasks into one batch via a per-kind compatibility matrix.
