# Page Format Pipeline — from [llm-scraper](https://github.com/mishushakov/llm-scraper)

> Domain: [[_domain]] · Source: https://github.com/mishushakov/llm-scraper · NotebookLM: <add link>

## What it does
Takes a live browser page and turns it into a single string (or image) in whichever representation you ask for. Six choices: the full raw HTML, the page converted to Markdown, just the readable article text, a cleaned-up HTML with noise stripped, a screenshot (as a base64 image), or a completely custom transform you supply. Whatever you pick is what the LLM downstream will actually read.

## Why it exists
An LLM extraction is only as good — and only as cheap — as the text you feed it. Raw web pages are enormous and mostly noise: analytics scripts, CSS, SVG icons, navigation chrome. Sending that wastes tokens and distracts the model. This pipeline is the **"choose your lens" step**: pick the representation that maximizes signal for your task. Scraping an article? Use readable text. Need layout/structure? Cleaned HTML. Site fights scrapers with obfuscated markup? Screenshot it and use a vision model. One knob, big leverage on cost and accuracy.

## How it actually works
A single `preprocess(page, options)` function branches on `options.format`:

- **`raw_html`** — just `page.content()`, the unmodified HTML. Escape hatch when you want everything.
- **`markdown`** — grabs the `<body>` inner HTML and runs it through **Turndown** (HTML→Markdown). Compact, keeps headings/lists/links, drops most attributes.
- **`text`** — runs **Mozilla Readability** *inside the page* (imported live from a CDN via `page.evaluate`) to extract the main article, then returns `"Page Title: <title>\n<textContent>"`. This is the "reader mode" extraction — strips everything but the article body.
- **`html`** (the default) — runs an in-browser **cleanup** scrub (its own feature, [[html-cleanup--from-llm-scraper]]) that deletes ~30 tag types and noise attributes, then returns the cleaned `page.content()`. Structure-preserving but far smaller than raw.
- **`image`** — takes a Playwright screenshot (optionally full-page) and returns it base64-encoded, for vision models.
- **`custom`** — you pass a `formatFunction(page)` and it returns whatever you produce. Throws if you select custom but forget the function.

Every branch returns the same shape: `{ url, content, format }`. Downstream code only has to know "format is image → send as image, else send as text."

## The non-obvious parts
- **Readability is imported from a CDN at runtime, inside the page's JS context** (`import('https://cdn.skypack.dev/@mozilla/readability')`). Clever (no bundling) but it means the `text` format silently needs network access to skypack and the page's CSP must allow it — a real-world failure mode that isn't obvious from the API.
- **`markdown` uses body innerHTML, but `html`/`raw_html` use full `page.content()`.** Subtle inconsistency: markdown drops `<head>`, the others don't (until cleanup removes it).
- **The format is a cost/fidelity tradeoff baked into one enum.** text < markdown < cleaned-html < raw-html in token count, roughly; image is its own axis (needs vision, survives HTML obfuscation).
- **`custom` is the extensibility seam.** Anything the four built-ins can't do — e.g. clicking through a modal, concatenating multiple frames — lives in a user function, keeping the core tiny.

## Related
- [[html-cleanup--from-llm-scraper]] — the scrub behind the default `html` format.
- [[schema-driven-extraction--from-llm-scraper]] / [[streaming-partial-objects--from-llm-scraper]] — the consumers; format choice flows straight into the message they send.
- See also: [[html-web-conversion--from-markitdown]] — server-side equivalent (BeautifulSoup + markdownify) for when there's no live browser.
