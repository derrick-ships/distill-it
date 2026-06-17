# Fractional Indexing (z-order) (build spec) — distilled from excalidraw

## Summary

Give each ordered item a string **order key** (`index`) such that lexicographic comparison yields visual/stacking order. Generate a key *between* any two existing keys (or at the ends via `null` bounds) so insert/move/reorder mutates **only the moved item** — never renumbers neighbors. Delegate key generation to `generateNKeysBetween(before, after, n)` (a base-62 fractional-indexing lib). Maintain the invariant `predecessor < current < successor`; detect violations (`validateFractionalIndices`) and repair contiguous broken runs by regenerating only those keys (`syncInvalidIndices`), with a fast path for known-moved items (`syncMovedIndices`). For multiplayer, use a **jittered** fork of the lib so concurrent inserts into the same gap don't collide.

## Core logic (inlined)

**1. The index field + ordering:**
```ts
type FractionalIndex = string & { _brand: "franctionalIndex" };
type OrderedExcalidrawElement = ExcalidrawElement & { index: FractionalIndex };

const isOrderedElement = (el): el is OrderedExcalidrawElement =>
  typeof el.index === "string" && el.index.length > 0;

// Sort the whole scene = compare index strings; id breaks exact ties.
export const orderByFractionalIndex = (elements: OrderedExcalidrawElement[]) =>
  elements.sort((a, b) => {
    if (isOrderedElement(a) && isOrderedElement(b)) {
      if (a.index < b.index) return -1;
      if (a.index > b.index) return 1;
      return a.id < b.id ? -1 : 1;          // identical index → stable tiebreak by id
    }
    return 1;                                // un-indexed sinks to the end (will be repaired)
  });
```

**2. Generate keys between bounds (the primitive everything calls):**
```ts
import { generateNKeysBetween } from "@excalidraw/fractional-indexing"; // JITTERED fork

// before/after are existing index strings or null for "the very bottom/top".
// returns `count` strings, each strictly between before and after, all distinct.
const between = (before: string | null, after: string | null, count: number) =>
  generateNKeysBetween(before, after, count) as FractionalIndex[];

// append on top:   between(topIndex, null, 1)
// prepend at base: between(null, bottomIndex, 1)
// insert into gap: between(loIndex, hiIndex, 1)
```

**3. Validate the invariant `predecessor < current < successor`:**
```ts
const isValidFractionalIndex = (index: string | null, predecessor: string | null, successor: string | null) => {
  if (!index) return false;
  if (predecessor && successor) return predecessor < index && index < successor;
  if (!predecessor && successor) return index < successor;   // first element
  if (predecessor && !successor) return predecessor < index; // last element
  return true;                                               // only element
};

export const validateFractionalIndices = (
  elements: readonly ExcalidrawElement[],
  { shouldThrow = false } = {},
) => {
  const errors: string[] = [];
  for (let i = 0; i < elements.length; i++) {
    const prev = elements[i - 1]?.index ?? null;
    const cur  = elements[i].index ?? null;
    const next = elements[i + 1]?.index ?? null;
    if (!isValidFractionalIndex(cur, prev, next)) {
      errors.push(`Fractional index invariant compromised at ${i}: [${prev}, ${cur}, ${next}]`);
    }
  }
  if (errors.length && shouldThrow) throw new Error(errors.join("\n"));
  return errors;
};
```

**4. Repair invalid indices — regenerate only contiguous broken runs:**
```ts
// Find runs of indices that break the invariant; each run is the set of array positions
// to regenerate, bracketed by the nearest VALID lower/upper indices.
const getInvalidIndicesGroups = (elements): number[][] => { /* scan; group contiguous bad positions */ };

const generateIndices = (elements, indicesGroups: number[][]) => {
  const updates = new Map<ExcalidrawElement, { index: FractionalIndex }>();
  for (const group of indicesGroups) {
    const lowerBoundPos = group.shift()!;      // last VALID before the run
    const upperBoundPos = group.pop()!;        // first VALID after the run
    const keys = generateNKeysBetween(
      elements[lowerBoundPos]?.index ?? null,
      elements[upperBoundPos]?.index ?? null,
      group.length,                            // # of broken elements between the bounds
    ) as FractionalIndex[];
    group.forEach((pos, i) => updates.set(elements[pos], { index: keys[i] }));
  }
  return updates;
};

export const syncInvalidIndices = (elements: readonly ExcalidrawElement[]) => {
  const groups = getInvalidIndicesGroups(elements);
  const updates = generateIndices(elements, groups);
  for (const [el, { index }] of updates) {
    mutateElement(el, { index });              // bumps el.version / versionNonce too
  }
  return elements as OrderedExcalidrawElement[];
};

// Fast path when you KNOW which elements moved (e.g. a drag-reorder):
export const syncMovedIndices = (elements, movedElements /* Map<id,el> */) => {
  try {
    const groups  = getMovedIndicesGroups(elements, movedElements);
    const updates = generateIndices(elements, groups);
    // validate the candidate ordering BEFORE committing:
    const candidate = elements.map(e => updates.has(e) ? { ...e, ...updates.get(e) } : e);
    validateFractionalIndices(candidate, { shouldThrow: true });
    for (const [el, { index }] of updates) mutateElement(el, { index });
    return elements as OrderedExcalidrawElement[];
  } catch {
    return syncInvalidIndices(elements);       // fall back to full repair
  }
};
```

