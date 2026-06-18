# Domain: rendering

How a product turns its data model into pixels — and the visual identity that comes with it. Covers canvas/SVG rendering pipelines, shape generation, deterministic-randomness aesthetics (seeded hand-drawn styles), and the caching that keeps re-rendering cheap.

## Features in this domain

- [[hand-drawn-rendering--from-excalidraw]] — Rough.js sketchy shapes with a frozen per-element `seed` for stable (non-shimmering) wobble; size-aware roughness; SVG-path rounded corners; WeakMap shape cache keyed on versionNonce.
- [[html-to-png-export--from-open-carrusel]] — headless-Chromium (Puppeteer) screenshot of HTML to pixel-exact PNG; one shared `wrapSlideHtml()` so live preview and export are byte-identical; base64 font/image inlining for self-contained headless render; `deviceScaleFactor:1` for exact dimensions; Sharp sRGB normalization; browser-restart-every-N and bounded concurrency for leak-free batches.
