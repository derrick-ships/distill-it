# Node Resizer (build spec) — distilled from xyflow

## Summary

Drag-to-resize a node via control points (8 handles). Wrap **d3-drag** on each handle in `XYResizer({ domNode, nodeId, getStoreItems, onChange, onEnd })` → `update({ controlPosition, boundaries, keepAspectRatio, resizeDirection, ... })`. Each handle carries a *direction* (which dims it affects, whether it moves x/y). A `getDimensionsAfterResize` helper returns clamped, aspect-correct `{ width, height, x, y }`; the factory diffs it against previous values, repositions child nodes when the origin shifts, respects min/max + parent/child extents + single-axis restriction, and emits changes only when something actually changed.

## Core logic (inlined)

### Control direction (which handle does what)
```ts
// 'top-left' | 'top' | 'top-right' | 'right' | 'bottom-right' | 'bottom' | 'bottom-left' | 'left'
function getControlDirection(controlPosition) {
  const isHorizontal = controlPosition.includes('right') || controlPosition.includes('left');
  const isVertical   = controlPosition.includes('top')   || controlPosition.includes('bottom');
  const affectsX = controlPosition.includes('left');   // dragging a LEFT handle moves node x
  const affectsY = controlPosition.includes('top');    // dragging a TOP handle moves node y
  return { isHorizontal, isVertical, affectsX, affectsY };
}
```

