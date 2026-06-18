# JSON File Store with Async-Mutex (build spec) — distilled from open-carrusel

## Summary

A zero-dependency-database persistence layer: app state lives as JSON files in a `data/` dir, made safe with **a per-file async mutex** (serializes concurrent writers of the same file without globally bottlenecking) and **atomic temp-file-and-rename writes** (a crash mid-write never corrupts the file). Reads are forgiving — missing file → default, corrupt file → caller-chosen fallback. Fits single-process, local-first / self-hosted apps; not for multi-process horizontal scaling.

## Core logic (inlined)

```ts
import { mkdir, readFile, writeFile, rename } from "node:fs/promises";
import path from "node:path";
import { Mutex } from "async-mutex";

const DATA_DIR = path.resolve(process.cwd(), "data");

// one lock per filename — unrelated files write in parallel
const mutexes = new Map<string, Mutex>();
function getMutex(filename: string): Mutex {
  let m = mutexes.get(filename);
  if (!m) { m = new Mutex(); mutexes.set(filename, m); }
  return m;
}

async function ensureDataDir() {
  await mkdir(DATA_DIR, { recursive: true });
}

export async function readData<T>(filename: string): Promise<T> {
  const filePath = path.join(DATA_DIR, filename);
  try {
    const raw = await readFile(filePath, "utf8");
    return JSON.parse(raw) as T;
  } catch (err: any) {
    if (err?.code === "ENOENT") throw new FileMissingError(filename); // not-yet-created
    throw err;                                                        // corrupt / unreadable
  }
}

export async function readDataSafe<T>(filename: string, fallback: T): Promise<T> {
  try { return await readData<T>(filename); }
  catch { return fallback; }                  // missing OR corrupt → caller's default
}

export async function writeData<T>(filename: string, data: T): Promise<void> {
  const mutex = getMutex(filename);
  await mutex.runExclusive(async () => {      // serialize same-file writers
    await ensureDataDir();
    const filePath = path.join(DATA_DIR, filename);
    const tmpPath = filePath + ".tmp";
    await writeFile(tmpPath, JSON.stringify(data, null, 2), "utf8");
    await rename(tmpPath, filePath);          // atomic swap — readers never see a torn file
  });
}

class FileMissingError extends Error {
  constructor(filename: string) { super(`Data file not found: ${filename}`); }
}
```

Usage (read-modify-write must also hold the lock for the *whole* sequence if you need atomicity across read+write):

```ts
// simple replace
await writeData("brand.json", brandConfig);

// safe read-modify-write: do it inside one writeData payload computed from a fresh read
async function pushCarousel(c: Carousel) {
  const data = await readDataSafe<{ carousels: Carousel[] }>("carousels.json", { carousels: [] });
  data.carousels.push(c);
  await writeData("carousels.json", data);
}
```

## Data contracts

- **Location:** `<cwd>/data/<name>.json`, one file per domain concern (`brand.json`, `carousels.json`, `templates.json`, `staged-actions.json`).
- **Each file:** a single JSON document (object or `{ items: [...] }` container).
- **Helpers:** `readData<T>(file)` (throws on missing/corrupt), `readDataSafe<T>(file, fallback)` (never throws), `writeData<T>(file, data)` (atomic + mutex).
- **Concurrency guarantee:** writes to the *same* filename are strictly serialized; writes to *different* filenames run in parallel.

## Dependencies & assumptions

- `async-mutex` (or any promise mutex; trivially hand-rollable with a chained promise).
- Node `fs/promises` with `rename` on the **same filesystem** as the target (atomic rename requires same mount — keep `.tmp` beside the file, which this does).
- **Single Node process.** The mutex is in-process memory; it does NOT coordinate across PM2 cluster workers, multiple containers, or serverless instances.
- Swappable: drop in SQLite/Postgres if you outgrow single-process; the read/write helper signatures can stay the same.

## To port this, you need:
- [ ] A writable `data/` dir (created on first write); add it to `.gitignore` if it holds user data.
- [ ] `async-mutex` or equivalent; a `Map<filename, Mutex>` for per-file locks.
- [ ] Atomic write = write `.tmp` then `rename` over the real path (same FS).
- [ ] `readDataSafe(file, fallback)` so first-run (no files) and transient corruption don't crash requests.
- [ ] Discipline: hold the lock across read-modify-write when you need the whole sequence atomic (compute new state from a fresh read inside the same `writeData`).

## Gotchas

- **In-process only.** Two server processes will still clobber each other — this is a local-first / single-instance pattern. Don't reach for it behind a load balancer.
- **Atomic rename needs same filesystem** — writing `.tmp` to `/tmp` and renaming across mounts is NOT atomic and can fail (`EXDEV`). Keep the temp file next to the target.
- **Read-modify-write races:** `writeData` locks only the write. A read, then an unrelated `await`, then a write can still interleave with another flow's full cycle. For true atomicity, do the read+mutate+write with no foreign `await`s, or run the whole sequence inside one `runExclusive`.
- **No migrations:** schema drift is on you — merge loaded data with defaults so older files don't break new code.
- **Whole-file rewrite per change** — fine for small docs, O(n) for big arrays; if a file grows large, shard it or move to a DB.
- **`readDataSafe` hides corruption** by returning the fallback — great for resilience, but log when it swallows a non-ENOENT error so you don't silently lose data.

## Origin (reference only)

- `src/lib/data.ts` — `DATA_DIR`, `mutexes` map, `ensureDataDir`, `readData`, `readDataSafe`, `writeData` (tmp + rename).
- Consumers: `src/lib/brand.ts`, `carousels.ts`, `templates.ts`, `staged-actions.ts`.
- Repo: https://github.com/Hainrixz/open-carrusel
