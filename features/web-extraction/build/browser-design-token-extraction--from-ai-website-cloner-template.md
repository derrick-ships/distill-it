# Browser Design Token Extraction (build spec) — distilled from ai-website-cloner-template

## Summary

Run `getComputedStyle()` on every DOM element via `page.evaluate()` in a headless Chromium session to extract the final resolved CSS values for a webpage. Deduplicate by frequency to surface the actual design system (brand colors, typography scale, spacing system). Capture interaction states via pseudo-class injection and responsive variants by viewport resizing. Output is a structured token document + screenshots saved to `docs/research/`.

## Core logic (inlined)

```typescript
import { chromium } from 'playwright'
import { parse, formatOklch } from 'culori'

async function extractDesignTokens(url: string): Promise<DesignTokens> {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  
  // Wait for full render including fonts and JS-driven styles
  await page.goto(url, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)  // font render settling
  
  // === COMPUTED STYLE EXTRACTION ===
  const rawTokens = await page.evaluate(() => {
    const STYLE_PROPS = [
      'color', 'backgroundColor', 'fontFamily', 'fontSize', 'fontWeight',
      'lineHeight', 'letterSpacing', 'padding', 'paddingTop', 'paddingRight',
      'paddingBottom', 'paddingLeft', 'margin', 'marginTop', 'marginRight',
      'marginBottom', 'marginLeft', 'borderRadius', 'borderColor', 'borderWidth',
      'display', 'flexDirection', 'gap', 'alignItems', 'justifyContent',
      'boxShadow', 'textDecoration', 'textTransform', 'opacity',
      'transition', 'transform', 'width', 'maxWidth', 'height',
    ]
    
    const records: Record<string, string>[] = []
    const elements = document.querySelectorAll('*')
    
    elements.forEach((el) => {
      const computed = window.getComputedStyle(el)
      const record: Record<string, string> = {
        tag: el.tagName.toLowerCase(),
        classes: el.className,
      }
      STYLE_PROPS.forEach((prop) => {
        const val = computed.getPropertyValue(
          prop.replace(/([A-Z])/g, '-$1').toLowerCase()
        )
        if (val && val !== '' && val !== 'none' && val !== 'normal') {
          record[prop] = val
        }
      })
      records.push(record)
    })
    
    return records
  })
  
  // === FREQUENCY ANALYSIS → DESIGN TOKENS ===
  const colorFreq: Map<string, number> = new Map()
  const fontFamilyFreq: Map<string, number> = new Map()
  const fontSizeFreq: Map<string, number> = new Map()
  
  rawTokens.forEach(r => {
    if (r.color) colorFreq.set(r.color, (colorFreq.get(r.color) || 0) + 1)
    if (r.backgroundColor) colorFreq.set(r.backgroundColor, (colorFreq.get(r.backgroundColor) || 0) + 1)
    if (r.fontFamily) fontFamilyFreq.set(r.fontFamily, (fontFamilyFreq.get(r.fontFamily) || 0) + 1)
    if (r.fontSize) fontSizeFreq.set(r.fontSize, (fontSizeFreq.get(r.fontSize) || 0) + 1)
  })
  
  // Top colors (sorted by frequency, converted to oklch)
  const brandColors = [...colorFreq.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([rgbColor]) => {
      const parsed = parse(rgbColor)
      return parsed ? formatOklch(parsed) : rgbColor
    })
  
  // === INTERACTION STATE CAPTURE ===
  const desktopScreenshot = await page.screenshot({ fullPage: true })
  
  // Force hover state via style injection
  await page.addStyleTag({ content: 'a:hover, button:hover { /* force */ }' })
  // More reliably: inject hover class or use CDP to set hover state
  await page.evaluate(() => {
    document.querySelectorAll('a, button, [data-hover]').forEach(el => {
      el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }))
    })
  })
  await page.waitForTimeout(300)  // transition settling
  const hoverScreenshot = await page.screenshot({ fullPage: true })
  
  // === RESPONSIVE CAPTURE ===
  const viewports = [
    { name: 'mobile', width: 375, height: 812 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'desktop', width: 1440, height: 900 },
  ]
  
  const responsiveScreenshots: Record<string, Buffer> = {}
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height })
    await page.waitForTimeout(200)
    responsiveScreenshots[vp.name] = await page.screenshot({ fullPage: true })
  }
  
  // === ASSET DISCOVERY ===
  const assets = await page.evaluate(() => {
    const images = [...document.querySelectorAll('img')].map(img => img.src)
    const videos = [...document.querySelectorAll('video source, video[src]')]
      .map(v => (v as HTMLSourceElement).src)
    return { images, videos }
  })
  
  await browser.close()
  
  return {
    brandColors,
    fontFamilies: [...fontFamilyFreq.entries()].sort((a, b) => b[1] - a[1]).map(([f]) => f),
    fontSizes: [...fontSizeFreq.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s),
    rawTokens,
    assets,
    screenshots: { desktop: desktopScreenshot, hover: hoverScreenshot, ...responsiveScreenshots },
  }
}
```

