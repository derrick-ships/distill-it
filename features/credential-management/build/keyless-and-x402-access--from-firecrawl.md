# Keyless & x402 Paid Access (build spec) — distilled from firecrawl

## Summary

Two account-less access tiers over the same metering. **Keyless:** anonymous callers identified by IP →
synthetic team `preview_keyless_{ip}` (deterministic UUID); two env-gated daily limits (requests +
credits), tier OFF unless BOTH set; per-request **reserve-then-reconcile** of credits in Redis; 429
(agent-aware) when out. **x402:** HTTP-402 pay-per-call via `@x402/express` resource server + EVM
"exact" scheme settled by a facilitator on a configurable network; enabled only with a pay-to address.

## Core logic (inlined)

### Keyless (`lib/keyless.ts`)

```ts
const KEYLESS_REQUESTS_PER_DAY = config.KEYLESS_REQUESTS_PER_DAY;   // no defaults
const KEYLESS_CREDITS_PER_DAY  = config.KEYLESS_CREDITS_PER_DAY;
export function isKeylessConfigured() {                              // tier ON only if BOTH set (even to 0)
  return typeof KEYLESS_REQUESTS_PER_DAY === "number" && typeof KEYLESS_CREDITS_PER_DAY === "number";
}
const KEYLESS_TEAM_PREFIX = "preview_keyless_";
export function keylessTeamId(ip) { return `${KEYLESS_TEAM_PREFIX}${ip}`; }      // identity = IP
export function keylessTeamUuid(teamId) { /* uuidv5(ip, KEYLESS_TEAM_UUID_NAMESPACE) -> stable team UUID */ }

export const KEYLESS_CREDITS_MESSAGE =
  "You've reached today's limit of free, unauthenticated credits... Sign up for a free API key at " +
  "https://firecrawl.dev ... (If you're an agent, use https://firecrawl.dev/auth.md)";   // agent-aware 429

// reserve-then-reconcile (Redis counters via rate-limit client):
export async function reserveKeylessCredits(teamId, n): Promise<{ok:boolean}> { /* INCRBY day-keyed counter, check <= limit, rollback if over */ }
export async function adjustKeylessCredits(teamId, delta) { /* true-up after real cost known */ }
export async function checkKeylessEligibility(ip) { /* read counters -> {eligible, remaining} WITHOUT spending */ }
```

Controller usage (e.g. search): `projectSearchTotalCredits()` → `reserveKeylessCredits` (429 on fail) →
do work → `adjustKeylessCredits(team, realCost - reserved)` (+ `logKeylessCreditUsage`). On error, refund
the reservation.

### Keyless eligibility endpoint (`controllers/v2/keyless-eligibility.ts`) — for the hosted MCP proxy

```ts
// gated by shared secret; checks an IP's quota WITHOUT consuming it
const secret = req.headers["x-firecrawl-keyless-secret"];
if (!config.KEYLESS_PROXY_SECRET || secret !== config.KEYLESS_PROXY_SECRET) return res.status(401).json({ eligible:false });
const ip = req.headers["x-firecrawl-keyless-ip"] || req.ip;
res.json(await checkKeylessEligibility(ip));   // { eligible, remaining }
```

### x402 (`lib/x402.ts`)

```ts
import { x402ResourceServer as X402ResourceServer } from "@x402/express";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { registerExactEvmScheme } from "@x402/evm/exact/server";

function getX402Network(): Network { return NETWORK_TO_CAIP2[config.X402_NETWORK || "base-sepolia"]; }
export function isX402Enabled() { return !!config.X402_PAY_TO_ADDRESS; }   // enabled only with a pay-to address
export function getX402ResourceServer() {
  const facilitator = new HTTPFacilitatorClient({ url: config.X402_FACILITATOR_URL || "https://x402.org/facilitator" });
  const server = new X402ResourceServer(facilitator);
  registerExactEvmScheme(server, { networks: [getX402Network()], payTo: config.X402_PAY_TO_ADDRESS });
  return server;
}
// x402SearchController = normal search behind the 402 paywall; small jobs:
const directToBullMQ = (req.acuc?.price_credits ?? 0) <= 3000;   // routing tweak
```

## Data contracts

- **Keyless team:** id `preview_keyless_{ip}`, uuid `uuidv5(ip, NAMESPACE)`. **Env:** `KEYLESS_REQUESTS_PER_DAY`, `KEYLESS_CREDITS_PER_DAY`, `KEYLESS_PROXY_SECRET`.
- **Reserve flow:** `reserveKeylessCredits(team, projected) -> {ok}`; reconcile `adjustKeylessCredits(team, real-reserved)`; 429 body `{success:false, error: KEYLESS_CREDITS_MESSAGE}`.
- **Eligibility:** req headers `x-firecrawl-keyless-secret`, `x-firecrawl-keyless-ip` → `{eligible, remaining}`.
- **x402:** advertises a price; client sends signed EVM payment (exact scheme); facilitator verifies+settles. **Env:** `X402_PAY_TO_ADDRESS`, `X402_NETWORK`, `X402_FACILITATOR_URL`.

## Dependencies & assumptions

- **Redis** (rate-limit client) for keyless day-counters; the shared credit metering ([[credit-billing-and-concurrency--from-firecrawl]]).
- **`@x402/express`, `@x402/core`, `@x402/evm`** + an EVM network + facilitator for x402.
- Swappable: keyless identity could hash more than IP; x402 network/facilitator are config.

## To port this, you need:

- [ ] An IP→synthetic-team mapping (stable UUID) for anonymous callers, gated ON only when both daily limits are configured.
- [ ] Reserve-then-reconcile credit counters in Redis, with an agent-aware 429 message.
- [ ] A secret-gated eligibility endpoint that checks quota without spending (for a proxy/MCP).
- [ ] (optional) x402: mount the resource server with an EVM scheme + facilitator + pay-to address; put paid endpoints behind it.

## Gotchas

- **Reserve before work, reconcile after** — charging only after lets a single request overspend the daily cap.
- **Tier OFF by default** — require BOTH limits explicitly (even 0) so you never accidentally serve free.
- **IP is the identity** — behind shared NAT this rate-limits many users together; behind no proxy it's spoofable. Know your edge.
- **Agent-aware errors** — the 429 should hand an LLM caller a machine-usable auth URL, not just prose.
- **x402 only with a pay-to address** — guard `isX402Enabled()` or you advertise payments you can't receive.
- **Refund the reservation on error paths** or failed requests silently burn a keyless caller's daily quota.

## Origin (reference only)

firecrawl/firecrawl @ `main`: `apps/api/src/lib/keyless.ts` (inlined), `apps/api/src/lib/keyless-credit-projection.ts`,
`apps/api/src/controllers/v2/keyless-eligibility.ts` (inlined verbatim), `apps/api/src/lib/x402.ts` (inlined),
`apps/api/src/controllers/v2/x402-search.ts`, `apps/api/src/controllers/v1/x402-search.ts`.

**Gaps to verify (cost-capped):** exact Redis key/TTL for keyless day-counters; `projectSearchTotalCredits` formula;
the full x402 request/settle handshake + `price_credits` mapping; `uuidv5` namespace usage details.
