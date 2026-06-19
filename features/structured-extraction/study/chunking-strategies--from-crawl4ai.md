# Chunking Strategies — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

crawl4ai ships seven `ChunkingStrategy` implementations that split web page text into segments before passing them to an LLM or a vector store. Each strategy offers a different granularity/overlap tradeoff: from a no-op passthrough to sentence-level boundaries to overlapping sliding windows. You wire one into `CrawlerRunConfig.chunking_strategy` and the crawler automatically segments the page content before extraction.

## Why it exists

LLMs have context windows; vector stores require segments of meaningful length. A 50KB web page can't be passed to a model as-is. But splitting naively (every N characters) breaks sentences, severs context, and creates incoherent segments. The chunking strategies provide semantically-aware splits that keep the signal intact.

## How it actually works

All strategies implement a single method: `chunk(text: str) -> List[str]`. The caller passes in the page text and gets back a list of segments. Strategies differ only in how they define "a segment."

**IdentityChunking:** Returns `[text]` — the entire page as one chunk. Useful when the LLM context window is large enough, or for short pages where chunking would create unnecessary splits.

**RegexChunking:** Applies a sequence of regex patterns to split the text. Default pattern is `r"\n\n"` (double newlines — paragraph breaks). Multiple patterns are applied iteratively: the result of splitting by pattern 1 is further split by pattern 2. Best for structured documents with consistent delimiters.

**NlpSentenceChunking:** Uses NLTK's `sent_tokenize()` to split on sentence boundaries. The tokenizer handles abbreviations (Dr., e.g.) and complex punctuation correctly. Returns one sentence per chunk — appropriate when you need maximum granularity for sentence-level similarity search.

**TopicSegmentationChunking:** Uses NLTK's `TextTilingTokenizer` to identify topic shifts within the text and split there. Each chunk is a topically coherent segment, not an arbitrary boundary. Optionally extracts N keywords per segment via `_extract_keywords()`. Best for long articles or documentation pages with multiple distinct sections.

**FixedLengthWordChunking:** Splits text by whitespace into groups of exactly `chunk_size` words. Simple, deterministic, no NLP dependency. Good when you need predictable chunk sizes for embedding model token limits.

**SlidingWindowChunking:** Creates overlapping chunks by advancing a `window_size`-word window by `step` words at a time. Overlap = `window_size - step`. The standard RAG approach: overlap ensures that context at chunk boundaries appears in at least one full context window.

**OverlappingWindowChunking:** Similar to sliding window but the constructor takes `window_size` and `overlap` directly (more intuitive than `step`). Advances by `window_size - overlap` words each time. Preferred for large documents needing substantial context bridges.

## The non-obvious parts

**Chunking happens before extraction, not after.** The `ExtractionStrategy` receives the chunked segments as its input. The `LLMExtractionStrategy` also has its own internal merge-and-chunk logic on top of this — so two levels of chunking can occur if both are configured. Typically you set one OR the other.

**`TopicSegmentationChunking` requires substantial text.** The TextTiling algorithm needs at least a few hundred words to detect topic shifts. On short pages, it may return one segment (the whole text). Test with representative content.

**`NlpSentenceChunking` requires an NLTK punkt download.** First use triggers `nltk.download('punkt')`. Add this to your setup routine to avoid runtime failures.

**No built-in metadata is attached to chunks.** The `chunk()` method returns plain strings. If you need to know which chunk came from which section of the page (for citation tracking), you must implement this tracking yourself around the chunking call.

**Overlap does NOT prevent duplicate extraction.** If you're using `SlidingWindowChunking` before `LLMExtractionStrategy`, the overlapping text will be processed twice by the LLM. Deduplicate extracted results by a key field after extraction.

## Related
- [[llm-structured-extraction--from-crawl4ai]] (chunking integrates with LLM extraction)
- [[content-filtering-strategies--from-crawl4ai]] (filter before chunking to reduce segment count)
