# schema-migrations — domain

**What this domain means across repos studied:** evolving a persisted data format over time without
breaking existing data — and, in the hardest cases, without breaking communication between clients
on different versions. The interesting engineering lives in *versioning* (how is "which version is
this?" recorded and compared?), *ordering* (how are independently-authored migrations sequenced
safely?), *directionality* (forward-upgrade vs. backward-downgrade), and *integration* (migration
woven into load/save and into the network handshake, not a one-off batch tool).

## Features filed here
| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Schema & Migrations | tldraw | [study](study/schema-migrations--from-tldraw.md) | [build](build/schema-migrations--from-tldraw.md) |

## Mental model
A robust in-document migration system has:
1. **Namespaced migration ids** (`sequenceId/version`) grouped into ordered **sequences** — so
   independent features version independently without colliding.
2. **Scopes** — `record` (transform one record), `store` (transform the whole record map), and
   sometimes `storage` (the persistence layer itself).
3. **Cross-sequence `dependsOn` + topological sort** — one correct global execution order from many
   sequences.
4. **A compact serialized schema** (`{schemaVersion, sequences:{id→version}}`) that travels with
   every snapshot and every connect handshake.
5. **Bidirectional migration** — `up` to open old data, `down` to send modern data to older peers
   (and a clean *rejection* when the gap can't be bridged).
