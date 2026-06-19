# OKLCH Theme Palettes — from [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator)

> Domain: [[_domain]] · Source: https://github.com/FranciscoMoretti/carousel-generator · NotebookLM:

## What it does

Gives the carousel a set of named, good-looking color themes ("aqua", "black", ...) and, for each,
automatically derives the three colors the slides actually use — a primary, a readable secondary
text color, and a background — even when the theme only specified a couple of base colors. Pick a
theme from a swatch picker and the whole carousel recolors coherently.

## Why it exists

A LinkedIn carousel needs to look designed, not default. But asking users to choose every color is
too much friction, and letting them pick arbitrary colors produces unreadable combinations (light
text on light background). The solution is a curated set of base themes plus a **derivation step**
that computes contrasting, legible companion colors from each theme — so any theme yields readable
slides without the user (or the AI) tuning contrast by hand.

## How it actually works

The theme definitions are DaisyUI-style records: each theme is an object with keys like `primary`,
`secondary`, `accent`, `neutral`, `base-100` (the background base), plus optional semantic colors
(`info`, `success`, ...). Colors are stored as hex *or* OKLCH strings interchangeably.

For the carousel, only three colors matter, and they're computed per theme:

- **primary** — the theme's `primary`, normalized to hex (or derived from it if missing).
- **background** — the theme's `base-100`, normalized to hex.
- **secondary** — *derived*: a readable foreground color generated **from the background**, so text
  always contrasts with whatever the background is.

The derivation is the clever part and it happens in OKLCH space (perceptually uniform, so blends
look natural):

1. **Decide light or dark.** A WCAG-style `isDark()` check on the input color picks the contrast
   target: blend toward **white** if the color is dark, toward **black** if it's light.
2. **Interpolate in OKLCH.** `generateForegroundColorFrom(color, 0.8)` interpolates 80% of the way
   from the input toward that target in the OKLCH color space, yielding a strongly-contrasting but
   still-tinted foreground (not pure black/white — it keeps a hint of the source hue).
3. **Convert back to hex.** The resulting OKLCH color is converted to RGB and formatted as a hex
   string the UI/Tailwind can use.

A sibling `generateDarkenColorFrom(color, 0.07)` makes subtle darker variants by interpolating only
7% toward black — used for hover/border shades.

All of this runs through the `culori` library (`parse`, `formatHex`, `interpolate`, `rgb`), and the
final `pallettes` object is just every theme mapped through this derivation once at module load.

## The non-obvious parts

- **Contrast is computed, not stored.** The secondary/foreground color isn't a hand-picked value per
  theme; it's derived from the background at runtime, so adding a new theme means specifying only a
  couple of base colors — readability comes for free.
- **OKLCH, not HSL/RGB, for the blend.** Interpolating toward black/white in OKLCH keeps perceived
  lightness changes uniform and avoids the muddy/gray midpoints you get blending in sRGB.
- **80% toward the contrast target, not 100%.** Stopping at 0.8 keeps a tint of the original hue in
  the text color, so it reads as "on-brand dark/light" rather than flat black/white.
- **Hex and OKLCH are accepted interchangeably** because every value passes through `culori.parse`
  first — themes can mix formats (the "aqua" theme literally stores `error` as an `oklch(...)` string
  while everything else is hex).
- **`isDark` uses a WCAG-style luminance test**, the same idea behind accessibility contrast ratios —
  reusing an accessibility heuristic as a styling decision.

## Related

- [[token-pipeline-orchestration--from-style-dictionary]] — the heavyweight "design tokens → platform code" take on the same single-source-of-truth idea
- [[transforms-and-transform-groups--from-style-dictionary]] — token *value* transforms (incl. color-space conversions) generalized
- [[design-systems-library--from-open-design]] — themes/design specs injected into generation, a different mechanism for the same goal
- [[dom-to-pdf-export--from-carousel-generator]] — same repo; these computed colors are what the PDF export must reproduce faithfully
- See also: DaisyUI's theme system (the schema here is directly inspired by it)
