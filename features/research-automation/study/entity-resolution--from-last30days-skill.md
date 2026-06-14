# Entity Resolution (Pre-Search Step 0.55) — from [last30days-skill](https://github.com/mvanhorn/last30days-skill)

> Domain: [[_domain]] · Source: https://github.com/mvanhorn/last30days-skill · NotebookLM:

## What it does

Before any platform search begins, `resolve.auto_resolve()` takes the raw research topic and identifies the specific people, communities, and repos that are most relevant to it. "Peter Steinberger" becomes `@steipete` on X and `steipete` on GitHub. "React Native" becomes `r/reactnative` and `r/javascript`. The result is a structured dict of targeting hints that the query planner uses to make every platform query more precise.

## Why it exists

Generic keyword searches on platform-specific APIs return poor results. Reddit's search is notoriously bad; X search works best when you already know the handle. The resolution step converts a human topic description into the platform-native identifiers that produce high-signal results. Without it, you'd miss the canonical community for a topic entirely.

## How it actually works

`auto_resolve()` runs four web searches in parallel via `ThreadPoolExecutor`:

1. **Subreddit discovery** — searches for the topic with a Reddit-focused query, then extracts `r/[name]` patterns via regex. Results are lowercased, deduped, and capped at 10 subreddits.

2. **News context** — fetches recent news results to build a 1-2 sentence context summary (capped at 300 characters) about the topic. This context feeds the query planner.

3. **X/Twitter handle identification** — searches for the topic's most associated handles. URL hits (e.g., `twitter.com/steipete`) get 3× weight over plain text mentions. Generic terms ("twitter", "search", "x") are filtered out.

4. **GitHub user/repo detection** — extracts both usernames and `owner/repo` pairs. Canonicalization removes noise: repos with `-action` suffixes are mapped to their base repos unless the topic is explicitly about CI/CD actions.

After parallel search, a **category enhancement** pass classifies the topic (tech, finance, culture, etc.) and merges in peer subreddits from that category that weren't found by web search.

**Output:** A dict with keys `subreddits` (list), `handles` (list), `repos` (list), and `context` (str ≤ 300 chars). This feeds directly into the query planner.

## The non-obvious parts

- Resolution runs on web search results, not platform APIs — it uses whatever web backend is configured (Brave, Exa, Serper, or parallel). This means it works even without Reddit or X credentials.
- URL weighting (3×) for handle detection is the key signal: if `twitter.com/steipete` appears in search results, that's near-certain. A name appearing in text is ambiguous.
- The 10-subreddit cap is deliberate — feeding 20 subreddits to the planner creates too many search tasks and dilutes focus.
- Category-based peer subreddits act as a "long tail" catch: if web search didn't surface `r/iOSProgramming` for an iOS topic, the category classifier still adds it.

## Related

- [[multi-source-research-engine--from-last30days-skill]] — calls auto_resolve() at Step 0.55
