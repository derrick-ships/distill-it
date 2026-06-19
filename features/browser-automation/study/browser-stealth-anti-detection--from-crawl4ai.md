# Browser Stealth & Anti-Detection — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

crawl4ai provides a multi-layer anti-detection system to bypass bot-blocking mechanisms on websites. It combines playwright-stealth patching (which hides Playwright's fingerprint), patchright integration (an "undetected" Playwright fork), proxy rotation, randomized user agents, session persistence, and adaptive retry logic that switches proxies when detection is suspected.

## Why it exists

Modern websites deploy sophisticated bot detection: they check WebDriver properties, canvas fingerprints, timing patterns, TLS fingerprints, and behavioral signals. A plain Playwright browser fails these checks and gets blocked on sites like LinkedIn, Amazon, Cloudflare-protected pages, and many news sites. crawl4ai builds the countermeasures into the framework so callers don't have to implement them per-site.

## How it actually works

**Layer 1 — Playwright-stealth:** When `enable_stealth=True` is set in `BrowserConfig`, crawl4ai applies `playwright-stealth` to the browser context. This patches ~20 JavaScript properties that reveal Playwright's identity: it fakes `navigator.webdriver`, patches `navigator.plugins` and `navigator.languages`, spoofs `chrome` object presence, normalizes `window.screen` values, and removes automation-specific APIs. Applied at context creation, before any page loads.

**Layer 2 — Patchright (undetected Chrome):** When `browser_mode="dedicated"` or the patchright adapter is selected, crawl4ai uses `patchright` instead of stock Playwright. Patchright is a fork that patches Chrome at a lower level — it fixes the TLS fingerprint (matching real Chrome's JA3/JA4 hash), removes process-level automation flags, and patches C++-level browser APIs that JavaScript can't reach. Harder to detect than playwright-stealth alone.

**Layer 3 — User agent randomization:** `user_agent_mode="random"` combined with `user_agent_generator_config` uses `fake-useragent` to pick a realistic, platform-matched UA string (real Chrome UAs from a live database, not hardcoded strings). The UA matches the browser type to avoid mismatches (e.g., a Chrome 120 UA on a browser reporting Chrome 121 in headers would be flagged).

**Layer 4 — Session persistence:** `user_data_dir` + `use_persistent_context=True` stores browser profile data between runs (cookies, localStorage, IndexedDB, cache). This lets the crawler build a "history" that makes it look like a returning human user. Combined with pre-loaded cookies (`BrowserConfig.cookies`), sessions can be pre-seeded with logged-in state.

**Layer 5 — Proxy rotation:** `ProxyConfig` defines a proxy server, and `ProxyRotationStrategy` (e.g., `RoundRobinProxyStrategy`) cycles through a list. Each failed request rotates to the next proxy. `proxy_session_id` enables sticky sessions — the same proxy is used for a given session identifier, useful for sites that track IP switching. `proxy_session_ttl` sets how long a sticky session survives before auto-release.

**Layer 6 — Detection recognition and retry:** After every page load, `is_blocked(status_code, html)` analyzes whether the response looks like a block page: HTTP 403/429/503, CAPTCHA-presence signals, and known block-page HTML patterns (Cloudflare challenge, bot-detection strings). If blocked, the crawler logs it and retries with the next proxy in rotation.

**Layer 7 — Behavioral human-mimicry via `init_scripts`.** `BrowserConfig.init_scripts` runs arbitrary JavaScript on every new page context. This is where you can inject mouse-movement simulation, scroll behavior, or timing randomization that makes the browser behave more like a human.

## The non-obvious parts

**`enable_stealth` alone is not enough for heavy-duty sites.** playwright-stealth patches JS properties, but modern detectors also check TLS fingerprints (at the network layer) and behavioral signals. For Cloudflare-protected sites, you need patchright (`browser_mode="dedicated"`) in addition to JS patching.

**Cookie pre-loading doesn't solve login walls.** `BrowserConfig.cookies` can inject authentication cookies for sites you're already logged into (you extract them from your real browser). But for sites requiring captcha on first login, you still need human intervention or third-party captcha solving.

**`storage_state` is more powerful than `cookies`.** Setting `storage_state` to a JSON export from Playwright (`context.storage_state()`) captures cookies, localStorage, AND sessionStorage in one object. This is the correct way to "clone" a logged-in browser state.

**Proxy session stickiness has a performance cost.** When `proxy_session_id` is set, all requests in that session go through the same proxy. If the proxy is slow, you can't rotate away. Balance stickiness (needed for session coherence on some sites) against the ability to escape slow proxies.

## Related
- [[async-web-crawler--from-crawl4ai]] (where stealth config is applied — via BrowserConfig)
- [[dispatcher-concurrency-control--from-crawl4ai]] (proxy rotation integrates with the dispatcher for per-task proxy assignment)
