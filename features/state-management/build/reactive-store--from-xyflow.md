# Reactive Store Architecture (build spec) — distilled from xyflow

## Summary

A central store holding all editor state (nodes, edges, viewport, selection, in-progress connection) with **surgical reads** (selector + equality subscriptions) and a derived **`nodeLookup` Map** alongside the user-facing arrays. The genuinely hard graph math lives in a **framework-agnostic core** (`@xyflow/system`); each reactive runtime (React/Zustand, Svelte/stores) is a thin adapter calling that core. This is the pattern to copy: *headless logic core + thin reactive shell + array/Map duality + selector subscriptions.*

## Core logic (inlined)

### React store (Zustand) — skeleton
```ts
import { createWithEqualityFn } from 'zustand/traditional';
import { adoptUserNodes, updateAbsolutePositions, updateNodeInternals as updateNodeInternalsSystem,
         fitViewport, getInternalNodesBounds } from '@xyflow/system';

function createStore({ nodes, edges, defaultNodes, defaultEdges, width, height,
                       fitView, nodeOrigin, nodeExtent, ...init }) {
  return createWithEqualityFn((set, get) => ({
    // ---- state ----
    nodes: [], edges: [],
    nodeLookup: new Map(), parentLookup: new Map(), edgeLookup: new Map(),
    transform: [0, 0, 1],                 // [x, y, zoom]
    nodesSelectionActive: false, userSelectionActive: false,
    connection: { inProgress: false /* ...nullConnection */ },
    nodeOrigin: nodeOrigin ?? [0, 0], nodeExtent: nodeExtent ?? [[-∞,-∞],[∞,∞]],
    panZoom: null, width: 0, height: 0,
    onNodesChange: null, onEdgesChange: null, onConnect: null,

    // ---- actions ----
    setNodes(nodes) {
      const { nodeLookup, parentLookup, nodeOrigin, nodeExtent } = get();
      // adoptUserNodes mutates the lookups in place, enriching each node with internals
      adoptUserNodes(nodes, nodeLookup, parentLookup, {
        nodeOrigin, nodeExtent, elevateNodesOnSelect: false, checkEquality: true });
      set({ nodes });
    },

    setEdges(edges) { /* rebuild edgeLookup, set({ edges }) */ },

    // ResizeObserver measured a node -> refresh size/handles/abs-position in the lookup
    updateNodeInternals(updates) {
      const { nodeLookup, parentLookup, transform, nodeOrigin, nodeExtent } = get();
      const { changes, updatedInternals } = updateNodeInternalsSystem(
        updates, nodeLookup, parentLookup, get().domNode, nodeOrigin, nodeExtent);
      if (!updatedInternals) return;
      updateAbsolutePositions(nodeLookup, parentLookup, { nodeOrigin, nodeExtent });
      // apply dimension changes, maybe fitView once on init, trigger onNodesChange
      set({ nodes: [...get().nodes] });
    },

    // called by XYDrag every tick (dragItems carry new positions)
    updateNodePositions(dragItems, dragging) {
      const changes = [];
      for (const [id, item] of dragItems) {
        const node = get().nodeLookup.get(id);
        if (node) { node.position = item.position; node.internals.positionAbsolute = item.internals.positionAbsolute; node.dragging = dragging; }
        changes.push({ id, type: 'position', position: item.position, dragging });
      }
      get().triggerNodeChanges(changes);   // -> onNodesChange (controlled) or internal set (uncontrolled)
    },

    addSelectedNodes(ids) {
      const { multiSelectionActive, nodeLookup } = get();
      // multi-select: add to selection; single: replace
      const changes = getSelectionChanges(nodeLookup, new Set(ids), multiSelectionActive);
      get().triggerNodeChanges(changes); set({ nodesSelectionActive: ids.length > 0 });
    },
    unselectNodesAndEdges(params) { /* clear selected flags, trigger changes */ },

    // viewport
    panBy(delta) { const { transform, panZoom, width, height, nodeExtent } = get();
      return panZoom ? panZoom.setViewportConstrained(
        { x: transform[0] + delta.x, y: transform[1] + delta.y, zoom: transform[2] },
        [[0,0],[width,height]], nodeExtent) : Promise.resolve(false); },
    setMinZoom(z) { get().panZoom?.setScaleExtent([z, get().maxZoom]); set({ minZoom: z }); },

    // the bridge every subsystem uses to read a coherent snapshot
    // (XYDrag/XYHandle/XYResizer call something shaped like this)
  }), Object.is);   // default equality
}
```

### The selector subscription (the performance secret)
```ts
// component side: subscribe to a SLICE with a custom equality so unrelated updates don't re-render you
const nodeIds = useStore(
  (s) => s.nodes.map(n => n.id),
  (a, b) => a.length === b.length && a.every((id, i) => id === b[i])  // shallow id-list compare
);
// only re-renders when the SET of node ids changes, not when a position updates.
```

