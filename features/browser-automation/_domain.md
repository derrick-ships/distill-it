# Domain: browser-automation

Controlling real browser instances programmatically — including stealth/anti-detection techniques, session management, proxy routing, and browser profile persistence. Distinct from [[web-scraping]] (which is about traversal strategy) and [[web-extraction]] (which processes HTML). This domain covers the browser-level concerns that determine whether a crawl can reach the page at all.

## Features studied

- [[browser-stealth-anti-detection--from-crawl4ai]] — multi-layer bot-bypass: playwright-stealth JS patching, patchright undetected Chrome mode, randomized user agents, session persistence via storage state, proxy rotation with sticky sessions, and post-load block detection with automatic retry.

## Cross-domain links
- Enables [[web-scraping]] — stealth config is applied via `BrowserConfig` to the `AsyncWebCrawler`.
- Related to [[credential-management]] — session persistence and cookie injection overlap with authentication credential handling.
