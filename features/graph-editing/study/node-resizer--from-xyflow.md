# Node Resizer — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

Those handles around a selected node — the 8 little grab points on the corners and edges. Drag a corner and the node grows or shrinks in two directions; drag an edge and it grows in one. Hold the aspect-ratio lock and it scales proportionally. It enforces minimum and maximum sizes, can be restricted to horizontal-only or vertical-only, keeps a node inside its parent's bounds, and — if the node is a container with children — moves those children correctly as the box changes.

## Why it exists

Nodes aren't always fixed-size boxes. Group/container nodes, sticky notes, sub-flows, image nodes — users need to resize them. The job-to-be-done is "let me change a node's dimensions by direct manipulation, with the same precision and constraints I'd expect from any design tool." The parent/child handling exists because React Flow supports nested nodes (a group containing other nodes), and resizing the group must not break the layout of what's inside it.

## How it actually works

Like dragging, the resizer wraps **d3-drag** — but the drag is attached to a *control point* (one of the handles), not the node body. The `XYResizer` factory runs a start → drag → end lifecycle.

Each control point knows its **direction**: which corner/edge it is, and therefore which dimensions it affects and whether dragging it should also move the node's position. (Dragging the *bottom-right* corner only changes width/height. Dragging the *top-left* corner changes width/height *and* the node's x/y, because the opposite corner has to stay anchored.)

On **start**, it snapshots everything: the node's current width, height, x, y; the pointer's starting world position; and the aspect ratio (width ÷ height) in case the lock is on. It also collects the node's parent (if it's extent-bound to the parent) and its children (whose positions may need to shift), pre-computing the bounds those relationships impose.

On each **drag** tick, the heavy lifting is in a `getDimensionsAfterResize` helper. Given the start snapshot, the control direction, the current pointer position, the min/max boundaries, the aspect-ratio flag, the node origin, and the parent/child extents, it returns the new width, height, x, and y — already clamped and proportioned. The factory then:
- Figures out what actually changed (width? height? x? y?).
- If position changed (because you dragged a top or left handle), it updates x/y *and* shifts every child by the inverse, so the children stay visually put relative to the world even as the box's origin moves.
- Applies single-axis restriction if configured (ignore height changes for a horizontal-only resizer, etc.).
- Handles `expandParent`: if the node should push its parent's bounds outward rather than be clamped, it adjusts accordingly.
- Computes a human-readable resize "direction" (which way it's growing) for callbacks.
- Calls an optional `shouldResize` veto, then fires `onResize` and pushes the change to the store.

On **end**, if any real resizing happened, it fires `onResizeEnd`.

## The non-obvious parts

- **Which handle you grab changes whether position moves.** Bottom-right resize is pure size. Top-left resize must also move the node's x/y so the bottom-right corner stays pinned. This corner-anchoring logic is the conceptual core; `getControlDirection` encodes "this handle affects X / affects Y."
- **Children move to compensate when the origin shifts.** When the box's top-left moves (because you dragged a top/left handle), children would appear to jump unless you shift them by the inverse of the x/y change. The resizer pre-collects children on start and repositions them every tick.
- **Aspect ratio is captured at start, not recomputed.** It stores width/height at grab time so the proportion stays exactly constant through the whole drag rather than drifting from rounding.
- **Node origin participates.** Nodes can have an origin other than top-left (e.g. centered). The math accounts for the origin offset when computing positions and child shifts, which is why the same drag produces different position changes for a centered vs top-left node.
- **Parent extent vs expandParent are opposite behaviors.** `extent: 'parent'` clamps the node inside the parent; `expandParent` instead grows the parent. The start handler sets up the right one.
- **It only commits if something changed.** A drag that hits a min/max wall produces no change and fires nothing, so callbacks aren't spammed and undo history stays clean.

## Related

- [[node-dragging--from-xyflow]] — sibling gesture; shares d3-drag, snap-to-grid, pointer→world conversion, and the parent/child/extent machinery, but changes size instead of position
- [[reactive-store--from-xyflow]] — reads node + children via `getStoreItems`, writes size/position changes back
- See also: any design tool's transform handles (Figma, Sketch) — same corner-anchoring model
