# Domain: canvas-interaction

Everything that makes an infinite 2D canvas feel alive: panning, zooming, dragging objects across it, and navigating it from an overview map. The shared problem is mapping between **screen pixels** and **flow/world coordinates** through a viewport transform `[x, y, zoom]`.

## What this domain is about

A node-based editor (React Flow / Svelte Flow / Figma-style canvas) renders content on a virtual plane far larger than the screen. A single affine transform — translate `(x, y)` then scale `zoom` — projects world coordinates onto the visible pane. Every interaction in this domain either *reads* that transform (to convert a mouse event into a world position) or *writes* it (to pan/zoom). The hard parts are: doing it at 60fps, respecting min/max zoom and pan extents, snapping, auto-panning when you drag near an edge, and keeping multiple renderers (React, Svelte) driving the same math.

## The core coordinate identities

- **screen → world (renderer → flow):** `worldX = (screenX - transform.x) / zoom`, `worldY = (screenY - transform.y) / zoom`.
- **world → screen:** `screenX = worldX * zoom + transform.x`.
- A `Viewport` is `{ x, y, zoom }`; a d3 `ZoomTransform` is `{ x, y, k }` (k == zoom). They are the same thing with different field names.

## Common patterns

- **Wrap d3, don't reinvent it.** d3-zoom owns the wheel/drag gesture math and the transform; d3-drag owns object dragging. The library wraps each in a factory (`XYPanZoom`, `XYDrag`, `XYMinimap`) that exposes `update(opts)` / `destroy()` and pushes changes out through callbacks.
- **Factory + update + destroy lifecycle.** Each subsystem is a closure created once against a DOM node, reconfigured every render via `update()`, and torn down with `destroy()`.
- **Auto-pan loop.** While dragging near the viewport border, a `requestAnimationFrame` loop nudges the viewport and re-derives the dragged position so the object keeps moving.
- **Constrained viewport writes.** Programmatic viewport changes pass through d3's `constrain()` so translateExtent/scaleExtent are honored.

## Features in this domain

- [[pan-zoom-canvas--from-xyflow]] — the d3-zoom-wrapped infinite viewport (wheel/pinch/drag, fit-view, animated transforms)
- [[node-dragging--from-xyflow]] — d3-drag node movement with multi-select, snap-to-grid, drag threshold, and auto-pan
- [[minimap-navigation--from-xyflow]] — overview panel that maps clicks/drags back onto the main viewport