### Array ↔ Map duality (the data-shape secret)
```
user gives:   nodes: Node[]                              // clean public API, drives render
store derives: nodeLookup: Map<id, InternalNode>         // O(1) engine access
InternalNode = Node + internals {
  positionAbsolute,        // parent chain resolved
  z, handleBounds,         // computed
  userNode,                // back-ref to the original
} + measured { width, height }   // from ResizeObserver
adoptUserNodes(nodes, nodeLookup, parentLookup, opts)    // builds/refreshes the Map from the array
updateAbsolutePositions(...)                             // resolves nested coords into internals
```

### Core/adapter split (the architecture secret)
```
@xyflow/system  (framework-free):
  adoptUserNodes, updateAbsolutePositions, updateNodeInternals, fitViewport,
  getInternalNodesBounds, XYDrag, XYHandle, XYResizer, XYPanZoom, edge path fns...
        ▲                              ▲
        │ thin shell (Zustand)         │ thin shell (Svelte stores)
@xyflow/react                    @xyflow/svelte
```
Each adapter: holds reactive state, exposes the same actions, and delegates all real computation to `@xyflow/system`. A fix in system fixes both UIs.

## Data contracts

```ts
type Transform = [x: number, y: number, zoom: number];

type Node = { id: string; position: {x:number;y:number}; data: any;
              type?: string; selected?: boolean; draggable?: boolean;
              parentId?: string; extent?: 'parent'|CoordinateExtent; origin?: [number,number] };

type InternalNode = Node & {
  measured: { width: number; height: number };
  internals: { positionAbsolute: {x:number;y:number}; z: number; handleBounds: any; userNode: Node };
};

type StoreState = {
  nodes: Node[]; edges: Edge[];
  nodeLookup: Map<string, InternalNode>;
  edgeLookup: Map<string, Edge>; parentLookup: Map<string, InternalNode[]>;
  transform: Transform; connection: ConnectionState;
  nodesSelectionActive: boolean; multiSelectionActive: boolean;
  panZoom: PanZoomInstance | null; width: number; height: number;
  // actions:
  setNodes; setEdges; updateNodeInternals; updateNodePositions;
  addSelectedNodes; unselectNodesAndEdges; resetSelectedElements;
  panBy; setCenter; setMinZoom; setMaxZoom; fitView;
};

// subscription
useStore<T>(selector: (s: StoreState) => T, equality?: (a:T,b:T)=>boolean): T;
```

## Dependencies & assumptions

- React side: `zustand` (specifically `createWithEqualityFn` from `zustand/traditional` for custom equality).
- A framework-free logic package you control (your `@xyflow/system` equivalent) holding the graph math + interaction engines.
- A `ResizeObserver` to measure node DOM and feed `updateNodeInternals`.
- Subsystems (drag/connect/resize) read via a `getStoreItems()` snapshot and write via actions.
- Swappable: the reactive runtime. The whole point is that the core doesn't depend on it.

## To port this, you need:

- [ ] A store lib with selector subscriptions + custom equality (Zustand, or Svelte stores, or Redux-with-reselect).
- [ ] Split your code: pure logic (no framework imports) vs a thin reactive shell. Put ALL graph math in the pure layer.
- [ ] An `adoptUserNodes`-equivalent that builds a `Map` lookup (enriched internal nodes) from the user array, plus `updateAbsolutePositions` for nesting.
- [ ] A ResizeObserver → `updateNodeInternals` path so measured sizes flow into the lookup.
- [ ] Actions that fire user callbacks (`onNodesChange`, `onConnect`) so controlled mode works.
- [ ] Wire each interaction engine to read `getStoreItems()` and write via actions.

## Gotchas

- **Selector equality is mandatory for perf** — a selector returning a fresh array/object every call (no equality fn) re-renders the subscriber on *every* store change. Use shallow/id-list comparisons.
- **Never let users edit the Map** — it's derived. Keep arrays as the public API and recompute the lookup, or the two drift.
- **Absolute position must be recomputed on any parent or position change** for nested nodes, or children render in the wrong place.
- **Measured size is async (post-paint)** — don't assume a node has a size until the ResizeObserver fires; layout-dependent math must wait or re-run.
- **Don't import React/Svelte into the core** — the moment the logic layer reaches into a framework, you've lost the dual-runtime benefit and re-coupled everything.
- **Controlled vs uncontrolled**: decide whether the store owns nodes or mirrors props; actions must support whichever (fire `onNodesChange` in controlled mode instead of mutating directly).

## Origin (reference only)

- `packages/react/src/store/index.ts` — `createStore` (Zustand `createWithEqualityFn`), all actions.
- `packages/react/src/hooks/useStore.ts` — the selector subscription hook.
- `packages/system/src/utils/` — `adoptUserNodes`, `updateAbsolutePositions`, `updateNodeInternals`, `fitViewport`, `getInternalNodesBounds`.
- `packages/svelte/src/lib/store/` — the Svelte adapter over the same system core.
- Repo: https://github.com/xyflow/xyflow (MIT).
