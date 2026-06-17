# Fractional Indexing (z-order) — from [excalidraw](https://github.com/excalidraw/excalidraw)

> Domain: [[_domain]] · Source: https://github.com/excalidraw/excalidraw · NotebookLM: 

## What it does

Every shape on an Excalidraw canvas has a stacking order — what's drawn on top of what. The naive way to store that is a number per element (0, 1, 2, 3…) or just the position in an array. Excalidraw instead gives each element a short **string** "index" like `"a0"`, `"a1"`, `"a2"`. The trick is that between any two of those strings you can always invent another string that sorts *between* them — `"a0V"` sits between `"a0"` and `"a1"` — without renumbering anything else. So "move this shape one layer up," "insert this shape between those two," and "send to back" all become *changing one element's index string*, never touching its neighbors. That single property is what makes layering survive real-time collaboration cleanly.

## Why it exists

The problem only becomes obvious once you add collaboration. With integer ranks, inserting an element "between rank 2 and rank 3" forces you to renumber everything from 3 upward — and if two collaborators do that at the same time, their renumberings collide and the whole order scrambles. You'd be broadcasting edits to dozens of untouched elements just because one was inserted. Fractional indices fix both: an insert touches *only the inserted element* (so the network payload is tiny and conflict surface is minimal), and the indices are comparable strings so any two clients sort the scene identically. It's the same technique Figma popularized for the same reason. For Excalidraw it's the quiet foundation that lets [[scene-reconciliation--from-excalidraw]] converge on z-order, not just on which elements exist.

## How it actually works

The **index** is an order key: a string from a base-62-ish alphabet engineered so plain lexicographic string comparison (`a < b`) gives you the visual stacking order. Sorting the scene is just `elements.sort((a, b) => a.index < b.index ? -1 : 1)`, with the element's `id` as a tiebreaker if two indices ever match.

**Generating a key between two others** is delegated to a small library (`generateNKeysBetween(before, after, n)`): give it the index just below and just above the gap, plus how many keys you need, and it returns that many strings that all sort strictly between the two. To append at the top, you pass `null` as the upper bound; to prepend at the bottom, `null` as the lower bound.

**Keeping indices valid.** The invariant the whole system relies on is simple: walking the array in order, each element's index must be strictly greater than the one before and strictly less than the one after — `predecessor < current < successor`. Excalidraw has machinery to detect and repair violations:
- `validateFractionalIndices` walks the elements and flags any that break the invariant (missing index, malformed index, or out-of-order).
- `syncInvalidIndices` finds the *contiguous runs* of broken elements, looks at the valid indices bracketing each run, and asks the library to generate fresh in-between keys for just those elements — then writes the new indices back. Only the broken ones change.
- `syncMovedIndices` is the optimized version used when you know exactly which elements the user moved: it regenerates keys for only those, validates the result, and falls back to the full repair if something's off.

**Why repair is ever needed.** New elements may arrive without an index (e.g. pasted, imported, or from an older document), or a merge from a collaborator can briefly produce an order that doesn't satisfy the invariant. Rather than trusting every index blindly, Excalidraw repairs on the way in. After reconciliation merges two clients' element sets, it sorts by index and runs the repair, so everyone lands on the same valid ordering.

**The jitter detail.** Excalidraw uses a *forked* version of the fractional-indexing library that adds a small random suffix ("jitter") to each generated key. Here's the subtle problem it solves: if two collaborators both insert an element "between A and B" at the same moment, a deterministic library would hand them the *identical* new key — and now two different elements share an index, forcing an id-tiebreak and risking visual interleaving. By jittering, the two independently-generated keys are almost certainly different, so concurrent inserts into the same gap stay distinct and stable. It trades perfectly-minimal key length for collision resistance under concurrency — exactly the right trade for a multiplayer canvas.

## The non-obvious parts

- **Indices are strings, compared lexicographically.** The entire ordering is "sort the strings." There's no numeric rank anywhere.
- **An insert/move touches exactly one element.** That's the headline benefit — minimal broadcast payload and minimal merge conflict, versus renumbering a whole array.
- **`null` bounds mean "the ends."** Append = generate above the topmost; prepend = generate below the bottommost.
- **The invariant is `predecessor < current < successor`,** and the system actively *repairs* violations rather than assuming inputs are clean — essential when ingesting pasted/imported/legacy elements.
- **Repair regenerates only contiguous broken runs,** bracketed by the nearest valid indices, so a single bad element doesn't reshuffle the whole scene.
- **Jitter is the multiplayer-specific addition.** The vanilla algorithm is deterministic and would collide under simultaneous same-gap inserts; the random suffix makes concurrent keys distinct. This is the non-obvious reason Excalidraw forked the library.
- **Indices can grow longer over time.** Repeatedly inserting between the same two elements lengthens the key strings. It's bounded in practice and worth it for the conflict-free property; a periodic rebalance could shorten them if ever needed.

## Related

- [[scene-reconciliation--from-excalidraw]] (sorts by these indices and repairs them as its final step)
- [[e2e-encrypted-collaboration--from-excalidraw]] (indices must round-trip through encrypted sync intact)
- [[hand-drawn-rendering--from-excalidraw]] (index order = paint order on the canvas)
- See also: Figma's z-index strategy and Yjs/Automerge list CRDTs solve the same "ordered insert without renumber" problem.
