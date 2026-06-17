# Pan & Zoom Canvas (build spec) — distilled from xyflow

## Summary

Build an infinite, pannable, zoomable canvas viewport by wrapping **d3-zoom**. A factory `XYPanZoom(params)` attaches a d3-zoom behavior to a DOM node, holds zoom/pan limits, and exposes imperative methods (`setViewport`, `scaleTo/By`, `getViewport`, `syncViewport`, `update`, `destroy`). The viewport is a single `{ x, y, zoom }` transform; d3 owns the live value. Changes stream out via callbacks. Configurable per render through `update()`, whose **filter** predicate encodes all product rules (pan-on-drag, activation keys, no-pan zones, pan-on-scroll).

## Core logic (inlined)

### Coordinate model
```
Viewport = { x, y, zoom }            // product-facing
d3 ZoomTransform = { x, y, k }       // k === zoom
viewportToTransform(v) = new ZoomTransform(v.zoom, v.x, v.y)  // d3-zoom: zoomIdentity.translate(x,y).scale(k)

screen -> world:  worldX = (screenX - x) / zoom ;  worldY = (screenY - y) / zoom
world  -> screen: screenX = worldX * zoom + x
```

### Factory skeleton (the load-bearing parts, condensed from source)
```ts
import { zoom, zoomTransform, ZoomTransform } from 'd3-zoom';
import { select } from 'd3-selection';
import { interpolate, interpolateZoom } from 'd3-interpolate';
import 'd3-transition'; // side-effect: enables selection.transition()

function XYPanZoom({ domNode, minZoom, maxZoom, translateExtent, viewport,
                    onPanZoom, onPanZoomStart, onPanZoomEnd, onDraggingChange }) {
  const bbox = domNode.getBoundingClientRect();
  const d3ZoomInstance = zoom().scaleExtent([minZoom, maxZoom]).translateExtent(translateExtent);
  const d3Selection = select(domNode).call(d3ZoomInstance);
  d3ZoomInstance.wheelDelta(wheelDelta); // normalize cross-browser wheel speed

  // seed initial viewport, clamped + constrained
  setViewportConstrained(
    { x: viewport.x, y: viewport.y, zoom: clamp(viewport.zoom, minZoom, maxZoom) },
    [[0,0],[bbox.width, bbox.height]], translateExtent);

  // keep handles to d3's default wheel + dblclick handlers so we can restore them
  const d3ZoomHandler        = d3Selection.on('wheel.zoom');
  const d3DblClickZoomHandler = d3Selection.on('dblclick.zoom');

  async function setTransform(transform, opts) {           // animated when opts.duration
    return new Promise(resolve => {
      d3ZoomInstance.interpolate(opts?.interpolate === 'linear' ? interpolate : interpolateZoom)
        .transform(getD3Transition(d3Selection, opts?.duration, opts?.ease, () => resolve(true)), transform);
    });
  }
  // getD3Transition: if duration -> selection.transition().duration(d).ease(e).on('end', onEnd); else selection

  async function setViewport(v, opts)            { const t = viewportToTransform(v); await setTransform(t, opts); return t; }
  async function setViewportConstrained(v, extent, transExtent) {
    const t = d3ZoomInstance.constrain()(viewportToTransform(v), extent, transExtent); // d3 clamps to legal bounds
    if (t) await setTransform(t); return t;
  }
  function getViewport()  { const t = zoomTransform(d3Selection.node()); return { x: t.x, y: t.y, zoom: t.k }; }
  async function scaleTo(z, opts) { /* same pattern, d3ZoomInstance.scaleTo(...) */ }
  async function scaleBy(f, opts) { /* d3ZoomInstance.scaleBy(...) */ }

  function syncViewport(v) {   // push state INTO d3 without emitting events
    const t = viewportToTransform(v);
    const cur = d3Selection.property('__zoom');
    if (cur.k !== v.zoom || cur.x !== v.x || cur.y !== v.y)
      d3ZoomInstance.transform(d3Selection, t, null, { sync: true }); // {sync:true} suppresses listeners
  }

  function update(opts) { /* see below */ }
  function destroy() { d3ZoomInstance.on('zoom', null); }

  return { update, destroy, setViewport, setViewportConstrained, getViewport,
           scaleTo, scaleBy, setScaleExtent, setTranslateExtent, syncViewport, setClickDistance };
}
```

### update() — runs every render, rebuilds handlers + filter
```ts
function update(opts) {
  // if a marquee selection is active and we're not already panning, disable zoom entirely
  if (opts.userSelectionActive && !zoomPanValues.isZoomingOrPanning) destroy();

  const isPanOnScroll = opts.panOnScroll && !opts.zoomActivationKeyPressed && !opts.userSelectionActive;

  // selection-on-drag => clickDistance Infinity so a bg drag is a marquee, not a pan
  d3ZoomInstance.clickDistance(opts.selectionOnDrag ? Infinity : Math.max(0, opts.paneClickDistance ?? 0));

  // wheel: either pan-on-scroll (Figma style) or zoom-on-scroll
  const wheelHandler = isPanOnScroll ? createPanOnScrollHandler(...) : createZoomOnScrollHandler(...);
  d3Selection.on('wheel.zoom', wheelHandler, { passive: false });

  d3ZoomInstance.on('start', startHandler);   // -> onPanZoomStart, onDraggingChange(true)
  d3ZoomInstance.on('zoom',  zoomHandler);    // -> onPanZoom(viewport), onTransformChange
  d3ZoomInstance.on('end',   endHandler);     // -> onPanZoomEnd, onDraggingChange(false)

  d3ZoomInstance.filter(createFilter(opts));  // THE gatekeeper, see below

  // dblclick bypasses the filter on touch, so toggle it directly
  d3Selection.on('dblclick.zoom', opts.zoomOnDoubleClick ? d3DblClickZoomHandler : null);
}
```

