# Reactive Store Architecture — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

It's the central brain that holds the entire state of a flow — every node, every edge, what's selected, the viewport, any in-progress connection — and lets hundreds of components each read just the slice they care about without the whole canvas re-rendering on every tiny change. It's also the seam where xyflow pulls off its biggest architectural trick: the *same* core logic powers both React Flow and Svelte Flow.

## Why it exists

A node editor is a stress test for state management. During a single drag, dozens of values update 60 times a second. If every change re-rendered the whole tree, the app would crawl. And the maintainers didn't want to write the graph logic twice (once for React, once for Svelte). The job-to-be-done is twofold: (1) make reads cheap and surgical so only the affected node re-renders, and (2) keep the genuinely hard graph math in one framework-agnostic place so both UIs share it. This is what lets a two-person team maintain two production libraries.

## How it actually works

**The store, React side.** React Flow uses **Zustand**, a tiny store library. One store holds the canonical state: the user's `nodes` and `edges` arrays, the viewport transform, selection, the connection-in-progress, plus a pile of imperative **actions** (`setNodes`, `updateNodePositions`, `panBy`, `addSelectedNodes`, …). Components subscribe with `useStore(selector, equalityFn)` — they pass a function that plucks out exactly the value they need, and an equality function that decides whether that value "really" changed. If a node drag updates node #5, only the components whose selectors touch node #5 re-render. Everything else is untouched. That selector-plus-equality pattern is the performance secret.

**The array/Map duality.** Users hand in `nodes` as a plain array (nice API). But for the engine, walking an array to find a node by id is too slow when it happens thousands of times during a drag. So the store derives a **`nodeLookup`** — a `Map` from id to an *internal* node enriched with computed data the user never provides: the node's measured pixel size (from a ResizeObserver), its absolute position (resolving the parent chain for nested nodes), z-index, handle positions. There are sibling lookups too (`edgeLookup`, `parentLookup`). The rule of thumb: the user-facing array is for rendering and the public API; the Map is what every interaction subsystem (drag, connect, resize) actually reads.

**The core/adapter split.** Here's the part that makes it elegant. All the *hard* graph math lives in a separate, framework-free package, `@xyflow/system` — functions like `adoptUserNodes` (turn raw user nodes into enriched internal ones), `updateAbsolutePositions` (resolve nested coordinates), `fitViewport` (frame the whole graph), plus the XYDrag / XYHandle / XYResizer / XYPanZoom engines we've already studied. The React store is a thin shell: its actions mostly call these system functions and then poke Zustand to notify subscribers. Svelte Flow has its *own* thin shell — Svelte stores instead of Zustand — calling the *same* system functions. Two reactive front-ends, one logic core.

**The actions.** `setNodes`/`setEdges` adopt the user's arrays and rebuild the lookups. `updateNodeInternals` responds when a node's measured size changes (a ResizeObserver fired). `updateNodePositions` is what drag calls every tick. Selection actions add/remove/reset selected elements respecting multi-select mode. Viewport actions (`panBy`, `setCenter`, `setMinZoom`) drive the pan/zoom instance. User callbacks (`onNodesChange`, `onConnect`, …) are fired from inside these actions so the app stays informed.

## The non-obvious parts

- **Selector + equality is the entire performance story.** Zustand alone re-renders a subscriber whenever the store changes *unless* the selector's output is equal by the provided comparison. Choosing good equality functions (shallow compare, id-list compare) is what keeps a 1,000-node graph at 60fps.
- **The Map is derived, not authored.** `nodeLookup` is never edited directly by users; it's recomputed from the array via `adoptUserNodes`. This keeps a clean public API (arrays) while giving the engine O(1) internal access.
- **Absolute position is computed, not stored.** For nested nodes, a child's *real* canvas position is its position plus all ancestors'. `updateAbsolutePositions` resolves this into the internal node, so subsystems never have to walk the parent chain themselves.
- **Measured size comes from the DOM, asynchronously.** Nodes can be any size the user's React component renders; a ResizeObserver measures them and `updateNodeInternals` feeds that back into the lookup. The store can't know a node's size until it's painted.
- **One core, two reactivities.** The split isn't cosmetic — it's why both libraries ship the same features simultaneously. A bug fix in `@xyflow/system` fixes both. This is the highest-leverage design decision in the whole repo.
- **Controlled vs uncontrolled.** The store can either own the nodes (uncontrolled, you use helper hooks) or mirror props the user controls (controlled, you handle `onNodesChange`). The actions are written to support both.

## Related

- [[node-dragging--from-xyflow]], [[connection-handles--from-xyflow]], [[node-resizer--from-xyflow]], [[pan-zoom-canvas--from-xyflow]], [[minimap-navigation--from-xyflow]] — every interaction subsystem reads this store via `getStoreItems()` and writes back via its actions
- See also: Zustand's selector pattern; the "headless core + thin view adapters" architecture (TanStack, etc.)
