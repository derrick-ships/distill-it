# Adaptive Crawler — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

`AdaptiveCrawler` is a query-driven crawler that stops when it has collected enough information to answer a specific research question — rather than exhausting a depth limit or page count. It statistically measures how much of the query's "information space" has been covered as it crawls, and stops when coverage reaches a confidence threshold (default 70%). It treats web crawling as an information-theoretic optimization problem.

## Why it exists

Standard BFS/DFS crawlers are target-oblivious: they don't know when they've found enough. For a researcher asking "what are the best Python async patterns?", crawling 200 pages when the answer was in the first 8 is wasteful. AdaptiveCrawler models the knowledge state as it goes and stops when saturation sets in.

## How it actually works

**Three confidence signals** are tracked simultaneously and combined into one overall confidence score:

*Coverage* measures how thoroughly the query terms appear across the crawled documents. For each query term, it counts what fraction of documents contain it and how often, then applies a square root curve to model diminishing returns. A term that appears in 80% of docs has high coverage; one in only 10% is a gap.

*Consistency* calculates pairwise Jaccard similarity between all pairs of crawled documents (using term sets, not full text). High consistency means the documents form a coherent cluster and agree about the topic. Low consistency means the crawler has wandered into unrelated territory.

*Saturation* tracks the rate of new term discovery across crawl iterations. Early crawls find many new terms (high novelty); as the crawler exhausts the topic's vocabulary, fewer new terms appear per page. When new-term discovery rate drops below a threshold, saturation is considered reached.

The three signals are combined: `confidence = 0.4*coverage + 0.3*consistency + 0.3*saturation`. When this exceeds the threshold, crawling stops.

**Link prioritization** uses a three-factor ranking for each candidate link:
1. *Relevance*: BM25 score of the link anchor text and surrounding context against the query
2. *Novelty*: percentage of terms in the link preview that are new (not seen in any crawled page yet)
3. *Authority*: URL structure signals (shorter paths, no heavy parameterization)

Only the top-K links per round exceeding a minimum gain threshold are actually fetched. This is the feedback loop: each round's results inform which links are worth following next.

**Embedding strategy (optional):** For deeper semantic coverage, AdaptiveCrawler can generate 10+ natural-language paraphrases of the query via an LLM, embed them all, and track which parts of the semantic space have been covered by crawled documents. Links are prioritized by their ability to fill the coverage gaps in this embedding space. This catches cases where important content uses different vocabulary than the query.

**Convergence detection:** The crawler exits when: confidence exceeds threshold, or the last N rounds yielded no improvement, or `max_pages` is hit. A "quality confidence" layer maps the internal score to a user-facing percentage that's capped at 95% (to convey that certainty is never complete).

## The non-obvious parts

**The crawler must be initialized differently from AsyncWebCrawler.** `AdaptiveCrawler` wraps `AsyncWebCrawler` internally — you pass the browser config to `AdaptiveCrawler`, not to a separate crawler.

**Saturation is measured per-iteration, not globally.** The system logs a "new terms found this round" count for each crawl batch. If this count stays near zero for two consecutive rounds, saturation has been reached regardless of the absolute confidence score.

**The BM25 link prioritization runs on preview text, not full page content.** Each candidate link's "preview" is a short snippet (from anchor text, surrounding paragraph, or from a HEAD peek). This means relevance scoring is shallow but fast — the crawler doesn't need to fetch a page to score it.

**Deduplication prevents semantic redundancy.** When using the embedding strategy, links whose embedding is within distance 0.85 of any already-crawled document are skipped. This prevents the crawler from over-indexing on one cluster of similar pages.

## Related
- [[deep-crawl-traversal--from-crawl4ai]] (simpler: depth/page limits only, no query model)
- [[async-web-crawler--from-crawl4ai]] (the underlying single-page engine)
- [[content-filtering-strategies--from-crawl4ai]] (often combined to get clean text for term analysis)
