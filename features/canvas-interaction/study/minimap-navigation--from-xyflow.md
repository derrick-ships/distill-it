# Minimap Navigation — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

The little overview panel in the corner of the canvas. It shows the whole graph in miniature with a rectangle marking what you're currently looking at. You can drag inside it to pan the main canvas, and (optionally) scroll over it to zoom. It's the "you are here" map for a diagram too big to see all at once.

## Why it exists

Once a graph outgrows the screen, users get lost — they pan somewhere, can't find their way back, lose the sense of scale. The minimap solves "where am I in this big thing, and let me jump somewhere fast." It's a navigation aid that turns an infinite canvas from disorienting into manageable. For dense professional diagrams it's close to essential.

## How it actually works

The minimap is its own little SVG that renders all the nodes scaled down to fit, plus a `<path>` rectangle (actually a rectangle-with-a-mask) showing the current viewport. The interesting part is the *interaction*: how a gesture inside the tiny map translates into moving the big canvas.

It reuses **d3-zoom** — the same library the main canvas uses — but attached to the minimap SVG. The `XYMinimap` factory wires up a d3-zoom whose job isn't to transform the minimap itself, but to capture pan/zoom gestures and forward them to the *main* viewport.

The core challenge is scale. The minimap is showing the world shrunk by some factor; a one-pixel drag in the minimap should move the main canvas by *many* world units. So as the user drags, it reads the pointer movement, multiplies it by a **move scale** that accounts for both how much the minimap is shrunk and the main canvas's current zoom, optionally inverts the direction (drag-the-map vs drag-the-viewport feel), and feeds the result into the main pan/zoom subsystem's `setViewportConstrained` — the "constrained" variant so you can't drag the view outside the legal bounds.

For wheel-zoom over the minimap, it computes a zoom delta from the scroll amount and a configurable step, then calls the main canvas's `scaleTo` to zoom the real viewport.

Because it goes through the main subsystem's constrained setters, the minimap can never put the canvas somewhere illegal, and the main viewport stays the single source of truth — the minimap is purely an input device.

## The non-obvious parts

- **It's an input controller, not a second viewport.** The minimap doesn't own any view state. It captures gestures and pushes them into the *main* pan/zoom instance. This keeps one source of truth and means the rectangle and the canvas can never disagree.
- **The move-scale couples two scales.** The translation factor blends the minimap's shrink ratio with the main canvas's zoom (with a logarithmic guard so it stays usable across extreme zoom levels). Get this wrong and dragging the map feels either glued or wildly oversensitive.
- **Inverse-pan is a feel toggle.** Some users expect "drag the map and the content follows" (inverse), others "drag and the viewport rectangle follows." A sign flip on the move-scale switches between the two.
- **Reusing d3-zoom for a non-zoom purpose.** d3-zoom here is essentially a gesture recognizer; the actual transform it would normally apply is discarded and re-interpreted as a command to the main canvas.
- **Constrained writes only.** It calls `setViewportConstrained`, never the raw setter, so map-driven navigation always respects the same pan/scale limits as direct interaction.

## Related

- [[pan-zoom-canvas--from-xyflow]] — the minimap is a remote control for this subsystem; it calls its `setViewportConstrained` and `scaleTo`
- [[reactive-store--from-xyflow]] — reads the node list (to draw the miniatures) and the current viewport (to position the rectangle)
- See also: the overview/navigator panel in Photoshop, Figma, any large-canvas editor
