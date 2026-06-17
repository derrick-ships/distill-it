# Node Dragging (build spec) — distilled from xyflow

## Summary

Drag a node (or a multi-selection as a rigid group) across a transformed canvas, with snap-to-grid, a screen-space drag threshold, extent clamping, and edge auto-pan. Wrap **d3-drag** in a factory `XYDrag({ getStoreItems, onDrag*, onNodeMouseDown })` that exposes `update({ domNode, nodeId, ... })` / `destroy()`. All positions computed in **world coordinates** via the viewport transform. State is read through a `getStoreItems()` callback and written via `updateNodePositions(dragItems, dragging)`.

## Core logic (inlined)

### Pointer → world conversion (the foundation)
```ts
// getPointerPosition returns BOTH raw and grid-snapped world coords
function getPointerPosition(event, { transform, snapGrid, snapToGrid, containerBounds }) {
  const { x, y } = getEventPosition(event, containerBounds);      // screen px relative to container
  const pos = pointToRendererPoint({ x, y }, transform);          // -> world: (p - t.xy) / t.zoom
  const snapped = snapToGrid ? snapPosition(pos, snapGrid) : pos; // round to grid
  return { x: pos.x, y: pos.y, xSnapped: snapped.x, ySnapped: snapped.y };
}
function pointToRendererPoint({x,y}, [tx,ty,tScale]) { return { x: (x-tx)/tScale, y: (y-ty)/tScale }; }
function snapPosition({x,y}, [gx,gy]) { return { x: gx*Math.round(x/gx), y: gy*Math.round(y/gy) }; }
```

### Drag items (recorded once on start)
```ts
// each moving node remembers its offset from the pointer so the formation stays rigid
function getDragItems(nodeLookup, nodesDraggable, pointerPos, nodeId) {
  const items = new Map();
  for (const [id, node] of nodeLookup) {
    const isMoving = (node.selected || id === nodeId) && (node.draggable ?? nodesDraggable);
    if (!isMoving) continue;
    items.set(id, {
      id, position: { ...node.position }, // world position
      distance: { x: pointerPos.x - node.internals.positionAbsolute.x,   // <- the rigid offset
                  y: pointerPos.y - node.internals.positionAbsolute.y },
      extent: node.extent, measured: node.measured, internals: node.internals,
    });
  }
  // if only the grabbed node and it isn't selected, still include just it
  return items;
}
```

### updateNodes — runs each drag tick
```ts
function updateNodes({ x, y }) {                       // x,y = current pointer world coords
  const isMultiDrag = dragItems.size > 1;
  const nodesBox = isMultiDrag ? rectToBox(getInternalNodesBounds(dragItems)) : null;
  // ONE snap offset for the whole group so the formation snaps as a unit
  const multiSnapOffset = (isMultiDrag && snapToGrid)
    ? calculateSnapOffset({ dragItems, snapGrid, x, y }) : null;

  let hasChange = false;
  for (const [id, item] of dragItems) {
    if (!nodeLookup.has(id)) continue;                 // node deleted mid-drag -> skip

    let next = { x: x - item.distance.x, y: y - item.distance.y };   // pointer minus rigid offset
    if (snapToGrid) {
      next = multiSnapOffset
        ? { x: Math.round(next.x + multiSnapOffset.x), y: Math.round(next.y + multiSnapOffset.y) }
        : snapPosition(next, snapGrid);
    }

    // multi-drag: per-node extent so the whole group stops at the boundary together
    let extent = nodeExtent;
    if (isMultiDrag && nodeExtent && !item.extent && nodesBox) {
      const a = item.internals.positionAbsolute;
      extent = [
        [a.x - nodesBox.x + nodeExtent[0][0],                        a.y - nodesBox.y + nodeExtent[0][1]],
        [a.x + item.measured.width  - nodesBox.x2 + nodeExtent[1][0], a.y + item.measured.height - nodesBox.y2 + nodeExtent[1][1]],
      ];
    }

    const { position, positionAbsolute } = calculateNodePosition({ nodeId: id, nextPosition: next,
      nodeLookup, nodeExtent: extent, nodeOrigin, onError });   // clamps to extent, handles parent offset

    hasChange ||= item.position.x !== position.x || item.position.y !== position.y;
    item.position = position;
    item.internals.positionAbsolute = positionAbsolute;
  }
  if (!hasChange) return;
  updateNodePositions(dragItems, true);                // commit, dragging=true
  onNodeDrag?.(dragEvent, current, currentNodes);
  if (!nodeId) onSelectionDrag?.(dragEvent, currentNodes);
}
```

