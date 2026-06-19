# Indexed DOM Serialization — from [browser-use](https://github.com/browser-use/browser-use)

> Domain: [[_domain]] · Source: https://github.com/browser-use/browser-use · NotebookLM: <link once added>

## What it does

This is the "eyes" of a browser agent. Before an LLM can decide to *click the login button* or *type into the search box*, it needs a description of the page it can actually reason about — raw HTML is far too noisy and far too big. Indexed DOM serialization walks the live page, finds every element a human could interact with (buttons, links, inputs, dropdowns…), throws away everything that's just layout or decoration, and hands the model a compact numbered list:

```
[1]<button>Sign in />
*[2]<input type="text" placeholder="Search" />
[3]<a>Pricing />
```

Each element gets an index. The model replies "click element 2," and the system knows exactly which real DOM node that maps back to. The asterisk (`*`) flags elements that are *new* since the last screenshot, so the model can notice "a modal just appeared" without diffing two giant page dumps itself.

## Why it exists

An LLM driving a browser has two hard problems: the page is enormous (tens of thousands of nodes), and the model can't hold a CSS selector or an XPath reliably across turns. The indexed list solves both. It shrinks the page to only the actionable parts, and it replaces fragile selectors with stable integer handles the model is good at repeating. This is the perception layer that makes the whole agent loop possible — the quality of everything downstream (does it click the right thing?) is capped by how good this serialization is.

## How it actually works

Every step, browser-use captures the page through the **Chrome DevTools Protocol (CDP)** — it talks to Chrome directly, not through Playwright's high-level API. It fires four CDP calls *in parallel*:

1. **A layout snapshot** (`DOMSnapshot.captureSnapshot`) — every element's on-screen rectangle, plus exactly ten computed CSS properties (display, visibility, opacity, cursor, position, background-color, and a few overflow/pointer ones). Only ten — deliberately — because asking Chrome for more crashes it on heavy pages.
2. **The full DOM tree** (`DOM.getDocument`, pierced so it includes shadow roots and iframes).
3. **The accessibility tree** (per frame) — gives each node its ARIA role and accessible name.
4. **The device pixel ratio** — to convert between CSS pixels and physical pixels.

Alongside those, it runs a small piece of JavaScript that asks Chrome (via the DevTools-only `getEventListeners()` API) which elements actually have click/mousedown/pointer handlers attached — catching the `<div onclick>` "fake buttons" that plague modern web apps. (This step is skipped on pages over 10,000 elements for speed.)

All of that gets merged, node by node, into one rich data structure (`EnhancedDOMTreeNode`) that knows each element's tag, attributes, ARIA role, exact position, visibility, and whether it has a real click handler. Then comes the **serializer**, which does the actual thinning:

- **Drops the junk** — `script`, `style`, `head`, `meta`, etc., and collapses SVG icon guts into a single marker.
- **Decides what's interactive** — a layered test: does it have a JS click listener? Is it a `<button>/<input>/<a>/<select>`? Does it have an interactive ARIA role? An `onclick` attribute? A `cursor: pointer` style? Any "yes" makes it clickable.
- **Decides what's visible** — checks display/visibility/opacity *and* whether the element falls within the viewport plus a 1000px buffer above and below (so near-the-fold, lazy-loaded content is included before the user scrolls to it).
- **Removes things hidden behind other things** — a "paint order" pass: it walks elements front-to-back and discards ones fully covered by something painted on top (e.g. a button hidden under a modal overlay).
- **De-duplicates nested noise** — if a `<button>` contains five nested `<span>`s, those children get folded into the button rather than listed separately.
- **Synthesizes controls** — for a `<select>` or a file input or a number stepper, it manufactures the sub-parts the model needs ("dropdown toggle," "increment button," "N files selected").

What survives gets numbered and rendered to the text string above, with only a curated set of ~50 useful attributes kept (type, name, placeholder, aria-label, checked, validation hints) and passwords explicitly redacted. The number→element map (`selector_map`) is cached on the session. When the model says "click 2," a lookup retrieves the real node, its coordinates are computed, and the click is dispatched as a real CDP mouse event (with a JS `element.click()` fallback).

## The non-obvious parts

- **The index numbers aren't 1, 2, 3.** They look sequential in examples, but under the hood the index the model is given is Chrome's internal **`backendNodeId`** — a large, non-contiguous integer that's stable across some operations where the ordinary `nodeId` resets. The selector map is keyed by it. This is the single most surprising design choice and the thing a re-implementer would get wrong first.
- **Four parallel CDP calls with a 10-second timeout, all-or-nothing.** If any of the four fails, the whole observation raises — a real reliability pressure point on slow pages.
- **Shadow DOM is *always* included**, even when it looks empty, because single-page apps (React/Vue web components) hide all their real interactive content inside shadow roots.
- **The 1000px visibility buffer means the model "sees" things the human currently can't** — content just below the fold. Intentional, but it means the agent's view and a screenshot don't perfectly agree.
- **iframe coordinate math is genuinely hard.** The code accumulates a running frame offset (subtracting scroll for each HTML frame, adding position for each iframe element) so that every element's coordinates end up in the top-level page's space. Get this wrong and the agent mis-clicks inside nested frames.
- **The `*` new-element marker is a cheap, powerful trick.** Instead of asking the model to compare two full page states, the system diffs the backendNodeIds against the previous step and prefixes anything new with an asterisk — directing the model's attention to what changed.

## Related
- [[agent-loop-recovery--from-browser-use]] — this serialization is the "observe" half of that loop; its output goes straight into the prompt each step.
- [[action-tool-registry--from-browser-use]] — actions like `click_element(index=…)` consume the indices this layer assigns.
- [[browser-session-stealth--from-browser-use]] — owns the CDP connection and the watchdog that triggers this capture.
- See also: [[browser-design-token-extraction--from-ai-website-cloner-template]] and [[agentic-browser-actions--from-firecrawl]] — other "read the live page through a real browser" approaches, but for cloning/extraction rather than agent perception.