**5. Integration with reconciliation** (the final convergence step):
```ts
const ordered = orderByFractionalIndex(reconciledElements);
syncInvalidIndices(ordered);   // repair anything merge/import left invalid
```

## The jitter fork (why & what)

Vanilla `fractional-indexing` (`generateKeyBetween`) is **deterministic**: `generateKeyBetween("a0","a1")` always returns the same key. In multiplayer, two clients inserting into the *same gap* simultaneously then produce the **identical** key → two elements share an index → forced id-tiebreak and possible visual interleaving on different clients.

Excalidraw uses `@excalidraw/fractional-indexing`, a fork that appends a small **random suffix (jitter)** to each generated key. Effect: concurrently-generated "between A and B" keys are almost surely distinct, so order stays stable under concurrent same-gap inserts. Cost: keys are a few chars longer than minimal. Worth it for a collaborative canvas.

If porting without the fork: take the upstream `fractional-indexing` and, in `generateKeyBetween`, append N random base-62 chars to the integer-part/fraction before returning; ensure the jittered key still satisfies `before < key < after`.

## Data contracts

```ts
type FractionalIndex = string;        // base-62 order key, lexicographically comparable
// element.index: FractionalIndex | null   (null = needs repair; sinks to end then gets a key)
// element.version / versionNonce bump whenever index is mutated (so reconcile/cache see the change)

// Library API consumed:
//   generateKeyBetween(a: string|null, b: string|null): string
//   generateNKeysBetween(a: string|null, b: string|null, n: number): string[]
//   (jittered fork: same signatures, random suffix added)
```

## Dependencies & assumptions

- **A fractional-indexing library** — ideally the jittered `@excalidraw/fractional-indexing`; upstream `fractional-indexing` works for single-user.
- A **mutation chokepoint** (`mutateElement`) that bumps `version`/`versionNonce` when `index` changes, so reconciliation and render-cache notice.
- Assumes items are kept in an array you can sort by `index`; the array position is *derived*, the index is *authoritative*.
- Pairs with [[scene-reconciliation--from-excalidraw]]; standalone it's just "ordered list with conflict-free inserts."

## To port this, you need:

- [ ] Add a string `index` field to your ordered items.
- [ ] Sort by `index` (string compare), tiebreak by stable `id`.
- [ ] `generateKeyBetween` / `generateNKeysBetween` (use the jittered fork if multiplayer).
- [ ] Insert/move = generate one key between the neighbor indices (or with a `null` bound at the ends) and write it to that one item only.
- [ ] `validateFractionalIndices` enforcing `predecessor < current < successor`.
- [ ] `syncInvalidIndices` to repair contiguous broken runs on ingest (paste/import/merge).
- [ ] `syncMovedIndices` fast path (+ fallback) if you do bulk drag-reorders.
- [ ] Ensure index mutations bump your version/nonce fields.

## Gotchas

- **Use the jittered fork for multiplayer** or concurrent same-gap inserts collide on an identical key → interleaving differs per client. This is the whole reason Excalidraw forked the lib.
- **Repair on ingest, don't trust inputs.** Pasted/imported/legacy/merged elements may have missing, malformed, or out-of-order indices. Run `syncInvalidIndices` after any external input.
- **Repair only contiguous broken runs**, bracketed by valid neighbors — never regenerate the whole scene for one bad element (that would re-broadcast everything and lengthen all keys).
- **Index mutations must bump version/versionNonce**, or reconciliation/echo-guards/render-cache won't see the reorder.
- **Keys lengthen with repeated same-gap inserts.** Bounded in practice; if it ever matters, do an offline rebalance (regenerate evenly spaced keys for the whole list) during a quiet moment, not mid-collaboration.
- **`null` bounds = the ends.** Mixing up which bound is null flips append/prepend.
- **Don't store array position as the source of truth.** The `index` string is authoritative; array order is derived by sorting. If you ever persist array order instead, you lose the conflict-free property.

## Origin (reference only)

Repo: https://github.com/excalidraw/excalidraw  
Key files: `packages/element/src/fractionalIndex.ts` (`orderByFractionalIndex`, `validateFractionalIndices`, `syncInvalidIndices`, `syncMovedIndices`, `generateIndices`, `getInvalidIndicesGroups`), `packages/fractional-indexing/` (the jittered fork of `generateKeyBetween`/`generateNKeysBetween`). Consumed by `packages/excalidraw/data/reconcile.ts`.