### d3-drag lifecycle
```ts
const d3DragInstance = drag()
  .clickDistance(nodeClickDistance)
  .on('start', (event) => {
    containerBounds = domNode.getBoundingClientRect();
    abortDrag = false; nodePositionsChanged = false; dragEvent = event.sourceEvent;
    if (nodeDragThreshold === 0) startDrag(event);     // threshold 0 => drag immediately
    const p = getPointerPosition(event.sourceEvent, store);
    lastPos = p; mousePosition = getEventPosition(event.sourceEvent, containerBounds); // SCREEN px
  })
  .on('drag', (event) => {
    const p = getPointerPosition(event.sourceEvent, store);
    dragEvent = event.sourceEvent;
    if ((event.sourceEvent.type === 'touchmove' && event.sourceEvent.touches.length > 1) ||
        (nodeId && !nodeLookup.has(nodeId))) abortDrag = true;       // multitouch / deleted node
    if (abortDrag) return;

    if (!autoPanStarted && autoPanOnNodeDrag && dragStarted) { autoPanStarted = true; autoPan(); }

    if (!dragStarted) {                                 // THRESHOLD measured in SCREEN px
      const m = getEventPosition(event.sourceEvent, containerBounds);
      const dx = m.x - mousePosition.x, dy = m.y - mousePosition.y;
      if (Math.sqrt(dx*dx + dy*dy) > nodeDragThreshold) startDrag(event);
    }
    if ((lastPos.x !== p.xSnapped || lastPos.y !== p.ySnapped) && dragItems && dragStarted) {
      mousePosition = getEventPosition(event.sourceEvent, containerBounds);
      updateNodes(p);
    }
  })
  .on('end', (event) => {
    if (!dragStarted || abortDrag) {
      if (abortDrag && dragItems.size) updateNodePositions(dragItems, false); // revert dragging flag
      return;
    }
    autoPanStarted = false; dragStarted = false; cancelAnimationFrame(autoPanId);
    if (nodePositionsChanged) updateNodePositions(dragItems, false);          // final commit, dragging=false
    onNodeDragStop?.(event.sourceEvent, current, currentNodes);
  })
  .filter((event) => !event.button                      // left button only
    && (!noDragClassName || !hasSelector(event.target, `.${noDragClassName}`, domNode))
    && (!handleSelector  ||  hasSelector(event.target, handleSelector, domNode)));

select(domNode).call(d3DragInstance);
```

### Auto-pan loop (rAF)
```ts
async function autoPan() {
  const [dx, dy] = calcAutoPan(mousePosition, containerBounds, autoPanSpeed); // 0 unless near edge
  if (dx !== 0 || dy !== 0) {
    lastPos.x -= dx / transform[2];   // shift remembered pointer by pan delta / zoom
    lastPos.y -= dy / transform[2];
    if (await panBy({ x: dx, y: dy })) updateNodes(lastPos);   // keep node moving though mouse is still
  }
  autoPanId = requestAnimationFrame(autoPan);
}
// calcAutoPan: distance from each edge -> clamp(speed * (1 - dist/margin)); margin ~ 50px
```

## Data contracts

```ts
type XYPosition = { x: number; y: number };
type NodeDragItem = {
  id: string; position: XYPosition;
  distance: XYPosition;                 // rigid offset from pointer, set on start
  extent?: CoordinateExtent | 'parent';
  measured: { width: number; height: number };
  internals: { positionAbsolute: XYPosition };
};
type Transform = [x: number, y: number, zoom: number];
type SnapGrid = [number, number];

type StoreItems = {
  nodeLookup: Map<string, InternalNode>; nodeExtent: CoordinateExtent;
  snapGrid: SnapGrid; snapToGrid: boolean; nodeOrigin: [number, number];
  multiSelectionActive: boolean; transform: Transform; domNode?: Element|null;
  autoPanOnNodeDrag: boolean; autoPanSpeed?: number;
  nodesDraggable: boolean; selectNodesOnDrag: boolean; nodeDragThreshold: number;
  panBy(delta: XYPosition): Promise<boolean>;
  updateNodePositions(items: Map<string,NodeDragItem>, dragging: boolean): void;
  unselectNodesAndEdges(): void;
  onNodeDragStart?; onNodeDrag?; onNodeDragStop?;     // (e, node, nodes)
  onSelectionDragStart?; onSelectionDrag?; onSelectionDragStop?;
  onError?;
};
```

## Dependencies & assumptions

- `d3-drag`, `d3-selection`.
- A viewport `Transform [x,y,zoom]` from your pan/zoom subsystem and a `panBy(delta)` that pans it.
- A node store keyed by id (`nodeLookup`) carrying measured size + absolute position; positions are world coords.
- `getEventPosition(event, bounds)` (screen px relative to container) and `getInternalNodesBounds`/`rectToBox` helpers (compute group bbox).
- Swappable: snapping, auto-pan, multi-select are all optional toggles.

## To port this, you need:

- [ ] Per-node DOM elements you can attach a d3-drag to (or one pane element for selection-drag with `nodeId` undefined).
- [ ] A viewport transform + `panBy` (see [[pan-zoom-canvas--from-xyflow]]).
- [ ] A node lookup with `measured` size and absolute position, plus an `updateNodePositions` writer.
- [ ] `getEventPosition` (screen-space) AND a world-space converter — you need both: world for placement, screen for the threshold.
- [ ] Decide: snap grid, drag threshold (px), node extent bounds, whether grabbing selects.

## Gotchas

- **Threshold in SCREEN pixels, not world.** Use `getEventPosition` (client space) for the start-to-now distance, else the dead-zone scales with zoom and feels wrong.
- **Group snapping = one offset for the whole selection.** Snapping each node independently shears neat formations. Compute `calculateSnapOffset` once from the group.
- **Per-node adjusted extent in multi-drag** or the group shears at boundaries (leftmost stops, rest keep moving).
- **Auto-pan must re-derive position from stored lastPos** (shifted by `panDelta / zoom`) because the mouse is stationary at the edge — otherwise the node freezes while the canvas scrolls.
- **Abort on multitouch** (`touches.length > 1`) and on the dragged node being deleted mid-drag (`!nodeLookup.has(nodeId)`), else you throw or misread a pinch as a drag.
- **Commit with `dragging:false` on end** (and on abort) so downstream knows the gesture finished; only emit change events when position actually changed.

## Origin (reference only)

- `packages/system/src/xydrag/XYDrag.ts` — the factory above.
- `packages/system/src/xydrag/utils.ts` — `getDragItems`, `calculateSnapOffset`, `getEventHandlerParams`, `hasSelector`.
- `packages/system/src/utils/` — `getPointerPosition`, `getEventPosition`, `calcAutoPan`, `calculateNodePosition`, `snapPosition`, `getInternalNodesBounds`, `rectToBox`.
- Repo: https://github.com/xyflow/xyflow (MIT).
