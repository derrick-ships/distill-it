# Scene Reconciliation (build spec) — distilled from excalidraw

## Summary

Deterministic, convergent merge of two element lists (local + remote) for real-time collaboration — **without** a CRDT or OT. Each element carries `version` (monotonic counter, +1 per mutation) and `versionNonce` (random per mutation). Merge per-element by id with last-write-wins, using `version` as the logical clock and `versionNonce` as a deterministic tiebreaker (lowest wins on equal version). Active local editing always overrides remote. Output is sorted by fractional z-index and index-repaired. The exact same function runs client-side (on peer update) and server-side (before persisting), so saves can't clobber concurrent edits.

## Core logic (inlined)

This is the complete reconciliation module, verbatim in spirit:

```ts
import throttle from "lodash.throttle";
import { arrayToMap } from "@excalidraw/common";
import {
  orderByFractionalIndex,
  syncInvalidIndices,
  validateFractionalIndices,
} from "@excalidraw/element";
import type { OrderedExcalidrawElement } from "@excalidraw/element/types";
import type { AppState } from "../types";

export type ReconciledExcalidrawElement = OrderedExcalidrawElement & Brand<"ReconciledElement">;
export type RemoteExcalidrawElement   = OrderedExcalidrawElement & Brand<"RemoteExcalidrawElement">;

// The decision: keep LOCAL (discard remote) when ANY condition holds.
export const shouldDiscardRemoteElement = (
  localAppState: AppState,
  local: OrderedExcalidrawElement | undefined,
  remote: RemoteExcalidrawElement,
): boolean => {
  if (
    local &&
    (
      // 1) user is actively interacting with the local element → never override
      local.id === localAppState.editingTextElement?.id ||
      local.id === localAppState.resizingElement?.id ||
      local.id === localAppState.newElement?.id ||
      // 2) local is strictly newer
      local.version > remote.version ||
      // 3) tie on version → deterministic tiebreak: lowest versionNonce wins
      (local.version === remote.version &&
        local.versionNonce <= remote.versionNonce)
    )
  ) {
    return true;
  }
  return false;
};

export const reconcileElements = (
  localElements: readonly OrderedExcalidrawElement[],
  remoteElements: readonly RemoteExcalidrawElement[],
  localAppState: AppState,
): ReconciledExcalidrawElement[] => {
  const localElementsMap = arrayToMap(localElements);
  const reconciledElements: OrderedExcalidrawElement[] = [];
  const added = new Set<string>();

  // Pass 1: walk remote elements, choose local-or-remote per id.
  for (const remoteElement of remoteElements) {
    if (!added.has(remoteElement.id)) {
      const localElement = localElementsMap.get(remoteElement.id);
      const discardRemote = shouldDiscardRemoteElement(localAppState, localElement, remoteElement);
      if (localElement && discardRemote) {
        reconciledElements.push(localElement);
        added.add(localElement.id);
      } else {
        reconciledElements.push(remoteElement);
        added.add(remoteElement.id);
      }
    }
  }

  // Pass 2: append local-only elements (remote hasn't seen them yet).
  for (const localElement of localElements) {
    if (!added.has(localElement.id)) {
      reconciledElements.push(localElement);
      added.add(localElement.id);
    }
  }

  // Converge z-order too: sort by fractional index, then repair invalid indices.
  const orderedElements = orderByFractionalIndex(reconciledElements);
  validateIndicesThrottled(orderedElements, localElements, remoteElements); // dev-only invariant check
  syncInvalidIndices(orderedElements); // mutates elements with fixed indices (bumps their version)

  return orderedElements as ReconciledExcalidrawElement[];
};
```

**Version/nonce maintenance (must hold for the above to work):**
```ts
// On EVERY mutation of an element:
element.version += 1;
element.versionNonce = randomInteger();   // 0 .. 2^31-1, see rendering doc
element.updated = Date.now();
```

**Where it's invoked, client-side** (on receiving a peer's broadcast):
```ts
// Collab.handleRemoteSceneUpdate:
const reconciled = reconcileElements(
  excalidrawAPI.getSceneElementsIncludingDeleted(),
  remoteElements as RemoteExcalidrawElement[],
  excalidrawAPI.getAppState(),
);
// prevent echo: record the version we just merged so we don't re-broadcast it
this.setLastBroadcastedOrReceivedSceneVersion(getSceneVersion(reconciled));
excalidrawAPI.updateScene({ elements: reconciled, captureUpdate: NEVER });
```

