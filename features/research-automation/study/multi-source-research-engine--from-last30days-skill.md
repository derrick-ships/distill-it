# Multi-Source Parallel Research Engine — from [last30days-skill](https://github.com/mvanhorn/last30days-skill)

> Domain: [[_domain]] · Source: https://github.com/mvanhorn/last30days-skill · NotebookLM:

## What it does

A Python engine (`last30days.py` + `lib/pipeline.py`) that simultaneously queries Reddit, X/Twitter, YouTube, TikTok, Hacker News, Polymarket, GitHub, Instagram, Threads, Bluesky, and Pinterest — then normalizes, deduplicates, ranks, and clusters all results into a unified research report. You give it a topic; it gives back a structured `Report` with the top findings across all sources weighted by real engagement signals.

## Why it exists

Each platform is a walled garden. Google doesn't index Reddit comments or X threads. ChatGPT can read Reddit but not X. No single source captures the full picture of what people are actually discussing. The engine exists to unify these gardens into one pass — and to rank by authentic engagement (upvotes, views, betting odds) rather than SEO or editorial authority.

## How it actually works

**Phase 0 — Preflight:** The engine checks which sources are available based on installed tools and present credentials. Reddit/HN/Polymarket/GitHub always pass. X requires Bird CLI, XAI API key, or xurl. YouTube requires `yt-dlp`. TikTok/Instagram require ScrapeCreators API key. Sources that fail preflight are excluded from planning.

**Phase 0.55 — Entity resolution:** Before any search, `resolve.auto_resolve()` identifies relevant handles, subreddits, and GitHub repos for named entities. See [[entity-resolution--from-last30days-skill]].

**Phase 0.75 — Query planning:** A planner generates per-source subqueries tailored to each platform's search semantics (e.g., Reddit uses subreddit-scoped queries; X uses handle-targeted queries from resolution).

**Phase 1 — Parallel retrieval:** A `ThreadPoolExecutor` submits one task per (subquery, source) pair. Each source module returns normalized result items. A thread-safe set tracks rate-limited sources — once one task hits a 429, all pending tasks for that source are skipped. 5xx errors trigger one automatic retry after 3 seconds.

**Depth tiers** control how many results per stream: quick=6, default=12, deep=20.

**Phase 2 — Supplemental search:** After Phase 1, the engine extracts notable entities (handles, subreddits) from the Phase 1 results and runs targeted follow-up queries on those specific entities.

**Phase 2b — Retry:** Sources that returned fewer than 3 items get one more attempt with a simplified, core-subject-only query.

**Post-retrieval:** Results are normalized across sources, annotated with relevance signals, pruned for quality, deduplicated, clustered (see [[cross-source-clustering--from-last30days-skill]]), and ranked (see [[engagement-signal-ranking--from-last30days-skill]]).

**Output:** A `schema.Report` object containing `items_by_source`, `errors_by_source`, `query_plan`, and `artifacts`. Emitted as JSON, Markdown, compact text, HTML brief, or context format for LLM consumption.

## The non-obvious parts

- The two-phase retrieval exists because Phase 1 discovers entities you didn't know to search for. Phase 2 exploits those discoveries. A single-phase approach misses the second layer.
- Rate-limit detection is cross-future: a 429 from one concurrent task immediately prevents other pending tasks for the same source from firing, saving wasted API calls.
- `--mock` mode replays fixture data without hitting live APIs — essential for testing without burning API quota.
- The engine is invoked by the LLM skill layer; the model passes arguments and receives stdout. The engine never calls back into the LLM.

## Related

- [[entity-resolution--from-last30days-skill]] — Phase 0.55 pre-search resolution
- [[engagement-signal-ranking--from-last30days-skill]] — post-retrieval ranking
- [[cross-source-clustering--from-last30days-skill]] — post-retrieval deduplication
- [[multi-tier-credentials--from-last30days-skill]] — preflight credential check
- [[agent-output-contract--from-last30days-skill]] — how the LLM layer presents the engine's output
