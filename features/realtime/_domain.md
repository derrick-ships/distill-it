# realtime — domain

**What this domain means across repos studied:** real-time multiplayer collaboration — letting many
clients edit shared state at once with instant local feedback, sane conflict resolution, and
graceful recovery. The interesting engineering lives in the *conflict model* (CRDT vs.
server-authoritative), the *optimistic-update + reconciliation* dance (apply locally now, fix up
when the server speaks), the *wire format* (compact diffs, clocks), *presence* (live cursors that
sync but don't persist), *catch-up* (late joiners, tombstones), and *resilience* (reconnect, version
skew).

## Features filed here
| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Multiplayer Sync | tldraw | [study](study/multiplayer-sync--from-tldraw.md) | [build](build/multiplayer-sync--from-tldraw.md) |
- [[debounced-file-watcher--from-hazelnut]] — watches folders via OS file events with last-seen-time debouncing (collapses the burst of events from a half-written file), a background initial scan of existing files, and longest-prefix routing of each file to its directory's rule set. The 'react the instant a file appears, but only once it settles' pattern.

## Mental model
tldraw's server-authoritative sync (the alternative to CRDTs):
1. **Optimistic clients** apply edits locally and instantly, stashing them as **speculative changes**.
2. **Compact diffs + clocks** go over WebSocket: a `clientClock` matches replies to requests; a
   room-wide `serverClock` gives a total order and cheap "what changed since?" queries.
3. **The server is the referee** — applies pushes to authoritative state and returns one of three
   verdicts: **commit**, **discard**, or **rebase-with-diff**.
4. **Clients rebase** — rewind speculative changes → apply the server's truth → replay
   still-unconfirmed changes on top.
5. **Presence** (cursors/selections) rides the same socket but is synced-not-persisted.
6. **Catch-up** uses `lastServerClock` + capped tombstones, or a full wipe; **migrations** bridge
   client/server version gaps in the connect handshake.
