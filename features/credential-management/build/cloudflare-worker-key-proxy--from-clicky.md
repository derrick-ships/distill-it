# Cloudflare Worker API-Key Proxy (build spec) — distilled from clicky

## Summary
A single-file Cloudflare Worker (`clicky-proxy`) that hides upstream API keys from a native client by relaying its requests to Anthropic, ElevenLabs, and AssemblyAI. Keys live as Worker secrets. Three POST routes: `/chat` (Claude Messages, SSE stream pass-through), `/tts` (ElevenLabs TTS, MP3 stream pass-through), `/transcribe-token` (broker a short-lived AssemblyAI streaming token to the client). No CORS, no client-to-worker auth, no rate-limiting.

## Core logic (inlined)

### `worker/wrangler.toml`
```toml
name = "clicky-proxy"
main = "src/index.ts"
compatibility_date = "2024-01-01"

[vars]
ELEVENLABS_VOICE_ID = "kPzsL2i3teMYv0FxEYQ6"
```
No `routes` block → deploys to `https://clicky-proxy.<subdomain>.workers.dev`.

### `worker/package.json`
```json
{
  "name": "clicky-proxy",
  "private": true,
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy"
  },
  "devDependencies": {
    "wrangler": "^3.0.0"
  }
}
```

### `worker/src/index.ts` (verbatim)
```typescript
/**
 * Clicky Proxy Worker
 *
 * Proxies requests to Claude and ElevenLabs APIs so the app never
 * ships with raw API keys. Keys are stored as Cloudflare secrets.
 *
 * Routes:
 *   POST /chat  → Anthropic Messages API (streaming)
 *   POST /tts   → ElevenLabs TTS API
 */

interface Env {
  ANTHROPIC_API_KEY: string;
  ELEVENLABS_API_KEY: string;
  ELEVENLABS_VOICE_ID: string;
  ASSEMBLYAI_API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    try {
      if (url.pathname === "/chat") {
        return await handleChat(request, env);
      }

      if (url.pathname === "/tts") {
        return await handleTTS(request, env);
      }

      if (url.pathname === "/transcribe-token") {
        return await handleTranscribeToken(env);
      }
    } catch (error) {
      console.error(`[${url.pathname}] Unhandled error:`, error);
      return new Response(
        JSON.stringify({ error: String(error) }),
        { status: 500, headers: { "content-type": "application/json" } }
      );
    }

    return new Response("Not found", { status: 404 });
  },
};

async function handleChat(request: Request, env: Env): Promise<Response> {
  const body = await request.text();

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[/chat] Anthropic API error ${response.status}: ${errorBody}`);
    return new Response(errorBody, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }

  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "text/event-stream",
      "cache-control": "no-cache",
    },
  });
}

async function handleTranscribeToken(env: Env): Promise<Response> {
  const response = await fetch(
    "https://streaming.assemblyai.com/v3/token?expires_in_seconds=480",
    {
      method: "GET",
      headers: {
        authorization: env.ASSEMBLYAI_API_KEY,
      },
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[/transcribe-token] AssemblyAI token error ${response.status}: ${errorBody}`);
    return new Response(errorBody, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }

  const data = await response.text();
  return new Response(data, {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

async function handleTTS(request: Request, env: Env): Promise<Response> {
  const body = await request.text();
  const voiceId = env.ELEVENLABS_VOICE_ID;

  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
    {
      method: "POST",
      headers: {
        "xi-api-key": env.ELEVENLABS_API_KEY,
        "content-type": "application/json",
        accept: "audio/mpeg",
      },
      body,
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[/tts] ElevenLabs API error ${response.status}: ${errorBody}`);
    return new Response(errorBody, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }

  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "audio/mpeg",
    },
  });
}
```

## Data contracts

### Route table
| Route | Method | Upstream | Upstream method | Secret/header injected | Request body | Response |
|---|---|---|---|---|---|---|
| `/chat` | POST | `https://api.anthropic.com/v1/messages` | POST | `x-api-key: <ANTHROPIC_API_KEY>` + `anthropic-version: 2023-06-01` + `content-type: application/json` | client's raw text body, passed through unchanged (caller sets model/messages/`stream:true`) | streamed `response.body`, content-type echoed or defaulted to `text/event-stream`, `cache-control: no-cache` |
| `/tts` | POST | `https://api.elevenlabs.io/v1/text-to-speech/${ELEVENLABS_VOICE_ID}` | POST | `xi-api-key: <ELEVENLABS_API_KEY>` + `content-type: application/json` + `accept: audio/mpeg` | client's raw text body, passed through (caller sets `text`, model, voice settings) | streamed `response.body`, content-type echoed or defaulted to `audio/mpeg` |
| `/transcribe-token` | POST (client) → GET (upstream) | `https://streaming.assemblyai.com/v3/token?expires_in_seconds=480` | GET | `authorization: <ASSEMBLYAI_API_KEY>` | none | token JSON, status 200, `content-type: application/json` |
| anything else | — | — | — | — | — | 404 "Not found" |
| non-POST | — | — | — | — | — | 405 "Method not allowed" |