### Factory + d3-drag lifecycle (VERBATIM-derived, condensed)
```ts
function XYResizer({ domNode, nodeId, getStoreItems, onChange, onEnd }) {
  const selection = select(domNode);
  let params = { controlDirection: getControlDirection('bottom-right'),
                 boundaries: { minWidth:0, minHeight:0, maxWidth:MAX, maxHeight:MAX },
                 resizeDirection: undefined, keepAspectRatio: false };

  function update({ controlPosition, boundaries, keepAspectRatio, resizeDirection,
                    onResizeStart, onResize, onResizeEnd, shouldResize }) {
    let prev = { width:0, height:0, x:0, y:0 };
    let start = { ...prev, pointerX:0, pointerY:0, aspectRatio:1 };
    params = { boundaries, resizeDirection, keepAspectRatio, controlDirection: getControlDirection(controlPosition) };

    let node, containerBounds = null, childNodes = [], parentNode, nodeExtent, childExtent, resizeDetected = false;

    const dragHandler = drag()
      .on('start', (event) => {
        const { nodeLookup, transform, snapGrid, snapToGrid, nodeOrigin, paneDomNode } = getStoreItems();
        node = nodeLookup.get(nodeId); if (!node) return;
        containerBounds = paneDomNode?.getBoundingClientRect() ?? null;
        const { xSnapped, ySnapped } = getPointerPosition(event.sourceEvent, { transform, snapGrid, snapToGrid, containerBounds });

        prev  = { width: node.measured.width, height: node.measured.height, x: node.position.x, y: node.position.y };
        start = { ...prev, pointerX: xSnapped, pointerY: ySnapped,
                  aspectRatio: prev.width / prev.height };          // captured ONCE

        // parent extent vs expandParent
        nodeExtent = isCoordinateExtent(node.extent) ? node.extent : undefined;
        if (node.parentId && (node.extent === 'parent' || node.expandParent)) parentNode = nodeLookup.get(node.parentId);
        if (parentNode && node.extent === 'parent')
          nodeExtent = [[0,0],[parentNode.measured.width, parentNode.measured.height]];

        // collect children (to compensate) + their combined extent
        childNodes = []; childExtent = undefined;
        for (const [childId, child] of nodeLookup) {
          if (child.parentId !== nodeId) continue;
          childNodes.push({ id: childId, position: { ...child.position }, extent: child.extent });
          if (child.extent === 'parent' || child.expandParent) {
            const ext = nodeToChildExtent(child, node, child.origin ?? nodeOrigin);
            childExtent = childExtent
              ? [[Math.min(ext[0][0],childExtent[0][0]), Math.min(ext[0][1],childExtent[0][1])],
                 [Math.max(ext[1][0],childExtent[1][0]), Math.max(ext[1][1],childExtent[1][1])]]
              : ext;
          }
        }
        onResizeStart?.(event, { ...prev });
      })
      .on('drag', (event) => {
        const { transform, snapGrid, snapToGrid, nodeOrigin: storeOrigin } = getStoreItems();
        const pointer = getPointerPosition(event.sourceEvent, { transform, snapGrid, snapToGrid, containerBounds });
        const childChanges = []; const change = {}; if (!node) return;
        const { x: prevX, y: prevY, width: prevW, height: prevH } = prev;
        const nodeOrigin = node.origin ?? storeOrigin;

        // THE math: clamp + aspect + extents all inside here
        const { width, height, x, y } = getDimensionsAfterResize(
          start, params.controlDirection, pointer, params.boundaries,
          params.keepAspectRatio, nodeOrigin, nodeExtent, childExtent);

        const isW = width !== prevW, isH = height !== prevH;
        const isX = x !== prevX && isW, isY = y !== prevY && isH;
        if (!isX && !isY && !isW && !isH) return;            // nothing changed -> emit nothing

        if (isX || isY || nodeOrigin[0] === 1 || nodeOrigin[1] === 1) {
          change.x = isX ? x : prev.x; change.y = isY ? y : prev.y;
          prev.x = change.x; prev.y = change.y;
          if (childNodes.length) {                            // shift children inverse to origin move
            const dx = x - prevX, dy = y - prevY;
            for (const c of childNodes) {
              c.position = { x: c.position.x - dx + nodeOrigin[0]*(width-prevW),
                             y: c.position.y - dy + nodeOrigin[1]*(height-prevH) };
              childChanges.push(c);
            }
          }
        }
        if (isW || isH) {                                     // single-axis restriction here
          change.width  = isW && (!params.resizeDirection || params.resizeDirection === 'horizontal') ? width  : prev.width;
          change.height = isH && (!params.resizeDirection || params.resizeDirection === 'vertical')   ? height : prev.height;
          prev.width = change.width; prev.height = change.height;
        }
        // expandParent clamp ...
        const direction = getResizeDirection({ width: prev.width, prevWidth: prevW, height: prev.height,
                            prevHeight: prevH, affectsX: params.controlDirection.affectsX, affectsY: params.controlDirection.affectsY });
        if (shouldResize?.(event, { ...prev, direction }) === false) return;   // veto
        resizeDetected = true;
        onResize?.(event, { ...prev, direction });
        onChange(change, childChanges);                       // commit to store
      })
      .on('end', (event) => {
        if (!resizeDetected) return;
        onResizeEnd?.(event, { ...prev }); onEnd?.({ ...prev }); resizeDetected = false;
      });
    selection.call(dragHandler);
  }
  function destroy() { selection.on('.drag', null); }
  return { update, destroy };
}
```

### getDimensionsAfterResize (the constraint pipeline — semantics)
```
given start snapshot, controlDirection {affectsX, affectsY, isHorizontal, isVertical}, pointer:
  // delta from start pointer, only on affected axes
  if isHorizontal: rawWidth  = affectsX ? start.width  - (pointer.x - start.pointerX)   // left handle: grow leftwards
                                        : start.width  + (pointer.x - start.pointerX)   // right handle
  if isVertical:   rawHeight = affectsY ? start.height - (pointer.y - start.pointerY)
                                        : start.height + (pointer.y - start.pointerY)
  width  = clamp(rawWidth,  minWidth,  maxWidth)
  height = clamp(rawHeight, minHeight, maxHeight)
  if keepAspectRatio: reconcile so width/height == start.aspectRatio (clamp the dominant axis, derive the other)
  // when a left/top handle moved, recompute x/y so the OPPOSITE edge stays anchored:
  x = affectsX ? start.x + (start.width  - width)  - nodeOrigin[0]*(width  - start.width)  : start.x ...
  y = affectsY ? start.y + (start.height - height) - nodeOrigin[1]*(height - start.height) : start.y ...
  // finally clamp x/y/width/height against nodeExtent (parent) and childExtent (can't shrink past children)
  return { width, height, x, y }
```

