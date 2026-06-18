# Domain: rendering

How a product turns its data model into pixels — and the visual identity that comes with it. Covers canvas/SVG rendering pipelines, shape generation, deterministic-randomness aesthetics (seeded hand-drawn styles), and the caching that keeps re-rendering cheap.

## Features in this domain

- [[hand-drawn-rendering--from-excalidraw]] — Rough.js sketchy shapes with a frozen per-element `seed` for stable (non-shimmering) wobble; size-aware roughness; SVG-path rounded corners; WeakMap shape cache keyed on versionNonce.
- [[dom-to-pdf-export--from-carousel-generator]] — export a live React view as a multi-page PDF: deep-clone the node, strip editor chrome by `id`-prefix, proxy cross-origin images same-origin, `html-to-image` rasterize at 1.8×, then slice the tall canvas into fixed-size jsPDF pages.
- [[wasm-skia-render-engine--from-penpot]] — a Rust→WASM (Emscripten) renderer on Skia drawing to one GPU canvas: C-ABI boundary (numbers + pointers only), a "current shape + setters" turtle API, packed fixed-size binary records in shared linear memory (28-byte path segs, 160-byte fills), and tile-based incremental rendering with a frame-spread loop.
- [[notch-anchored-companion-overlay--from-clicky]] — *OS-level* rendering rather than in-canvas: a menu-bar-only macOS app with a borderless NSPanel dropping out of the menu-bar/notch strip plus per-screen full-screen click-through `OverlayWindow`s at `.screenSaver` level using `.ignoresSafeArea()` to draw a companion over the whole display (notch included). Note: the "notch usage" is anchoring + ignoring safe area — there is no notch-detection API in play.
- [[visualization-auto-selection--from-metabase]] — a chart registry where each visualization self-describes applicability (isSensible/checkRenderable), so picking the right chart for a result set is just filtering the registry. New chart types plug in by answering the same predicates.
