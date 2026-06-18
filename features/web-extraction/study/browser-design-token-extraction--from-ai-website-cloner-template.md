# Browser Design Token Extraction — from [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)

> Domain: [[_domain]] · Source: https://github.com/JCodesMore/ai-website-cloner-template · NotebookLM:

## What it does

This technique uses the browser's own rendering engine to extract the *computed* visual design of any webpage — colors, typography, spacing, borders, shadows — by reading the final resolved styles from every element using `getComputedStyle()`. The output is a structured set of design tokens: the raw material that AI builders use to recreate the site with pixel accuracy in Tailwind CSS v4's oklch color space.

## Why it exists

Reading a website's CSS source files is unreliable. Modern sites use CSS-in-JS, utility frameworks with dynamic class generation, CDN-hosted stylesheets you can't easily parse, or preprocessors that obscure the actual values. The browser, however, always knows the final answer: after parsing, cascading, inheriting, and resolving all custom properties, `getComputedStyle(element)` returns exactly what the browser rendered. This technique skips source-file parsing entirely and goes straight to the ground truth.

## How it actually works

The agent opens a headless Chromium browser and navigates to the target URL. Once the page fully loads (after JavaScript executes, fonts load, lazy images resolve), it injects a `page.evaluate()` call that runs inside the browser's JavaScript context.

Inside that context, it queries every DOM element with `querySelectorAll('*')`, and for each element reads a predefined list of computed style properties: color, background-color, font-family, font-size, font-weight, line-height, letter-spacing, padding, margin, border-radius, display, flex-direction, gap, box-shadow, and more. These values are already resolved — `var(--color-brand)` becomes `oklch(0.65 0.18 270)`, `1.5rem` becomes `24px`, `inherit` is replaced by the actual inherited value.

The collected values are deduplicated and bucketed: frequently-occurring colors become the brand palette, the most-used font families become the typography tokens, and common spacing values suggest the spacing scale. The agent serializes all this into a structured token document saved to `docs/research/`.

**Interaction states** are captured via a second round of screenshots: the agent programmatically simulates hover (via `:hover` pseudo-class injection or `mouseover` events), focus (`element.focus()`), and active (`mousedown` events) states and takes screenshots at each. The visual diff between normal and interaction screenshots tells the AI builder exactly what changes (color shift, scale transform, shadow appearance) without needing to parse CSS transition rules.

**Responsive behavior** is captured by resizing the viewport to mobile (375px), tablet (768px), and desktop (1440px) widths and re-running `getComputedStyle()` at each size. This surfaces layout reflows (flex to block), font size changes, and hidden/shown elements.

The extracted colors are converted to oklch format (a perceptually uniform color space that Tailwind v4 uses natively) using a color conversion library. This enables the generated Tailwind config to produce accurate, harmonious color palettes.

## The non-obvious parts

**`getComputedStyle()` resolves everything.** Custom properties, calc() expressions, clamp(), env() values — all resolved to their final concrete form. This is the most reliable source of visual truth available without access to source code.

**You need to wait for full render.** If you extract too early, you get default styles before custom fonts load (causing font-family fallbacks) or before JS-driven class additions. The agent waits for `networkidle` and a short delay before extracting.

**Deduplication reveals the design system.** Raw extraction produces thousands of records. The design tokens that matter are the ones used consistently. Counting occurrences of each color, font, and spacing value and taking the top N reveals the actual design system the site uses, even if it was never documented.

**oklch conversion.** Most browsers return colors as `rgb(r, g, b)` or `rgba(r, g, b, a)`. Converting these to oklch for Tailwind v4 requires a color math library (culori is the standard choice). The oklch values are more perceptually accurate and allow Tailwind to generate proper color scale utilities.

**Interaction state capture via pseudo-class injection.** You can't hover over an element programmatically with a pointer event alone in many cases. A reliable technique is to inject a `<style>` tag that forces `:hover` CSS to apply, take the screenshot, then remove the style tag.

## Related

- [[website-cloning-pipeline--from-ai-website-cloner-template]] — this is Phase 1 of the cloning pipeline
- [[component-spec-generation--from-ai-website-cloner-template]] — the extracted tokens feed the component specs
- [[html-web-conversion--from-markitdown]] — the text-content counterpart: extracting readable content from HTML
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — AI-driven extraction of structured data (different goal: data, not design)
- [[scrape-engine-fallback-pipeline--from-firecrawl]] — robustness patterns for headless browser scraping
