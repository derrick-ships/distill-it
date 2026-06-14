# Entity Resolution (build spec) — distilled from last30days-skill

## Summary
Given a topic string, auto-resolve the canonical social/code/community identities associated
with it by firing 4 parallel web searches and post-processing the results into a structured
dict. The resolved entities are fed into downstream source adapters that need platform-specific
handles (e.g. the Reddit adapter needs a subreddit name, the GitHub adapter needs owner/repo).

## Core Logic (inlined)

```python
# resolve.py
from concurrent.futures import ThreadPoolExecutor
import re

def auto_resolve(topic: str) -> dict:
    """Returns {subreddits, handles, repos, context}."""

    queries = {
        "subreddit": f"reddit.com/r/ {topic} community",
        "news":      f"{topic} latest news",
        "x_handle":  f"site:x.com OR site:twitter.com {topic} official",
        "github":    f"site:github.com {topic} repository",
    }

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {k: pool.submit(_web_search, q) for k, q in queries.items()}
        raw = {k: f.result() for k, f in futures.items()}

    return {
        "subreddits": _parse_subreddits(raw["subreddit"]),
        "handles":    _parse_handles(raw["x_handle"]),
        "repos":      _parse_repos(raw["github"]),
        "context":    _parse_context(raw["news"]),
    }
```

### Subreddit parsing
```python
def _parse_subreddits(text: str) -> list[str]:
    # Regex captures r/word from search snippets
    found = re.findall(r'r/([A-Za-z0-9_]+)', text)
    # Deduplicate preserving order, cap at 10
    seen = set()
    out = []
    for s in found:
        if s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
        if len(out) == 10:
            break
    return out
```

### News context
```python
def _parse_context(text: str) -> str:
    # Truncate to 300 chars — just enough for downstream LLM context injection
    return text.strip()[:300]
```

### X handle parsing (3× URL weight)

```python
def _parse_handles(text: str) -> list[str]:
    # URL-form handles count triple (stronger signal than mention-form)
    url_handles = re.findall(r'(?:x|twitter)\.com/([A-Za-z0-9_]{1,50})(?:/|\s|$)', text)
    mention_handles = re.findall(r'@([A-Za-z0-9_]{1,50})', text)

    scores: dict[str, int] = {}
    for h in url_handles:
        scores[h.lower()] = scores.get(h.lower(), 0) + 3
    for h in mention_handles:
        scores[h.lower()] = scores.get(h.lower(), 0) + 1

    # Sort by score desc, return original-case versions
    case_map = {h.lower(): h for h in url_handles + mention_handles}
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [case_map[k] for k, _ in ranked[:5]]
```

### GitHub repo parsing (-action canonicalization)

```python
def _parse_repos(text: str) -> list[str]:
    found = re.findall(r'github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', text)
    out = []
    seen = set()
    for repo in found:
        # Strip GitHub Actions noise (owner/repo-action → owner/repo)
        canonical = re.sub(r'-action$', '', repo, flags=re.IGNORECASE)
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            out.append(canonical)
    return out[:5]
```

### Category enhancement pass

After the 4 parallel lookups, an optional LLM call enriches the context field with
a category label (e.g. "AI model", "crypto protocol", "media company"). This is a
single cheap call and runs synchronously after the ThreadPoolExecutor closes.

## Data Contracts

```python
# Output of auto_resolve()
{
    "subreddits": ["MachineLearning", "LocalLLaMA"],   # list[str], max 10
    "handles":    ["sama", "ylecun"],                   # list[str], max 5
    "repos":      ["openai/openai-python"],             # list[str] "owner/repo"
    "context":    "OpenAI released ...",                # str, max 300 chars
}
```

## Dependencies & Assumptions
- A `_web_search(query: str) -> str` function returning raw text snippets
- Python `re` and `concurrent.futures` (stdlib only)
- Optional: LLM client for category enhancement pass

## To Port This
- [ ] Wire `_web_search` to your search provider (Brave, Exa, Serper, etc.)
- [ ] Adjust regex caps if your topic space has longer handle/repo names
- [ ] Feed resolved entities into source adapters that need them

## Gotchas
- GitHub Actions repos (`owner/thing-action`) are common false positives; the `-action`
  strip is a heuristic that occasionally removes legitimate repo suffixes
- X handle detection from mentions is noisy; URL-form is more reliable (hence 3× weight)
- Reddit regex finds any `r/word` including navigation links — inspect top results manually
  when testing a new topic domain

## Origin (reference only)
Repo: https://github.com/mvanhorn/last30days-skill
Key file: `engine/resolve.py`
