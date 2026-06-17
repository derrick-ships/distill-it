# BYOK Proxy — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

BYOK (Bring Your Own Key) is how Open Design routes AI API calls through your own provider credentials instead of a managed account. You bring your Anthropic, OpenAI, Azure, Google, Ollama, or SenseAudio API key; the app's local daemon acts as a streaming proxy between the web UI and those providers.

## Why it exists

Two reasons: cost control and privacy. If you have enterprise agreements with Anthropic or OpenAI, using BYOK means you're paying your negotiated rate (not Open Design's markup) and your prompts go directly to the provider without passing through Open Design's servers. For teams with data sovereignty requirements, local-proxied API calls stay on your network.

## How it actually works

The daemon exposes a proxy endpoint for each supported provider:
```
POST /api/proxy/anthropic/stream
POST /api/proxy/openai/stream
POST /api/proxy/azure/stream
POST /api/proxy/google/stream
POST /api/proxy/ollama/stream
POST /api/proxy/senseaudio/stream
```

Each endpoint accepts the provider's base URL, your API key, the model ID, and the messages array. You pass the API key directly in the request body (not in a header). The daemon forwards the request to the actual provider, then streams the response back using Server-Sent Events.

The stream emits four event types:
- **start** — optional model confirmation
- **delta** — incremental text chunks as the model responds
- **error** — something went wrong
- **end** — done, with optional HTTP status code

One important safety feature: the proxy blocks SSRF attacks by refusing to forward requests to internal IP addresses, link-local addresses, or CGNAT ranges. This prevents the "prompt my app to call my internal network" attack.

Ollama support means you can run the whole thing offline — Ollama serves local models and the proxy treats it exactly like any other provider.

## The non-obvious parts

**API keys travel in the request body.** They're not stored as environment variables or in a config file by default — the client passes the key each time. Whether keys get persisted to the local SQLite database for convenience is not confirmed in the public code.

**SenseAudio is a separate provider** specifically for audio generation — not for LLM chat. It appears alongside the text providers because the proxy is unified, but it serves a different purpose.

**The proxy is not an LLM gateway with caching or rate limiting.** It's a thin streaming relay. Don't expect cache headers, request deduplication, or quota management from the proxy layer itself.

## Related

- [[local-first-architecture--from-open-design]] (the daemon that hosts this proxy)
- [[design-artifact-generation--from-open-design]] (image/video generation also routes through provider APIs)
