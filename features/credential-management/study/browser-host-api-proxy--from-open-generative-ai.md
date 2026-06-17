# Browser→Host API Proxy + Auth Bridge — from [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI)

> Domain: [[_domain]] · Source: https://github.com/Anil-matcha/Open-Generative-AI · NotebookLM: <add link>

## What it does
This is the plumbing that lets a web app talk to a third-party AI service smoothly — sidestepping the browser's cross-site security blocks, attaching the user's API key in the right place, and gracefully popping up a "please enter your key" box the moment a request comes back unauthorized. Crucially, the *same* app code works two ways: in a normal browser it routes through its own server as a middleman, and in the desktop (Electron) version it talks to the AI service directly. One codebase, two delivery modes.

## Why it exists
Browsers refuse to let a page on your domain freely call someone else's API (that's CORS), and you don't want secret keys scattered through front-end code or visible in every network request. Meanwhile this app ships both as a website *and* as a desktop app, which have completely different rules. The job-to-be-done is **"make API calls Just Work in both environments, keep the key handled cleanly, and recover smoothly when auth fails"** — without writing the networking layer twice.

## How it actually works
There are three ideas stacked together:

1. **The middleman (proxy).** In the browser, the app calls *itself* — a path like `/api/...` on its own domain. Its server catches that, copies the request, attaches the user's key, and forwards it to the real AI gateway, then pipes the answer straight back. Because the browser only ever talks to its own domain, there's no cross-site block. And because the key gets attached on the server side of that hop, it's handled in one controlled place instead of sprinkled around. The forwarder is careful: it cleans out a few technical headers that shouldn't be passed along, and it passes the response through as raw bytes so that images and videos (not just text) come back intact.

2. **The environment switch.** A single line decides the mode: if it's running in a real browser, use the `/api` middleman; if it's the desktop or server build, skip the middleman and call the gateway directly (no cross-site rules there to worry about). Same code, different path, chosen automatically.

3. **The auth bridge.** Any request, anywhere in the app, that comes back "unauthorized" (a 401 or 403) shouts a single app-wide signal — like ringing a bell the whole building can hear. A top-level component is always listening for that bell, and when it rings it clears the key and brings up the key-entry box. When the user saves a new key, it's stored in two places on purpose: one the front-end reads, and one (a cookie) the server middleman reads — so both halves of the system stay in sync.

## The non-obvious parts
- **The key is stored on the user's own machine, by design.** This is a "bring your own key" tool — the user pays the gateway with their own account — so keeping the key in local storage and a cookie is convenient and appropriate. The big caveat: this exact setup is the *wrong* way to hide a *company's shared* secret from users, because the cookie is readable by the page. The pattern fits the threat model it was built for; copy it only into the same one.
- **It's an event, not a status check.** Instead of every screen constantly asking "are we still logged in?", failures broadcast a one-time signal that a single listener handles. That decoupling means any of the hundreds of API calls can trigger re-auth without knowing anything about the UI.
- **Raw bytes, not JSON.** Because this app moves images and video, the middleman deliberately forwards the response as bytes and preserves its content type — a detail that's easy to get wrong and that would silently corrupt media if treated as text.
- **Two storage spots for one key.** The split between local-storage (for the browser) and a cookie (for the server middleman) is the quiet glue that makes "browser app with a server helper" work — both sides must see the same key or one of them thinks you're logged out.

## Related
- [[submit-and-poll-generation-client--from-open-generative-ai]] — every request it makes flows through this proxy and trips this auth bridge on 401/403.
- [[multi-studio-shell-architecture--from-open-generative-ai]] — the shell is the top-level listener that catches the auth event and shows the key modal.
- See also: [[byok-proxy--from-open-design]] and [[multi-tier-credentials--from-last30days-skill]] — other bring-your-own-key and credential-threading designs to compare against.
