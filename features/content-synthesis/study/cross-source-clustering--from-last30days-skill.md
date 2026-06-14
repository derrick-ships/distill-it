# Cross-Source Story Clustering — from [last30days-skill](https://github.com/mvanhorn/last30days-skill)

> Domain: [[_domain]] · Source: https://github.com/mvanhorn/last30days-skill · NotebookLM:

## What it does

Takes the ranked pool of results from all sources and groups the same story together — even when it appears on Reddit, X, and YouTube with completely different wording. For each cluster, selects up to 3 representative items using Maximal Marginal Relevance (MMR), balancing quality with diversity. The output is a deduplicated, clustered list where multi-platform stories are flagged as stronger signals.

## Why it exists

The same news story or discussion topic appears on every platform simultaneously but with different phrasing. Without clustering, the research output would show "OpenAI releases GPT-5" five times — once from Reddit, once from HN, once from X, once from a YouTube video title, once from a news snippet. Clustering collapses these into one finding and uses the multi-platform presence as a confidence signal: if three independent communities are talking about the same thing, it's more significant than something only one community mentioned.

## How it actually works

Clustering runs in two passes (`cluster.py`):

**Pass 1 — Text similarity (greedy):** Items are compared pairwise by text content. If similarity exceeds a threshold, they're grouped. The threshold varies by intent: `breaking_news` uses 0.42 (looser — news coverage shares few exact words), other intents use 0.48. Greedy means each item joins the first cluster it's similar enough to — fast, but imperfect for same-story-different-phrasing cases.

**Pass 2 — Entity-based merging:** This catches what Pass 1 misses. Significant words are extracted from each item: proper nouns, numbers, capitalized terms, filtered against a stopword list. Small clusters (≤3 items) that share overlapping entities by overlap coefficient get merged together. This handles "Elon Musk's xAI raises $6B" (Reddit) merging with "xAI funding round" (X) even though text similarity was low.

**Safeguards:**
- Only merges clusters from *different* sources — same-source duplicates are handled by a separate deduplication step
- Polymarket clusters never merge with news clusters — prediction market odds and news stories are different signal types
- Clusters produced from a single source get a `single-source` flag; clusters with very few items get `thin-evidence`
- Clustering is skipped entirely when the query intent isn't in the clusterable set (e.g., pure data lookups)

**MMR representative selection:** For each cluster, up to 3 representatives are chosen using Maximal Marginal Relevance. Candidates are scored by final ranking, then selected greedily — a high-scoring candidate that's too similar to an already-selected representative faces a diversity penalty. This ensures the 3 reps show different facets of the same story.

## The non-obvious parts

- The two-pass design is essential: text similarity alone fails for same-story-different-phrasing (the most important deduplication case). Entity overlap catches what word-level similarity misses.
- Uncertainty flags (`single-source`, `thin-evidence`) are surfaced to the LLM synthesis layer, which is instructed to weight multi-source clusters more heavily. The flags don't suppress output; they inform confidence.
- MMR's diversity penalty means you get "Reddit discussion + X thread + YouTube transcript" rather than three Reddit posts, even if Reddit posts scored highest individually.
- The overlap *coefficient* (not Jaccard) is used for entity merging because it handles different-length entity sets better: it divides shared entities by the size of the *smaller* set.

## Related

- [[multi-source-research-engine--from-last30days-skill]] — clustering is the final post-retrieval step
- [[engagement-signal-ranking--from-last30days-skill]] — ranking feeds into the clustering input
