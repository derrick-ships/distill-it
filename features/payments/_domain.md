# Domain: payments

**What this domain means:** Everything involved in taking money from a buyer and getting it to a seller through a payment gateway — choosing the right provider, building the checkout/webhook/refund flows, and doing it *securely* (signed webhooks, idempotent charges, no leaked keys). This domain spans two very different concerns that always travel together:

1. **Provider selection** — which gateway (Stripe, Mercado Pago, Wompi, Lemon Squeezy, Adyen, …) is correct for a given seller geography, buyer geography, currency, payment methods, and business model. This is a data + decision problem, not a coding problem.
2. **Secure integration** — the actual server code: a checkout endpoint, a signature-verified webhook that consumes the *raw* request body, idempotency on every charge-creating call, and a dedup table so a replayed webhook doesn't double-fulfill an order.

## Recurring ideas across repos studied

- **The provider is a data row, not a code branch.** Treat each gateway as a structured record (regions, currencies, methods, fees, KYC, webhook scheme, anti-patterns) so selection is filtering + scoring over data, and integration is template selection keyed by `(provider, stack, orm)`.
- **Raw body before parse.** Every signed-webhook bug starts with `request.json()` running before signature verification — the HMAC is computed over bytes that no longer exist once a framework parsed them.
- **Idempotency is non-optional on money.** Network retries duplicate charges; a cryptographic UUID idempotency key on every create call plus a server-side dedup table is the minimum bar.
- **LATAM is a first-class case, not an afterthought.** Cash vouchers (OXXO, Boleto), bank-transfer rails (PIX, PSE, SPEI), and installments change which provider wins and which methods the integration must surface.

## Features filed here

| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Payment Provider Advisor | pagokit | [study](study/payment-provider-advisor--from-pagokit.md) | [build](build/payment-provider-advisor--from-pagokit.md) |
| Secure Payment Webhook & Idempotency | pagokit | [study](study/secure-payment-webhook--from-pagokit.md) | [build](build/secure-payment-webhook--from-pagokit.md) |

## Related domains
- [[agent-guardrails]] — PagoKit's payment-security rules are *enforced* by deterministic hooks, not just recommended.
- [[credential-management]] — payment keys are the canonical "never hardcode this" secret.
- [[schema-migrations]] — payment integrations ship DB tables (payments, subscriptions, idempotency_keys, webhook_events_processed).
