# BYOK + Rate-Limited AI Action — from [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator)

> Domain: [[_domain]] · Source: https://github.com/FranciscoMoretti/carousel-generator · NotebookLM:

## What it does

Lets the app offer "free" AI generation on the hosted demo without getting its OpenAI bill drained,
while still letting self-hosters plug in their own key. A single Next.js server action stands in
front of the AI call: it refuses to run if no key is configured, throttles how often any one visitor
can generate, and only then forwards the request to OpenAI.

## Why it exists

An AI feature exposed to the public internet has two problems: **cost abuse** (anyone can spam
generations on your dime) and **key safety** (you can't ship a secret OpenAI key to the browser).
The hosted demo wants to feel free and instant, but the maintainer can't eat unbounded usage. This
feature is the cheap, no-database guardrail that makes a public AI demo survivable: throttle per
IP, keep the key server-side, and degrade gracefully when limits hit.

## How it actually works

The AI is only ever called from a server action (`"use server"`), so the secret key never reaches
the client. The action runs three gates in order:

1. **Key presence.** If `OPENAI_API_KEY` isn't set in the server env, it returns `null` immediately —
   the feature simply isn't available rather than erroring.
2. **Rate limit (optional, env-gated).** If Upstash Redis credentials are present
   (`KV_REST_API_URL` + `KV_REST_API_TOKEN`), it takes the caller's IP from the `x-real-ip` header
   (falling back to `"local"`) and asks an Upstash rate limiter whether this IP is within budget. The
   limiter is a **sliding window of 10 requests per 15 minutes**, keyed under a prefix. Over budget →
   return `null`. If no Redis creds exist (e.g. local dev or a self-host without Upstash), this whole
   gate is skipped — rate limiting is opt-in by configuration.
3. **Forward to OpenAI.** Only now does it call the generation function with the server's key and
   return the slides.

On the client there's a parallel "bring your own key" path: a small hook holds an API key (seeded
from a public env var, editable via an "API keys" dialog) so a self-hoster can supply their own key
rather than rely on the server's. The hosted, rate-limited server key and the user-supplied key are
two different routes to the same generation function.

## The non-obvious parts

- **Rate limiting is opt-in by env presence, not a hard dependency.** The same code runs locally with
  no Redis (limit skipped) and in production with Upstash (limit enforced). Branching on
  `if (KV_REST_API_URL && KV_REST_API_TOKEN)` makes the guardrail zero-config to disable.
- **Upstash (serverless Redis over HTTP) is the key choice** — it works from edge/serverless
  functions where you can't hold a persistent Redis socket, and it needs no infra to stand up. That's
  what makes "add a rate limit to my Vercel app" a five-line change.
- **Sliding window, not fixed window**, avoids the burst-at-the-boundary problem (where a fixed
  window lets 2× the limit fire across a window edge).
- **IP from `x-real-ip` with a `"local"` fallback** is pragmatic but weak: behind some proxies the
  header is spoofable or shared (NAT/corporate), so the limit is a speed bump, not real auth.
- **Failures return `null`, not errors** — the code even flags `// TODO: Handle returning errors`.
  The UX is "nothing happened" on a throttle, which is a known rough edge.
- **The client key is seeded from `NEXT_PUBLIC_OPENAI_KEY`** — anything `NEXT_PUBLIC_` is shipped to
  the browser, so that path is for self-hosters' own keys, *not* a way to hide the maintainer's key.

## Related

- [[ai-carousel-generation--from-carousel-generator]] — the generation call this action guards
- [[dom-to-pdf-export--from-carousel-generator]] — same repo; the `/api/proxy` edge route is sibling server plumbing
- [[byok-proxy--from-open-design]] — a far richer take: a multi-provider streaming gateway with SSRF protection (this is the lightweight cousin)
- [[multi-tier-credentials--from-last30days-skill]] — another "key from env, fall back gracefully" credential strategy
- See also: any Upstash `@upstash/ratelimit` sliding-window guard on a Next.js route/action
