# Engagement-Signal Ranking — from [last30days-skill](https://github.com/mvanhorn/last30days-skill)

> Domain: [[_domain]] · Source: https://github.com/mvanhorn/last30days-skill · NotebookLM:

## What it does

After all sources have returned results, the engine ranks them by real engagement signals — Reddit upvotes, YouTube view counts, X likes, Polymarket betting volume — rather than by recency or editorial authority. The ranking combines weighted reciprocal-rank fusion (RRF) across sources with an LLM reranking pass, producing a final ordered list where the most-engaged content rises to the top.

## Why it exists

Search results sorted by recency or keyword match are a poor proxy for importance. A Reddit post with 12,000 upvotes that appeared 3 weeks ago is more significant than one with 3 upvotes from yesterday. Polymarket prediction odds at 73% represent real money behind a belief, making them a higher-confidence signal than a tweet. Engagement ranking exists to surface what the internet actually cared about, not just what's newest.

## How it actually works

**Source weights:** The query planner assigns a `source_weights` dict to each research session based on the topic type. Topics with financial implications weight Polymarket higher; tech topics weight GitHub and HN higher. These weights are used in the fusion step.

**Reciprocal-rank fusion (RRF):** Each source returns its results in ranked order. RRF combines these lists by giving each item a score of `1 / (k + rank)` (k=60 by default) and summing scores across sources. This merges heterogeneous ranked lists without needing a common score unit — upvotes and view counts don't need to be normalized against each other because only the within-source rank matters.

**LLM reranking:** After RRF, an LLM reranking pass (`rerank.py`) re-evaluates the top results for relevance to the specific topic. This catches cases where high-engagement items are tangentially related — a viral Reddit thread about a celebrity that happens to mention your topic doesn't belong at the top.

**Quality nudging:** `quality_nudge.compute_quality_score()` monitors for research degradation signals — e.g., YouTube returning captions-disabled videos instead of transcripts, or a source returning suspiciously few results. Quality issues surface as warnings rather than silently degrading output.

**Depth profiles affect input volume:** quick=6 results per stream, default=12, deep=20. Higher depth feeds more candidates into the ranking funnel, improving result diversity at the cost of latency.

## The non-obvious parts

- RRF with k=60 is deliberately robust to outliers: a single source returning one item ranked #1 doesn't dominate the fusion. The k parameter dampens the benefit of being first.
- Source weights are topic-sensitive, not fixed. A generic query uses equal weights; a financial query upweights Polymarket; a dev tools query upweights GitHub stars and HN points.
- The LLM reranking pass is the most expensive step. It's only applied to a top-N slice, not the full result set.
- Polymarket odds are cited as percentages only, never dollar volumes — this is a SKILL.md law, not an engine constraint.

## Related

- [[multi-source-research-engine--from-last30days-skill]] — runs ranking after Phase 2
- [[cross-source-clustering--from-last30days-skill]] — clustering happens alongside/after ranking
