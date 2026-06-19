# Secure Payment Webhook & Idempotency (build spec) — distilled from PagoKit

## Summary

The transplant-grade pattern for a **secure payment integration**: a checkout endpoint that creates charges with a cryptographic UUID idempotency key, and a webhook endpoint that (in strict order) reads the **raw body**, verifies the provider signature, rejects stale timestamps (replay), deduplicates by event id, then acts. Plus refund + customer-portal endpoints and 5 DB tables. Provider-specific details (header, algorithm, tolerance) are read from a provider record, not hardcoded. Reimplement this exactly; getting the *order* wrong (parse-before-verify) is itself the vulnerability.

## Core logic (inlined)

### Checkout — idempotent charge creation

```ts
// app/api/checkout/route.ts  (Next.js + Stripe)
import Stripe from 'stripe';
import { randomUUID } from 'node:crypto';
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);   // NEVER hardcode the key

export async function POST(req: Request) {
  const { priceId, customerId } = await req.json();
  const idempotencyKey = randomUUID();                       // crypto UUID, NOT Math.random/Date.now
  const session = await stripe.checkout.sessions.create(
    { mode: 'payment', line_items: [{ price: priceId, quantity: 1 }],
      customer: customerId, success_url: '...', cancel_url: '...' },
    { idempotencyKey }                                       // provider de-dupes retries on this key
  );
  return Response.json({ url: session.url });
}
```

### Webhook — the mandatory order (raw → verify → replay-check → dedup → act)

```ts
// app/api/webhook/stripe/route.ts  (Next.js App Router + Stripe)
import Stripe from 'stripe';
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(req: Request) {
  // 1) RAW body FIRST — never req.json() before verifying. HMAC is over these exact bytes.
  const rawBody = await req.text();
  const sig = req.headers.get('stripe-signature')!;

  // 2+3) VERIFY signature; constructEvent throws on bad sig AND on stale timestamp (replay).
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET!);
    // Stripe-Signature embeds t=<ts>; the SDK rejects ts outside the default tolerance (~300s).
  } catch {
    return new Response('Invalid signature', { status: 400 });
  }

  // 4) DEDUP by event id — idempotent processing across redeliveries.
  if (await db.webhookEventsProcessed.findUnique({ where: { eventId: event.id } }))
    return new Response('ok', { status: 200 });               // already handled, ack & stop
  await db.webhookEventsProcessed.create({ data: { eventId: event.id, type: event.type } });

  // 5) ACT, then 200.
  switch (event.type) {
    case 'payment_intent.succeeded': /* mark order paid, provision */ break;
    case 'charge.refunded':          /* reverse fulfillment */ break;
    // customer.subscription.updated/deleted, invoice.payment_failed, charge.dispute.created ...
  }
  return new Response('ok', { status: 200 });
}
// Next.js App Router gives raw body via req.text(); Pages Router needs `export const config = { api: { bodyParser: false } }`.
```

**Express variant** — register raw body ONLY on the webhook route (global `express.json()` would consume it first):
```js
app.post('/webhook/stripe', express.raw({ type: 'application/json' }), (req, res) => {
  const event = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], process.env.STRIPE_WEBHOOK_SECRET);
  /* dedup + act */ res.send('ok');
});
```

