# Multi-Tier Credentials (build spec) — distilled from last30days-skill

## Summary
Three-tier credential system: Tier 1 sources need no auth (keyless); Tier 2 sources use
browser-harvested cookies; Tier 3 sources need explicit API keys from .env. A startup preflight
script validates what's available and degrades gracefully — missing Tier 2/3 credentials
skip those sources rather than crashing. Dual .env hierarchy (project-local beats user-global).

## Core Logic (inlined)

### Tier 1 — Keyless sources

```python
# No credentials required. Sources and fallback order:

KEYLESS_SOURCES = {
    "reddit": [
        "pushshift",          # PRAW fallback 1
        "old.reddit.com",     # fallback 2 (no JS scrape)
        "unddit",             # fallback 3
        "pullpush",           # fallback 4
    ],
    "hackernews": "algolia_api",   # HN Algolia search, no key
    "polymarket": "public_api",    # Polymarket REST, no key
    "github":     "public_api",    # GitHub public search, no key (rate-limited)
}
```

### Tier 2 — Browser cookie auth (X / YouTube)

```python
# credentials/browser_cookies.py

def get_x_cookies() -> dict | None:
    """Try Bird CLI first, then Chrome, then Safari."""
    # Option A: Bird CLI
    result = subprocess.run(["bird", "cookies"], capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)

    # Option B: Chrome cookie db
    try:
        from chrome_cookies import get_cookies
        return get_cookies("x.com")
    except ImportError:
        pass

    # Option C: Safari cookie db
    try:
        from safari_cookies import get_cookies
        return get_cookies("x.com")
    except ImportError:
        pass

    # Option D: xurl wrapper (reads system keychain)
    result = subprocess.run(["xurl", "--dump-cookies"], capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)

    return None   # X source will be skipped

def get_youtube_cookies() -> dict | None:
    """yt-dlp --cookies-from-browser chrome or SSH proxy."""
    ssh_host = os.environ.get("LAST30DAYS_YOUTUBE_SSH_HOST")
    if ssh_host:
        return _fetch_via_ssh(ssh_host)
    result = subprocess.run(
        ["yt-dlp", "--cookies-from-browser", "chrome", "--dump-cookies", "/dev/stdout"],
        capture_output=True, text=True,
    )
    return _parse_netscape_cookies(result.stdout) if result.returncode == 0 else None
```

### Tier 3 — API key sources

```python
# credentials/api_keys.py

API_KEY_SOURCES = {
    "tiktok":    ("SCRAPECREATORS_KEY", "https://api.scrapecreators.com"),
    "instagram": ("SCRAPECREATORS_KEY", "https://api.scrapecreators.com"),
    "threads":   ("SCRAPECREATORS_KEY", "https://api.scrapecreators.com"),
    "pinterest": ("SCRAPECREATORS_KEY", "https://api.scrapecreators.com"),
    "perplexity":("OPENROUTER_KEY",     "https://openrouter.ai/api/v1"),
    "brave":     ("BRAVE_KEY",          "https://api.search.brave.com"),
    "exa":       ("EXA_KEY",            "https://api.exa.ai"),
    "serper":    ("SERPER_KEY",         "https://google.serper.dev"),
}

def get_api_key(service: str) -> str | None:
    env_var, _ = API_KEY_SOURCES[service]
    return os.environ.get(env_var)    # already loaded from .env by preflight
```

### .env hierarchy (dual-file, perms 600)

```python
# credentials/loader.py
import os
from pathlib import Path
from dotenv import load_dotenv

def load_credentials():
    """Project-local beats user-global. Neither file is required."""
    user_env   = Path.home() / ".config" / "last30days" / ".env"
    project_env = Path(".claude") / "last30days.env"

    # Load user-global first (lower precedence)
    if user_env.exists():
        load_dotenv(user_env, override=False)

    # Load project-local second (higher precedence — overrides user-global)
    if project_env.exists():
        load_dotenv(project_env, override=True)

    # Enforce permissions on both files
    for path in [user_env, project_env]:
        if path.exists():
            os.chmod(path, 0o600)
```

### preflight.py startup checks

```python
def run_preflight() -> dict[str, str]:
    """Returns {source: "ok"|"missing"|"degraded"} for all configured sources."""
    results = {}
    for source in ALL_SOURCES:
        tier = SOURCE_TIERS[source]
        if tier == 1:
            results[source] = "ok"       # always available
        elif tier == 2:
            cookies = get_browser_cookies(source)
            results[source] = "ok" if cookies else "missing"
        elif tier == 3:
            key = get_api_key(source)
            results[source] = "ok" if key else "missing"
    return results
```

## Dependencies & Assumptions
- `python-dotenv` for .env loading
- `yt-dlp` for YouTube cookie extraction (optional)
- Bird CLI (`bird`) for X cookie extraction (optional)
- `LAST30DAYS_YOUTUBE_SSH_HOST` env var if using SSH cookie proxy

## To Port This
- [ ] Copy the dual-file `.env` loader with `override=True` for project-local
- [ ] Enforce `chmod 600` on both `.env` files at startup
- [ ] Implement `run_preflight()` and log missing credentials at startup (not crash)
- [ ] Map your sources to tiers; add any new API-key sources to `API_KEY_SOURCES`
- [ ] Handle `LAST30DAYS_YOUTUBE_SSH_HOST` if your deployment runs on a remote host

## Gotchas
- Browser cookie extraction breaks frequently as browsers add anti-extraction protections
- The `override=True` on the project-local load is critical; without it the user-global
  file silently wins
- Never commit `.env` files; add both paths to `.gitignore`
- ScrapeCreators key covers 4 sources (TikTok, Instagram, Threads, Pinterest) —
  a single key expiry breaks all four simultaneously

## Origin (reference only)
Repo: https://github.com/mvanhorn/last30days-skill
Key files: `credentials/loader.py`, `credentials/browser_cookies.py`,
           `credentials/api_keys.py`, `engine/preflight.py`