**Where it's invoked, server-side** (Firebase save, inside a transaction so concurrent saves merge instead of clobber):
```ts
// saveToFirebase:
const prevStored = await decryptStoredElements(docSnapshot, roomKey); // [] if doc missing
const reconciled = reconcileElements(elements, prevStored as RemoteExcalidrawElement[], appState);
const { ciphertext, iv } = await encryptElements(roomKey, reconciled);
transaction.set(docRef, { sceneVersion: getSceneVersion(reconciled), ciphertext, iv });
```

## Data contracts

```ts
type OrderedExcalidrawElement = ExcalidrawElement & {
  index: FractionalIndex;   // non-null z-order key; see fractional-indexing doc
};

type ExcalidrawElement = {
  id: string;
  version: number;        // monotonic logical clock, +1 per mutation
  versionNonce: number;   // random per mutation; tiebreaker on equal version
  updated: number;        // ms timestamp
  index: string | null;   // fractional index
  // ...geometry/style fields...
};

// AppState fields the merge reads (active-interaction guards):
type AppState = {
  editingTextElement: { id: string } | null;
  resizingElement:    { id: string } | null;
  newElement:         { id: string } | null;
  // ...
};

// getSceneVersion(elements) = sum (or max-aware combination) of element.version across the scene;
// used to detect "did anything change since I last broadcast/saved?"
```

## Dependencies & assumptions

- **No CRDT/OT runtime.** Pure function over two arrays + app state. This is the whole point — keep it that way.
- Requires the **element model to maintain `version`/`versionNonce`/`updated` on every mutation** (a single `mutateElement` chokepoint is the clean way).
- Depends on a **fractional-index** scheme for z-order (`orderByFractionalIndex`, `syncInvalidIndices`) — see the fractional-indexing build doc. If you don't have one, you can substitute a stable numeric z-order, but you lose conflict-free concurrent reordering.
- `lodash.throttle` only for the dev-time index-invariant validator (optional; strip in prod).
- Branded types (`MakeBrand`) are TS hygiene only — they prevent passing un-reconciled lists where reconciled ones are expected. Optional.

## To port this, you need:

- [ ] Every shared object has `version: number` (+1 per edit) and `versionNonce: number` (random per edit).
- [ ] A single mutation chokepoint that maintains those two fields (don't mutate objects ad hoc).
- [ ] `reconcileElements(local, remote, appState)` implementing the two-pass merge above.
- [ ] `shouldDiscardRemoteElement` with the three OR-conditions; keep `<=` (not `<`) in the nonce tie rule so it's total.
- [ ] App-state guards for "currently editing/resizing/creating" so live interaction wins.
- [ ] A deterministic z-order (fractional index ideal) sorted + repaired after the merge.
- [ ] Run the SAME reconcile on the persistence path, inside a transaction, before writing.
- [ ] An echo-guard (`lastBroadcastedOrReceivedSceneVersion`) so you don't re-broadcast what you just merged in.

## Gotchas

- **`<=` vs `<` is a correctness bug if you get it wrong.** With `<`, two clients holding equal version + equal nonce would each *keep their own* element → permanent divergence. `<=` makes the relation total so exactly one side wins everywhere. (Equal nonces are astronomically unlikely but the relation must still be total.)
- **You must bump `versionNonce` on EVERY mutation, with fresh randomness.** If a mutation forgets to regenerate it, ties resolve to stale data and clients can diverge.
- **Active-editing guards are essential UX.** Without them, a peer's update can delete the character you're typing or snap back a shape mid-resize. Guard by id against the live-interaction app state.
- **Reconcile must also order z-index**, or two clients agree on the element set but disagree on stacking → visible divergence. Sort by fractional index and repair invalids as the final step.
- **`syncInvalidIndices` mutates elements (bumps their version).** That re-entrancy is intentional but means a reconcile can itself produce broadcastable changes — design your broadcast/echo logic to tolerate that.
- **Run it server-side too.** If the save path just overwrites with the client's elements, a slower client's save can wipe a faster collaborator's edits. Reconcile-in-transaction prevents the clobber.
- **It's per-element LWW, so it does NOT merge two concurrent edits to the same shape** — one wins wholesale. Acceptable for whiteboards; not acceptable for, say, collaborative text inside one field (use a CRDT there).

## Origin (reference only)

Repo: https://github.com/excalidraw/excalidraw  
Key files: `packages/excalidraw/data/reconcile.ts` (`reconcileElements`, `shouldDiscardRemoteElement`), `excalidraw-app/collab/Collab.tsx` (`handleRemoteSceneUpdate`, echo-guard), `excalidraw-app/data/firebase.ts` (`saveToFirebase` transactional reconcile), `packages/element/src/mutateElement.ts` (version/versionNonce maintenance).
