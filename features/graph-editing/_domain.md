# Domain: graph-editing

The interactions that **change the graph itself** — drawing a new edge by dragging from one node's handle to another, and resizing a node by dragging its border. Distinct from canvas-interaction (which moves the *view* or moves whole objects without changing their size or connectivity).

## What this domain is about

A node editor isn't just a viewer; users build the graph by hand. Two primitive gestures cover most of it:

1. **Connect** — press a connection point ("handle") on a node, drag a live wire to another handle, release; if the target is valid, a new edge is created. Needs proximity detection (snap to the closest handle within a radius), validity rules (no source→source in strict mode, no self-loops, custom predicates), and a ghost connection line that follows the pointer.
2. **Resize** — drag one of 8 control points on a node's bounding box to change its width/height (and reposition x/y when dragging a top/left edge). Needs min/max clamps, optional aspect-ratio lock, optional single-axis restriction, parent-extent containment, and proportional child repositioning.

Both are framework-agnostic engines wrapped in a `XY*` factory and surfaced as components (`<Handle>`, `<NodeResizer>`).

## Common patterns

- **DOM as hit-test surface.** Connection validity uses `document.elementFromPoint()` + CSS classes/`data-*` attributes on handles rather than pure geometry — the handle under the cursor wins over the geometrically-closest one.
- **Live preview state.** An in-progress connection / resize is held as transient state and streamed to the renderer each pointermove, committed only on a valid pointerup.
- **Constraint pipeline.** Raw pointer delta → snap → min/max clamp → extent clamp → aspect ratio → emit change.

## Features in this domain

- [[connection-handles--from-xyflow]] — drag-to-connect: closest-handle search, strict/loose validity, onConnect lifecycle
- [[node-resizer--from-xyflow]] — drag-to-resize with aspect lock, min/max, parent/child extents
