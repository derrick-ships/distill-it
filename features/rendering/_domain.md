# Domain: rendering

How a product turns its data model into pixels — and the visual identity that comes with it. Covers canvas/SVG rendering pipelines, shape generation, deterministic-randomness aesthetics (seeded hand-drawn styles), and the caching that keeps re-rendering cheap.

## Features in this domain

- [[hand-drawn-rendering--from-excalidraw]] — Rough.js sketchy shapes with a frozen per-element `seed` for stable (non-shimmering) wobble; size-aware roughness; SVG-path rounded corners; WeakMap shape cache keyed on versionNonce.
- [[dom-to-pdf-export--from-carousel-generator]] — export a live React view as a multi-page PDF: deep-clone the node, strip editor chrome by `id`-prefix, proxy cross-origin images same-origin, `html-to-image` rasterize at 1.8×, then slice the tall canvas into fixed-size jsPDF pages.
- [[wasm-skia-render-engine--from-penpot]] — a Rust→WASM (Emscripten) renderer on Skia drawing to one GPU canvas: C-ABI boundary (numbers + pointers only), a "current shape + setters" turtle API, packed fixed-size binary records in shared linear memory (28-byte path segs, 160-byte fills), and tile-based incremental rendering with a frame-spread loop.
