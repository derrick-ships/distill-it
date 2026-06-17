# Hand-Drawn Rendering (build spec) — distilled from excalidraw

## Summary

Render shapes in a hand-sketched style by delegating geometry to **Rough.js**, with one critical discipline: give every element a permanent integer **`seed`** at creation and feed it into Rough on every render so the pseudo-random wobble is *deterministic and stable* (no shimmer on move/zoom/reload). Translate user style choices (stroke style, roughness, fill) into Rough `Options`, dispatch each element type to the matching Rough generator method, and hand-build SVG paths for anything Rough can't draw natively (rounded rectangles). Cache the generated drawable keyed on geometry-affecting fields.

## Core logic (inlined)

**1. Per-element seed (the load-bearing part).** At element creation, assign:
```ts
// random.ts — seeded by Date.now() at module load, reseedable for tests
import { Random } from "roughjs/bin/math";
let random = new Random(Date.now());
export const randomInteger = () => Math.floor(random.next() * 2 ** 31); // 0 .. 2^31-1

// at element creation:
element.seed = randomInteger();          // FROZEN for the element's whole life
element.versionNonce = randomInteger();  // regenerated on every mutation (used elsewhere)
```
The seed never changes once set. It is what makes the wobble reproducible.

**2. Build Rough options from the element:**
```ts
import type { Options } from "roughjs/bin/core";

const ROUGHNESS = { architect: 0, artist: 1, cartoonist: 2 } as const;

const generateRoughOptions = (element, continuousPath = false): Options => {
  const options: Options = {
    seed: element.seed,                          // ← deterministic wobble
    strokeWidth: element.strokeWidth,
    roughness: adjustRoughness(element),         // size-aware, see below
    stroke: element.strokeColor,
    fillWeight: element.strokeWidth / 2,
    hachureGap: element.strokeWidth * 4,
    // confident double-stroke ON for solid, OFF for dashed/dotted:
    disableMultiStroke: element.strokeStyle !== "solid",
    // bump stroke width a bit for non-solid so dashes read:
    // strokeWidth: element.strokeStyle !== "solid" ? element.strokeWidth + 0.5 : element.strokeWidth,
    preserveVertices: continuousPath || element.roughness < ROUGHNESS.cartoonist,
  };
  switch (element.fillStyle) {
    case "hachure": options.fillStyle = "hachure"; break;
    case "cross-hatch": options.fillStyle = "cross-hatch"; break;
    case "solid":   options.fillStyle = "solid"; break;
  }
  if (element.backgroundColor !== "transparent") options.fill = element.backgroundColor;
  if (element.strokeStyle === "dashed") options.strokeLineDash = [8, 8 + element.strokeWidth];
  else if (element.strokeStyle === "dotted") options.strokeLineDash = [1.5, 6 + element.strokeWidth];
  return options;
};

// Roughness must be visually proportional: dial DOWN for very small and very large elements.
const adjustRoughness = (element): number => {
  const maxSize = Math.max(element.width, element.height);
  const roughness = element.roughness;
  if (maxSize >= 50) return roughness;                 // normal
  // shrink toward 0 for tiny elements so wobble doesn't become noise
  return Math.min(roughness / (maxSize < 10 ? 3 : 2), roughness);
  // (Excalidraw also slightly reduces roughness for very large shapes.)
};
```

