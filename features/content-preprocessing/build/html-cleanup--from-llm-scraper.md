# HTML Cleanup (build spec) — distilled from llm-scraper

## Summary
An in-browser DOM scrub: remove ~30 noise/media/chrome tag types entirely, and strip any attribute whose name prefix-matches a noise list (style/src/alt/title/role/aria-/tabindex/on/data-). Runs via `page.evaluate(cleanup)`. Produces lean, structure-preserving HTML for cheap LLM input.

## Core logic (inlined)

```javascript
export default function cleanup() {
  const elementsToRemove = [
    'script', 'style', 'noscript', 'iframe', 'svg', 'img', 'audio', 'video',
    'canvas', 'map', 'source', 'dialog', 'menu', 'menuitem', 'track', 'object',
    'embed', 'form', 'input', 'button', 'select', 'textarea', 'label', 'option',
    'optgroup', 'aside', 'footer', 'header', 'nav', 'head',
  ]

  const attributesToRemove = [
    'style', 'src', 'alt', 'title', 'role', 'aria-', 'tabindex', 'on', 'data-',
  ]

  const elementTree = document.querySelectorAll('*')

  elementTree.forEach((element) => {
    if (elementsToRemove.includes(element.tagName.toLowerCase())) {
      element.remove()
    }
    Array.from(element.attributes).forEach((attr) => {
      if (attributesToRemove.some((a) => attr.name.startsWith(a))) {
        element.removeAttribute(attr.name)
      }
    })
  })
}
```

Invoked from preprocess as: `await page.evaluate(cleanup)` then `content = await page.content()`.

## Data contracts
- No inputs/outputs in the function-signature sense — it's a side-effecting DOM mutation executed in the page context. The "contract" is the two lists above. Result is observed by reading `page.content()` after.

## Dependencies & assumptions
- Runs in a **browser DOM context** (`document`, `element.remove()`, `element.attributes`, `removeAttribute`). Must be passed to `page.evaluate` (Playwright/Puppeteer) — it cannot run in Node directly.
- No external libs. Pure DOM API. Trivially portable to any headless-browser stack.

## To port this, you need:
- [ ] A way to execute JS in the page's DOM context (`evaluate`).
- [ ] To run it *before* reading the page's HTML.
- [ ] (Optional) Tune the two lists for your domain — e.g. keep `<form>` if you extract form fields, or add `<picture>`.

## Gotchas
- **Destructive on the live DOM** — the page is permanently altered. Don't run it then expect to interact with removed elements (forms/buttons are gone). Preprocess as the final step.
- **Attribute removal is prefix-matched**, so `on` nukes every `on*` handler (intended) but also any attribute literally starting "on"; `title` removes `title` only. Broad and fast, occasionally over-eager — acceptable for LLM-input prep, not for faithful DOM preservation.
- **`href` is intentionally NOT stripped** — links survive, which extraction usually wants. If you also want to drop tracking URLs, add `href` to the list (but you'll lose link targets).
- **Removes `<head>`** — all page metadata (meta tags, canonical, JSON-LD) is discarded. If you need structured metadata, capture it before cleanup.
- **No allowlist / no nesting awareness** — removing a parent removes its kept children too (a `<p>` inside a removed `<form>` is gone). Usually fine, occasionally surprising.

## Origin (reference only)
`mishushakov/llm-scraper` — `src/cleanup.ts` (default-exported `cleanup`).
