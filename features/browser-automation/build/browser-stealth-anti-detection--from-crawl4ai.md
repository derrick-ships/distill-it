# Browser Stealth & Anti-Detection (build spec) — distilled from crawl4ai

## Summary

Multi-layer bot-detection bypass built into crawl4ai's `BrowserConfig`. Layers: playwright-stealth JS patching, patchright undetected Chrome mode, randomized user agents, session persistence, proxy rotation with sticky sessions, and post-load block detection with automatic retry.

## Core logic (inlined)

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.async_configs import ProxyConfig, RoundRobinProxyStrategy

# Full stealth configuration
browser_config = BrowserConfig(
    # Layer 1: JS-level stealth patching
    enable_stealth=True,          # applies playwright-stealth

    # Layer 2: Undetected Chrome (TLS + native-level patches)
    browser_mode="dedicated",     # uses patchright instead of stock Playwright
    # (or: use_managed_browser=True for CDP-based advanced control)

    # Layer 3: Randomized user agent
    user_agent_mode="random",     # picks realistic UA from fake-useragent DB
    # Or explicit:
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",

    # Layer 4: Session persistence
    user_data_dir="/tmp/crawl4ai-profile",
    use_persistent_context=True,
    # Or pre-load cookies:
    cookies=[
        {"name": "session_id", "value": "abc123", "domain": ".example.com"}
    ],
    # Or full storage state (cookies + localStorage):
    storage_state="/path/to/storage_state.json",  # Playwright format

    # Layer 5: Proxy
    proxy_config=ProxyConfig(
        server="http://proxy.example.com:8080",
        username="user",
        password="pass",
    ),

    # Other anti-detection helpers
    headless=True,
    viewport_width=1920,
    viewport_height=1080,
    device_scale_factor=1.0,
    headers={"Accept-Language": "en-US,en;q=0.9"},

    # Init scripts run on every new page context
    init_scripts=[
        # Example: disable webdriver detection
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
    ],
)

# Proxy rotation for batch crawling (Layers 5+6)
proxies = [
    ProxyConfig(server="http://p1.example.com:8080", username="u", password="p"),
    ProxyConfig(server="http://p2.example.com:8080", username="u", password="p"),
]
rotation = RoundRobinProxyStrategy(proxies)

run_config = CrawlerRunConfig(
    proxy_rotation_strategy=rotation,
    proxy_session_id="user-session-1",  # sticky: same proxy reused per session
    proxy_session_ttl=3600,             # session expires after 1 hour
    max_retries=3,                      # retry with next proxy if blocked
    fallback_fetch_function=None,       # last resort: custom async fetch handler
)

async with AsyncWebCrawler(config=browser_config) as crawler:
    result = await crawler.arun("https://target.example.com", config=run_config)
    if not result.success:
        print(f"Failed: {result.error_message}")  # check if blocked
```

**Block detection logic (simplified from source):**
```python
def is_blocked(status_code: int, html: str) -> tuple[bool, str]:
    # HTTP-level signals
    if status_code in (403, 429, 503):
        return True, f"HTTP {status_code}"
    # HTML-level signals
    block_patterns = [
        r"cloudflare.*challenge",
        r"are you a human",
        r"captcha",
        r"access denied",
        r"bot detection",
        r"automated.*traffic",
    ]
    for pattern in block_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return True, f"pattern: {pattern}"
    return False, ""
```

**Extracting storage state from existing session (run once manually):**
```python
# Use Playwright directly to log in and save state
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=False)  # headless=False to log in
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto("https://example.com/login")
    # ... perform login manually ...
    await context.storage_state(path="storage_state.json")
    await browser.close()
# Then pass storage_state="storage_state.json" to BrowserConfig
```

## Data contracts

**ProxyConfig:**
```python
ProxyConfig(
    server: str,          # "http://host:port" or "socks5://host:port"
    username: str = None,
    password: str = None,
)
```

**RoundRobinProxyStrategy methods:**
```python
async def get_next_proxy() -> ProxyConfig
async def get_proxy_for_session(session_id: str, ttl: int) -> ProxyConfig
async def release_session(session_id: str) -> None
```

**CrawlResult fields relevant to anti-detection:**
```python
result.success          # bool — False if blocked or network error
result.status_code      # int — HTTP response code
result.error_message    # str — includes block reason if detected
result.session_id       # str — which session/proxy was used
result.crawl_stats      # dict — attempts, proxies_tried, final_resolution
```

## Dependencies & assumptions

- `playwright` — core browser engine
- `patchright` — undetected Chrome fork (optional but recommended for heavy sites)
- `playwright-stealth` — JS patching library
- `fake-useragent` — realistic UA database
- Proxies: external service required (residential proxies for best results)

## To port this, you need:
- [ ] Install: `pip install crawl4ai patchright playwright-stealth`
- [ ] Run: `playwright install chromium && patchright install chromium`
- [ ] Choose stealth level: `enable_stealth=True` (light) vs `browser_mode="dedicated"` (heavy)
- [ ] For session auth: extract `storage_state.json` from a real logged-in browser session
- [ ] For proxy rotation: instantiate `RoundRobinProxyStrategy` with your proxy list
- [ ] Test against your target site with `verbose=True` to see detection signals
- [ ] Check `result.crawl_stats["resolution_method"]` to see how each crawl succeeded

## Gotchas

**`browser_mode="dedicated"` uses patchright, not stock Playwright.** Some Playwright APIs may behave slightly differently. Test your custom hooks and `init_scripts` under patchright.

**Headless browsers are still more detectable than headful.** For the hardest targets, run `headless=False` with a visible browser — the rendering pipeline differences are a strong signal to detectors. In cloud environments, use `Xvfb` to fake a display.

**User agent must match the actual browser version.** If Playwright is Chrome 122 but your UA says Chrome 110, fingerprint checks will catch the mismatch. Use `user_agent_mode="random"` with type-matched generation, or manually check the installed Playwright browser version and set the UA accordingly.

**Proxy rotation does NOT prevent IP-based behavioral correlation.** If a site tracks behavior (e.g., session cookies) and you switch proxies mid-session, it may flag the IP switch. Use `proxy_session_id` for session-level stickiness.

**`max_retries=3` retries with different proxies, not the same proxy.** Each retry exhausts the next proxy in rotation. If you have 2 proxies and `max_retries=3`, the second proxy gets tried twice.

## Origin (reference only)
- Repo: https://github.com/unclecode/crawl4ai
- Key files: `crawl4ai/async_configs.py`, `crawl4ai/browser_config.py`, `crawl4ai/async_webcrawler.py`
