# Cloudflare Worker API-Key Proxy — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[credential-management]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
Clicky is a macOS app that talks to three paid AI services: Anthropic (Claude, for chat/vision), ElevenLabs (text-to-speech), and AssemblyAI (live speech-to-text). Instead of baking the secret API keys for those services into the shipped Mac app, clicky puts a tiny Cloudflare Worker in the middle. The app sends its requests to the Worker; the Worker attaches the real API keys (which live only on Cloudflare's servers) and forwards the request upstream, then streams the answer back to the app. The keys never leave the server.

The Worker exposes exactly three endpoints:
- `POST /chat` — relays a Claude Messages API call (streams the response back as it arrives).
- `POST /tts` — relays a text-to-speech call to ElevenLabs and streams back MP3 audio.
- `POST /transcribe-token` — fetches a short-lived (8-minute) AssemblyAI streaming token and hands it to the app, so the app can open its own live transcription websocket directly without ever holding the AssemblyAI key.

## Why it exists
Anything shipped inside a downloadable desktop app can be extracted by a determined user — strings in the binary, network inspection, etc. If the Anthropic/ElevenLabs/AssemblyAI keys were embedded in the app, anyone could pull them out and run up the developer's bill. By moving the keys behind a Worker and storing them as Cloudflare "secrets," the app binary contains only the Worker's public URL. The two long-lived secrets (Anthropic, ElevenLabs) are never exposed at all; the AssemblyAI key is exposed only indirectly, as a token that self-expires after eight minutes.

A second reason is convenience: Cloudflare Workers run at the edge, are free at low volume, stream natively, and deploy with a single `wrangler deploy`, so this is a near-zero-maintenance way to add a key-hiding layer.

## How it actually works
The whole Worker is one file. Every request first gets rejected unless it's a `POST` (returns 405). Then the Worker looks at the URL path and routes to one of three handler functions; anything else returns 404. A try/catch around the routing turns any thrown error into a 500 JSON response.

- **/chat**: reads the incoming body as raw text and re-POSTs it unchanged to `https://api.anthropic.com/v1/messages`, adding three headers: `x-api-key` (the secret), `anthropic-version: 2023-06-01`, and `content-type: application/json`. The app is responsible for the actual JSON shape (model, messages, `stream: true`, etc.) — the Worker just passes it through. The crucial trick: the Worker returns `new Response(response.body, ...)`, i.e. it hands back the upstream's *unread* body stream directly. That makes Claude's server-sent-events stream flow through the Worker token-by-token instead of being buffered. It defaults the content-type to `text/event-stream` and sets `cache-control: no-cache`.
- **/tts**: same pattern — reads the body, POSTs it to `https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}` with the `xi-api-key` secret, `content-type: application/json`, and `accept: audio/mpeg`. The voice ID comes from a plain (non-secret) config variable. The MP3 audio body is streamed straight back, defaulting content-type to `audio/mpeg`.
- **/transcribe-token**: takes no body. It does a `GET` to AssemblyAI's `streaming.assemblyai.com/v3/token?expires_in_seconds=480` endpoint with the key in the `authorization` header, and returns the resulting token JSON to the app. The app then connects to AssemblyAI's realtime websocket itself using that temporary token.

On any upstream non-OK response, the handler reads the error body, logs it to the Worker console, and forwards that body and status code back to the app as JSON.

Deployment is: store the three secrets with `wrangler secret put`, set the voice ID in `wrangler.toml`, and `wrangler deploy`. That prints the live `*.workers.dev` URL the app points at.

## The non-obvious parts
- **There is no CORS handling at all.** That's deliberate — the client is a native macOS app, not a browser, so no preflight/`Access-Control-*` headers are needed. If you reuse this for a web client you must add CORS yourself.
- **There is no auth or rate-limiting between the app and the Worker.** The Worker URL is effectively an open, unauthenticated relay to your paid APIs. Anyone who learns the URL can spend your credits. This is a real gap inherited from the source; a serious deployment needs a shared token, Cloudflare Access, or per-IP rate limits.
- **Streaming works because of one line**: `new Response(upstream.body, ...)`. The body is never `await`ed/read in the success path, so Cloudflare pipes it through lazily. Reading it first (e.g. `await response.text()`) would break SSE and audio streaming.
- **The two patterns differ on purpose**: `/chat` and `/tts` are full relays (key stays server-side forever). `/transcribe-token` is a token broker — it hands the client a self-expiring credential so the *client* can open a long-lived websocket the Worker couldn't economically proxy.
- **Two kinds of config**: real keys are Cloudflare *secrets* (`wrangler secret put`, never in the repo); the ElevenLabs voice ID is a plain `[vars]` entry in `wrangler.toml` (not sensitive, checked into source).
- **`compatibility_date = "2024-01-01"`** pins Worker runtime behavior; there are no `routes` configured, so it deploys to the default `workers.dev` subdomain.

## Related
- [[streaming-claude-screen-context--from-clicky]] (the app-side consumer of `/chat` — sends screen context to Claude and reads the SSE stream this Worker proxies)
- [[elevenlabs-streaming-tts--from-clicky]] (the app-side consumer of `/tts` — plays the MP3 audio this Worker streams back)
- [[push-to-talk-streaming-transcription--from-clicky]] (the app-side consumer of `/transcribe-token` — uses the short-lived token to open AssemblyAI's realtime websocket)
