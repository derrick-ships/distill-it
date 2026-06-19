# Keyless & x402 Paid Access — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

Two ways to use the API without a normal account. **Keyless**: an anonymous caller (identified by IP)
gets a small free daily allowance — a few requests / a few credits — before being asked to sign up.
**x402**: an agent can *pay per call* on the spot using the HTTP 402 "Payment Required" protocol,
settling a small crypto payment per request instead of holding an account.

## Why it exists

Both lower the barrier for the two audiences firecrawl cares about: humans trying it for the first time
(keyless = instant, no signup) and autonomous agents that need to buy data on demand (x402 = machine-native
micropayments). It's growth and agent-commerce, expressed as access tiers on top of the same metering.

## How it actually works

**Keyless.** A request with no API key is mapped to a synthetic team derived from its IP —
`preview_keyless_{ip}`, with a deterministic UUID (so it has a stable team identity without a row in the
users table). There are two daily limits, *both* configurable via env (`KEYLESS_REQUESTS_PER_DAY`,
`KEYLESS_CREDITS_PER_DAY`), and the whole tier is **off unless both are set** — even setting them to 0 is
a deliberate "configured." On each request the controller projects the cost, **reserves** that many
keyless credits up front (a Redis counter), runs the work, then **reconciles** to the real cost
afterward (refunding the difference). If the IP is out of allowance it returns a 429 with a friendly
"sign up for a free key" message — even tailored for agents (pointing at an auth URL). A separate
internal endpoint lets the hosted MCP proxy *check eligibility* for an IP at connect time without
spending quota, gated by a shared secret.

**x402.** Firecrawl wires the `@x402/express` resource-server: it advertises a price, and a paying client
attaches a signed EVM payment (the "exact" scheme) that a **facilitator** (default `x402.org/facilitator`)
verifies and settles on a network (default `base-sepolia`, configurable). It's enabled only when a
`X402_PAY_TO_ADDRESS` is set. The x402 search controller is essentially the normal search flow behind a
payment wall, with small routing tweaks (e.g. small jobs go straight to BullMQ when `price_credits` is
low).

## The non-obvious parts

- **Keyless identity is just the IP**, hashed into a stable synthetic team — no DB row, but consistent
  metering. Clever, and it means the rate limit is per-IP.
- **Reserve-then-reconcile**, not charge-after. Cost is projected and held *before* work so a keyless
  caller can't overspend mid-request; the real cost is trued-up afterward.
- **The tier is off by default** and only "on" when *both* limits are explicitly configured — safe
  default, no accidental free service.
- **Agent-aware 429** — the "out of quota" message includes an agent-friendly auth URL, because the
  intended caller might be an LLM, not a human.
- **x402 is real crypto micropayments** via a pluggable facilitator + network, not a metaphor — pay-per-
  call settled on an EVM chain.
- **Both are thin shells over the same metering** ([[credit-billing-and-concurrency--from-firecrawl]]) —
  they're *access/identity* layers, not separate billing engines.

## Related
- [[credit-billing-and-concurrency--from-firecrawl]] (keyless reserve/reconcile and x402 both feed the same credit metering)
- [[web-search-with-scrape--from-firecrawl]] (the x402 search controller is this flow behind a payment wall)
- [[multi-tier-credentials--from-last30days-skill]] (the same "keyless → free key → paid" tiering idea, client-side)