**3. Dispatch by element type to the Rough generator** (`rough.generator()` → `RoughGenerator`, returns a `Drawable`):
```ts
const generateElementShape = (element, generator /* RoughGenerator */) => {
  switch (element.type) {
    case "rectangle":
    case "iframe":
    case "embeddable":
    case "frame": {
      if (element.roundness) {
        // Rough has no rounded-rect → hand-build an SVG path, then roughen it:
        const w = element.width, h = element.height;
        const r = getCornerRadius(Math.min(w, h), element);
        return generator.path(
          `M ${r} 0 L ${w - r} 0 Q ${w} 0, ${w} ${r} ` +
          `L ${w} ${h - r} Q ${w} ${h}, ${w - r} ${h} ` +
          `L ${r} ${h} Q 0 ${h}, 0 ${h - r} ` +
          `L 0 ${r} Q 0 0, ${r} 0`,
          generateRoughOptions(element, true /* continuousPath */),
        );
      }
      return generator.rectangle(0, 0, element.width, element.height,
                                 generateRoughOptions(element));
    }
    case "ellipse":
      return generator.ellipse(element.width / 2, element.height / 2,
                               element.width, element.height,
                               generateRoughOptions(element));
    case "diamond": {
      const { topX, topY, rightX, rightY, bottomX, bottomY, leftX, leftY } =
        getDiamondPoints(element);
      if (element.roundness) {
        // rounded diamond → SVG path with Q arcs at each vertex, then generator.path(...)
        return generator.path(roundedDiamondPath(element), generateRoughOptions(element, true));
      }
      return generator.polygon(
        [[topX, topY], [rightX, rightY], [bottomX, bottomY], [leftX, leftY]],
        generateRoughOptions(element),
      );
    }
    case "line":
    case "arrow": {
      const points = element.points; // [[x,y], ...] relative to element
      const options = generateRoughOptions(element, true);
      if (element.roundness) return generator.curve(points, options);  // curved
      // closed polygon if first≈last point, else open linear path:
      return isPathClosed(points)
        ? generator.polygon(points, options)
        : generator.linearPath(points, options);
      // arrowheads are computed separately (geometry), not by Rough.
    }
    case "freedraw": {
      // pressure strokes use perfect-freehand for the STROKE; Rough only for fill:
      const svgPath = getFreeDrawSvgPath(element); // perfect-freehand → filled polygon path
      return generator.path(svgPath, { ...generateRoughOptions(element),
                                       fillStyle: "solid",
                                       stroke: "none",
                                       fill: element.strokeColor });
      // The visible stroke is the perfect-freehand polygon, drawn directly (not roughened).
    }
  }
};
```

**4. Cache the drawable.** Generating is expensive; memoize per element keyed on geometry-affecting state.
```ts
// ShapeCache: WeakMap<Element, Drawable | Drawable[]>
// Key invalidation: regenerate only when a geometry/style field changed.
// Practical key = element.versionNonce (changes on every mutation) OR a hash of
// {type,width,height,roughness,strokeWidth,strokeStyle,fillStyle,backgroundColor,roundness,points,seed}.
const ShapeCache = {
  cache: new WeakMap(),
  get(el) { return this.cache.get(el); },
  generateElementShape(el, generator) {
    const cached = this.cache.get(el);
    if (cached && el.versionNonce === cached.versionNonce) return cached.shape;
    const shape = generateElementShape(el, generator);
    this.cache.set(el, { shape, versionNonce: el.versionNonce });
    return shape;
  },
};
```
Because `seed` is NOT in the mutation that fires on a *move* (only x/y change), and because seed is passed into options either way, a move reuses identical wobble; a resize/restyle bumps versionNonce → regenerate → still same seed → consistent look.

**5. Paint.** On canvas: `const rc = rough.canvas(canvasEl); rc.draw(shape);`. For SVG export: `const rsvg = rough.svg(svgRoot); const node = rsvg.draw(shape); svgRoot.appendChild(node);`. Paint order = element z-order (fractional index order).

## Data contracts

