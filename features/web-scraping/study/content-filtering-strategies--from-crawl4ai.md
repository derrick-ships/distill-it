# Content Filtering Strategies — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

Before the crawler hands HTML to an LLM or extraction pipeline, it runs a content filter to strip noise — ads, navigation bars, footers, comment sections, sidebars. crawl4ai ships three distinct strategies: **PruningContentFilter** (DOM-tree scoring), **BM25ContentFilter** (query-relevance scoring), and **LLMContentFilter** (model-based semantic filtering). Each produces a cleaner version of the content, exposed as `fit_markdown` on the result.

## Why it exists

Raw web pages are 30–70% noise by word count. Feeding that noise to an LLM wastes tokens, inflates costs, and can drown out the signal. Content filtering is the triage step that maximizes the signal-to-noise ratio before any expensive downstream processing.

## How it actually works

**PruningContentFilter** works entirely offline — no model calls needed. It traverses the parsed HTML DOM as a tree, computing a composite score for every node. The score blends: text density (words per character), link density (links-to-text ratio, penalized), tag importance (article, main, and heading tags score high; nav, footer, and aside score low), class/ID name signals (a regex that penalizes "ads", "comment", "footer", "sidebar" etc. in class names), and raw text length. Nodes below the threshold (default 0.48) are removed. The pruned HTML is then converted to Markdown and returned as `fit_markdown`.

**BM25ContentFilter** is query-aware. It first extracts a query from the page itself — the title, h1, first paragraph, and meta description. It then segments the body into text chunks, tokenizes both query and corpus, optionally applies Porter stemming, removes stop words, and scores each chunk with the Okapi BM25 algorithm. Scores are multiplied by tag-importance weights (h1=5x, h2=4x, strong=2x, etc.). Only chunks scoring above `bm25_threshold` (default 1.0) survive. Results are re-sorted by original document order and deduplicated. Best for when you have a known search intent.

**LLMContentFilter** delegates to a language model. It splits the HTML into overlapping chunks (default 50% overlap), sends each chunk to the configured LLM with an instruction prompt ("convert this HTML to clean markdown, preserving structure"), extracts the XML-wrapped response blocks, and concatenates them. Results are cached locally via MD5 hash of (html + instruction). It's the most flexible but slowest and most expensive option.

All three strategies share a base class (`RelevantContentFilter`) that defines `included_tags` (article, main, section, p, headings) and `excluded_tags` (nav, footer, script, style), along with a regex exclude-pattern for class names.

## The non-obvious parts

**The BM25 query is auto-extracted from the page itself**, not supplied by the caller — so it works even when you don't know what the page is about. It constructs the query from the page's own metadata (title, h1, meta description, first paragraph). This is clever but means it's query-answering pages that benefit most; list pages or landing pages often have thin metadata.

**PruningContentFilter's `dynamic` threshold mode** adjusts the cutoff per-node based on the node's tag type and surrounding context. "dynamic" is more aggressive on generic divs and more lenient on semantic HTML5 tags.

**LLMContentFilter caches aggressively.** Results are stored in a local directory keyed on MD5(html+instruction). If you call it twice on the same HTML with the same instruction, the second call is instant. `ignore_cache=True` bypasses this.

**These filters produce `fit_html` (pruned HTML) AND `fit_markdown`.** The raw Markdown generation still uses the full HTML. Only `fit_markdown` reflects the filtered result. So `result.markdown.raw_markdown` ≠ `result.markdown.fit_markdown`.

## Related
- [[async-web-crawler--from-crawl4ai]] (these strategies plug into aprocess_html)
- [[llm-structured-extraction--from-crawl4ai]] (often combined: filter first, then extract)
- [[chunking-strategies--from-crawl4ai]] (chunking happens on the filtered output for RAG)