**Per-provider verification (read from the provider record, don't hardcode):**
- **Stripe** — header `Stripe-Signature`; `stripe.webhooks.constructEvent(raw, sig, secret)`; HMAC-SHA256 with embedded timestamp; tolerance ~300s; replay = timestamp-window.
- **Mercado Pago** — header `x-signature` (+ `x-request-id`); HMAC-SHA256 over the manifest string `id:<data.id>;request-id:<x-request-id>;ts:<ts>;`, key = `MP_WEBHOOK_SECRET`; replay = "both" (timestamp window + id dedup); **also** send `X-Idempotency-Key` on POST /payments.
- **Wompi** — SHA-256 checksum: `verifyWompiChecksum(event, process.env.WOMPI_EVENTS_SECRET)`.
- **Lemon Squeezy** — HMAC over raw body: `verifyLemonSignature(rawBody, sig, process.env.LEMONSQUEEZY_WEBHOOK_SECRET)`.

Always compare digests with a timing-safe equality (`crypto.timingSafeEqual`).

### Raw-body trap per framework (what NOT to do)
| Framework | WRONG (breaks HMAC) | RIGHT |
|-----------|--------------------|-------|
| Next.js   | `await request.json()` | `await request.text()` |
| Express   | global `express.json()` | `express.raw({type:'application/json'})` on the webhook route |
| FastAPI   | `await request.json()` / `get_json()` | `await request.body()` (raw bytes) |
| Laravel   | `$request->all()` | `$request->getContent()` |
| Rails     | `params` | `request.raw_post` |

## Data contracts

**5 tables (Prisma-ish):**
```
payments(id, provider, provider_payment_id, amount, currency, status, customer_id, created_at)
subscriptions(id, provider, provider_sub_id, customer_id, status, current_period_end)
customers(id, provider, provider_customer_id, email)
idempotency_keys(key PK, scope, created_at)              // request-level de-dup record
webhook_events_processed(event_id PK, type, processed_at) // event-level de-dup (the replay/redelivery guard)
```

**Webhook scheme (from the provider record — see payment-provider-advisor build spec):**
```jsonc
"webhook": { "signature_header":"Stripe-Signature", "algorithm":"HMAC-SHA256-with-timestamp",
  "signature_includes_timestamp": true, "recommended_tolerance_seconds": 300,
  "replay_mitigation_strategy": "timestamp-window",
  "required_events_minimum": ["payment_intent.succeeded","payment_intent.payment_failed","charge.refunded","charge.dispute.created","invoice.payment_failed","customer.subscription.deleted","customer.subscription.updated"] }
```

**Env vars:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (and `MP_WEBHOOK_SECRET`, `WOMPI_EVENTS_SECRET`, `LEMONSQUEEZY_WEBHOOK_SECRET` as applicable). `.env.example` must hold only `*_test_*` placeholders, never live keys.

## Dependencies & assumptions

- Provider SDK (`stripe`, `mercadopago`, `@lemonsqueezy/lemonsqueezy.js`, …), an ORM with migrations (Prisma/Drizzle/SQLAlchemy), and a framework whose raw body you can access on the webhook route.
- Node ≥18 for `crypto.randomUUID()`/`timingSafeEqual` (else `uuid` pkg + constant-time compare).
- Assumes secrets live in env, and a dedup store (the DB table) exists. Webhook endpoint must be reachable by the provider and respond <~10s.

## To port this, you need:

- [ ] A checkout endpoint that passes a `crypto.randomUUID()` idempotency key to the create call.
- [ ] A webhook endpoint that does, **in this order**: read raw body → verify signature (provider's canonical verifier) → reject stale timestamp → dedup by event id (DB) → act → 200.
- [ ] Raw-body access wired correctly for your framework (see table) — this is the #1 thing to get right.
- [ ] `STRIPE_WEBHOOK_SECRET` (and per-provider secrets) in env; `.env.example` with test placeholders only.
- [ ] The 5 tables (esp. `webhook_events_processed`) via your migration tool.
- [ ] Refund endpoint + customer billing portal; a cross-provider error→{en,es} mapper.
- [ ] (Strongly recommended) the deterministic hooks from [[deterministic-security-hooks--from-pagokit]] to keep all of the above from regressing.

## Gotchas

- **Parse-before-verify is THE bug.** `await request.json()` (or any framework auto-parse) before signature verification destroys the exact bytes the HMAC was computed over; verification then "mysteriously fails" and gets disabled. Read raw, verify, *then* parse.
- **Express global `express.json()` silently eats the raw body.** Mount `express.raw()` on the webhook route specifically, before any global JSON parser can run.
- **Two idempotency mechanisms, don't conflate them.** Request idempotency key (create call) stops double-charge; event dedup table (webhook) stops double-fulfillment. Both required.
- **Weak idempotency keys collide.** `Math.random()`/`Date.now()` under concurrency produce dupes — use a cryptographic UUID.
- **A valid signature is not replay protection.** Reject timestamps outside the tolerance window (~300s) or a captured valid request can be replayed indefinitely.
- **Always 200 a duplicate.** If you've already processed an event id, ack 200 and do nothing — returning an error makes the provider retry forever.
- **Provider schemes differ.** MP signs a manifest string with `x-request-id` and needs an explicit `X-Idempotency-Key` on POST /payments; Wompi uses a SHA-256 checksum; don't paste Stripe's verifier for another provider — read the scheme from the provider record.
- **Use timing-safe comparison** for any manual HMAC check (`crypto.timingSafeEqual`), never `===`.

## Origin (reference only)

Repo: https://github.com/Hainrixz/agente-pagokit
Generated by `skills/integration-builder` (47 templates keyed by provider×stack×orm×deploy) and the `agents/integration-specialist.md` subagent; enforced by `hooks/checks/{webhook-has-signature,raw-body,idempotency-canonical,no-hardcoded-keys}.js`. Example output files: `app/api/checkout/route.ts`, `app/api/webhook/stripe/route.ts`, `app/api/portal/route.ts`, `app/api/refund/route.ts`, `components/CheckoutButton.tsx`, `lib/payments/stripe.ts`. Webhook schemes/tolerances live in `skills/payment-advisor/data/providers.json`. Phase-1 providers: Stripe, Mercado Pago, Wompi, Lemon Squeezy; stacks Next.js App Router + Express; ORMs Prisma/Drizzle/SQLAlchemy.
