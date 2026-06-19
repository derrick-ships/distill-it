# Domain: browser-automation

Driving a real Chromium browser programmatically over the Chrome DevTools Protocol (CDP): launching or connecting to a browser, managing tabs and pages, capturing screenshots and page state, evading bot detection, and routing through proxies — the substrate an AI browser agent stands on.

## What this domain is about

An AI agent that "uses a browser" needs a reliable, controllable browser underneath it. That means: a way to launch Chromium (or connect to an already-running one, local or cloud), a clean configuration surface for every launch/connect/context option, robust tab and session tracking that survives crashes and reconnects, fast page-state capture (screenshot + DOM), and the unglamorous but essential anti-bot and proxy plumbing that lets the agent reach real sites without being blocked. This domain is distinct from web-extraction (which turns a page into clean content) — here the concern is *controlling the browser itself*, not interpreting what's on the page.

## Common patterns

- **CDP-first, not Playwright-first**: talk to Chrome directly over the DevTools Protocol WebSocket; use Playwright (if at all) only to locate/install a Chromium binary.
- **Config as one model**: a single profile object holds launch args, context options, proxy, stealth flags, and navigation policy.
- **Event-driven watchdogs**: discrete responsibilities (screenshots, DOM, storage, security, permissions, captcha) each subscribe to a browser event bus instead of one monolithic session class.
- **Flags-based stealth**: hide automation fingerprints through Chrome launch flags rather than runtime JS patching.
- **Two-layer proxy**: a launch flag for traffic routing plus a CDP `Fetch.authRequired` interceptor for authenticated proxies.

## Features in this domain

- [[browser-session-stealth--from-browser-use]] — CDP-based session management (launch/connect/cloud), a unified `BrowserProfile` config, an event-bus watchdog architecture, flags-only anti-bot stealth, externally-signalled CAPTCHA waiting, two-layer proxy auth, storage-state persistence, and keep-alive/auto-reconnect.

## Cross-domain links
- [[indexed-dom-serialization--from-browser-use]] (web-extraction) — the DOM watchdog here triggers that capture; this domain owns the CDP connection it runs on.
- [[agent-loop-recovery--from-browser-use]] (agent-architecture) — consumes `get_browser_state_summary()` (screenshot + DOM) from this layer each step and relies on its reconnect tolerance.
- See also [[agentic-browser-actions--from-firecrawl]] (web-extraction) — a hosted-browser alternative for interacting with JS-gated pages.