## Data contracts

```ts
type ControlPosition = 'top-left'|'top'|'top-right'|'right'|'bottom-right'|'bottom'|'bottom-left'|'left';
type ResizeControlDirection = 'horizontal' | 'vertical';     // single-axis restriction

type XYResizerChange      = { x?: number; y?: number; width?: number; height?: number };
type XYResizerChildChange = { id: string; position: XYPosition; extent?: 'parent'|CoordinateExtent };

type XYResizerUpdateParams = {
  controlPosition: ControlPosition;
  boundaries: { minWidth:number; minHeight:number; maxWidth:number; maxHeight:number };
  keepAspectRatio: boolean;
  resizeDirection?: ResizeControlDirection;
  onResizeStart?(e, size): void;
  onResize?(e, { width,height,x,y,direction }): void;
  onResizeEnd?(e, size): void;
  shouldResize?(e, next): boolean;     // return false to veto a tick
};

type StoreItems = {
  nodeLookup: Map<string, InternalNode>; transform: [x,y,zoom];
  snapGrid?: [number,number]; snapToGrid: boolean; nodeOrigin: [number,number];
  paneDomNode: HTMLDivElement | null;
};
```

## Dependencies & assumptions

- `d3-drag`, `d3-selection`.
- `getPointerPosition` (screen→world, snap-aware) — shared with node-dragging.
- A node store with `measured` size, `position`, `origin`, `extent`/`expandParent`, and parent/child relationships via `parentId`.
- Per-handle DOM elements to attach drag to; the component renders 8 of them around a selected node.
- `clamp`, `isCoordinateExtent` utils.

## To port this, you need:

- [ ] 8 control-point DOM elements around the node (corners + edges), each calling `update({ controlPosition })` with its own position.
- [ ] A node model with measured size + position + origin; a writer that applies `XYResizerChange` and `childChanges`.
- [ ] `getPointerPosition` (reuse from [[node-dragging--from-xyflow]]).
- [ ] If you support nested nodes: `parentId`, child collection, and parent/child extent math. If not, you can drop the children/parent branches entirely.
- [ ] Decide min/max, aspect lock, single-axis restriction per resizer.

## Gotchas

- **Top/left handles must move x/y to anchor the opposite edge** — the corner-anchoring is the whole game; skip it and the node "slides" while resizing.
- **Shift children by the inverse of the origin move** every tick (with the `nodeOrigin*(Δsize)` term) or nested nodes visibly jump when you drag a top/left handle.
- **Capture aspect ratio once at start** — recomputing it per tick lets rounding drift the proportion.
- **Node origin (non-top-left) changes the position math** — fold `nodeOrigin` into both the x/y recompute and the child shift, or centered nodes resize from the wrong anchor.
- **Emit nothing when nothing changed** (the `if (!isX && !isY && !isW && !isH) return`) — keeps callbacks/undo clean when you hit a min/max wall.
- **`extent: 'parent'` (clamp) vs `expandParent` (grow parent) are opposites** — resolve which at start; doing both clamps you can't expand.
- **`shouldResize` veto returns false to cancel a tick** — honor it before committing.

## Origin (reference only)

- `packages/system/src/xyresizer/XYResizer.ts` — the factory above (verbatim source available).
- `packages/system/src/xyresizer/utils.ts` — `getControlDirection`, `getDimensionsAfterResize`, `getResizeDirection`.
- `packages/react/src/additional-components/NodeResizer/` — the `<NodeResizer>` / `<ResizeControl>` components that render handles.
- Repo: https://github.com/xyflow/xyflow (MIT).
