# Minimap Navigation (build spec) — distilled from xyflow

## Summary

An overview panel that is a **remote control for the main viewport**, not a second viewport. Render all nodes scaled into a small SVG plus a viewport rectangle. Attach **d3-zoom** to the minimap SVG purely as a gesture recognizer; translate its pan/zoom deltas — scaled by the minimap shrink ratio × main zoom — into calls on the main pan/zoom instance's `setViewportConstrained` (pan) and `scaleTo` (zoom). The main viewport stays the single source of truth.

## Core logic (inlined)

### Factory (reconstructed from source semantics)
```ts
import { zoom } from 'd3-zoom';
import { select, pointer } from 'd3-selection';

function XYMinimap({ domNode, panZoom, getTransform, getViewScale }) {
  const selection = select(domNode);   // the minimap SVG

  function update({ translateExtent, width, height, zoomStep = 10,
                    pannable = true, zoomable = true, inversePan = false }) {

    const panStartHandler = (event) => {
      if (event.sourceEvent.type !== 'wheel') startMousePos = pointer(event.sourceEvent);
    };

    const panHandler = (event) => {
      const transform = getTransform();                 // main canvas [x,y,zoom]
      if (event.sourceEvent.type !== 'mousemove') return;
      // couple minimap shrink (getViewScale) with main zoom; log guard for extreme zoom
      const moveScale = getViewScale() * Math.max(transform[2], Math.log(transform[2])) * (inversePan ? -1 : 1);
      const position = pointer(event.sourceEvent);
      const delta = { x: -(position[0] - startMousePos[0]) * moveScale,
                      y: -(position[1] - startMousePos[1]) * moveScale };
      startMousePos = position;
      // CONSTRAINED write -> never leaves legal bounds; main viewport is source of truth
      panZoom.setViewportConstrained(
        { x: transform[0] + delta.x, y: transform[1] + delta.y, zoom: transform[2] },
        [[0,0],[width, height]], translateExtent);
    };

    const zoomHandler = (event) => {
      const transform = getTransform();
      const pinchDelta = -event.sourceEvent.deltaY * (event.sourceEvent.deltaMode === 1 ? 0.05 : event.sourceEvent.deltaMode ? 1 : 0.002) * zoomStep;
      const nextZoom = transform[2] * Math.pow(2, pinchDelta);
      panZoom.scaleTo(nextZoom);                         // zoom the REAL viewport
    };

    const zoomAndPanHandler = zoom()
      .on('start', panStartHandler)
      .on('zoom', pannable ? panHandler : null)
      .on('zoom.wheel', zoomable ? zoomHandler : null);

    selection.call(zoomAndPanHandler, {});
  }

  function destroy() { selection.on('zoom', null); }
  return { update, destroy };
}
```

### Rendering the miniatures + viewport rect (the static side)
```
- Compute the bounding box of all node absolute positions (+ padding).
- viewBox the minimap SVG to that bbox so nodes auto-fit (SVG does the shrink for free).
- getViewScale() = minimapInnerWidth / viewBoxWidth  (how shrunk the map is).
- Draw each node as a <rect> at its absolute x/y/width/height.
- Draw the current viewport as a <path> rectangle: the inverse-projected screen rect
  { x: -transform.x/zoom, y: -transform.y/zoom, w: elementWidth/zoom, h: elementHeight/zoom },
  often as a full-cover rect with an even-odd mask so the "outside" is dimmed.
```

## Data contracts

```ts
type XYMinimapParams = {
  domNode: SVGSVGElement;
  panZoom: PanZoomInstance;          // the MAIN canvas instance (see pan-zoom-canvas build spec)
  getTransform(): [x:number,y:number,zoom:number];
  getViewScale(): number;            // minimap shrink ratio
};

type MinimapUpdate = {
  translateExtent: CoordinateExtent;
  width: number; height: number;     // main pane size (for the constrain extent)
  zoomStep?: number;                 // wheel zoom sensitivity, default 10
  pannable?: boolean;                // default true
  zoomable?: boolean;                // default false in React Flow's component
  inversePan?: boolean;              // flip drag direction, default false
};
```

## Dependencies & assumptions

- `d3-zoom`, `d3-selection` (for `pointer`).
- A working main pan/zoom instance exposing `setViewportConstrained` and `scaleTo` ([[pan-zoom-canvas--from-xyflow]]).
- Access to the live main transform (`getTransform`) and the minimap shrink ratio (`getViewScale`).
- The node list (absolute positions + sizes) to draw the miniatures — read from your store.

## To port this, you need:

- [ ] A small SVG element sized/positioned in a corner, with a `viewBox` fit to the graph bbox.
- [ ] The main pan/zoom instance + its constrained setters.
- [ ] `getTransform()` and `getViewScale()` wired to live values.
- [ ] A viewport rectangle drawn from the inverse-projected screen rect.
- [ ] Decide `inversePan`, `zoomable`, `zoomStep` for your UX.

## Gotchas

- **Never give the minimap its own view state** — push everything through the main instance's *constrained* setters. Two sources of truth → the rectangle and canvas drift.
- **The move-scale must couple both scales** (minimap shrink × main zoom, with a `Math.log` guard). Using only one makes dragging feel glued (zoomed in) or hyperactive (zoomed out).
- **`inversePan` is a sign flip** — pick the convention your users expect and make it configurable; people have strong opinions.
- **d3-zoom here is a gesture recognizer, not a transformer** — you discard the transform it computes and re-issue it as a command. Don't let it actually transform the minimap SVG.
- **Normalize wheel delta** (`deltaMode` handling) just like the main canvas, or zoom speed differs across browsers/trackpads.

## Origin (reference only)

- `packages/system/src/xyminimap/index.ts` — `XYMinimap` factory (pan/zoom forwarding).
- `packages/react/src/additional-components/MiniMap/` — the React `<MiniMap>` component (renders the SVG, miniatures, mask, viewport rect).
- Repo: https://github.com/xyflow/xyflow (MIT).