### The filter — encodes every product rule (reconstructed)
```ts
function createFilter(o) {
  return (event) => {
    const zoomScroll = o.zoomOnScroll || o.panOnScroll || o.zoomOnPinch;
    const target = event.target;

    // block while a marquee selection is active
    if (o.userSelectionActive) return false;
    // only zoom while activation key held, if a key is required and not for wheel/pinch
    if (!o.zoomActivationKeyPressed && !zoomScroll && event.type === 'wheel') return false;
    // never pan/zoom over a node while a connection is in progress
    if (o.connectionInProgress) return false;
    // respect "no-pan" / "no-wheel" CSS zones
    if (isWrappedWithClass(event, o.noPanClassName) && event.type !== 'wheel') return false;
    if (isWrappedWithClass(event, o.noWheelClassName) && event.type === 'wheel') return false;
    // pinch (ctrlKey on wheel) allowed if zoomOnPinch
    if (event.ctrlKey && event.type === 'wheel') return o.zoomOnPinch;
    // left button only for pan (button 0/1), right button only if panOnDrag includes 2
    const buttonAllowed = Array.isArray(o.panOnDrag)
      ? o.panOnDrag.includes(event.button) : o.panOnDrag;
    if (event.type === 'mousedown' && !buttonAllowed && !o.selectionOnDrag) return false;
    return true;
  };
}
```

### wheelDelta override (normalize browsers)
```ts
function wheelDelta(event) {
  const factor = event.ctrlKey && isMacOs() ? 10 : 1; // pinch on mac reports tiny deltas
  return -event.deltaY * (event.deltaMode === 1 ? 0.05 : event.deltaMode ? 1 : 0.002) * factor;
}
```

## Data contracts

```ts
type Viewport = { x: number; y: number; zoom: number };
type CoordinateExtent = [[minX: number, minY: number], [maxX: number, maxY: number]];

type PanZoomParams = {
  domNode: Element; minZoom: number; maxZoom: number;
  translateExtent: CoordinateExtent; viewport: Viewport;
  onPanZoom?(e, vp: Viewport): void;
  onPanZoomStart?(e, vp: Viewport): void;
  onPanZoomEnd?(e, vp: Viewport): void;
  onDraggingChange(dragging: boolean): void;
};

type PanZoomTransformOptions = { duration?: number; ease?: (t:number)=>number;
                                 interpolate?: 'smooth' | 'linear' };

type PanZoomInstance = {
  update(opts: PanZoomUpdateOptions): void;
  destroy(): void;
  setViewport(v: Viewport, o?: PanZoomTransformOptions): Promise<ZoomTransform>;
  setViewportConstrained(v, extent, translateExtent): Promise<ZoomTransform|undefined>;
  getViewport(): Viewport;
  scaleTo(z: number, o?): Promise<boolean>;
  scaleBy(f: number, o?): Promise<boolean>;
  setScaleExtent([min,max]): void;
  setTranslateExtent(ext): void;
  syncViewport(v: Viewport): void;
  setClickDistance(n: number): void;
};
```

## Dependencies & assumptions

- `d3-zoom`, `d3-selection`, `d3-interpolate`, `d3-transition` (import for side-effect to enable `.transition()`).
- A `clamp(v,min,max)` and `isNumeric` util (trivial).
- The DOM node must have non-zero size at init (it reads `getBoundingClientRect()` for the initial constrain).
- Render loop (React/Svelte/vanilla) that calls `update()` whenever interaction options change, and feeds `onPanZoom` back into wherever the viewport is stored.
- Swappable: the callbacks. You can ignore them and just use `getViewport()` imperatively.

## To port this, you need:

- [ ] A single canvas/pane DOM element to attach to, and a transformed inner element (`transform: translate(x,y) scale(zoom)`) that holds your content.
- [ ] State (or just d3) to hold `{ x, y, zoom }`; wire `onPanZoom` → your store and your store → `syncViewport`.
- [ ] Min/max zoom and a translate extent (use `[[-∞,-∞],[∞,∞]]` for unbounded).
- [ ] A filter predicate reflecting your rules (which mouse buttons pan, no-pan zones).
- [ ] Decide pan-on-scroll vs zoom-on-scroll for your UX.

## Gotchas

- **Two owners of the viewport.** d3 holds `__zoom`; if you also keep it in app state you MUST reconcile with `syncViewport` (which writes with `{sync:true}` to avoid an event→state→event loop). Skipping this causes drift/jitter.
- **`passive: false` on wheel is mandatory** or you can't `preventDefault()` and the page scrolls instead of zooming.
- **Double-click on touch bypasses the filter** — toggle `dblclick.zoom` by setting/clearing the handler, not via the filter.
- **clickDistance vs marquee select:** set it to `Infinity` when a background drag should start a selection rectangle, else a tiny drag steals the gesture as a pan.
- **Animated transforms return promises** — await them if you chain (e.g. fit-view then center).
- **Initial constrain needs real bounds:** if the node is `display:none` at mount, `getBoundingClientRect()` is 0×0 and the seed viewport is wrong. Init after layout.

## Origin (reference only)

- `packages/system/src/xypanzoom/XYPanZoom.ts` — the factory above.
- `packages/system/src/xypanzoom/utils.ts` — `viewportToTransform`, `getD3Transition`, `wheelDelta`.
- `packages/system/src/xypanzoom/filter.ts` — `createFilter`.
- `packages/system/src/xypanzoom/eventhandler.ts` — start/zoom/end + pan-on-scroll handlers.
- Repo: https://github.com/xyflow/xyflow (MIT).
