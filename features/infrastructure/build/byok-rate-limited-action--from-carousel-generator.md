# BYOK + Rate-Limited AI Action (build spec) — distilled from carousel-generator

## Summary
A Next.js server action that fronts an AI call with three ordered gates — **(1) server key must
exist, (2) optional per-IP Upstash sliding-window rate limit (enabled only when Redis env vars are
present), (3) forward to the model** — keeping the secret key server-side. A parallel client hook
holds a user-supplied (BYOK) key for self-hosters. Zero-database, opt-in throttling that's a ~5-line
add to any serverless/edge Next.js app.

## Core logic (inlined)

Server action — `src/app/actions.tsx` (verbatim):

```tsx
"use server";
import { messageRateLimit } from "@/lib/rate-limit";
import { generateCarouselSlides } from "@/lib/langchain";
import { headers } from "next/headers";

export async function generateCarouselSlidesAction(userPrompt: string) {
  if (!process.env.OPENAI_API_KEY) {
    return null;                                   // gate 1: feature unavailable w/o key
  }

  if (process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN) {   // gate 2: opt-in by env
    const ip = headers().get("x-real-ip") ?? "local";
    const rl = await messageRateLimit.limit(ip);
    if (!rl.success) {
      // TODO: Handle returning errors
      return null;                                 // over budget -> silent null
    }
  }

  const generatedSlides = await generateCarouselSlides(  // gate 3: forward, server key
    userPrompt,
    process.env.OPENAI_API_KEY
  );
  return generatedSlides;
}
```

Rate limiter — `src/lib/rate-limit.ts` (verbatim):

```ts
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

const redis = new Redis({
  url: process.env.KV_REST_API_URL || "",
  token: process.env.KV_REST_API_TOKEN || "",
});

export const messageRateLimit = new Ratelimit({
  redis,
  limiter: Ratelimit.slidingWindow(10, "15 m"),   // 10 requests / 15 min, sliding
  analytics: true,
  prefix: "ratelimit:carousel:msg",
});
```

Client BYOK hook — `src/lib/hooks/use-keys.tsx` (verbatim):

```tsx
import { useState } from "react";

export function useKeys() {
  const [apiKey, setApiKey] = useState<string>(
    process.env.NEXT_PUBLIC_OPENAI_KEY || ""       // NEXT_PUBLIC_ => shipped to browser
  );
  return { apiKey, setApiKey };
}
// Edited via an "API keys" dialog (api-keys-dialog.tsx); lets a self-hoster supply their own key.
```

## Data contracts
- **Action input:** `userPrompt: string`. **Output:** generated slides object or `null`.
- **Env (server):** `OPENAI_API_KEY` (required to enable), `KV_REST_API_URL` + `KV_REST_API_TOKEN`
  (both required to enable rate limiting; absence = no limiting).
- **Env (client):** `NEXT_PUBLIC_OPENAI_KEY` (optional seed for BYOK; visible in the browser bundle).
- **Rate limit:** sliding window, **10 req / 15 min**, key = client IP (`x-real-ip` ?? `"local"`),
  Redis key prefix `ratelimit:carousel:msg`. `messageRateLimit.limit(id)` → `{ success, limit,
  remaining, reset }`.

## Dependencies & assumptions
- `@upstash/ratelimit`, `@upstash/redis` (HTTP-based Redis — works on edge/serverless).
- Next.js App Router server actions (`"use server"`) + `next/headers`.
- An Upstash Redis (or Vercel KV, which exposes the same `KV_REST_API_*` vars) for the limit path.
- Swappable: any `limiter` (`slidingWindow`/`fixedWindow`/`tokenBucket`); any key (user id instead of IP).

## To port this, you need:
- [ ] A server-only entry point (server action or API route) so the secret key never ships to the client.
- [ ] An Upstash/Vercel-KV instance + its REST URL & token in env (only if you want throttling).
- [ ] A way to identify callers (IP header, session, or user id) to key the limit.
- [ ] Graceful "feature off" behavior when the key/env is absent (return null/empty, not a 500).

## Gotchas
- **`x-real-ip` is proxy/host-dependent and spoofable**, and NAT/corporate users share an IP — this
  is a cost speed-bump, not security. For real protection key on an authenticated user id.
- **Silent `null` on throttle** = confusing UX (the code admits `// TODO: Handle returning errors`).
  Return a typed `{ error: "rate_limited", reset }` and surface a toast.
- **`NEXT_PUBLIC_OPENAI_KEY` is exposed to the browser** — never put the maintainer's paid key there;
  it's only for a self-hoster's own key. The server action uses the *non-public* `OPENAI_API_KEY`.
- Sliding window > fixed window for avoiding 2×-burst at window edges; keep that choice.
- The limiter module instantiates `Redis` at import with `|| ""` fallbacks — if env is missing it
  constructs a broken client, but the action's `if (KV_*)` guard means `.limit()` is never reached.
  If you call the limiter elsewhere, replicate that guard.
- `analytics: true` writes extra Redis keys (per-day counters) — fine, but it's not free request-wise.

## Origin (reference only)
`src/app/actions.tsx` (gated action), `src/lib/rate-limit.ts` (Upstash limiter),
`src/lib/hooks/use-keys.tsx` + `src/components/api-keys-dialog.tsx` (client BYOK).
Forwards to `src/lib/langchain.ts` (see ai-carousel-generation build spec).
