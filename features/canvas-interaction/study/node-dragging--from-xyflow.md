# Node Dragging — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

Grab a node and move it. If several nodes are selected, they all move together as a rigid group. If snap-to-grid is on, they click onto grid lines. If you drag a node toward the edge of the canvas, the canvas auto-scrolls so you can keep going past what's currently visible. A small "drag threshold" means a slightly shaky click doesn't accidentally move the node. Drag start / drag / drag stop all fire callbacks so the app can react (persist positions, run layout, etc.).

## Why it exists

Positioning nodes by hand is the second most-used interaction after pan/zoom (and often the *point* of the tool — building a flowchart, a mind map, a pipeline). The job-to-be-done is "let me place things exactly where I want, including moving a whole cluster at once, without fighting the tool." The auto-pan and snap behaviors exist because real diagrams are bigger than the screen and users want alignment without manual fiddling.

## How it actually works

Like pan/zoom, dragging wraps a d3 module — here **d3-drag** — so the cross-browser pointer/touch gesture handling is borrowed, not rebuilt. The `XYDrag` factory attaches a drag behavior to a node's DOM element (or to the whole pane for selection-drag) and runs a start → drag → end lifecycle.

The key trick is converting the mouse position into **world coordinates** using the current viewport transform (the same `[x, y, zoom]` from the pan/zoom subsystem). Everything downstream works in world space.

On **start**, it figures out which nodes are actually moving: the grabbed node, plus every other currently-selected node if this is a multi-drag. For each one it records the node's *distance* from the pointer — the rigid offset that must be preserved for the whole drag. It also records the initial mouse position so it can measure the drag threshold.

On each **drag** tick:
- It first checks the threshold: until you've moved more than N *screen* pixels (measured in client space so it behaves the same at every zoom level), nothing happens. Once exceeded, the "real" drag starts.
- For every moving node it computes a new position = current pointer minus that node's recorded offset.
- If snapping is on, it rounds to the grid. For a multi-node drag it computes a *single* snap offset for the whole group (so the group stays rigid and snaps as a unit, rather than each node snapping independently and the formation breaking).
- It clamps each node to the allowed extent (and, for grouped nodes, computes an *adjusted* extent per node so the group can't be pushed partway out of bounds).
- It writes the new positions into the store and fires `onNodeDrag` / `onSelectionDrag`.

**Auto-pan** runs as its own `requestAnimationFrame` loop the moment a drag starts (if enabled). Each frame it measures how close the pointer is to the container's edges; if it's in the hot zone it nudges the viewport by a small amount and — crucially — re-runs the node-position update with the shifted viewport, so the node keeps sliding even though the mouse is stationary at the edge.

On **end**, it stops the auto-pan loop, does one final position commit (marked as "dragging finished" so the store knows the gesture is over), and fires `onNodeDragStop` / `onSelectionDragStop`.

## The non-obvious parts

- **Threshold is measured in screen pixels, not world units.** If it were world units, the "wiggle tolerance" would change with zoom — feeling twitchy when zoomed out. They deliberately measure the start-to-now distance in client coordinates so it's consistent.
- **Group snapping uses one offset, not per-node snapping.** Snap each node independently and a neat row of nodes turns into a jagged mess after one drag. Computing the group's snap offset once keeps the formation intact.
- **Per-node adjusted extent for multi-drag.** A naive extent clamp would let the leftmost node hit the boundary while the rest of the group keeps moving, shearing the group. They recompute each node's effective extent from the group's bounding box so the whole cluster stops together.
- **Auto-pan re-derives position from a *stored* last pointer.** Because the mouse isn't moving during edge auto-pan, the loop adjusts the remembered last position by the pan delta (divided by zoom) and re-runs the update — that's what makes "hold at the edge and the node keeps going" work.
- **Multitouch aborts the drag.** A second finger (touchmove with >1 touch) sets an abort flag so a pinch doesn't get misread as a drag.
- **Deleting a node mid-drag is handled.** If the dragged node disappears from the lookup (deleted by some other code), it aborts cleanly instead of throwing.
- **selectNodesOnDrag vs not.** Whether grabbing a node also selects it (and deselects others) is a configurable product decision handled at drag start.

## Related

- [[pan-zoom-canvas--from-xyflow]] — provides the viewport transform this converts through, and the `panBy` used by auto-pan
- [[reactive-store--from-xyflow]] — `XYDrag` reads everything via `getStoreItems()` and writes via `updateNodePositions`
- [[node-resizer--from-xyflow]] — sibling gesture that changes size instead of position; same d3-drag + snap + extent toolkit
- See also: any drag-and-drop canvas; the "record offset on start, reproject on move" pattern is universal
