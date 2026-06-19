# Content Filtering Strategies (build spec) — distilled from crawl4ai

## Summary

Three swappable content filter classes (Pruning, BM25, LLM) that take raw HTML and return noise-stripped `fit_markdown`. Plug one into `CrawlerRunConfig.content_filter` and it runs automatically inside `aprocess_html()`.

## Core logic (inlined)

### PruningContentFilter

```python
from crawl4ai import PruningContentFilter, DefaultMarkdownGenerator

filter = PruningContentFilter(
    threshold=0.48,           # 0.0-1.0; higher = more aggressive pruning
    threshold_type="fixed",   # "fixed" | "dynamic"
    min_word_threshold=0,     # optional: skip blocks with < N words
)

# Used via CrawlerRunConfig:
config = CrawlerRunConfig(
    content_filter=filter,
    markdown_generator=DefaultMarkdownGenerator(content_filter=filter)
)

# Pruning algorithm (simplified):
def _score_node(node) -> float:
    text = node.get_text()
    text_density = len(text.split()) / max(len(text), 1)
    link_density = len(node.find_all("a")) / max(len(text.split()), 1)
    tag_weight = TAG_WEIGHTS.get(node.name, 0.5)  # article=1.0, nav=0.1, div=0.5
    class_weight = -0.3 if NOISE_PATTERN.search(node.get("class", "")) else 0.1
    text_length = min(len(text), 1000) / 1000

    score = (0.4 * text_density + 0.2 * (1 - link_density) + 0.2 * tag_weight
             + 0.1 * class_weight + 0.1 * text_length)
    return score
```

### BM25ContentFilter

```python
from crawl4ai import BM25ContentFilter

filter = BM25ContentFilter(
    user_query=None,          # auto-extracted from page if None
    bm25_threshold=1.0,       # minimum BM25 score; lower = keep more
    language="english",       # for stemming
    use_stemming=True,
)

# BM25 scoring:
# 1. Extract query from page (title + h1 + meta_description + first_paragraph)
# 2. Segment body into chunks (one per block-level element)
# 3. Tokenize + stem + remove stop words
# 4. Score each chunk vs query with Okapi BM25:
#    score(d,q) = Σ IDF(qi) * (f(qi,d)*(k1+1)) / (f(qi,d) + k1*(1-b+b*|d|/avgdl))
#    k1=1.5, b=0.75 (typical defaults)
# 5. Multiply by tag weights: h1=5.0, h2=4.0, h3=3.0, strong=2.0, p=1.0
# 6. Keep chunks with adjusted_score > bm25_threshold
# 7. Re-sort by original document position
```

### LLMContentFilter

```python
from crawl4ai import LLMContentFilter, LLMConfig

filter = LLMContentFilter(
    llm_config=LLMConfig(
        provider="anthropic/claude-haiku-4-5-20251001",  # or "openai/gpt-4o-mini"
        api_token="sk-...",
    ),
    instruction="Convert this HTML to clean, structured Markdown. Remove ads and navigation.",
    chunk_token_threshold=4096,   # max tokens per chunk sent to LLM
    overlap_rate=0.5,             # 50% overlap between chunks
    word_token_rate=0.2,          # words-to-tokens ratio estimate
    ignore_cache=False,           # use local cache if available
)
```

## Data contracts

**Input:** raw HTML string (the full page HTML or a pre-selected portion)

**Output (via CrawlResult.markdown):**
```python
MarkdownGenerationResult(
    raw_markdown=str,          # full page, no filtering
    fit_markdown=str,          # filtered version (this is what the filter affects)
    fit_html=str,              # the pruned HTML that generated fit_markdown
    references_markdown=str,   # citation-style links
    markdown_with_citations=str,
)
```

**Filter selection guide:**

| Use case | Filter | Why |
|----------|--------|-----|
| Generic noise removal, no query | `PruningContentFilter` | Fast, offline, no cost |
| Topic-focused extraction (you know what you want) | `BM25ContentFilter` | Query-aware, still free |
| Highest quality, custom semantic rules | `LLMContentFilter` | Flexible, expensive |
| No filtering needed | (omit content_filter) | `fit_markdown` == `raw_markdown` |

## Dependencies & assumptions

- `PruningContentFilter`: `beautifulsoup4`, `lxml` (already core deps)
- `BM25ContentFilter`: `rank-bm25`, `snowballstemmer`, `nltk` (stop words)
- `LLMContentFilter`: `unclecode-litellm` (LLM client); requires API key
- All three: part of `crawl4ai` core package

## To port this, you need:
- [ ] Install crawl4ai (`pip install crawl4ai`)
- [ ] Import your chosen filter class
- [ ] Pass instance to `CrawlerRunConfig(content_filter=...)` AND `DefaultMarkdownGenerator(content_filter=...)`
- [ ] Read `result.markdown.fit_markdown` (not `raw_markdown`) to get filtered output
- [ ] For BM25: optionally pass `user_query` if auto-extraction from page is unreliable
- [ ] For LLM filter: configure `LLMConfig` with provider and API token
- [ ] For LLM filter: manage cache directory (default is `~/.crawl4ai/cache/llm_filter/`)

## Gotchas

**You must pass the filter to BOTH `content_filter` AND `DefaultMarkdownGenerator`.** The filter is used in two places: once during HTML processing, once during markdown generation. Passing to only one leaves the other unfiltered.

**BM25 auto-query can fail on thin pages.** Pages with no title, no h1, and no meta description will have a poor auto-extracted query. Pass `user_query` explicitly for such pages.

**`threshold_type="dynamic"` is experimental.** The dynamic mode adjusts thresholds per node type but can be unpredictable on unusual page structures. Start with `"fixed"`.

**LLMContentFilter output varies per model.** The instruction prompt can be customized, but the extraction logic expects XML-tagged blocks in the response (`<block>...</block>`). If you swap models, verify the response format matches.

**Stop words list requires NLTK download.** First run triggers `nltk.download('stopwords')` if not already present. Add to your setup routine.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key file: `crawl4ai/content_filter_strategy.py`
