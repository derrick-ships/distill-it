# WASM/Skia Render Engine — from [penpot](https://github.com/penpot/penpot)

> Domain: [[_domain]] · Source: https://github.com/penpot/penpot · NotebookLM:

## What it does

It's the part of Penpot that actually paints the design on screen — every rectangle, path, image,
gradient, and blur. The interesting bit is *how*: instead of drawing with the browser's normal web
tech (SVG/HTML/DOM), Penpot ships a tiny graphics engine written in a low-level language (Rust),
compiled to run inside the browser at near-native speed (WebAssembly), drawing onto a single canvas
with the same professional 2D graphics library that powers Chrome and Android (Skia). The payoff:
big boards with thousands of shapes pan, zoom, and edit smoothly instead of choking the DOM.

## Why it exists

A design tool's hardest performance problem is rendering. The naive approach — one DOM/SVG node per
shape — falls apart at scale: thousands of nodes make layout, paint, and hit-testing crawl, and zoom/
pan re-layout the whole tree. Browsers just aren't built to be a high-shape-count 2D canvas. By moving
rendering into a Rust+WASM module drawing to a single GPU-backed canvas via Skia, Penpot gets a
predictable, fast pipeline it controls end to end — the same rendering quality across browsers, and
headroom for features (blurs, blend modes, big documents) that would melt an SVG approach. It's a
strategic bet: own the renderer to be competitive with native design tools.

## How it actually works

There are three layers: a **Rust engine**, a thin **C-style function interface** the browser calls,
and a **shared-memory protocol** for shipping shape data across the boundary.

**The engine holds the state and the Skia surface.** On the Rust side there's a global render state:
the Skia surface/canvas (backed by a GL context for GPU acceleration), the current viewport
(pan/zoom), the background, and the tree of shapes. The browser doesn't draw — it *tells* the engine
what exists and asks it to render.

**The browser talks to the engine through plain C functions.** WASM can only pass numbers across the
boundary, so the API is a set of exported functions like `init`, `set_canvas_background`,
`resize_viewbox`, `use_shape`, `set_shape_transform`, `set_shape_opacity`, `set_children`,
`set_modifiers`, and `render`. There are no rich objects — just numeric arguments and pointers.

**Shapes are sent via a "current shape" + setters pattern.** To describe a shape, the browser calls
`use_shape(id)` to make it "current," then fires a series of setters (`set_shape_transform`,
`set_shape_opacity`, …) that mutate that current shape in the engine's state. It's like a turtle:
"select this shape, now set its position, now its opacity." This avoids marshalling a whole object at
once.

**Bulk/complex data goes through raw shared memory.** For things too big for a few numbers — a list
of child ids, the segments of a path, a shape's fills, transform modifiers — the browser asks the
engine to allocate a chunk of memory (`alloc_bytes`), writes a tightly *packed binary layout* into
it, then calls a function (`set_children`, `set_shape_fills`, `set_modifiers`) that reads those raw
bytes and frees them. The byte layouts are fixed and documented: a shape type is a single byte (0=
Frame, 1=Group, 3=Rect, 4=Path, 5=Text, 6=Circle, 8=Image…), each path segment is exactly 28 bytes
(command + flags + coordinates), each fill is 160 bytes (enough for a solid color, an image ref, or a
gradient). No JSON, no per-field function calls — just memcpy a struct array.

**Rendering is tile-based and incremental.** Rather than repaint the entire (possibly huge) canvas
every frame, the engine divides the world into tiles and re-renders only the tiles that changed or
came into view, then signals back to the browser when tiles finish. There's a render loop
(`start_render_loop`/`continue_render_loop`) so long renders can be spread across frames instead of
blocking. During an interactive drag, lightweight "modifiers" (a transform delta per shape) are
applied so the shape moves without rebuilding it from scratch.

**Reading data back out.** When the browser needs results — the bounding box of a selection, or a
rasterized snapshot of a shape — the engine renders/computes into a buffer and returns a *pointer*;
the browser reads the bytes out of shared memory at that address.

## The non-obvious parts

- **The boundary only speaks numbers.** Every design here flows from that constraint: the "current
  shape + setters" turtle API and the packed-bytes-in-shared-memory protocol both exist because you
  can't hand WASM a real object — only ints, floats, and pointers.
- **Fixed-size binary layouts beat JSON at this boundary.** A 28-byte path segment or 160-byte fill is
  a `memcpy` away from a Rust struct; parsing JSON per shape thousands of times a frame would be the
  bottleneck. Uniform record sizes (even when a fill type uses less than 160 bytes) keep indexing trivial.
- **Tiles are why it scales.** Re-rendering only changed/visible tiles decouples cost from total
  document size — a 10,000-shape board costs about what's on screen, not the whole thing.
- **Modifiers vs. full updates.** Dragging applies a cheap transform modifier per frame and only
  "commits" the real change at the end — interactive manipulation stays smooth without rewriting state.
- **It's GPU-backed via a GL context**, not a 2D-canvas fallback — that's what makes blurs, blends, and
  large fills affordable.
- **It's feature-flagged** (`enable-feature-render-wasm`): the WASM renderer rides alongside the
  legacy SVG renderer and is switched on per-environment — a pragmatic way to ship a risky rewrite.
- **Emscripten generates the JS "glue."** The build doesn't just produce a `.wasm`; it emits the
  JavaScript that loads it, wires up the shared memory, and exposes the exported functions.

## Related

- [[change-based-mutation-model--from-penpot]] — same repo; the change system mutates the file state this engine renders
- [[native-design-tokens--from-penpot]] — same repo; resolved token values become the colors/sizes this engine paints
- [[hand-drawn-rendering--from-excalidraw]] — a contrasting renderer: Rough.js sketchy shapes drawn to canvas, no WASM
- [[dom-to-pdf-export--from-carousel-generator]] — the opposite philosophy: lean on the DOM and screenshot it, rather than own a renderer
- See also: any Rust→WASM + Skia (rust-skia / CanvasKit) pipeline; the FFI patterns here are the reusable part
