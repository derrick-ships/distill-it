# Page Format Pipeline (build spec) — distilled from llm-scraper

## Summary
A single `preprocess(page, options)` that converts a live Playwright page into `{ url, content, format }`, branching on a `format` enum: `raw_html | markdown | text | html | image | custom`. Each format trades token cost against fidelity. This is the upstream step every extraction/codegen call runs first.

## Core logic (inlined)

```typescript
import { type Page } from 'playwright'
import Turndown from 'turndown'
import cleanup from './cleanup.js'   // see html-cleanup build spec

export type PreProcessOptions =
  | { format?: 'html' | 'text' | 'markdown' | 'raw_html' }
  | { format: 'custom'; formatFunction: (page: Page) => Promise<string> | string }
  | { format: 'image'; fullPage?: boolean }

export type PreProcessResult = { url: string; content: string; format: PreProcessOptions['format'] }

export async function preprocess(
  page: Page, options: PreProcessOptions = { format: 'html' }
): Promise<PreProcessResult> {
  const url = page.url()
  const format = options.format ?? 'html'
  let content

  if (format === 'raw_html') {
    content = await page.content()
  }

  if (format === 'markdown') {
    const body = await page.innerHTML('body')
    content = new Turndown().turndown(body)
  }

  if (format === 'text') {
    const readable = await page.evaluate(async () => {
      const readability = await import(
        // @ts-ignore
        'https://cdn.skypack.dev/@mozilla/readability'
      )
      return new readability.Readability(document).parse()
    })
    content = `Page Title: ${readable.title}\n${readable.textContent}`
  }

  if (format === 'html') {
    await page.evaluate(cleanup)      // mutates the live DOM in-browser
    content = await page.content()
  }

  if (format === 'image') {
    const image = await page.screenshot({
      fullPage: 'fullPage' in options ? options.fullPage : undefined,
    })
    content = image.toString('base64')
  }

  if (format === 'custom') {
    if (!('formatFunction' in options) || typeof options.formatFunction !== 'function') {
      throw new Error('customPreprocessor must be provided in custom mode')
    }
    content = await options.formatFunction(page)
  }

  return { url, content, format }
}
```

## Data contracts
- **Input**: Playwright `Page` (already navigated) + `PreProcessOptions` (default `{ format: 'html' }`).
- **Output**: `{ url: string, content: string, format }`. For `image`, `content` is raw base64 (no `data:` prefix). For all others it's a text string.
- Downstream consumer keys on `format === 'image'` to decide image-vs-text message part.

## Dependencies & assumptions
- `playwright` — `page.content()`, `page.innerHTML('body')`, `page.evaluate()`, `page.screenshot()`.
- `turndown` — HTML→Markdown for the `markdown` format.
- `@mozilla/readability` — **loaded at runtime from `https://cdn.skypack.dev`** inside the page context for `text` format. Requires page network access + permissive CSP. Swap for a bundled import to remove the network dependency.
- `cleanup` — the in-browser scrub function (see [[html-cleanup--from-llm-scraper]]); runs via `page.evaluate`.

## To port this, you need:
- [ ] A browser handle exposing: full HTML, body innerHTML, arbitrary in-page JS eval, and screenshots.
- [ ] An HTML→Markdown lib (Turndown or equivalent) if you want `markdown`.
- [ ] Readability (bundled or CDN) if you want `text`; otherwise drop that branch.
- [ ] The `cleanup` function ported for the default `html` format.
- [ ] A decision on default format (here: `html`).

## Gotchas
- **`text` format silently depends on the network + CDN (skypack) + page CSP.** On a CSP-locked page or offline, the dynamic import throws inside `evaluate`. Bundle Readability to harden.
- **`html` format mutates the live DOM** (cleanup runs `element.remove()` in the page). If you reuse the page afterward, it's already been scrubbed — preprocess last, or clone.
- **`markdown` only takes `<body>`**, dropping head metadata; `raw_html` keeps everything. Pick deliberately.
- **No format validation beyond `custom`** — an unknown format string leaves `content` undefined and returns it. Guard if accepting external format values.
- **Screenshot `fullPage` defaults to `undefined`** (Playwright treats as viewport-only). Pass `fullPage: true` for long pages.

## Origin (reference only)
`mishushakov/llm-scraper` — `src/preprocess.ts` (`preprocess`, `PreProcessOptions`, `PreProcessResult`).
