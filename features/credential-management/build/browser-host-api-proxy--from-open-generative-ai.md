# Browser→Host API Proxy + Auth Bridge (build spec) — distilled from open-generative-ai

## Summary
A same-origin proxy that lets a browser SPA call a third-party API gateway without CORS pain and without the gateway key ever living in client code paths it shouldn't. The browser calls `/api/...` (same origin); a Next.js catch-all route forwards the request to `https://api.muapi.ai/...`, injecting the `x-api-key` and stripping hop-by-hop headers; the raw response (any content type) is streamed back. The *same* client code runs in Electron/SSR by flipping its base URL to the real host (no proxy needed there). A lightweight **auth bridge** completes it: any 401/403 anywhere fires a global DOM event that a top-level component listens for to re-open the API-key modal.

## Core logic (inlined)

**1) The base-URL switch** decides proxy vs. direct, by environment:

```javascript
const BASE_URL = (typeof window !== 'undefined' && window.location?.protocol?.startsWith('http'))
    ? '/api'                       // real browser over http(s) → same-origin proxy route
    : 'https://api.muapi.ai';      // SSR / Electron (file:// or no window) → call gateway directly
```

Why: in a browser, calling the gateway cross-origin triggers CORS and would expose the key in network logs / require it in client config. Routing through `/api` keeps requests same-origin and lets the server attach the key. In Electron there's no CORS sandbox and no shared server, so it calls the gateway directly.

**2) The generic proxy forwarder** (runs server-side) — clean headers, inject key, pass body through, return raw bytes:

```javascript
export async function handleProxyRequest(prefix, path, method, headers, body, apiKey) {
    const url = `${BASE_URL}/${prefix}/${path}`;

    const finalHeaders = new Headers(headers);
    finalHeaders.delete('host');            // hop-by-hop / origin headers must not be forwarded
    finalHeaders.delete('connection');
    finalHeaders.delete('content-length');  // let fetch recompute

    if (apiKey) finalHeaders.set('x-api-key', apiKey);   // the secret is injected HERE, server-side

    const response = await fetch(url, {
        method,
        headers: finalHeaders,
        body: (method !== 'GET' && method !== 'HEAD') ? body : undefined,
        redirect: 'follow',
    });

    const contentType = response.headers.get('Content-Type') || 'application/json';
    const buffer = await response.arrayBuffer();         // works for JSON *and* binary (images/video)
    return { status: response.status, contentType, data: buffer };
}
```

**3) The Next.js route adapter** — turns a framework Request into the generic call, preserving path + query:

```javascript
export async function handleServerSideProxy(prefix, request, params, apiKey) {
    const slug = await params;
    const pathSegments = slug.path || [];
    const path = pathSegments.join('/');

    const method = request.method;
    let body = null;
    if (method !== 'GET' && method !== 'HEAD') {
        body = await request.arrayBuffer();
    }

    const { search } = new URL(request.url);
    const pathWithSearch = search ? `${path}${search}` : path;   // keep ?query intact

    return await handleProxyRequest(prefix, pathWithSearch, method, request.headers, body, apiKey);
}
```

This is wired into a Next.js App Router catch-all route. **Mind the path composition:** the browser `BASE_URL` is `/api`, and the client then appends the gateway's own path `/api/v1/...` (e.g. `submitAndPoll` posts to `` `${BASE_URL}/api/v1/${endpoint}` ``). So the request the browser actually fires is **`/api/api/v1/...`** — the first `/api` is the same-origin *proxy mount*, the rest is the gateway path echoed through. The route file must therefore live at **`app/api/api/v1/[[...path]]/route.js`** (serving `/api/api/v1/...`), with siblings under `app/api/` for the other gateway prefixes the client uses (`app/api/agents/[[...path]]`, `app/api/workflow/[[...path]]`, `app/api/app/[[...path]]`). Each route exports the HTTP verbs, reads the key from the request cookie, and forwards with `prefix='api/v1'` so the upstream URL becomes `https://api.muapi.ai/api/v1/...`. Sketch of the route file:

```javascript
// app/api/api/v1/[[...path]]/route.js   ← note the doubled "api": /api mount + api/v1 gateway path
import { handleServerSideProxy } from 'studio';   // re-exported from packages/studio/src/muapi.js
import { cookies } from 'next/headers';

async function handler(request, { params }) {
    const apiKey = (await cookies()).get('muapi_key')?.value;   // key set by the modal (see below)
    // prefix 'api/v1' is what gets re-prepended to the UPSTREAM url (BASE_URL is the gateway server-side):
    const { status, contentType, data } = await handleServerSideProxy('api/v1', request, params, apiKey);
    return new Response(data, { status, headers: { 'Content-Type': contentType } });
}
export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
```

**4) The auth bridge.** The client never inspects a global auth state; instead, on any 401/403 it broadcasts a DOM event (the dispatcher is shared by every API function and the poller):

```javascript
function notifyAuthRequired(status, detail) {
    if (typeof window === 'undefined') return;          // no-op on server
    if (status !== 401 && status !== 403) return;       // only auth failures
    window.dispatchEvent(new CustomEvent('muapi:auth-required', { detail: { status, message: detail } }));
}
```

A top-level component (the app shell) listens and re-opens the key modal; saving a key writes it to **both** `localStorage` (for the client) **and** a cookie (so the *server-side proxy* can read it):

