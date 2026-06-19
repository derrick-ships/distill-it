# Chunking Strategies (build spec) — distilled from crawl4ai

## Summary

Seven `ChunkingStrategy` implementations (Identity, Regex, NLP Sentence, Topic Segmentation, Fixed Length Word, Sliding Window, Overlapping Window) that split page text into segments for LLM extraction or RAG vector ingestion. Plug into `CrawlerRunConfig.chunking_strategy`.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.chunking_strategy import (
    IdentityChunking,
    RegexChunking,
    NlpSentenceChunking,
    TopicSegmentationChunking,
    FixedLengthWordChunking,
    SlidingWindowChunking,
    OverlappingWindowChunking,
)

# Strategy 1: No chunking (entire page as one segment)
chunker = IdentityChunking()

# Strategy 2: Split on paragraph breaks (or custom patterns)
chunker = RegexChunking(
    patterns=[r"\n\n", r"\n#{1,3} "]  # paragraphs, then markdown headings
)

# Strategy 3: Sentence-level splits (NLTK)
chunker = NlpSentenceChunking()  # requires: nltk.download('punkt')

# Strategy 4: Topic-aware segments (TextTiling)
chunker = TopicSegmentationChunking(num_keywords=3)  # also extracts keywords

# Strategy 5: Fixed word count (simple, predictable)
chunker = FixedLengthWordChunking(chunk_size=200)  # 200 words per chunk

# Strategy 6: Sliding window with overlap (standard RAG approach)
chunker = SlidingWindowChunking(
    window_size=150,   # words per chunk
    step=75,           # advance by 75 words → 75 words overlap
)

# Strategy 7: Overlapping window (explicit overlap param)
chunker = OverlappingWindowChunking(
    window_size=1000,  # words per chunk
    overlap=100,       # 100 words overlap between consecutive chunks
)

# Wire into CrawlerRunConfig
config = CrawlerRunConfig(
    chunking_strategy=chunker,
    # The chunker runs on the page content before extraction
)

# Use standalone (outside crawler)
text = "Long article text here..."
chunks = chunker.chunk(text)  # List[str]
for i, chunk in enumerate(chunks):
    print(f"Chunk {i}: {chunk[:100]}...")
```

**Implementation internals:**
```python
class SlidingWindowChunking(ChunkingStrategy):
    def __init__(self, window_size=100, step=50):
        self.window_size = window_size
        self.step = step

    def chunk(self, text: str) -> List[str]:
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + self.window_size, len(words))
            chunks.append(" ".join(words[start:end]))
            if end == len(words):
                break
            start += self.step
        return chunks

class OverlappingWindowChunking(ChunkingStrategy):
    def __init__(self, window_size=1000, overlap=100):
        self.window_size = window_size
        self.step = window_size - overlap  # derived

    def chunk(self, text: str) -> List[str]:
        words = text.split()
        chunks = []
        for start in range(0, len(words), self.step):
            end = min(start + self.window_size, len(words))
            chunks.append(" ".join(words[start:end]))
        return chunks

class TopicSegmentationChunking(ChunkingStrategy):
    def __init__(self, num_keywords=3):
        self.num_keywords = num_keywords

    def chunk(self, text: str) -> List[str]:
        tokenizer = TextTilingTokenizer()
        try:
            segments = tokenizer.tokenize(text)
        except ValueError:
            return [text]  # too short for topic detection
        if self.num_keywords > 0:
            return [(seg, self._extract_keywords(seg, self.num_keywords))
                    for seg in segments]
        return segments
```

## Data contracts

**All strategies:**
```python
strategy.chunk(text: str) -> List[str]
# text: plain text (markdown works; HTML is cleaned first by the crawler)
# returns: list of string segments

# TopicSegmentationChunking with num_keywords>0 returns:
List[Tuple[str, List[str]]]  # (segment_text, keyword_list) pairs
```

**Choosing a strategy:**

| Strategy | Best for | Notes |
|----------|----------|-------|
| `IdentityChunking` | Short pages, large context window | No deps |
| `RegexChunking` | Markdown docs, structured text | Fastest |
| `NlpSentenceChunking` | Fine-grained similarity search | NLTK required |
| `TopicSegmentationChunking` | Long multi-topic articles | NLTK + min ~300 words |
| `FixedLengthWordChunking` | Embedding pipelines with token limits | Simplest |
| `SlidingWindowChunking` | RAG retrieval, standard approach | step = window - overlap |
| `OverlappingWindowChunking` | Long docs, large overlap needed | More intuitive params |

## Dependencies & assumptions

- `RegexChunking`, `IdentityChunking`, `FixedLengthWordChunking`, `SlidingWindowChunking`, `OverlappingWindowChunking`: no extra deps (stdlib only)
- `NlpSentenceChunking`: `nltk` — run `nltk.download('punkt')` at setup
- `TopicSegmentationChunking`: `nltk` — run `nltk.download('stopwords')` + `nltk.download('punkt')`

## To port this, you need:
- [ ] Choose strategy based on your use case (see table above)
- [ ] For NLTK-based strategies: add `nltk.download('punkt', 'stopwords')` to your setup
- [ ] Wire into `CrawlerRunConfig(chunking_strategy=chunker)` OR call `chunker.chunk(text)` standalone
- [ ] For LLM pipelines: combine with `LLMExtractionStrategy` (chunking runs first)
- [ ] For RAG: use `SlidingWindowChunking` or `OverlappingWindowChunking`; store chunks + source URL as metadata
- [ ] Tune `window_size` to your embedding model's token limit (typically 256-512 tokens → ~200-400 words)

## Gotchas

**TopicSegmentation fails on short text.** TextTiling needs multiple "blocks" (typically 10+ sentences) to detect boundaries. On news snippets or short pages, it degrades to returning the entire text as one segment. Add a length check before using it: `if len(text.split()) < 200: use IdentityChunking`.

**Word-based chunking breaks on languages without spaces.** Japanese, Chinese, Thai, etc. require character-level or tokenizer-aware splitting. All the word-based strategies (Fixed, Sliding, Overlapping) produce one giant "chunk" for these languages.

**`TopicSegmentationChunking` with `num_keywords > 0` changes the return type.** Instead of `List[str]`, it returns `List[Tuple[str, List[str]]]`. This breaks code that expects `List[str]`. Set `num_keywords=0` if you don't need keywords and want consistent typing.

**Chunks don't carry source position metadata.** There's no built-in way to know "this chunk came from paragraph 3, section 2." If you need that for citation tracking or UI highlighting, wrap the chunker and track positions manually.

**LLMExtractionStrategy has its own internal chunking via `_merge()`.** If you set `chunking_strategy` AND use `LLMExtractionStrategy`, your chunks are re-merged before being sent to the LLM. The two chunking systems are additive. In practice, set one or the other — not both.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key file: `crawl4ai/chunking_strategy.py`
