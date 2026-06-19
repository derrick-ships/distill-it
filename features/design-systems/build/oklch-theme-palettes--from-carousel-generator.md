# OKLCH Theme Palettes (build spec) — distilled from carousel-generator

## Summary
A curated set of DaisyUI-style named themes, each reduced at module-load to the three colors a
carousel actually needs — `primary`, `secondary` (a derived readable foreground), `background`.
The reusable core is **deriving a contrasting foreground color from any base color by interpolating
toward black/white in OKLCH space**, with the direction chosen by a WCAG `isDark()` test. Accepts
hex or OKLCH inputs interchangeably (everything goes through `culori.parse`).

## Core logic (inlined)

Color derivation — `src/lib/theme-utils.ts`:

```ts
import { interpolate, rgb, formatHex, parse, type Color, type Oklch } from "culori";
// isDark(input): WCAG-style relative-luminance test — true when the color is dark.

export const generateForegroundColorFrom = function (
  input: Color | string,
  percentage = 0.8
) {
  const result = interpolate(
    [input, isDark(input) ? "white" : "black"],
    "oklch"
  )(percentage);
  return colorObjToString(result);
};

const generateDarkenColorFrom = function (input: any, percentage = 0.07) {
  const result = interpolate([input, "black"], "oklch")(percentage);
  return colorObjToString(result);
};

export const colorObjToString = function (input: Oklch) {
  const rbgColor = rgb(input);
  return `${formatHex(rbgColor)}`;
};
```

Theme → 3-color palette — `src/lib/pallettes.tsx`:

```ts
import { generateForegroundColorFrom } from "@/lib/theme-utils";
import themes, { Theme } from "@/lib/themes";
import { ColorSchema } from "@/lib/validation/theme-schema";
import { formatHex, parse } from "culori";

export type Colors = z.infer<typeof ColorSchema>;  // { primary, secondary, background }

export const pallettes: Record<string, Colors> = Object.entries(themes).reduce(
  (acc, [themeName, theme]) => { acc[themeName] = ThemeToColors(theme); return acc; },
  {} as Record<string, Colors>
);

function ThemeToColors(theme: Theme): { primary: string; secondary: string; background: string } {
  return {
    primary:
      (theme["primary"] && formatHex(parse(theme["primary"]))) ||
      generateForegroundColorFrom(theme.primary),
    secondary: generateForegroundColorFrom(theme["base-100"]),   // readable text from background
    background: formatHex(parse(theme["base-100"])) || theme["base-100"],
  };
}
```

Theme definitions — `src/lib/themes.ts` (DaisyUI-style; hex or OKLCH values mixed freely):

```ts
export interface Theme {
  "color-scheme": string;
  primary: string;            "primary-content"?: string;
  secondary: string;          "secondary-content"?: string;
  accent: string;             "accent-content"?: string;
  neutral: string;            "neutral-content"?: string;
  "base-100": string;         "base-content"?: string;   // base-100 = background base
  info?: string; success?: string; warning?: string; error?: string;
}
const themes: Record<string, Theme> = {
  aqua: {
    "color-scheme": "dark",
    primary: "#09ecf3", "primary-content": "#005355",
    secondary: "#966fb3", accent: "#ffe999", neutral: "#3b8ac4",
    "base-100": "#345da7",
    info: "#2563eb", success: "#16a34a", warning: "#d97706",
    error: "oklch(73.95% 0.19 27.33)",   // <- OKLCH and hex coexist
  },
  black: { "color-scheme": "dark", primary: "#373737", secondary: "#373737",
           accent: "#373737", "base-100": "#000000", neutral: "#373737",
           info: "#0000ff", success: "#008000", warning: "#ffff00", error: "#ff0000" },
  // ...more themes
};
export default themes;
```

## Data contracts
- **Theme** (input): record keyed by name → `Theme` interface above. Color values are hex **or**
  any culori-parseable string (incl. `oklch(...)`).
- **Colors** (output, `ColorSchema`): `{ primary: string; secondary: string; background: string }`,
  all hex.
- `generateForegroundColorFrom(input, percentage=0.8)` → hex string: foreground that contrasts
  `input`, blended `percentage` of the way to white (if input dark) or black (if input light) in OKLCH.
- `pallettes`: `Record<themeName, Colors>` computed once at module load.

## Dependencies & assumptions
- `culori` (`parse`, `formatHex`, `interpolate`, `rgb`), `zod`.
- An `isDark(color)` helper (WCAG relative-luminance threshold). culori has the pieces; or use a
  standard luminance formula: `L = 0.2126R+0.7152G+0.7152B` on linearized sRGB, dark if `L < 0.5`.
- Swappable: the theme list is DaisyUI-derived but arbitrary; the derivation works on any base color.

## To port this, you need:
- [ ] `culori` (or any OKLCH-capable color lib with interpolation + hex formatting).
- [ ] An `isDark()` luminance test to choose the contrast target.
- [ ] A theme source (object/JSON) providing at least a `primary` and a background (`base-100`).
- [ ] A reduce step that maps each theme to your runtime color set once at load.

## Gotchas
- **Interpolate in OKLCH, not sRGB/HSL** — sRGB blends pass through muddy grays and break perceived
  contrast; OKLCH keeps lightness uniform.
- Stop at ~0.8 toward the target (not 1.0) to retain a hue tint; 1.0 gives flat black/white.
- `parse()` returns `undefined` on an unrecognized string → `formatHex(undefined)` misbehaves; the
  `|| fallback` guards in `ThemeToColors` matter (note the `|| theme["base-100"]` raw fallback).
- `isDark` must agree with human perception at edges; a naive RGB-average threshold misjudges
  saturated colors — use proper relative luminance.
- Derivation runs at module import; if themes are user-editable at runtime, recompute on change.

## Origin (reference only)
`src/lib/theme-utils.ts` (derivation), `src/lib/pallettes.tsx` (theme→palette),
`src/lib/themes.ts` (DaisyUI-style theme records), `src/lib/validation/theme-schema.tsx` (`ColorSchema`).
