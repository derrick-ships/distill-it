# Domain: state-management

How a complex interactive editor keeps one authoritative model of its world — nodes, edges, selection, viewport, in-progress connection — and lets many components read slices of it without re-rendering the whole tree. The xyflow case is interesting because the *same* state model is driven by two different reactive runtimes (React via Zustand, Svelte via stores) over a shared core.

## What this domain is about

A node editor has thousands of moving values that change at 60fps during drag. Naive prop-drilling or a single React context re-renders everything. The pattern: a central **store** holds the canonical state plus imperative **actions**; components **subscribe to selectors** so each only re-renders when its slice changes; and expensive derived structures (a `Map` lookup keyed by id for O(1) access) are maintained alongside the user-facing arrays.

The portable lesson is the **lookup-alongside-array** pattern and the **framework-agnostic core + thin reactive adapter** split: all the heavy math (`adoptUserNodes`, `updateAbsolutePositions`, `fitViewport`) lives in a plain-TS package, and each framework wrapper just wires that math into its own reactivity.

## Common patterns

- **Array + Map duality.** User gives `nodes: Node[]`; the store derives `nodeLookup: Map<id, InternalNode>` enriched with measured size, absolute position, z-index, parent chain. Drag/connect read the Map; render reads the array.
- **Selector subscriptions with equality fn.** `createWithEqualityFn` lets each `useStore(sel, eq)` pick a slice and supply a comparison so unrelated updates don't re-render it.
- **Imperative actions on the store.** `setNodes`, `updateNodePositions`, `panBy`, `addSelectedNodes` mutate state and trigger callbacks; subsystems (XYDrag, XYHandle) call these.
- **Core/adapter split.** `@xyflow/system` = pure logic; `@xyflow/react` / `@xyflow/svelte` = reactive shells.

## Features in this domain

- [[reactive-store--from-xyflow]] — the Zustand store, nodeLookup derivation, selector pattern, and the system/adapter split