```ts
type ExcalidrawElement = {
  id: string;
  type: "rectangle" | "ellipse" | "diamond" | "line" | "arrow" | "freedraw" | "text" | "image" | ...;
  x: number; y: number; width: number; height: number; angle: number;
  strokeColor: string; backgroundColor: string;       // "transparent" if none
  fillStyle: "hachure" | "cross-hatch" | "solid";
  strokeWidth: number;                                  // px
  strokeStyle: "solid" | "dashed" | "dotted";
  roughness: 0 | 1 | 2;                                 // architect | artist | cartoonist
  roundness: { type: number; value?: number } | null;  // null = sharp corners
  seed: number;          // ← FROZEN per element, drives deterministic Rough wobble
  version: number;       // logical clock, +1 per mutation
  versionNonce: number;  // random per mutation; doubles as cache key + merge tiebreaker
  index: string | null;  // fractional index (z-order) — see fractional-indexing doc
  points?: [number, number][];  // for line/arrow/freedraw, relative to x/y
  pressures?: number[];         // for freedraw
};

// Rough.js types you depend on:
import type { Options, Drawable } from "roughjs/bin/core";
import type { RoughGenerator } from "roughjs/bin/generator";
```

## Dependencies & assumptions

- **roughjs** (`rough.generator()`, `rough.canvas()`, `rough.svg()`, and its `Random`/`Math` PRNG). This is the core dependency and is small/MIT.
- **perfect-freehand** — only for `freedraw` strokes (variable-width pressure paths). Optional unless you support a pencil tool.
- A **seeded PRNG** for `seed`/`versionNonce`. Rough.js ships one (`roughjs/bin/math` `Random`); any 32-bit integer generator works.
- Assumes an **immutable-ish element model** where each mutation bumps `version`/`versionNonce` so the cache can key on it.
- No GPU/WebGL needed — renders on 2D canvas or to SVG.

## To port this, you need:

- [ ] An element record with a permanent `seed: number` set once at creation (NEVER regenerated).
- [ ] A `versionNonce`/version that bumps on every mutation (for cache invalidation; also reused by reconciliation).
- [ ] `generateRoughOptions(element)` mapping your style fields → Rough `Options`, passing `seed: element.seed`.
- [ ] Size-aware `adjustRoughness()` so wobble stays proportional at extreme sizes.
- [ ] `disableMultiStroke: strokeStyle !== "solid"` and dash patterns for dashed/dotted.
- [ ] A per-type dispatch to `generator.rectangle/ellipse/polygon/linearPath/curve/path`.
- [ ] Hand-built SVG path strings (with `Q` Bézier corners) → `generator.path()` for rounded rects/diamonds and any shape Rough lacks.
- [ ] A `WeakMap` ShapeCache keyed on `versionNonce` (or a geometry hash).
- [ ] roughjs (+ perfect-freehand if you want pencil strokes).

## Gotchas

- **Forgetting to freeze the seed = constant shimmer.** If you regenerate the seed on render (or never store one), every repaint redraws different wobble. This is the #1 mistake. Seed is created once, stored on the element, sent to collaborators, survives reload.
- **Don't put `seed` in the move mutation.** Moving an element must not change geometry-affecting fields; otherwise the cache busts and (if you also touched seed) the look changes. Only x/y change on a move.
- **Cache key too coarse → stale shapes; too fine → no caching.** Key on `versionNonce` (bumps on real mutations) or a precise geometry hash. Don't key on object identity alone (mutations may keep identity) and don't include x/y (moves shouldn't regenerate).
- **Rounded corners must bypass Rough primitives.** `generator.rectangle()` ignores roundness; you must emit the rounded SVG path yourself and roughen it via `generator.path()`.
- **Non-solid strokes need `disableMultiStroke: true`** or dashes render as overlapping mush.
- **Roughness at extreme sizes looks wrong** without `adjustRoughness` — tiny shapes become illegible noise, huge shapes look mechanically straight.
- **Arrowheads are separate geometry**, not produced by Rough — compute them from the last segment's angle and draw as their own (roughened) path/lines.

## Origin (reference only)

Repo: https://github.com/excalidraw/excalidraw  
Key files: `packages/element/src/shape.ts` (`generateRoughOptions`, `generateElementShape`, `_generateElementShape`), `packages/element/src/ShapeCache.ts`, `packages/common/src/random.ts` (`randomInteger`, `Random`), `packages/element/src/freedraw.ts` / `getFreeDrawSvgPath` (perfect-freehand). Library: `roughjs`.
