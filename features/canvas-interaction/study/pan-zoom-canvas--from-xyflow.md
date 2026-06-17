# Pan & Zoom Canvas — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

It's the thing that makes a React Flow / Svelte Flow canvas feel like an infinite sheet of paper you can shove around with your mouse and scale in and out of. Scroll the wheel to zoom, pinch on a trackpad to zoom, drag the empty background to pan, double-click to zoom in. Programmatically it also powers "fit the whole graph in view," "center on this node," and smooth animated jumps from one viewport to another. Everything you see on the canvas is really painted at a fixed position; this subsystem just moves and scales the *window* you're looking through.

## Why it exists

A node graph is almost always bigger than the screen. Without pan and zoom you could only ever see a corner of your diagram. The job-to-be-done is "let me navigate a 2D space larger than my viewport, fluidly, at 60fps, with sane limits so I can't get lost." For the business, this is table stakes: it's the single most-used interaction in the entire product, so it has to feel buttery. Getting it wrong (janky zoom, drift, fighting the browser's own scroll) makes the whole tool feel broken.

## How it actually works

The whole canvas has one piece of state: a **viewport** of three numbers — `x`, `y`, and `zoom`. Think of it as "shift everything by (x, y) pixels, then scale it by `zoom`." To find where a node lands on screen you do `screenX = nodeX * zoom + x`. To find what world point your mouse is over you invert it: `worldX = (mouseX - x) / zoom`. That one transform is the entire mental model.

Rather than implement wheel/drag/pinch gesture handling from scratch — which is genuinely hard to get right across browsers and trackpads — xyflow wraps **d3-zoom**, a battle-tested library that already owns this. The `XYPanZoom` factory attaches a d3-zoom behavior to the canvas DOM node and then mostly translates between "what the product wants" and "what d3 understands."

The flow:
- On creation it sets the allowed zoom range (`scaleExtent`) and the allowed pan range (`translateExtent`), seeds the starting viewport, and overrides d3's wheel-delta math so one wheel notch feels right.
- An `update()` method runs on every React/Svelte render. It reads the current settings (is panning on drag allowed? is zoom-on-scroll on? is there an activation key like holding Cmd? is the user mid-text-selection?) and rebuilds d3's event handlers and **filter** accordingly. The filter is the gatekeeper that decides whether a given mouse/wheel event should count as a pan/zoom at all — e.g. ignore drags that start on a node, ignore the wheel when the cursor is over a scrollable panel, only zoom while the activation key is held.
- A special "pan on scroll" mode swaps the wheel handler so scrolling *pans* instead of zooming (Figma-style), with pinch still zooming.
- As d3 fires its start/zoom/end lifecycle, wrapper handlers push the new viewport out through callbacks (`onPanZoomStart`, `onPanZoom`, `onPanZoomEnd`) so the store and any user listeners stay in sync.

For programmatic moves there are async methods — `setViewport`, `scaleTo`, `scaleBy` — that drive d3's transform. They optionally **animate**: you pass a duration and easing, and d3 interpolates from the current transform to the target (using a zoom-aware interpolation by default, or linear if asked), resolving a promise when the animation finishes. `setViewportConstrained` runs the target through d3's `constrain()` first so you can never animate outside the legal pan/scale bounds. `syncViewport` is the quiet one: when state changes elsewhere, it pushes the transform into d3 *without* firing events, so the two never drift apart.

## The non-obvious parts

- **They don't own the transform — d3 does.** The source of truth for the live viewport is d3's internal `__zoom` property on the DOM node. `getViewport()` reads it back out. This is why `syncViewport` exists and has to be careful to write without re-emitting events: there are two parties (the store and d3) that both think they know the viewport, and they must be reconciled without an infinite loop.
- **The filter is where all the product rules live.** Pan-on-drag vs select-on-drag, "no-pan" CSS class zones, activation keys, "don't pan while a connection is being drawn" — none of that is in the gesture math, it's all in one `filter` predicate rebuilt every render.
- **Double-click zoom can't go through the filter.** On touch screens a double-tap bypasses the filter entirely and fires `dblclick.zoom` directly, so they wire/unwire that handler separately depending on whether double-click zoom is enabled.
- **`clickDistance` defends real clicks.** If you move less than N pixels it's treated as a click, not a pan — and when select-on-drag is on, they set it to `Infinity` so the background drag becomes a selection rectangle instead of a pan.
- **Wheel delta is overridden.** Browsers report wildly different wheel deltas (pixels vs lines vs pages); the custom `wheelDelta` normalizes that so zoom speed is consistent.

## Related

- [[node-dragging--from-xyflow]] — the sibling subsystem; wraps d3-drag instead of d3-zoom, and depends on this transform to convert pointer events to world coordinates
- [[minimap-navigation--from-xyflow]] — drives this subsystem's `setViewportConstrained` / `scaleTo` from the overview panel
- [[reactive-store--from-xyflow]] — owns the viewport state and calls `update()` each render
- See also: any Figma-style canvas; the d3-zoom pattern here is the canonical web approach
