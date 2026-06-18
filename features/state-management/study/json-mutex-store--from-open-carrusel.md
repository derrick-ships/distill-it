# JSON File Store with Async-Mutex — from [open-carrusel](https://github.com/Hainrixz/open-carrusel)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/open-carrusel · NotebookLM: <link once added>

## What it does

Open Carrusel has no database. All persistent state — your brand config, every carousel and its slides, saved templates, the staged-actions queue — lives in plain JSON files in a `data/` folder at the project root. The clever bit is the layer that makes that *safe*: an async mutex per file plus atomic temp-file-and-rename writes, so concurrent requests can't corrupt a file or interleave half-writes.

## Why it exists

The product is deliberately **local-first and zero-infrastructure**: clone, `npm run setup && npm run dev`, done. No Postgres to provision, no migrations, no cloud. For a single-user desktop-ish app, a database is overkill — but naive `fs.writeFile` on JSON has two real hazards: (1) two requests writing the same file at once interleave and produce garbage, and (2) a crash mid-write leaves a truncated, unparseable file. This module buys you database-grade durability for those two specific failure modes while keeping the "it's just JSON files" simplicity.

## How it actually works

1. **One folder, one file per concern.** `data/` holds `brand.json`, `carousels.json`, `templates.json`, `staged-actions.json`, etc. The directory is created on first write (`ensureDataDir()`).

2. **A mutex per filename.** A `Map<filename, Mutex>` hands out one lock per file. Before any write, the code grabs that file's mutex and runs the write inside `mutex.runExclusive(...)`. So two requests writing `carousels.json` queue up — second waits for first — while a write to `brand.json` proceeds in parallel (different lock). Serialization is per-file, not global.

3. **Atomic writes via temp + rename.** A write goes to `<file>.tmp` first, then `rename()`s it over the real path. `rename` is atomic on the same filesystem, so a reader (or a crash) never sees a partially written file — it sees either the old complete file or the new complete file, never a torn one.

4. **Forgiving reads.** `readData()` parses JSON and distinguishes "file doesn't exist yet" (return a default) from "file is corrupt" (throw). `readDataSafe(file, fallback)` wraps that and returns the fallback on *any* read error — so a missing or even briefly-bad file degrades gracefully instead of crashing a request.

## The non-obvious parts

- **Per-file locks, not one global lock.** A single global mutex would serialize the whole app; a lock *per filename* serializes only writers of the same file, keeping unrelated writes concurrent. That's the difference between "safe" and "safe and not a bottleneck."
- **The mutex protects against *in-process* concurrency**, i.e. multiple async requests in the same Node process — which is exactly the threat model for a single-server local app. It does **not** coordinate across multiple processes/servers (that's why this pattern fits local-first, not horizontally scaled deploys).
- **Temp-file-and-rename is the whole crash-safety story.** It's a classic Unix durability trick: writes are not atomic, but `rename` over an existing path is. Skipping it is the most common way "just save JSON" corrupts data on a kill -9 during write.
- **`readDataSafe` with a fallback is what makes first-run work** — before anything is ever saved, every read just returns the empty default, so the app boots with no files and no special-casing.
- **No schema/migrations** — the trade-off of file-JSON. Shape changes are handled in code (merge with defaults), which is fine at this scale and a liability if the data model churns hard.

## Related

- [[staged-actions-queue--from-open-carrusel]] (a queue persisted through exactly this store)
- [[reactive-record-store--from-tldraw]] (the heavyweight cousin: in-memory normalized store with diffs/snapshots — different end of the same "where does app state live" spectrum)
- [[reactive-store--from-xyflow]] (central store + selectors; this one is the *durable* layer rather than the reactive read layer)