### Env / secrets (the `Env` interface)
- `ANTHROPIC_API_KEY` — secret (`wrangler secret put ANTHROPIC_API_KEY`)
- `ELEVENLABS_API_KEY` — secret (`wrangler secret put ELEVENLABS_API_KEY`)
- `ASSEMBLYAI_API_KEY` — secret (`wrangler secret put ASSEMBLYAI_API_KEY`)
- `ELEVENLABS_VOICE_ID` — plain `[vars]` value in `wrangler.toml` (not secret), default `kPzsL2i3teMYv0FxEYQ6`

### Error contract
Upstream non-2xx → forwards upstream's error body + status, `content-type: application/json`, and logs `[<route>] <Service> API error <status>: <body>`. Any thrown error → `{ "error": "<String(error)>" }` with status 500.

## Dependencies & assumptions
- Cloudflare Workers runtime; `wrangler` ^3.0.0; `compatibility_date = "2024-01-01"`.
- Native (non-browser) client → no CORS needed.
- Client is trusted to format Anthropic and ElevenLabs request JSON correctly; Worker does zero body validation/transformation.
- AssemblyAI token endpoint is the v3 streaming token broker; the client opens the realtime websocket itself using the returned token (480s = 8 min TTL).
- Streaming relies on Cloudflare piping an unread `Response.body` ReadableStream straight through.

## To port this, you need:
- [ ] A Cloudflare account + `wrangler` installed.
- [ ] `wrangler.toml` with `name`, `main`, `compatibility_date`, and `[vars] ELEVENLABS_VOICE_ID` (or your equivalent non-secret config).
- [ ] Set the three secrets: `npx wrangler secret put ANTHROPIC_API_KEY`, `... ASSEMBLYAI_API_KEY`, `... ELEVENLABS_API_KEY`.
- [ ] The single `src/index.ts` above (adapt route names/upstreams/header names per provider).
- [ ] Deploy with `npx wrangler deploy`; capture the printed `*.workers.dev` URL.
- [ ] Point the client at that URL (clicky hardcodes it; search for `clicky-proxy` references in the Swift code; for local dev use `http://localhost:8787` via `npx wrangler dev` + a `worker/.dev.vars` file containing the keys).
- [ ] (RECOMMENDED, not in source) Add a shared-secret/bearer check or Cloudflare Access + rate limiting before going public.
- [ ] (If targeting browsers) Add CORS preflight + `Access-Control-*` response headers.

## Gotchas
- **Streaming is fragile**: success path MUST return `new Response(upstream.body, ...)` without reading the body. Calling `await response.text()`/`.json()` on the upstream in the success path buffers everything and kills SSE (Claude) and audio (ElevenLabs) streaming.
- **No client→Worker auth or rate limit**: the deployed URL is an open relay to your paid APIs. Inherited gap — must be fixed for production.
- **No CORS**: only works for non-browser clients as-is.
- **AssemblyAI header is `authorization` with the raw key** (no `Bearer ` prefix). Anthropic uses `x-api-key` (not `Authorization: Bearer`). ElevenLabs uses `xi-api-key`. Each provider's auth header name differs — easy to get wrong.
- **`/transcribe-token` is GET upstream but the route is reached only via POST** from the client (the top-level guard rejects non-POST). The handler ignores the request body entirely.
- **`anthropic-version: 2023-06-01` is hardcoded** — must stay compatible with whatever Messages API features the client uses.
- **Voice ID is a build-time `[vars]` value**, not per-request — all TTS uses one voice unless you change the config and redeploy.
- **`expires_in_seconds=480`** caps the transcription session window; long sessions need re-fetching a token.
- **Default `workers.dev` deploy** (no `routes`) — fine for a hobby app; add `routes`/custom domain for production stability.

## Origin (reference only)
- Repo: https://github.com/farzaa/clicky
- Files: `worker/wrangler.toml`, `worker/package.json`, `worker/src/index.ts`, root `README.md` (worker deploy section).
- Secrets set via `wrangler secret put`; voice ID via `wrangler.toml [vars]`; deploy via `npx wrangler deploy`; local dev via `npx wrangler dev` + `worker/.dev.vars`.
