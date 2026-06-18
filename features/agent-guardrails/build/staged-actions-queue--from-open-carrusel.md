# Staged Actions Confirmation Queue (build spec) — distilled from open-carrusel

## Summary

A persisted **propose → review → apply/discard** queue that sits between an AI agent and the mutations it wants to make. The agent stages an action (typed, described, with a payload) instead of mutating directly; a human (or a per-action `autoExecute` flag) resolves it. Backed by an atomic JSON store so pending proposals survive restarts. A tiny `pending → resolved` state machine that gives agent writes a checkpoint and an audit trail.

## Core logic (inlined)

### Types

```ts
export type StagedActionType =
  | "create-slide" | "update-slide" | "delete-slide"
  | "save-template" | "write-file" /* extend per app */;

export type StagedActionStatus = "pending" | "applied" | "discarded" | "failed";

export interface StagedAction {
  id: string;
  type: StagedActionType;
  fileName?: string;        // target, if a file/slide
  content?: string;         // the payload to apply (e.g. slide HTML)
  description: string;      // REQUIRED human-readable summary — the review surface
  carouselId?: string;      // domain scope key (generalize to entityId)
  autoExecute: boolean;     // apply immediately, skip human review
  status: StagedActionStatus;
  createdAt: string;        // ISO
  resolvedAt?: string;      // ISO — set ONCE, on first exit from "pending"
}

export interface StagedActionsData { actions: StagedAction[] }
```

### Operations (over an atomic JSON store — see json-mutex-store build spec)

```ts
import { randomUUID } from "node:crypto";
const FILE = "staged-actions.json";
const empty: StagedActionsData = { actions: [] };

export async function listStagedActions(): Promise<StagedAction[]> {
  return (await readDataSafe<StagedActionsData>(FILE, empty)).actions;
}

export async function getStagedAction(id: string): Promise<StagedAction | null> {
  return (await listStagedActions()).find(a => a.id === id) ?? null;
}

export async function createStagedAction(input: {
  type: StagedActionType; description: string;
  fileName?: string; content?: string; carouselId?: string; autoExecute?: boolean;
}): Promise<StagedAction> {
  const action: StagedAction = {
    id: randomUUID(),
    type: input.type,
    fileName: input.fileName,
    content: input.content,
    description: input.description,
    carouselId: input.carouselId,
    autoExecute: input.autoExecute ?? false,
    status: "pending",
    createdAt: new Date().toISOString(),
  };
  const data = await readDataSafe<StagedActionsData>(FILE, empty);
  data.actions.push(action);
  await writeData(FILE, data);                 // atomic + mutex
  if (action.autoExecute) await applyStagedAction(action.id); // trust tier short-circuit
  return action;
}

export async function updateStagedActionStatus(
  id: string, status: StagedActionStatus,
): Promise<StagedAction | null> {
  const data = await readDataSafe<StagedActionsData>(FILE, empty);
  const a = data.actions.find(x => x.id === id);
  if (!a) return null;
  const wasPending = a.status === "pending";
  a.status = status;
  if (wasPending && status !== "pending") a.resolvedAt = new Date().toISOString(); // stamp ONCE
  await writeData(FILE, data);
  return a;
}

// applying = perform the real mutation, then mark resolved
export async function applyStagedAction(id: string): Promise<void> {
  const a = await getStagedAction(id);
  if (!a || a.status !== "pending") return;
  try {
    await performMutation(a);                   // <-- the only place real writes happen
    await updateStagedActionStatus(id, "applied");
  } catch {
    await updateStagedActionStatus(id, "failed");
  }
}

export async function discardStagedAction(id: string): Promise<void> {
  await updateStagedActionStatus(id, "discarded"); // resolve without acting
}

// app-specific: turn an action into a real change
async function performMutation(a: StagedAction): Promise<void> {
  switch (a.type) {
    case "create-slide":
    case "update-slide": /* write a.content to the slide a.fileName / carouselId */ break;
    case "save-template": /* persist a.content as a template */ break;
    // ...
  }
}
```

## Data contracts

- **Stored file `staged-actions.json`:** `{ actions: StagedAction[] }`.
- **A StagedAction:** see the interface above. `description` and `status` are mandatory; `resolvedAt` is write-once.
- **State machine:** `pending → applied | discarded | failed`. Only `pending` actions may be applied/discarded; resolved actions are terminal.
- **Agent contract:** when the agent wants to mutate, it calls `createStagedAction({...})` with a clear `description`, NOT the mutation endpoint directly. (Enforced by what tools/endpoints you expose to it.)

## Dependencies & assumptions

- An atomic, concurrency-safe key→JSON store with `readDataSafe(file, fallback)` and `writeData(file, data)` (see [[json-mutex-store--from-open-carrusel]]). Any DB works; the pattern is storage-agnostic.
- `crypto.randomUUID` (or any id generator).
- A UI surface that lists pending actions and exposes apply/discard.
- Swappable: store rows in Postgres/SQLite instead of JSON; the state machine is identical.

## To port this, you need:
- [ ] A typed action record with `type`, `description`, payload fields, `status`, `autoExecute`, and write-once `resolvedAt`.
- [ ] CRUD over a persisted store (survives restart) — list / get / create / updateStatus.
- [ ] A single `performMutation()` choke point that is the *only* place real writes occur, called by `applyStagedAction`.
- [ ] To wire your agent so its "destructive" intents go through `createStagedAction`, not directly to the mutation endpoints.
- [ ] A review UI (or auto-execute policy) that resolves pending actions.

## Gotchas

- **The guardrail only works if the agent can't bypass it.** Staging is worthless if the same agent also has a direct write tool/endpoint — restrict what the agent can call so its only path to mutation is the queue.
- **`resolvedAt` must stamp once.** Guard on `wasPending`; otherwise retries/duplicate resolves rewrite the audit timestamp.
- **`autoExecute` is a trust decision, treat it carefully** — it's the off-switch for the very safety this provides; default it to `false` and only enable for genuinely safe action types.
- **Make `description` mandatory and agent-authored** — an unreviewable queue (no human-readable summaries) defeats the purpose.
- **Apply is fallible** — wrap `performMutation` in try/catch and record `failed` so a botched apply doesn't silently look done or get stuck mid-pending.
- **Concurrency:** two resolves of the same action can race — rely on the atomic store's per-file mutex, and re-check status inside apply (`if status !== "pending" return`).

## Origin (reference only)

- `src/lib/staged-actions.ts` — types (`StagedAction`, `StagedActionsData`), `createStagedAction`, `listStagedActions`, `getStagedAction`, `updateStagedActionStatus`/`updateStagedAction`.
- `src/app/api/staged-actions/` — the review/apply endpoints.
- Repo: https://github.com/Hainrixz/open-carrusel
