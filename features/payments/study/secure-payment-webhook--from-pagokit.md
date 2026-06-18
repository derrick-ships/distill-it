# Secure Payment Webhook & Idempotency (the pattern PagoKit generates) — from [PagoKit](https://github.com/Hainrixz/agente-pagokit)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/agente-pagokit · NotebookLM:

## What it does

This is the *correct* shape of a payment integration that PagoKit generates and then enforces: a checkout endpoint that creates a charge with an idempotency key, a webhook endpoint that verifies the provider's signature over the **raw** request body before trusting a single byte, replay protection, a dedup table so the same event can't fulfill an order twice, plus a refund endpoint and a customer billing portal. It's the difference between "it works in the demo" and "it survives a malicious actor and a flaky network."

## Why it exists

Three failures show up in almost every hand-rolled payment integration, and all three are silent until they're catastrophic:

1. **Unsigned (or wrongly-verified) webhooks.** If your `/webhook` endpoint trusts its POST body without verifying the provider's signature, anyone can `curl` it and mark orders as paid. Free money out the door.
2. **Body parsed before verification.** Signature verification is an HMAC computed over the *exact raw bytes* the provider sent. The instant a framework runs `request.json()`, those bytes are gone — re-serializing the parsed object produces different bytes, the HMAC won't match, and developers "fix" it by skipping verification. So the parse order itself is a security bug.
3. **Duplicate charges / double fulfillment.** Networks retry. Without a cryptographic idempotency key on the create call, a retry charges the customer twice; without a server-side dedup table on webhooks, a redelivered `payment.succeeded` event ships the product twice.

The job-to-be-done is to encode the known-correct pattern so a developer (or an AI agent) gets all three right by default.

## How it actually works

**Checkout side.** The create-charge call (Stripe `paymentIntents.create` / `checkout.sessions.create`, Mercado Pago preference/payment create) is sent with a **cryptographic UUID idempotency key** — `crypto.randomUUID()` (Node 19+) or `uuidv4()`. The provider remembers that key, so a retried request returns the original charge instead of creating a second one. Weak sources (`Math.random()`, `Date.now()`) are explicitly forbidden because they collide.

**Webhook side, in strict order:**
1. Read the **raw body** as bytes/text — `await request.text()` in Next.js, `express.raw()` middleware in Express, `request.body()` in FastAPI, `request.getContent()` in Laravel, `request.raw_post` in Rails. Never `.json()` first.
2. Read the signature header — `Stripe-Signature`, or Mercado Pago's `x-signature` (+ `x-request-id`).
3. **Verify** with the provider's canonical verifier: Stripe `webhooks.constructEvent(rawBody, sig, secret)`; Mercado Pago HMAC-SHA256 over the manifest string `id:<data.id>;request-id:<x-request-id>;ts:<ts>;`; Wompi a SHA-256 checksum; Lemon Squeezy an HMAC over the raw body. Compare with a timing-safe equality.
4. **Replay protection.** Stripe's signature embeds a timestamp; reject events whose timestamp is outside a tolerance window (≈300s) so a captured-and-replayed request is refused. Mercado Pago uses "both" timestamp-window and id-based mitigation.
5. **Deduplicate.** Record each processed event id in a `webhook_events_processed` table; if you've seen it, ack 200 and do nothing. This makes processing idempotent end-to-end, so a legitimate redelivery never double-fulfills.
6. Only now act on the event (mark order paid, provision, etc.) and return 200.

**Persistence.** The pattern ships five tables: `payments`, `subscriptions`, `customers`, `idempotency_keys`, and `webhook_events_processed` (via Prisma/Drizzle/SQLAlchemy migrations). A cross-provider error mapper translates each gateway's error codes into a uniform English/Spanish shape so the app handles them uniformly.

Every one of these properties is independently *enforced* by PagoKit's deterministic hooks — see [[deterministic-security-hooks--from-pagokit]] — so the pattern isn't just documented, it's unshippable to violate.

## The non-obvious parts

- **Parse order is a security property, not a style choice.** "Read raw body *then* verify *then* parse" is non-negotiable; the common instinct to `await request.json()` at the top of the handler quietly breaks signature verification and is the single most frequent cause of "verification doesn't work."
- **Idempotency exists in two places, for two different failures.** The *request* idempotency key (on the create call) stops a retried checkout from double-charging. The *event* dedup table (on the webhook) stops a redelivered notification from double-fulfilling. You need both; they protect different legs.
- **The idempotency key must be cryptographic.** `Math.random()`/`Date.now()` collide under concurrency, defeating the whole point. It has to be a UUID from a secure source.
- **Timestamp tolerance is the replay defense.** A valid signature alone isn't enough — a captured valid request can be replayed forever. The ~300s timestamp window (where the signature includes a timestamp, as Stripe's does) bounds the replay window.
- **Webhook schemes differ per provider, so the data drives the code.** Header name, algorithm, whether the signature includes a timestamp, the tolerance, and the replay strategy all come from the provider's record (see [[payment-provider-advisor--from-pagokit]]) — the generator reads those fields rather than hardcoding Stripe's scheme.
- **Refunds and the customer portal are part of "done."** A real integration isn't just charge + webhook; the pattern includes a refund endpoint and a self-serve billing portal, because those are where the next round of security/idempotency mistakes live.

## The playbook (how this drives trust)

- **Secure-by-default is the product promise.** PagoKit's pitch is that the generated integration is production-grade — signed webhooks, idempotency, replay protection — without the developer needing to know why. The pattern *is* the value.
- **Bilingual error mapping** (EN/ES) and LATAM provider coverage make the secure pattern usable in markets the big US-centric guides ignore.
- **Cloneability:** the pattern is well-known to payment experts and freely documented by each provider — the value isn't secret knowledge, it's getting *all* of it right *together*, every time, and having a machine refuse the insecure shortcuts.

## Related
- [[deterministic-security-hooks--from-pagokit]] — the enforcement layer that makes this pattern unshippable to violate (raw-body, signature, idempotency rules).
- [[payment-provider-advisor--from-pagokit]] — supplies the per-provider webhook scheme (header/algorithm/tolerance) this integration reads.
- [[byok-proxy--from-open-design]] — same family of "structure the secure path so the secret/signature is handled correctly by construction."
- [[schema-migrations--from-tldraw]] — the migrations machinery this ships its 5 tables through.
