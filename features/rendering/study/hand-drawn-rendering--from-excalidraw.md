# Hand-Drawn Rendering — from [excalidraw](https://github.com/excalidraw/excalidraw)

> Domain: [[_domain]] · Source: https://github.com/excalidraw/excalidraw · NotebookLM: 

## What it does

Every shape you draw in Excalidraw looks like it was sketched by hand with a marker — wobbly lines, slightly-off corners, hatched fills. That's not a CSS filter or a font; it's the actual geometry of each shape being re-computed with controlled randomness. A "rectangle" isn't four straight lines — it's four *almost*-straight lines that wiggle a little, drawn twice and overlapped so they look like a confident pen stroke. The magic is that the wobble is **stable**: the same rectangle wobbles the same way every time it redraws, even as you drag it around, zoom, or reload the page.

## Why it exists

The hand-drawn look is Excalidraw's entire brand and its core product insight. A crisp, precise diagram *feels finished* — people are reluctant to critique it or change it. A sketchy diagram *feels like a draft* — it invites collaboration, comments, and quick iteration. That lowered psychological stakes is the whole reason teams reach for Excalidraw over a "real" diagram tool. So the rendering style isn't decoration; it's a deliberate behavioral lever that makes the canvas feel low-commitment and brainstorm-friendly.

## How it actually works

Excalidraw doesn't draw shapes itself. It hands the geometry to a small library called **Rough.js**, whose entire job is "draw this shape, but make it look hand-sketched." You give Rough.js a rectangle and some options, and it gives you back a set of squiggly paths that approximate that rectangle.

The clever part is the **seed**. Rough.js's wobble is driven by a pseudo-random number generator. If you let it pick a fresh random number every time, your rectangle would wiggle *differently* on every single repaint — it would visibly shimmer as you dragged it. Excalidraw avoids this by giving every element a permanent random number called its **seed** at the moment it's created. That seed is fed into Rough.js every time the shape is drawn, so the random wobble comes out *identical* every time. The shape looks hand-drawn but never shimmers. The seed is stored with the element and travels with it forever — copy the element, reload, sync it to a collaborator, and the wobble is the same everywhere.

**The options Excalidraw feeds Rough.js** translate the user's choices into sketch parameters:
- The **stroke style** (solid / dashed / dotted) becomes a dash pattern, and for non-solid strokes Excalidraw turns *off* Rough's "draw each line twice" behavior so dashes stay readable.
- **Roughness** is how wild the wobble is — there are three levels (architect / artist / cartoonist). Excalidraw even *scales roughness down* for very tiny or very huge shapes, because a fixed wobble looks like noise on a 10px box and looks too tame on a giant one.
- **Fills** are hatched: instead of a solid color, the inside is filled with diagonal pen strokes whose spacing (`hachureGap`) and thickness (`fillWeight`) are derived from the stroke width.

**Different shapes get different Rough.js calls.** A rectangle is `generator.rectangle()`; an ellipse is `generator.ellipse()`; a diamond is a four-point `generator.polygon()`. Lines and arrows become `linearPath` (straight segments) or `curve` (when the line is set to "curved"). **Rounded rectangles are special** — Rough.js doesn't do rounded corners, so Excalidraw builds the rounded outline itself as an SVG path string (straight edges joined by quadratic-Bézier corner arcs) and asks Rough.js to render *that path* in the sketchy style. So you get rounded corners that are still hand-drawn.

**Freehand strokes** (the pencil tool) are a different beast entirely — those use a separate library (perfect-freehand) to make pressure-sensitive variable-width strokes, and only the *fill* is routed through Rough.js.

**Caching makes it fast.** Generating these squiggly paths is expensive, so Excalidraw computes each element's Rough.js "drawable" once and caches it. The cache is keyed on the things that change the shape's geometry (size, roughness, fill, etc.). When you merely *move* an element, the cached drawable is reused — only a real geometry change busts the cache and regenerates. Because the seed is part of the element and never changes on a move, the regenerated shape still matches.

## The non-obvious parts

- **The seed is the whole trick.** Without a stored per-element seed, the hand-drawn look would be unusable — it would jitter on every frame. People assume the wobble is "random"; it's actually *frozen* randomness. This is the single insight to copy.
- **Roughness is auto-scaled by element size.** A naive clone uses one roughness value for everything and looks wrong at the extremes. Excalidraw quietly dials it down for tiny and giant shapes.
- **Rounded corners bypass Rough's shape primitives.** They're hand-built SVG paths fed to Rough's generic `path()` renderer. This is the pattern for *any* shape Rough.js doesn't natively support — describe it as an SVG path, then roughen the path.
- **Non-solid strokes disable multi-stroke.** Rough draws each outline ~2× by default for the confident-pen look; that turns dashes into mush, so it's switched off for dashed/dotted.
- **The cache key is the element's version, not its identity.** Move = same cached shape; resize/restyle = new shape. Getting that key wrong either shimmers (too aggressive) or shows stale geometry (too lazy).

## Related

- [[fractional-indexing--from-excalidraw]] (z-order determines paint order of these shapes)
- [[scene-reconciliation--from-excalidraw]] (the element `seed` and `versionNonce` that drive both rendering-cache and merge live on the same element record)
- See also: any product wanting a "sketchy"/low-fidelity aesthetic — tldraw uses a similar perfect-freehand + seeded-roughness approach.
