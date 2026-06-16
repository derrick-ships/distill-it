# HTML Cleanup — from [llm-scraper](https://github.com/mishushakov/llm-scraper)

> Domain: [[_domain]] · Source: https://github.com/mishushakov/llm-scraper · NotebookLM: <add link>

## What it does
Strips a web page down to its meaningful structure by deleting all the tags and attributes an LLM doesn't need — scripts, styles, media, forms, navigation chrome, and noisy attributes like inline styles, event handlers, and `data-`/`aria-` junk. What's left is lean HTML that still carries the document's structure and text, at a fraction of the token count.

## Why it exists
The default extraction format is cleaned HTML, and "cleaned" is what makes it affordable. A raw modern page is mostly machinery: analytics scripts, CSS, SVG icons, tracking attributes. Feeding that to a model burns tokens and dilutes attention. This scrub is the **token-diet step** — it's why you can send a real page to an LLM without blowing the context window, while keeping enough structure (headings, lists, tables, links) for accurate extraction.

## How it actually works
It's a function that runs *inside the browser page* (via Playwright's `evaluate`), so it has direct DOM access:

1. **Select every element** (`document.querySelectorAll('*')`).
2. **Drop unwanted tags.** For each element whose tag name is in a removal list, delete it from the DOM. The list is ~30 tags covering three buckets: executable/styling (`script`, `style`, `noscript`), media/embeds (`img`, `svg`, `video`, `audio`, `canvas`, `iframe`, `object`, `embed`, `source`, `track`, `map`), and interactive/chrome (`form`, `input`, `button`, `select`, `textarea`, `label`, `option`, `nav`, `header`, `footer`, `aside`, `dialog`, `menu`, `head`, …).
3. **Strip noisy attributes.** For every surviving element, remove any attribute whose name *starts with* one of: `style`, `src`, `alt`, `title`, `role`, `aria-`, `tabindex`, `on` (catches all `onclick`/`onload` handlers), `data-`. Prefix-matching is the trick — one entry `on` kills every event handler; `aria-`/`data-` kill whole attribute families.

After it runs, the caller reads `page.content()` and gets the slimmed HTML.

## The non-obvious parts
- **It mutates the live DOM, it doesn't copy.** Elements are actually removed from the page. If you reuse that page object afterward, it's permanently scrubbed — order of operations matters.
- **Prefix matching on attributes is the clever, slightly dangerous bit.** `startsWith('on')` removes `onclick` — but would also remove a hypothetical `onsale` attribute. `startsWith('title')` removes `title` but nothing else common. It's a pragmatic broad net, not a precise filter.
- **`<a>` tags and their `href` survive** — links are kept (href isn't in the strip list), which matters because extraction often wants URLs. But `src` is stripped, so `<img>` would lose its source even if the tag weren't already removed.
- **It's deliberately destructive and dumb.** No allowlist, no semantic preservation logic, no readability scoring. Just "delete this set, strip these attrs." Cheap, fast, runs in-page, good enough — and far simpler than Readability (which the `text` format uses instead when you want the *article* rather than the *structure*).

## Related
- [[page-format-pipeline--from-llm-scraper]] — the parent; cleanup is what the default `html` format runs.
- See also: [[html-web-conversion--from-markitdown]] — markitdown's server-side cleanup (BeautifulSoup removing script/style) solving the same noise problem off-browser.
