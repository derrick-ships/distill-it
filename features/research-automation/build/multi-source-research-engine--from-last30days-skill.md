# Multi-Source Research Engine (build spec) — distilled from last30days-skill

## Summary
A parallel retrieval engine that fans out to 6–20 named sources simultaneously using
`ThreadPoolExecutor`, collects structured `Report` objects per source, retries on transient
failures, and emits a unified output in one of five formats. The engine is depth-tiered:
quick/default/deep modes cap the source count and control downstream ranking behavior.

## Core Logic (inlined)

### Entry point

```python
# pipeline.py
from concurrent.futures import ThreadPoolExecutor, as_completed

def run(topic: str, depth: str = "default", emit: str = "compact") -> str:
    sources = _select_sources(depth)        # returns list of source callables
    query_plan = _build_query_plan(topic)   # returns dict with source_weights, queries

    results: dict[str, list] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {pool.submit(_fetch_with_retry, src, topic, query_plan): src.__name__
                   for src in sources}
        for fut in as_completed(futures):
            src_name = futures[fut]
            try:
                results[src_name] = fut.result()
            except Exception as e:
                errors[src_name] = str(e)

    report = Report(
        items_by_source=results,
        errors_by_source=errors,
        query_plan=query_plan,
        topic=topic,
    )
    return _emit(report, fmt=emit)
```

### Depth tiers

| depth  | max sources | ranking behavior |
|--------|-------------|-----------------|
| quick  | 6           | RRF only, no LLM rerank |
| default| 12          | RRF + LLM rerank top-20 |
| deep   | 20          | RRF + LLM rerank top-40, entity pass enabled |

### Retry logic

```python
def _fetch_with_retry(src_callable, topic: str, query_plan: dict) -> list:
    _RATE_LIMIT_SEEN: set[str] = set()   # shared across threads via closure / module-level

    try:
        return src_callable(topic, query_plan)
    except RateLimitError:
        if src_callable.__name__ in _RATE_LIMIT_SEEN:
            raise                         # already retried this source
        _RATE_LIMIT_SEEN.add(src_callable.__name__)
        raise                             # no retry on rate-limit; skip source
    except ServerError:                   # 5xx
        time.sleep(3)
        return src_callable(topic, query_plan)   # single retry
```

### Report schema

```python
@dataclass
class Report:
    items_by_source: dict[str, list[Item]]   # source_name → raw items
    errors_by_source: dict[str, str]         # source_name → error message
    query_plan: dict                         # {queries, source_weights, artifacts}
    topic: str
    artifacts: list[str] = field(default_factory=list)  # file paths for deep mode
```

### Emit formats

| fmt     | description |
|---------|-------------|
| compact | Merged ranked bullet list, no source attribution |
| json    | Full Report as JSON (for downstream piping) |
| context | Compact + entity resolution block for LLM context injection |
| md      | Markdown with per-source sections |
| html    | Styled HTML brief |

## Dependencies & Assumptions
- Python 3.11+ (ThreadPoolExecutor, match statements)
- Source adapters must accept `(topic: str, query_plan: dict)` and return `list[Item]`
- `Item` must implement `canonical_id() -> str` for deduplication

## To Port This
- [ ] Define the `Item` and `Report` dataclasses
- [ ] Implement at least 3 source adapters conforming to the callable signature
- [ ] Choose an LLM provider for `llm_call()` (OpenRouter, OpenAI, local)
- [ ] Wire `_select_sources(depth)` to your source registry
- [ ] Implement all 5 emit formats or drop to the ones you need

## Gotchas
- Rate-limit dedup set must be thread-safe (module-level or use `threading.Lock`)
- `as_completed` returns futures in completion order — don't assume source order
- The 3s sleep before 5xx retry blocks the thread; acceptable for ≤20 sources

## Origin (reference only)
Repo: https://github.com/mvanhorn/last30days-skill
Key files: `engine/pipeline.py`, `engine/schema.py`, `engine/emit.py`