```javascript
// in the shell:
useEffect(() => {
    const onAuth = () => setApiKey(null);   // dropping the key forces the ApiKeyModal to render
    window.addEventListener('muapi:auth-required', onAuth);
    return () => window.removeEventListener('muapi:auth-required', onAuth);
}, []);

const handleKeySave = useCallback((key) => {
    localStorage.setItem(STORAGE_KEY, key);                                  // client reads this
    setApiKey(key);
    fetchBalance(key);
    document.cookie = `muapi_key=${key}; path=/; max-age=31536000; SameSite=Lax`;  // server proxy reads this
}, [fetchBalance]);
```

## Data contracts
- **Browser → proxy**: any method to `/{prefix}/{...path}?{query}` (e.g. `/api/v1/predictions/abc/result`). No key needed from the browser if the cookie path is used; the client may also pass `x-api-key` directly (the proxy overwrites it).
- **Proxy → gateway**: `{BASE_URL}/{prefix}/{path}` with `x-api-key` set, `host`/`connection`/`content-length` stripped, body forwarded for non-GET/HEAD, `redirect: 'follow'`.
- **Proxy return (internal)**: `{ status, contentType, data: ArrayBuffer }` → wrapped in a `Response(data, { status, headers })`. Binary-safe.
- **Key storage**: `localStorage[STORAGE_KEY]` (client) **and** cookie `muapi_key` (server), kept in sync by `handleKeySave`. Cookie: `path=/`, `max-age=31536000`, `SameSite=Lax`.
- **Auth event**: `CustomEvent('muapi:auth-required', { detail: { status, message } })` on `window`.

## Dependencies & assumptions
- Next.js App Router (catch-all `[[...path]]` routes, `cookies()` from `next/headers`). Any server with a wildcard route + outbound fetch works.
- A browser environment for the client half; an SSR/desktop environment that can reach the gateway directly for the bypass half.
- The gateway authenticates via a single injectable header (`x-api-key`).

## To port this, you need:
- [ ] A same-origin wildcard server route that forwards method, path, query, headers, and body to the upstream.
- [ ] Server-side injection of the secret header so it's added on the server, not baked into client bundles.
- [ ] Hop-by-hop header hygiene (`host`, `connection`, `content-length`) so forwarding doesn't corrupt the request.
- [ ] Binary-safe passthrough (`arrayBuffer`, preserve `Content-Type`) — generated media is not JSON.
- [ ] An environment switch so the same client code calls the proxy in-browser and the upstream directly elsewhere (Electron/SSR/tests).
- [ ] A global "auth required" signal (event/observable) + a top-level listener that drives re-auth UI.
- [ ] Key persisted where *both* readers can see it (client storage for the SPA, cookie/session for the server proxy).

## Gotchas
- **The key lives in `localStorage` AND a cookie, and the cookie is readable JS-side (not `HttpOnly`).** This is a *BYOK convenience proxy*, not a secrecy boundary — the user's own key is on their own machine. Do NOT reuse this pattern to hide a *shared/company* secret from users; for that the key must come from a server env var and never touch the cookie/client. Know which threat model you're in.
- **`SameSite=Lax` + 1-year `max-age`** means the key persists and is sent on top-level navigations. Fine for a single-user desktop-ish app; reconsider lifetime/flags for a shared deployment.
- **Forgetting to strip `content-length`** after the framework already parsed/!rebuilt the body leads to truncated or hung upstream requests. Strip it and let fetch recompute.
- **Don't forward `host`.** Forwarding the original `Host` makes the upstream (or its CDN) reject or misroute the request.
- **`arrayBuffer()` is mandatory for media.** Parsing as JSON/text corrupts images and video. Always pass bytes through and echo the upstream `Content-Type`.
- **The auth bridge is fire-and-forget.** Many concurrent failures fire many events; debounce in the listener or you'll thrash the modal. The dispatcher also no-ops on the server (`typeof window === 'undefined'`), so server-side proxy 401s won't reach the client UI unless the client's own poll also sees a 401 — which it does, since the proxy returns the upstream status.
- **Two routes, two key readers.** If you change where/how the key is stored, update *both* the client (`localStorage`) and the server (`cookie`) paths, or the browser will think it's authed while the proxy sends no key (or vice versa).
- **The doubled `/api` is load-bearing, not a typo.** Because `BASE_URL='/api'` and the client appends the gateway path `/api/v1/...`, the in-browser request is `/api/api/v1/...`. The proxy route must be mounted to match exactly (`app/api/api/v1/[[...path]]`). If you port this and "simplify" the route to `app/api/v1/...`, every generation/poll request 404s in the browser. Either keep the mount aligned with the client's composition, or change the client so `BASE_URL` is `''` (and routes live at `app/api/v1/...`) — but change both sides together.

## Origin (reference only)
`Anil-matcha/Open-Generative-AI` — `packages/studio/src/muapi.js` (`BASE_URL` switch, `handleProxyRequest`, `handleServerSideProxy`, `notifyAuthRequired`); `app/api/api/v1/[[...path]]/route.js` (+ siblings `app/api/agents|workflow|app/[[...path]]/route.js`) — catch-all proxy routes reading the `muapi_key` cookie; note the doubled `api` segment matches the client's `/api` mount + `api/v1` gateway path; `components/StandaloneShell.js` (`handleKeySave`, auth-event listener, key persistence); `components/ApiKeyModal.js` (key entry UI).
