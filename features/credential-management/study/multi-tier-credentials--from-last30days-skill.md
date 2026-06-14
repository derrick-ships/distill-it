# Multi-Tier Credential Management — from [last30days-skill](https://github.com/mvanhorn/last30days-skill)

> Domain: [[_domain]] · Source: https://github.com/mvanhorn/last30days-skill · NotebookLM:

## What it does

Manages authentication for 10+ heterogeneous data sources across three tiers: sources that need no credentials (always work), sources that use browser session cookies (free, user already logged in), and sources that require paid API keys. The system reads credentials from a two-location `.env` file hierarchy, checks source availability at startup, and gracefully excludes any source whose credentials are absent — without crashing or requiring the user to configure everything before getting started.

## Why it exists

Different platforms have radically different access models. Reddit and Hacker News have public APIs. X/Twitter requires either scraping browser cookies or an API key. TikTok is only accessible via a paid scraping API. Forcing users to configure all 10+ sources before the tool does anything useful is a massive adoption barrier. The tiered model lets the tool deliver immediate value (Reddit + HN + GitHub + Polymarket) and incrementally unlock richer sources as users add credentials.

## How it actually works

**Tier 1 — Keyless (always available):** Reddit (via public scraping, multiple fallback modules: `reddit_keyless.py`, `reddit_rss.py`, `reddit_shreddit.py`, `reddit_public.py`), Hacker News, Polymarket, GitHub. No configuration required.

**Tier 2 — Browser cookie (free):** X/Twitter and YouTube. The engine extracts cookies from the user's browser using `chrome_cookies.py` or `safari_cookies.py`. Alternatively, X can be accessed via the Bird CLI (a vendored Node.js client at `lib/vendor/bird-search`), the XAI API, or xurl — the engine tries each in order. YouTube uses `yt-dlp`, which handles YouTube's auth via cookies automatically.

**Tier 3 — API key (paid/registered):** TikTok, Instagram, Threads, Pinterest (all via ScrapeCreators API — one key unlocks all four), Perplexity (via OpenRouter), Brave/Exa/Serper (web search backends).

**Credential loading:** `env.get_config()` loads from two locations in priority order:
1. `.claude/last30days.env` in the current project directory (client/project-scoped)
2. `~/.config/last30days/.env` (user-level global)

The project-scoped file takes priority, enabling per-client API key isolation without wrapper scripts. Both files should have permissions `600` on POSIX systems.

**Preflight checking** (`preflight.py`): At engine startup, before planning or retrieval, the engine determines which sources are available. It checks: Is the binary installed? Is the env var present? Can a test connection be made? Sources that fail preflight are excluded from the query plan entirely — they don't show up as errors in output, they simply don't run.

## The non-obvious parts

- Reddit has four fallback scraping strategies (keyless → RSS → shreddit → public). If one is blocked, the engine tries the next. This makes Reddit nearly always available even as Reddit's anti-scraping measures evolve.
- The Bird CLI is a vendored Node.js binary, not a Python package. It handles X's auth complexity without requiring users to manage OAuth flows.
- Per-project `.claude/last30days.env` files are the recommended pattern for agency/consulting use — each client's credentials stay scoped to their folder with no risk of cross-client key exposure.
- `LAST30DAYS_YOUTUBE_SSH_HOST` enables SSH tunnel proxying for YouTube — useful when YouTube is geo-blocked or when the user wants to route traffic through a specific region.

## Related

- [[multi-source-research-engine--from-last30days-skill]] — preflight output feeds Phase 0 source selection
