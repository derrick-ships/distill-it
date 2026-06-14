# Engagement Signal Ranking (build spec) — distilled from last30days-skill

## Summary
Two-stage ranking pipeline: (1) Reciprocal Rank Fusion merges ranked lists from all sources
into a single score; (2) an LLM reranker re-orders the top-N by topic relevance using the
query_plan context. A quality nudge layer detects content degradation and adjusts weights.

## Core Logic (inlined)

### Stage 1 — Reciprocal Rank Fusion

```python
# fusion.py
def rrf_merge(ranked_lists: dict[str, list[Item]], k: int = 60,
              source_weights: dict[str, float] | None = None) -> list[Item]:
    """
    ranked_lists: {source_name: [Item, ...]} already sorted best-first per source
    k: RRF constant (60 is the published default; lower = rank position matters more)
    source_weights: optional per-source multiplier from query_plan (default 1.0)
    """
    scores: dict[str, float] = {}
    items: dict[str, Item] = {}

    for source, items_list in ranked_lists.items():
        w = (source_weights or {}).get(source, 1.0)
        for rank, item in enumerate(items_list):
            key = item.canonical_id()          # deduplicate by URL or content hash
            scores[key] = scores.get(key, 0.0) + w * (1.0 / (k + rank + 1))
            if key not in items:
                items[key] = item

    merged = sorted(items.values(), key=lambda i: scores[i.canonical_id()], reverse=True)
    return merged
```

### Stage 2 — LLM Reranker

```python
# rerank.py
def llm_rerank(items: list[Item], topic: str, query_plan: dict,
               top_n: int = 20) -> list[Item]:
    """
    Send top_n items to LLM with topic + query_plan context.
    LLM returns reordered indices. Items beyond top_n are appended unchanged.
    """
    candidates = items[:top_n]
    tail = items[top_n:]

    prompt = _build_rerank_prompt(candidates, topic, query_plan)
    response = llm_call(prompt)            # calls OpenRouter or local model
    reordered_indices = _parse_indices(response)   # e.g. [3,0,7,1,...]

    reranked = [candidates[i] for i in reordered_indices if i < len(candidates)]
    # Append any candidates not mentioned by LLM (safety net)
    mentioned = set(reordered_indices)
    reranked += [c for i, c in enumerate(candidates) if i not in mentioned]
    return reranked + tail
```

### Quality nudge (degradation detection)

```python
# quality_nudge.py
def compute_quality_score(items: list[Item]) -> float:
    """
    Returns 0.0–1.0. Low score = degraded content (spam, duplicates, off-topic).
    Used to down-weight a source's contribution to RRF in subsequent calls.
    """
    if not items:
        return 0.0
    total = len(items)
    unique_domains = len({urlparse(i.url).netloc for i in items if i.url})
    avg_snippet_len = sum(len(i.snippet or "") for i in items) / total

    domain_diversity = unique_domains / total          # 1.0 = all different domains
    content_density = min(avg_snippet_len / 200, 1.0) # normalised at 200 chars
    return (domain_diversity * 0.6) + (content_density * 0.4)
```

### Topic-sensitive source weights

`query_plan` carries a `source_weights` dict populated by the query planner:

```python
# Example query_plan for topic "OpenAI"
{
    "source_weights": {
        "reddit":      1.2,   # community signal boosted for tech topics
        "hackernews":  1.4,   # HN weight boosted for AI topics
        "x":           1.0,
        "github":      0.8,   # lower for news-heavy topics
        "polymarket":  0.6,   # markets less relevant unless financial topic
    },
    "queries": {...},
}
```
These weights are multiplied into the RRF score in `rrf_merge()`.

## Data Contracts

```python
# Input to rrf_merge
ranked_lists: dict[str, list[Item]]   # per-source sorted lists
k: int = 60                            # RRF constant
source_weights: dict[str, float]      # from query_plan

# Output: single merged list[Item] sorted by fused score
```

## Dependencies & Assumptions
- All source adapters return items in descending-relevance order (best first)
- `Item.canonical_id()` provides a stable dedup key (URL hash recommended)
- LLM reranker prompt must fit within model context (top_n=20 is safe for most models)

## To Port This
- [ ] Implement `Item.canonical_id()` using URL normalization
- [ ] Wire `llm_call()` to your LLM provider for the reranker
- [ ] Populate `source_weights` in your query planner or hard-code defaults
- [ ] Add `compute_quality_score()` as a post-run health metric per source
- [ ] Tune `k` for your domain: lower k (e.g. 20) prioritizes rank position more

## Gotchas
- RRF with k=60 is robust but slow to respond to rank position; if top results
  from a single high-quality source should dominate, lower k or raise its weight
- LLM reranker can be slow; set a timeout and fall back to RRF order if it exceeds it
- Quality nudge scores are advisory — don't auto-drop sources below a threshold;
  a temporarily degraded source may recover next run

## Origin (reference only)
Repo: https://github.com/mvanhorn/last30days-skill
Key files: `engine/fusion.py`, `engine/rerank.py`, `engine/quality_nudge.py`
