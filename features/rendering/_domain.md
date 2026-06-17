# Domain: rendering

How a product turns its data model into pixels — and the visual identity that comes with it. Covers canvas/SVG rendering pipelines, shape generation, deterministic-randomness aesthetics (seeded hand-drawn styles), and the caching that keeps re-rendering cheap.

## Features in this domain

- [[hand-drawn-rendering--from-excalidraw]] — Rough.js sketchy shapes with a frozen per-element `seed` for stable (non-shimmering) wobble; size-aware roughness; SVG-path rounded corners; WeakMap shape cache keyed on versionNonce.
