# Multiplayer Sync — from [tldraw](https://github.com/tldraw/tldraw)

> Domain: [[_domain]] · Source: https://github.com/tldraw/tldraw (`packages/sync-core`, `@tldraw/sync`) · NotebookLM: <add link>

## What it does
It makes a tldraw document collaborative in real time: many people draw on the same canvas at once,
see each other's cursors and selections live, and never clobber each other's work. Under the hood
it's a **server-authoritative** sync protocol over WebSockets. Each client keeps its own local copy
of the store and edits it instantly (no waiting on the network), while sending those edits to a
central room on the server. The server holds the one true version of the document, decides the
canonical order of changes, and tells everyone what actually happened. Live cursors and selections
(presence) ride the same channel but with different rules — they're broadcast but never saved.

## Why it exists
Collaboration is table stakes for a modern canvas tool, but doing it well is brutally hard: edits
must feel instant locally, conflicts between simultaneous editors must resolve sensibly, late
joiners must catch up, flaky connections must recover, and clients on slightly different app
versions must still work together. tldraw needed all of that as a reusable, self-hostable piece —
the same engine powering tldraw.com and shippable to customers. They deliberately chose a
**server-authoritative diff model** over CRDTs: simpler to reason about, smaller on the wire, and a
natural fit for the store's existing diff machinery. The job-to-be-done: "let N people edit one
canvas with instant local feedback, sane conflict resolution, and graceful recovery — and let
anyone host it."

## How it actually works
**Every client is optimistic.** When you draw, the change is applied to your local store
*immediately* and rendered. That same change is also stashed as a **speculative change** —
"something I've done locally that the server hasn't confirmed yet" — and queued to send. You never
wait for a round-trip to see your own edit.

**Changes are sent as compact diffs with a client clock.** The client doesn't send whole records; it
sends a **network diff** — a per-record list of operations (`Put` a whole record, `Patch` it with a
field-level object-diff, or `Remove` it). Each push carries an incrementing **clientClock** so the
client can match the server's eventual reply to the exact request that caused it. Sends are
throttled to the sync frame rate, so a flurry of edits during a drag collapses into a few pushes.

**The server is the referee.** A **room** on the server holds the authoritative document: every
record plus a per-record clock saying when it last changed, and a single room-wide **serverClock**
that ticks on every committed change. When a push arrives, the server validates it, applies it to
the authoritative state, assigns a new serverClock, and then decides one of three verdicts for the
pushing client:
- **commit** — your change applied cleanly exactly as you sent it; keep your optimistic version.
- **discard** — your change was a no-op against the authoritative state; drop it.
- **rebase** — the world had moved; here's the *actual* diff that resulted. Throw away your guess
  and use this.

The server then **broadcasts a patch** of what changed to every *other* client in the room.

**The client rebases to reconcile.** This is the clever heart. When server messages arrive, the
client: (1) rewinds all its unconfirmed speculative changes (applies their inverse), putting its
store back to the last server-agreed state; (2) applies the incoming server patches and resolves
each of its own pending pushes by the server's verdict (commit/discard/rebase); (3) re-applies any
still-unconfirmed local changes on top. The result is a store that always reflects "the
server's truth, plus my not-yet-confirmed edits layered on" — so your in-flight work survives even
as other people's edits land underneath it.

**Joining and catching up.** On connect, the client sends its `lastServerClock` (where it last left
off) and its schema. The server figures out what changed since then and replies with either a
targeted diff or a **full wipe-and-replace** if the client is too far behind (or new). The reply
says `hydrationType: 'wipe_all'` or `'wipe_presence'` so the client knows how much to reset.
Deletions are remembered as **tombstones** with the clock at which they happened, so a returning
client can be told "these ids are gone" — but tombstones are capped (oldest discarded past a limit),
and if a client is older than the tombstone history, it just gets a full resync.

**Presence is a separate citizen.** Cursors, selections, and name tags are `presence`-scoped
records. They flow over the same socket but are stored apart, broadcast to others, **never
persisted**, and cleaned up when a session ends. A connecting client's own presence is excluded from
its initial hydration (it'll push fresh presence immediately). Read-only sessions can send presence
but their document edits are ignored.

**Version gaps are handled by migration.** The connect handshake exchanges schemas. If the client is
on an older format, the server **migrates records down** to the client's version before sending them
(and migrates the client's pushes **up**). If the gap can't be bridged — e.g. a required
down-migration doesn't exist — the server sends an `incompatibility_error` instead of corrupting
data. (See [[schema-migrations]].)

**Recovery is built in.** A ping every few seconds and a health-check timer detect dead connections;
if the client hasn't heard from the server in time, it resets and reconnects, which triggers the
catch-up flow again. The reference server implementation runs as a **Cloudflare Durable Object** —
one object instance per room, giving each document a single-threaded authority with built-in
storage — but the room logic is transport-agnostic and can run on plain Node + SQLite too.

## The non-obvious parts
- **Optimistic + rebase, not CRDT.** tldraw bets that a central authority assigning a total order,
  plus clients that speculatively edit and then rebase onto the truth, is simpler and lighter than
  CRDTs — at the cost of needing a server. The "rewind speculative → apply server → replay
  speculative" dance is the price, and it's the core of the whole design.
- **Three verdicts, not two.** Naïve sync is "accept or reject." tldraw's *rebase* verdict — "your
  intent was fine but the result differs; here's reality" — is what makes concurrent edits to the
  same shape resolve gracefully instead of bouncing.
- **Clocks do the bookkeeping.** A monotonic serverClock gives a total order and a cheap "what
  changed since?" query; the clientClock matches replies to requests. Per-record clocks let the
  server compute a minimal catch-up diff. No vector clocks, no Lamport gymnastics — just integers.
- **Tombstones, capped.** You must remember deletions to tell late clients "this is gone," but you
  can't remember them forever. The cap + "too old → full resync" fallback is the pragmatic
  compromise.
- **Presence is deliberately second-class.** By giving cursors their own scope (synced, never saved,
  auto-expiring), tldraw avoids polluting the document and undo history with transient liveness data
  while still feeling alive.
- **Migration is in the connect path.** Cross-version collaboration isn't an afterthought — every
  connect handshake can trigger up/down migration, and the protocol can cleanly refuse an
  unbridgeable client rather than fail mysteriously.
- **Field-level diffs keep it cheap.** Sending `Patch` with an object-diff (only the changed fields,
  with `Append` ops for growing arrays like a freehand stroke) rather than whole records is what
  keeps a fast-moving multiplayer canvas inside a reasonable bandwidth budget.

## Related
- [[reactive-record-store]] — the local copy on each client; sync drives it via `mergeRemoteChanges`
  and consumes its diffs; `source: user|remote` prevents echo loops.
- [[schema-migrations]] — runs in the connect handshake to bridge client/server version gaps (up/down).
- [[signals-reactivity-engine]] — the store underneath is signals-based; presence is computed from it.
- See also: Yjs/Automerge (CRDT, peer-friendly, larger payloads), Liveblocks/PartyKit (hosted
  server-authoritative rooms), Figma's multiplayer (also server-authoritative with a central source
  of truth).
