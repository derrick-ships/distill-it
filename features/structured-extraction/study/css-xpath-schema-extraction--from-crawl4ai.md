# CSS/XPath/Lxml Schema Extraction — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

`JsonCssExtractionStrategy` and `JsonLxmlExtractionStrategy` extract structured data from web pages using declarative CSS selectors or XPath expressions — no LLM required. You define a schema that describes which elements to select and which fields to pull from each, and the extractor returns a list of typed dictionaries. Think of it as a structured "form fill" driven by CSS or XPath rules.

## Why it exists

For pages with consistent, predictable HTML structures (e-commerce product listings, news articles, job boards, sports stats), rule-based extraction is faster, cheaper, and more reliable than LLM-based approaches. A well-written CSS schema runs in milliseconds; the same extraction via LLM takes seconds and costs money. Rule-based extraction is the first choice; LLM is the fallback for irregular structures.

## How it actually works

**Schema design:** The schema is a dictionary with three key parts. `baseSelector` identifies the repeating container element (e.g., `"div.product-card"` for a product listing). `fields` is a list of field definitions, each with a `name`, a `selector` (relative to the base element), and a `type` that tells the extractor what to extract:

- `"text"` — the element's text content (normalized whitespace)
- `"attribute"` — an HTML attribute value (e.g., `href`, `src`, `data-price`)
- `"html"` — the raw inner HTML
- `"regex"` — apply a regex pattern to the text and return the match
- `"nested"` — extract a sub-object (recursive schema)
- `"nested_list"` — extract a list of sub-objects
- `"list"` — extract a list of text/attribute values from multiple matching elements
- `"computed"` — call a user-provided Python function with the element

**Extraction flow:** The base elements are selected first using `baseSelector`. For each base element, every field is extracted by running `selector` against that element and applying the `type` transform. The result is a list of dicts — one per base element.

**Two implementations:**
- `JsonCssExtractionStrategy` uses **BeautifulSoup4** with the lxml parser. More Pythonic API, easier to debug, slightly slower for large pages.
- `JsonLxmlExtractionStrategy` uses **lxml** directly with multiple fallback strategies for selector matching: direct CSS compilation → XPath conversion → nth-child specialization → class/ID fallback → tag name search. This aggressive fallback is what makes it robust to unusual selectors and is 3-5x faster on large pages.

**lxml's selector caching:** `JsonLxmlExtractionStrategy` caches compiled CSS selectors and their XPath translations. The first use of a selector pays the compilation cost; subsequent uses are lookups into a `dict`. For batch crawling the same page structure, this yields significant speedups.

**Source navigation with `+` syntax:** A field can have `"source": "+ td:nth-child(2)"` which traverses to a sibling element relative to the selected node. This handles cases like definition lists or adjacent-cell table patterns where key and value are in sibling elements rather than parent-child.

## The non-obvious parts

**`baseSelector` scoping is relative.** When you write a `selector` inside `fields`, it's evaluated relative to each base element — not the full document. `"h2.title"` finds the h2 with class "title" inside the current product card, not all h2s on the page.

**`"computed"` type is for custom logic, not eval.** The function is a Python callable you pass at schema construction time — not an eval'd string. This is safe and allows arbitrary Python logic, including formatting, unit conversions, or data lookups.

**lxml's fallback strategies can produce unexpected results.** When a CSS selector fails, the strategy tries XPath conversion, then increasingly broad fallbacks. On unusual selectors, you might get more matches than expected. Test schemas against real page HTML before deploying.

**`"transform"` modifies extracted text.** Each field can have `"transform": "lowercase"`, `"uppercase"`, or `"strip"` applied after extraction. Useful for normalizing prices, status strings, or names.

**Automatic schema generation.** `LLMExtractionStrategy.agenerate_schema()` can generate a JsonCSS-compatible schema from example HTML. The generated schema dict can be used directly with `JsonCssExtractionStrategy` — bridging LLM intelligence at schema-generation time with deterministic execution at extraction time.

## Related
- [[llm-structured-extraction--from-crawl4ai]] (the fallback when CSS rules can't express the extraction)
- [[schema-driven-extraction--from-llm-scraper]] (similar concept but Zod schema + AI SDK instead of Python/Pydantic)
- [[async-web-crawler--from-crawl4ai]] (this strategy plugs into the crawler via CrawlerRunConfig)
