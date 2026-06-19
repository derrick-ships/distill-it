# CSS/XPath/Lxml Schema Extraction (build spec) — distilled from crawl4ai

## Summary

Two deterministic extraction strategies (`JsonCssExtractionStrategy` / `JsonLxmlExtractionStrategy`) that map a JSON schema (CSS selectors + field types) to a list of typed dicts extracted from HTML. No LLM required. Plugs into `CrawlerRunConfig.extraction_strategy`.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, JsonLxmlExtractionStrategy
import json

# Define schema
schema = {
    "name": "Products",
    "baseSelector": "div.product-card",   # repeated container
    "baseFields": [                         # fields evaluated at base element level
        {"name": "data_id", "type": "attribute", "attribute": "data-product-id"}
    ],
    "fields": [
        {"name": "title", "selector": "h2.product-title", "type": "text"},
        {"name": "price", "selector": "span.price", "type": "text",
         "transform": "strip"},
        {"name": "url", "selector": "a.product-link", "type": "attribute",
         "attribute": "href"},
        {"name": "image", "selector": "img.product-image", "type": "attribute",
         "attribute": "src"},
        {"name": "in_stock", "selector": "span.stock-status", "type": "text"},
        {"name": "rating", "selector": "div.stars", "type": "attribute",
         "attribute": "data-rating"},
        {"name": "tags", "selector": "span.tag", "type": "list"},  # multiple elements
        {"name": "description", "selector": "div.desc", "type": "html"},
        # Nested example:
        {"name": "seller", "selector": "div.seller-info", "type": "nested",
         "fields": [
             {"name": "name", "selector": "span.seller-name", "type": "text"},
             {"name": "rating", "selector": "span.seller-rating", "type": "text"},
         ]},
        # Sibling navigation:
        {"name": "sku", "selector": "td.label:contains('SKU')",
         "type": "text", "source": "+ td"},
        # Computed field:
        {"name": "price_float", "selector": "span.price", "type": "computed",
         "fn": lambda el: float(el.get_text().strip().replace("$", ""))},
    ]
}

# Choose implementation:
strategy = JsonLxmlExtractionStrategy(schema, verbose=True)   # faster, more robust
# OR:
strategy = JsonCssExtractionStrategy(schema, verbose=True)    # BeautifulSoup4, easier debug

config = CrawlerRunConfig(extraction_strategy=strategy)

async with AsyncWebCrawler(config=BrowserConfig()) as crawler:
    result = await crawler.arun("https://shop.example.com/products", config=config)
    if result.success:
        products = json.loads(result.extracted_content)
        # products: List[dict] — one per matched baseSelector element
        for p in products:
            print(p.get("title"), p.get("price"))
```

**Core extraction pseudocode (JsonLxmlExtractionStrategy):**
```python
def extract(self, url, html_content):
    tree = lxml.html.fromstring(html_content)
    # Select base elements using multi-strategy fallback
    base_elements = self._get_base_elements(tree, self.schema["baseSelector"])
    results = []
    for element in base_elements:
        item = {}
        # Extract baseFields first (evaluated at base element)
        for field in self.schema.get("baseFields", []):
            item[field["name"]] = self._extract_field(element, field)
        # Then regular fields
        for field in self.schema["fields"]:
            item[field["name"]] = self._extract_field(element, field)
        results.append(item)
    return results

def _get_elements(self, element, selector):
    # Multi-strategy CSS→XPath with caching:
    if selector in self._selector_cache:
        return self._selector_cache[selector](element)
    try:
        fn = CSSSelector(selector)  # try direct lxml CSS selector
    except:
        try:
            xpath = css_to_xpath(selector)  # convert to XPath
            fn = lambda el: el.xpath(xpath)
        except:
            fn = fallback_search(selector)  # tag/class/ID fallback
    self._selector_cache[selector] = fn
    return fn(element)
```

## Data contracts

**Field definition schema:**
```python
{
    "name": str,                    # output dict key
    "selector": str,                # CSS selector (relative to base element)
    "type": "text" | "attribute" | "html" | "regex" | "nested" |
             "nested_list" | "list" | "computed",
    "attribute": str,               # required for type="attribute"
    "pattern": str,                 # required for type="regex" (Python re pattern)
    "transform": "lowercase" | "uppercase" | "strip",  # optional post-processing
    "default": Any,                 # returned when selector finds nothing
    "source": "+selector",          # navigate to sibling before extracting
    "fn": Callable[[Element], Any], # required for type="computed"
    # For nested/nested_list:
    "fields": [...]                 # recursive field definitions
}
```

**Output shape:**
```python
# result.extracted_content is a JSON string
# After json.loads():
[
    {"title": "Widget A", "price": "$29.99", "url": "/products/widget-a", ...},
    {"title": "Widget B", "price": "$49.99", "url": "/products/widget-b", ...},
]
```

**Strategy constructor:**
```python
JsonCssExtractionStrategy(
    schema: dict,           # the schema dict described above
    verbose: bool = False,
    input_format: str = "html",  # "html" | "markdown" (html is correct for CSS extraction)
)

JsonLxmlExtractionStrategy(
    schema: dict,
    verbose: bool = False,
    input_format: str = "html",
    use_cache: bool = True,  # enable selector result caching
)
```

## Dependencies & assumptions

- `beautifulsoup4` + `lxml` — for `JsonCssExtractionStrategy`
- `lxml` + `cssselect` — for `JsonLxmlExtractionStrategy`
- Both are core crawl4ai dependencies (no extras needed)
- `input_format` must be `"html"` — CSS selectors don't work on markdown

## To port this, you need:
- [ ] Inspect the target page's HTML structure (browser DevTools) to identify `baseSelector`
- [ ] Map each data field to its CSS selector and type
- [ ] Use `JsonLxmlExtractionStrategy` for production (faster, better fallback)
- [ ] Set `input_format="html"` (default for these strategies — don't change)
- [ ] Parse `result.extracted_content` with `json.loads()`
- [ ] Validate at least one result manually before large-scale crawling
- [ ] For page structure changes: update the schema dict — no code changes needed

## Gotchas

**`baseSelector` must match the repetition unit, not the container.** On a page with `<div class="grid">` containing many `<div class="item">`, the `baseSelector` is `div.item`, not `div.grid`.

**Selectors are relative, not absolute.** `"h2.title"` inside a field means "find h2.title inside the current base element" — not globally. This is the most common confusion when porting selectors from browser DevTools (where selectors are document-scoped).

**`"list"` type returns a list of text from ALL matching elements.** If `selector: "span.tag"` matches 3 spans inside a product card, `type: "list"` gives `["Tag A", "Tag B", "Tag C"]`. Use this for multi-value fields.

**lxml's `nth-child` handling is specialized.** The strategy has explicit handling for `td:nth-child(N)` patterns because CSS `nth-child` in lxml's XPath translation is fragile. If table cell extraction breaks, try `tr > td:nth-child(2)` or the `"source"` sibling navigation instead.

**Empty selections return `default` value or `None`.** If a selector matches nothing, the field is set to `default` (if specified) or `None`. Always handle `None` in downstream code.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key file: `crawl4ai/extraction_strategy.py` (classes `JsonCssExtractionStrategy`, `JsonLxmlExtractionStrategy`, `JsonElementExtractionStrategy`)
