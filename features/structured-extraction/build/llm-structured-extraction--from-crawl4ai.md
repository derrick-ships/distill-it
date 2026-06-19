# LLM-Based Structured Extraction (build spec) — distilled from crawl4ai

## Summary

`LLMExtractionStrategy` sends page content (markdown or HTML) to any LLM in chunks and parses typed structured data matching a Pydantic schema. Plugs into `CrawlerRunConfig.extraction_strategy`. Returns extracted data as a JSON string in `CrawlResult.extracted_content`.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel
from typing import List

# Define your target schema
class ProductSchema(BaseModel):
    name: str
    price: float
    description: str
    in_stock: bool
    rating: float | None = None

# Configure the strategy
strategy = LLMExtractionStrategy(
    llm_config=LLMConfig(
        provider="anthropic/claude-haiku-4-5-20251001",
        api_token="sk-ant-...",
        # Optional:
        base_url=None,           # custom API endpoint
        extra_args={},           # passed to litellm
    ),
    schema=ProductSchema,        # Pydantic model → JSON schema constraint
    extraction_type="schema",    # "schema" | "block"
    instruction="Extract all products listed on this page.",
    input_format="fit_markdown", # "markdown" | "html" | "fit_markdown"
    chunk_token_threshold=4096,
    overlap_rate=0.1,            # 10% overlap between chunks
    word_token_rate=0.25,        # 1 word ≈ 0.25 tokens (English estimate)
    verbose=True,
)

config = CrawlerRunConfig(
    extraction_strategy=strategy,
    content_filter=PruningContentFilter(threshold=0.48),
    markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter(threshold=0.48)),
)

async with AsyncWebCrawler(config=BrowserConfig()) as crawler:
    result = await crawler.arun("https://shop.example.com/products", config=config)
    if result.success:
        products = json.loads(result.extracted_content)
        # products is a List[dict] matching ProductSchema
        for p in products:
            print(p["name"], p["price"])
    strategy.show_usage()  # print token cost report
```

**Internal chunking flow:**
```python
def run(self, url, sections):
    # sections = list of content blocks from the scraping strategy
    merged = self._merge(
        sections,
        threshold=self.chunk_token_threshold,
        overlap=int(self.chunk_token_threshold * self.overlap_rate),
    )
    # Each merged chunk is sent to the LLM with schema-aware prompt
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(self.extract, url, i, chunk) for i, chunk in enumerate(merged)]
        for f in futures:
            results.extend(f.result())
    return results

def extract(self, url, index, html_chunk):
    prompt = build_prompt(html_chunk, self.schema_json, self.instruction)
    response = litellm.completion(
        model=self.llm_config.provider,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
        api_key=self.llm_config.api_token,
    )
    text = response.choices[0].message.content
    # Parse XML-wrapped blocks:
    blocks = re.findall(r"<block>(.*?)</block>", text, re.DOTALL)
    parsed = []
    for block in blocks:
        try:
            parsed.append(json.loads(block.strip()))
        except json.JSONDecodeError:
            pass  # silent skip malformed blocks
    return parsed
```

**Schema generation (when you don't have a schema yet):**
```python
schema = await LLMExtractionStrategy.agenerate_schema(
    html="<html>...</html>",  # or urls=["https://..."]
    query="product listings with price and name",
    llm_config=LLMConfig(provider="openai/gpt-4o", api_token="sk-..."),
    validate=True,            # test schema against HTML and refine
    max_refinements=3,
)
# schema is a dict: {"baseSelector": "...", "fields": [...]}
```

## Data contracts

**LLMConfig:**
```python
LLMConfig(
    provider: str,         # LiteLLM model string: "openai/gpt-4o", "anthropic/claude-haiku-4-5-20251001", "ollama/llama3"
    api_token: str = None, # API key; auto-reads from env if None
    base_url: str = None,  # custom endpoint (Ollama, Azure, etc.)
    extra_args: dict = {},  # additional litellm kwargs (temperature, max_tokens, etc.)
)
```

**`result.extracted_content` shape:**
```python
# Always a JSON string; parse with json.loads()
# Schema mode: list of objects matching the schema
[{"name": "Widget A", "price": 29.99, "in_stock": True, ...}, ...]

# Block mode: list of text blocks
[{"index": 0, "content": "...", "tags": [], "error": False}, ...]
```

**Token usage (from strategy after run):**
```python
strategy.usage  # TokenUsage object
strategy.usage.total_tokens      # int
strategy.usage.prompt_tokens     # int
strategy.usage.completion_tokens # int
strategy.show_usage()            # prints per-chunk breakdown
```

## Dependencies & assumptions

- `unclecode-litellm` (LiteLLM fork bundled with crawl4ai)
- `pydantic` ≥ 2.0
- API key for your chosen provider
- Content should be in `fit_markdown` or filtered `markdown` for best token efficiency

## To port this, you need:
- [ ] Define a Pydantic `BaseModel` matching your target data shape
- [ ] Choose a provider and get an API key
- [ ] Set `extraction_type="schema"` and pass your Pydantic model as `schema=`
- [ ] Set `input_format="fit_markdown"` and configure a `ContentFilterStrategy` to reduce tokens
- [ ] Parse `result.extracted_content` with `json.loads()`
- [ ] Call `strategy.show_usage()` after runs to track API costs
- [ ] For Groq: chunks are sent sequentially (built-in); no special configuration needed

## Gotchas

**Empty `extracted_content` is usually a prompt/format issue.** The LLM must respond with `<block>JSON</block>` tags. If it responds with raw JSON or markdown fences, extraction returns an empty list. Test with `verbose=True` to see raw LLM output.

**Overlap creates duplicate records.** If the same product appears near a chunk boundary, it may be extracted twice. Add a deduplication step using a unique key field (e.g., product ID or name+price).

**Large pages blow token budgets fast.** A 50KB HTML page is ~12,500 tokens of markdown. At 4096 tokens/chunk with 10% overlap, that's 3-4 LLM calls at full prompt size. Filter aggressively with `PruningContentFilter` before extraction.

**Schema validation doesn't happen at runtime.** If the LLM returns a field with the wrong type, `json.loads()` will still succeed — you'll get a string where you expected a float. Validate the parsed result against your Pydantic model explicitly: `ProductSchema(**item)` raises if types don't match.

**`agenerate_schema` requires good example HTML.** Pass the actual target page HTML, not a simplified version. The LLM infers the schema from the real element structure.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key file: `crawl4ai/extraction_strategy.py` (class `LLMExtractionStrategy`)