### globals.css generation from tokens
```typescript
function generateTailwindV4Config(tokens: DesignTokens): string {
  const [bg, text, accent, ...rest] = tokens.brandColors
  const [bodyFont] = tokens.fontFamilies
  
  return `@import "tailwindcss";

:root {
  --color-background: ${bg ?? 'oklch(1 0 0)'};
  --color-foreground: ${text ?? 'oklch(0.1 0 0)'};
  --color-accent: ${accent ?? 'oklch(0.6 0.18 270)'};
  --color-accent-hover: ${rest[0] ?? 'oklch(0.5 0.20 270)'};
  --font-sans: ${bodyFont ?? 'Inter'}, sans-serif;
}
`
}
```

## Data contracts

### DesignTokens output shape
```typescript
interface DesignTokens {
  brandColors: string[]         // oklch strings, sorted by frequency
  fontFamilies: string[]        // CSS font-family strings, sorted by frequency
  fontSizes: string[]           // px values, sorted by frequency
  rawTokens: Array<{            // per-element records
    tag: string
    classes: string
    color?: string
    backgroundColor?: string
    fontFamily?: string
    fontSize?: string
    fontWeight?: string
    lineHeight?: string
    // ... all STYLE_PROPS
  }>
  assets: {
    images: string[]            // absolute URLs
    videos: string[]
  }
  screenshots: {
    desktop: Buffer
    hover: Buffer
    mobile: Buffer
    tablet: Buffer
  }
}
```

## Dependencies & assumptions

- **Playwright** (Chromium) — `npm install playwright`
- **culori** — oklch color conversion: `npm install culori`
- Target URL must be publicly accessible; no auth wall
- Node.js 24+ (for top-level await, native fetch)
- Chromium binary available (`npx playwright install chromium`)

## To port this, you need:

- [ ] Playwright + Chromium installed
- [ ] culori for color space conversion
- [ ] A `docs/research/` output directory
- [ ] A defined STYLE_PROPS list matching the design properties you care about
- [ ] A frequency analysis step that distinguishes "brand color" from "default browser color"
- [ ] Screenshot storage (Buffer → file via `fs.writeFile`)
- [ ] Viewport resize loop for responsive capture

## Gotchas

**Browser default styles pollute the token set.** `getComputedStyle()` returns values even for browser-default styles on unclassed elements. Filter out common defaults (`rgb(0, 0, 0)`, `rgba(0, 0, 0, 0)`, `normal`, `""`, `auto`) before frequency analysis.

**Font family strings include fallbacks.** `getComputedStyle()` returns `"Inter", "Helvetica Neue", sans-serif` — you want only the first token. Split on `,` and take `[0]`, strip surrounding quotes.

**`networkidle` isn't always enough.** Some sites lazy-load fonts via JavaScript after networkidle. Add a `waitForTimeout(500)` after `networkidle` as insurance, and check for web font loading with `document.fonts.ready`.

**Pseudo-class injection for hover.** The cleanest way to force hover state for screenshots is to use Chrome DevTools Protocol: `client.send('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: ['hover'] })`. Playwright exposes this via `page.hover(selector)` but that requires knowing the selector in advance.

**oklch may not serialize cleanly.** Some older versions of culori's `formatOklch()` produce values with excessive decimal places. Round to 4 significant digits before writing to CSS.

**Iframes are a separate document.** Content inside `<iframe>` elements is not reachable via `querySelectorAll('*')` on the parent. You need a separate `page.frames()[n].evaluate()` call for each frame.

## Origin (reference only)

- Repo: https://github.com/JCodesMore/ai-website-cloner-template
- Key files: `.claude/skills/clone-website/SKILL.md`, `AGENTS.md`
- The extraction logic is described in the agent skill instructions; no source code ships (it's an LLM instruction set, not an npm package)
