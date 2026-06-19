# Adaptive Crawler (build spec) — distilled from crawl4ai

## Summary

A query-driven web crawler that models information coverage using statistical term analysis (or optionally embeddings) and stops when it has collected enough content to answer a research question. Wraps `AsyncWebCrawler` internally; you interact with `AdaptiveCrawler` directly.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMConfig
from crawl4ai import AdaptiveCrawler, AdaptiveConfig

# Basic usage (statistical strategy)
config = AdaptiveConfig(
    query="Python async programming patterns",
    strategy="statistical",         # "statistical" | "embedding" | "llm"
    confidence_threshold=0.7,       # stop when this is reached (0.0-1.0)
    max_pages=50,
    max_depth=3,
)

async with AsyncWebCrawler(config=BrowserConfig()) as crawler:
    adaptive = AdaptiveCrawler(crawler, config)
    result = await adaptive.digest(
        start_url="https://docs.python.org/asyncio",
        run_config=CrawlerRunConfig(),
    )
    print(f"Crawled {result.pages_crawled} pages")
    print(f"Confidence: {result.confidence:.1%}")
    print(result.answer)          # synthesized answer to the query
```

**Statistical confidence calculation:**
```python
def _calculate_confidence(self) -> float:
    # Coverage: fraction of query terms well-represented in corpus
    query_terms = set(tokenize(self.query))
    doc_term_sets = [set(tokenize(doc)) for doc in self.crawled_docs]
    coverage_scores = []
    for term in query_terms:
        doc_freq = sum(1 for doc in doc_term_sets if term in doc)
        cov = doc_freq / max(len(doc_term_sets), 1)
        coverage_scores.append(math.sqrt(cov))  # square root curve
    coverage = sum(coverage_scores) / max(len(coverage_scores), 1)

    # Consistency: average pairwise Jaccard similarity
    pairs = [(a, b) for i, a in enumerate(doc_term_sets) for b in doc_term_sets[i+1:]]
    if pairs:
        jaccard_scores = [len(a & b) / len(a | b) for a, b in pairs if a | b]
        consistency = sum(jaccard_scores) / len(jaccard_scores)
    else:
        consistency = 0.0

    # Saturation: 1 - (new_terms_this_round / total_terms_seen)
    saturation = 1.0 - (self.new_terms_this_round / max(len(self.all_terms_seen), 1))

    return 0.4 * coverage + 0.3 * consistency + 0.3 * saturation

def _rank_links(self, candidates: List[Link]) -> List[Link]:
    scored = []
    for link in candidates:
        relevance = bm25_score(link.preview_text, self.query_terms)
        novelty = len(set(tokenize(link.preview_text)) - self.all_terms_seen) / \
                  max(len(tokenize(link.preview_text)), 1)
        authority = 1.0 / (1 + url_path_depth(link.href))
        score = 0.5 * relevance + 0.3 * novelty + 0.2 * authority
        if score > self.min_gain_threshold:
            scored.append((link, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [link for link, _ in scored[:self.top_k_links]]
```

## Data contracts

**AdaptiveConfig:**
```python
AdaptiveConfig(
    query: str,                          # the research question
    strategy: str = "statistical",       # "statistical" | "embedding" | "llm"
    confidence_threshold: float = 0.7,   # 0.0-1.0; stop threshold
    max_pages: int = 50,
    max_depth: int = 3,
    top_k_links: int = 5,                # max links to follow per round
    min_gain_threshold: float = 0.1,     # min score for a link to be fetched
    embedding_overlap_threshold: float = 0.85,  # dedup threshold (embedding mode)
    coverage_radius: float = 0.2,        # embedding distance for "covered"
    link_preview_timeout: float = 5.0,   # seconds to wait for link preview fetch
    llm_config: LLMConfig | None = None, # required for "embedding" or "llm" strategy
)
```

**AdaptiveCrawlResult:**
```python
@dataclass
class AdaptiveCrawlResult:
    pages_crawled: int
    confidence: float               # final confidence score (0.0-1.0)
    confidence_pct: float           # user-friendly 0-95% capped version
    answer: str                     # LLM-synthesized answer (if llm strategy)
    coverage: float                 # coverage component
    consistency: float              # consistency component
    saturation: float               # saturation component
    crawled_urls: List[str]
    stop_reason: str                # "threshold_reached" | "max_pages" | "saturated"
    knowledge_base: List[CrawlResult]  # all crawled page results
```

## Dependencies & assumptions

- `crawl4ai` core package
- Statistical strategy: no extra deps
- Embedding strategy: `sentence-transformers`, `torch` (crawl4ai `[cosine]` extra)
- LLM strategy: `unclecode-litellm`, API key
- Must be used inside `AsyncWebCrawler` context

## To port this, you need:
- [ ] Install crawl4ai with appropriate extras: `pip install "crawl4ai[cosine]"` for embeddings
- [ ] Define a clear `query` — the more specific, the better the confidence model performs
- [ ] Set `max_pages` and `confidence_threshold` based on your tolerance for false-convergence
- [ ] For `embedding` strategy: configure `LLMConfig` for query paraphrase generation
- [ ] Process `result.knowledge_base` (list of `CrawlResult`) for downstream RAG/extraction
- [ ] Check `result.stop_reason` to understand why crawling stopped

## Gotchas

**Statistical strategy works poorly on query-agnostic pages.** If the site uses very different vocabulary than your query (synonyms, domain jargon), coverage will be incorrectly low. Use `strategy="embedding"` for semantic matching.

**Consistency signal can fool the crawler on single-topic sites.** A site with all pages about one narrow topic will have high consistency from page 1. The crawler may stop early because all three signals converge quickly. Use a higher threshold (0.85+) for narrow-topic sites.

**`min_gain_threshold` is the knob for thoroughness vs speed.** Low threshold (0.05) = more pages crawled, higher coverage. High threshold (0.5) = stops sooner, may miss peripheral content.

**`answer` field requires `strategy="llm"`.** The statistical and embedding strategies don't synthesize an answer — they just identify when enough content has been gathered. You must then run your own summarization over `result.knowledge_base`.

**Link preview fetch can be the bottleneck.** With `link_preview_timeout=5.0` and 50+ candidate links per round, scoring links can take minutes. Reduce `top_k_links` or disable preview fetch for faster iterations.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key file: `crawl4ai/adaptive_crawler.py`
