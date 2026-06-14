# Cross-Source Clustering (build spec) — distilled from last30days-skill

## Summary
Two-pass clustering algorithm that groups related items from different sources into story
clusters, then picks up to 3 representative items per cluster using Maximal Marginal Relevance.
Designed to surface the same story across Reddit, X, HN, etc. without merging items from the
same source.

## Core Logic (inlined)

### Pass 1 — Greedy text similarity

```python
# cluster.py
import difflib

BREAKING_NEWS_THRESHOLD = 0.42
DEFAULT_THRESHOLD = 0.48

def cluster_items(items: list[Item], is_breaking: bool = False) -> list[Cluster]:
    threshold = BREAKING_NEWS_THRESHOLD if is_breaking else DEFAULT_THRESHOLD
    clusters: list[Cluster] = []

    for item in items:
        placed = False
        for cluster in clusters:
            if _same_source(item, cluster):
                continue                      # never merge same-source items
            if _text_similarity(item, cluster.centroid()) >= threshold:
                cluster.add(item)
                placed = True
                break
        if not placed:
            clusters.append(Cluster([item]))

    return clusters

def _text_similarity(item: Item, centroid: Item) -> float:
    a = (item.title + " " + item.snippet).lower()
    b = (centroid.title + " " + centroid.snippet).lower()
    return difflib.SequenceMatcher(None, a, b).ratio()
```

### Pass 2 — Entity overlap on small clusters

```python
def refine_small_clusters(clusters: list[Cluster],
                           entity_map: dict[str, list[str]]) -> list[Cluster]:
    """
    For clusters with ≤3 items from different sources, try entity-overlap merge.
    Entity overlap coefficient = |A∩B| / min(|A|,|B|)
    """
    ENTITY_THRESHOLD = 0.5
    changed = True
    while changed:
        changed = False
        for i in range(len(clusters)):
            if clusters[i].size() > 3:
                continue
            for j in range(i + 1, len(clusters)):
                if clusters[j].size() > 3:
                    continue
                if _entity_overlap(clusters[i], clusters[j], entity_map) >= ENTITY_THRESHOLD:
                    clusters[i].merge(clusters[j])
                    clusters.pop(j)
                    changed = True
                    break
            if changed:
                break
    return clusters
```

### MMR representative selection

```python
def pick_representatives(cluster: Cluster, max_reps: int = 3) -> list[Item]:
    """Maximal Marginal Relevance: balance relevance vs diversity."""
    if cluster.size() <= max_reps:
        return cluster.items

    selected = [cluster.items[0]]   # always include highest-scored item
    candidates = cluster.items[1:]

    while len(selected) < max_reps and candidates:
        best_idx, best_score = -1, -float("inf")
        for i, cand in enumerate(candidates):
            relevance = cand.rrf_score                        # from fusion step
            max_sim = max(_text_similarity(cand, s) for s in selected)
            mmr = 0.7 * relevance - 0.3 * max_sim            # lambda = 0.7
            if mmr > best_score:
                best_score, best_idx = mmr, i
        selected.append(candidates.pop(best_idx))

    return selected
```

### Safeguards

```python
SAFEGUARDS = {
    "no_same_source_merge": True,          # enforced in Pass 1 via _same_source()
    "polymarket_isolated": True,           # Polymarket items never merged with others
    "single_source_flag": True,            # cluster.is_single_source → flag in output
    "thin_evidence_flag": True,            # cluster.size() == 1 → flag "thin evidence"
}

def _same_source(item: Item, cluster: Cluster) -> bool:
    return any(item.source == existing.source for existing in cluster.items)
```

## Data Contracts

```python
@dataclass
class Cluster:
    items: list[Item]
    is_single_source: bool = False
    is_thin_evidence: bool = False
    representatives: list[Item] = field(default_factory=list)

# Pipeline output
clusters: list[Cluster]    # sorted by cluster.representatives[0].rrf_score desc
```

## Dependencies & Assumptions
- `Item.rrf_score` populated by the fusion step before clustering
- `Item.source` is a stable string identifier (e.g. "reddit", "hackernews")
- `entity_map: dict[str, list[str]]` from the entity-resolution step for Pass 2

## To Port This
- [ ] Implement `Cluster` dataclass with `add()`, `merge()`, `centroid()`, `size()`
- [ ] Run Pass 1 on the RRF-merged list (already sorted best-first)
- [ ] Run Pass 2 only on clusters with size ≤ 3 (larger clusters don't need entity help)
- [ ] Call `pick_representatives()` before emitting final output
- [ ] Respect the Polymarket isolation safeguard if you include prediction markets

## Gotchas
- Threshold 0.48 was tuned for English-language news; for technical/code topics
  consider raising to 0.55 to avoid merging unrelated library releases
- `difflib.SequenceMatcher` is O(n²) on large item lists — for >500 items switch to
  TF-IDF cosine or a lightweight embedding model
- Same-source enforcement is critical: Reddit + Reddit merging creates echo-chamber clusters

## Origin (reference only)
Repo: https://github.com/mvanhorn/last30days-skill
Key file: `engine/cluster.py`
