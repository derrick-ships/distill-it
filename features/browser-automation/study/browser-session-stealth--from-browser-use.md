# Browser Session & Stealth — from [browser-use](https://github.com/browser-use/browser-use)

> Domain: [[_domain]] · Source: https://github.com/browser-use/browser-use · NotebookLM: <link once added>

## What it does

This is the layer that owns the actual browser. It launches Chromium (or connects to one you already have running, or provisions one in browser-use's cloud), keeps track of every tab, captures screenshots and page state for the agent, hides the tell-tale signs of automation so sites don't block it, routes traffic through proxies (including authenticated ones), persists your cookies and logins between runs, and quietly reconnects if the browser drops. Everything the agent's "hands" do happens through here.

## Why it exists

An AI browser agent is only useful if the browser underneath it is dependable and looks human enough to be let in. Real sites throw up bot detection, CAPTCHAs, proxies, crashes, and authentication walls. This layer is the accumulated answer to all of that — a single, configurable session object that abstracts "give me a working, stealthy, authenticated browser I can drive" so the agent loop can stay focused on reasoning rather than browser plumbing. A notable design stance: browser-use talks to Chrome *directly* over the DevTools Protocol rather than through Playwright's API, which gives it finer control and removes a heavy dependency from the hot path.

## How it actually works

**One config object.** `BrowserProfile` is a big Pydantic model holding everything: connection mode (`cdp_url` to attach, or `use_cloud`), launch options (`headless`, `executable_path`, `channel`, `user_data_dir`, raw `args`), context options (`storage_state`, `viewport`, `user_agent`, `permissions`, `accept_downloads`), proxy settings, stealth flags, and navigation policy (`allowed_domains`, `prohibited_domains`, `block_ip_addresses`, page-load waits). Its `get_args()` method compiles the final Chrome command line: start from ~48 default flags, subtract any you've ignored, add yours, add Docker/headless/security flags conditionally, append extension and proxy and user-agent flags, and merge all the `--disable-features` values into one deduplicated flag so Chrome doesn't ignore duplicates. If you don't give a `user_data_dir`, it auto-creates a fresh temp one — so every session is isolated by default.

**The watchdog architecture.** Rather than one giant session class, `BrowserSession` dispatches events onto an event bus, and a set of **watchdogs** each handle one concern by subscribing to events: a local-browser watchdog (launches the Chromium subprocess), screenshot, DOM, storage-state, security, permissions, popups, downloads, captcha, recording. They auto-register their `on_EventName` handlers. Starting a session fires `BrowserStartEvent`, which attaches all the watchdogs, acquires the browser (cloud / local-launch / existing-CDP), and connects.

**Launching and connecting.** The local-browser watchdog finds a Chromium binary (honoring `executable_path`, then `channel`, then Playwright's bundled cache, then system paths, then `uvx playwright install` as a last resort), picks a free port, launches Chrome with `--remote-debugging-port`, and polls `/json/version` until CDP is ready. Then `connect()` opens a CDP WebSocket (via the `cdp_use` library, not Playwright), turns on auto-attach so new tabs are tracked, discovers existing page targets, and creates an `about:blank` if needed. A `SessionManager` maintains the canonical maps of CDP targets ↔ sessions and recovers focus when the focused tab detaches.

**Getting page state.** When the agent asks for state, a `BrowserStateRequestEvent` fans out: the screenshot watchdog runs `Page.captureScreenshot` (base64 PNG) while the DOM watchdog builds the indexed element tree — in parallel. The result is a `BrowserStateSummary` (DOM state, screenshot, URL, title, tabs, scroll info, errors) that the agent loop consumes each step.

**Stealth — and the surprise.** There's no patchright, no playwright-stealth library, no runtime JavaScript patching of `navigator.webdriver`. Stealth is **entirely Chrome launch flags**: principally `--disable-blink-features=AutomationControlled` plus `AutomationControlled` in `--disable-features`, both aimed at hiding the automation fingerprint, alongside a raft of flags disabling background networking, sync, phishing detection, and update checks. CAPTCHA handling is *external*: a captcha watchdog listens for `BrowserUse.captchaSolverStarted/Finished` CDP events (emitted by a browser-side component in the `cdp_use` library, likely a companion extension/proxy) and simply blocks the agent loop on an async event until the solve finishes or times out.

**Proxies and persistence.** Proxy is two-layer: a `--proxy-server=` launch flag for routing, plus — for authenticated proxies — a CDP `Fetch.authRequired` handler that supplies credentials through Chrome's native proxy-auth flow. The storage-state watchdog loads cookies + localStorage on connect (via `Network.setCookies` and an init script), polls every 30s, and atomically writes changes to a Playwright-format `storage_state.json`. `keep_alive` prevents teardown; a WebSocket-drop callback triggers exponential-backoff auto-reconnect that reuses the same `cdp_url` and restores focus.

## The non-obvious parts

- **No Playwright at runtime.** The entire control path is `cdp_use.CDPClient` over a WebSocket. Playwright is only ever used to *find or install* a Chromium binary — never to drive it. This is the biggest architectural surprise.
- **Stealth is flags-only.** No JS injection, no stealth library. Just `--disable-blink-features=AutomationControlled` and friends. Simple, and it means the "stealth" is exactly as good as those flags — anyone expecting deep fingerprint spoofing will be surprised.
- **The CAPTCHA solver isn't in the Python code.** The library only *waits* (an async event with a ~120s timeout). The actual solving is signalled by a `BrowserUse` CDP domain that lives browser-side — a companion component, not the Python package.
- **Authenticated proxy auth uses CDP `Fetch`, not a local MITM proxy.** Credentials flow through Chrome's native proxy challenge handling, intercepted at the protocol level.
- **`user_data_dir=None` silently means "fresh temp profile."** Every session without an explicit dir is isolated — convenient, but a foot-gun if you expected persistence.
- **`from_system_chrome()`** connects straight to your installed Chrome with your real profile, so the agent can act in already-authenticated sessions without exporting cookies.
- **Watchdog order matters.** The local-browser watchdog must be attached before `connect()` so it can handle the launch event; the storage watchdog must load auth state on `BrowserConnectedEvent` before the agent's first action.

## Related
- [[indexed-dom-serialization--from-browser-use]] — the DOM watchdog here triggers that capture; this layer owns the CDP connection it runs on.
- [[agent-loop-recovery--from-browser-use]] — consumes `get_browser_state_summary()` each step and leans on this layer's reconnect tolerance and captcha-wait.
- [[action-tool-registry--from-browser-use]] — actions receive the `browser_session`/`cdp_client` from here as injected special params.
- See also: [[agentic-browser-actions--from-firecrawl]] (hosted-browser interaction) and [[browser-design-token-extraction--from-ai-website-cloner-template]] (headless Chromium for a different end).
