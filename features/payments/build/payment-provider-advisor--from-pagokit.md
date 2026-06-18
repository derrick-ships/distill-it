# Payment Provider Advisor (build spec) — distilled from PagoKit

## Summary

A **data-driven recommendation engine that selects one payment gateway** from a structured catalog, given seller/buyer geography, currency, required payment methods, and business model. Each provider is a JSON record carrying its capabilities + a set of context-keyed `score_modifiers`. The engine: (1) asks ≤5 questions, (2) applies *hard filters* that eliminate ineligible providers, (3) scores survivors as `base 5 + sum(matching modifiers)`, (4) returns the top provider with reasons, a real fee calc, KYC timeline, anti-patterns, and a "verified on <date>" disclaimer. Adding a provider = adding a JSON row; the engine never changes.

## Core logic (inlined)

```
INPUTS gathered from ≤5 questions:
  sellerCountry, buyerRegions[], recurrence ('one_time'|'subscription'),
  currency, requiredMethods[] (e.g. ['pix','oxxo']), businessModel tags,
  sellerType ('individual'|'business'), platform (stack/orm/lang)

STEP 1 — HARD FILTERS (sequential; any failure eliminates the provider):
  candidates = providers.filter(p =>
       p.status === 'active'                                  // not deprecated/acquired-out
    && p.regions.includes(sellerCountry)                      // regional availability
    && p.currencies.includes(currency)                        // currency support
    && requiredMethods.every(m => p.methods.includes(m))      // payment-method coverage
    && (recurrence !== 'subscription' || p.supports.subscriptions)   // capability if needed
    && kycEligible(p, sellerCountry, sellerType)              // KYC eligibility
  )
  // kycEligible: if sellerType==='individual' require p.kyc.individual_allowed,
  //   and sellerCountry NOT in p.kyc.business_required_countries.

STEP 2 — SCORE the survivors:
  for (p of candidates) {
    let score = 5                                              // base
    for (const [ctxTag, delta] of Object.entries(p.score_modifiers))
       if (contextTagsActive.has(ctxTag)) score += delta      // context-keyed modifiers
  }
  // contextTagsActive derived from inputs, e.g.:
  //   us_saas, eu_subscription, latam_individual_seller, marketplace_multi_seller,
  //   needs_cash_payment_only, ios_digital_goods, digital_goods_cross_border,
  //   wants_no_fiscal_overhead
  winner = candidates.sortDesc(score)[0]

STEP 3 — RECOMMENDATION (never show the number):
  - 3 concrete reasons (derived from which filters it passed + top positive modifiers)
  - real fee on a typical txn: e.g. amount*card_domestic_pct/100 + card_domestic_fixed_usd
  - KYC: p.kyc.time_to_activate_days
  - anti-patterns: p.anti_patterns
  - disclaimer: "Information verified on {p.last_verified_at}"
  - legal obligations appended by region: GDPR(EU) / LGPD(BR) / LFPDPPP(MX) / CCPA(US)

STEP 4 — HANDOFF to the code generator with structured params:
  { provider: p.id, stack, orm, lang, methods: requiredMethods,
    recurrence, recommended_api_flow: p.recommended_api_flow, webhook: p.webhook }
```

**Worked example of scoring (real modifier tables):**
- Stripe `score_modifiers`: `{us_saas:+3, eu_subscription:+2, digital_goods_cross_border:-1, wants_no_fiscal_overhead:-2, marketplace_multi_seller:+2, ios_digital_goods:-5, latam_individual_seller:-2, needs_cash_payment_only:-3}`
- Mercado Pago `score_modifiers`: `{latam_individual_seller:+3, needs_cash_payment_only:+2, us_saas:-3, marketplace_multi_seller:+1, digital_goods_cross_border:-1}`
- US SaaS billing globally → Stripe 5+3=8, MP 5−3=2 → **Stripe**.
- Solo MX seller, MX buyers, wants OXXO cash → MP passes method filter (`oxxo`), scores 5+3(+2 cash)=10; Stripe scores 5−2(−3 cash)=0 → **Mercado Pago**.

## Data contracts

**Top-level:** `{ "$schema": "...", "providers": [ <ProviderRecord>... ] }`. Companion files: `regions.json` (availability + fallbacks), `use_cases.json`, `methods.json` (payment-method directory), `SECURITY_RULES.md`.

**ProviderRecord (all fields), with a real entry inlined:**

```jsonc
{
  "id": "stripe",
  "name": "Stripe",
  "last_verified_at": "2026-05-20",
  "verified_by": "human",
  "status": "active",                         // active | deprecated | acquired
  "phase": 1,
  // "acquired_by"/"successor" present when status != active
  "regions": ["US","CA","UK","EU","MX","BR","SG","AU","NZ","HK","JP","IN"],
  "currencies": ["USD","EUR","GBP","CAD","AUD","MXN","BRL","SGD","JPY","HKD","NZD","INR"],
  "methods": ["card","apple_pay","google_pay","sepa_debit","ach_debit","klarna","afterpay","oxxo","boleto","pix","bizum","usdc","link"],
  "supports": {
    "subscriptions": true, "one_time": true, "marketplace_payouts": true,
    "merchant_of_record": false, "tokenization_owner": "shared", "save_card": true,
    "iap_compatible": false, "agentic_toolkit": true, "stablecoin_settlement": true,
    "cash_voucher": {"MX":"oxxo","BR":"boleto"},
    "installments": {"BR":true,"MX":true},
    "qr": {"BR":"pix","ES":"bizum"}
  },
  "tax_handling": {"stripe_tax_available": true, "automated_collection": true, "vat_eu": true, "sales_tax_us": true},
  "fees": {"card_domestic_pct":2.9,"card_domestic_fixed_usd":0.30,"card_international_pct":3.9,
           "eea_card_pct":1.4,"eea_card_fixed_eur":0.25,"usdc_pct":1.5,"notes":"..."},
  "kyc": {"individual_allowed": true, "business_required_countries": ["BR"], "time_to_activate_days": "1-7"},
  "secret_key_pattern": "^sk_(test|live)_[A-Za-z0-9]{20,}$",
  "publishable_key_pattern": "^pk_(test|live)_[A-Za-z0-9]{20,}$",
  "developer_experience": {"sdk_quality":5,"docs_quality":5,"sandbox":true,"test_keys_prefix":"sk_test_","live_keys_prefix":"sk_live_"},
  "sdks": {"node":{"pkg":"stripe","version_pinned":true}, "python":{"pkg":"stripe"}, "php":{"pkg":"stripe/stripe-php"}, "ruby":{"pkg":"stripe"}, "go":{"pkg":"github.com/stripe/stripe-go"}, "java":{"pkg":"com.stripe:stripe-java"}},
  "api_version": "2025-04-30.basil",
  "recommended_api_flow": "payment_intents",
  "deprecated_flows": ["charges.create"],
  "webhook": {"signature_header":"Stripe-Signature","algorithm":"HMAC-SHA256-with-timestamp",
              "signature_includes_timestamp":true,"recommended_tolerance_seconds":300,
              "replay_mitigation_strategy":"timestamp-window",
              "required_events_minimum":["payment_intent.succeeded","payment_intent.payment_failed","charge.refunded","charge.dispute.created","invoice.payment_failed","customer.subscription.deleted","customer.subscription.updated"],
              "expected_filenames":["webhook","events","stripe-webhook"],"ip_allowlist_available":true},
  "frontend_options": ["hosted","embedded","elements"],
  "anti_patterns": ["Do not use stripe.charges.create — legacy; use payment_intents so 3DS/SCA works.","Do not call request.json() before signature verification — Stripe needs the raw body."],
  "test_cards": {"success":"4242 4242 4242 4242","decline":"4000 0000 0000 0002","insufficient_funds":"4000 0000 0000 9995","three_d_secure":"4000 0025 0000 3155"},
  "docs_url": "https://stripe.com/docs",
  "score_modifiers": {"us_saas":3,"eu_subscription":2,"digital_goods_cross_border":-1,"wants_no_fiscal_overhead":-2,"marketplace_multi_seller":2,"ios_digital_goods":-5,"latam_individual_seller":-2,"needs_cash_payment_only":-3},
  "notes": ["Stripe acquired Lemon Squeezy (Jul 2024); launched Stripe Managed Payments (preview, Apr 2026) as MoR successor."]
}
```

Mercado Pago differs in the ways that matter for routing: `regions:["AR","BR","CL","CO","MX","PE","UY"]`, `methods` include `pix/boleto/oxxo/spei/pse/efecty/pago_facil/...`, `kyc.time_to_activate_days:"0-1"` and `individual_allowed:true` (instant solo activation), `tax_handling.automated_collection:false` (seller invoices locally — CFDI/NF-e), `recommended_api_flow:"preferences_checkout_pro"`, webhook `signature_header:"x-signature"` / `algorithm:"HMAC-SHA256-with-id-and-timestamp"` / `replay_mitigation_strategy:"both"`, and the modifier table above.

## Dependencies & assumptions

- Just data + a small pure engine — no SDKs, no network. Runs as a Claude Code **skill** (`payment-advisor`) whose SKILL.md drives the wizard and loads the JSON catalog; portable to any runtime that can load JSON and prompt the user.
- Assumes a separate code-generator agent consumes the structured handoff (PagoKit: `integration-specialist`).
- Swappable: the question script, the context-tag derivation, and the catalog. The filter→score→recommend engine is fixed.

## To port this, you need:

- [ ] A `providers.json` catalog using the ProviderRecord shape above (one row per gateway you support), plus `last_verified_at`/`verified_by` on each.
- [ ] A question flow capped at ~5, ordered by decision-impact (geography → recurrence → required methods), in the user's language.
- [ ] The engine: sequential hard filters (status/region/currency/methods/capability/KYC) → `base 5 + matching score_modifiers` → top pick.
- [ ] A context-tag derivation mapping answers → modifier keys (`us_saas`, `latam_individual_seller`, `needs_cash_payment_only`, `ios_digital_goods`, …).
- [ ] A recommendation renderer: 3 reasons, real fee calc from `fees`, KYC timeline, `anti_patterns`, "verified on <date>", region legal note — and that **never prints the score**.
- [ ] A structured handoff object for the downstream code generator.

## Gotchas

- **Filter before you score, always.** Scoring an ineligible provider and letting a big modifier win produces a recommendation that literally can't serve the seller's country or can't bill subscriptions. Disqualifying facts must eliminate, not just subtract.
- **Stale data is the core liability.** Fees, regional availability, and acquisitions change constantly (Stripe↔Lemon Squeezy, MoR successors). Carry `last_verified_at` per record and surface it in every recommendation; treat the catalog as a maintained asset, not a one-time write.
- **Never expose the numeric score** — it invites bikeshedding and implies false precision. Output reasons.
- **Methods can outweigh fees in LATAM.** If a buyer base needs OXXO/PIX cash rails, a provider lacking them is out *regardless* of cheaper card fees. Model cash_voucher/qr/installments as real `supports`/`methods` fields.
- **KYC eligibility is per-country and per-seller-type.** `individual_allowed` + `business_required_countries` decide whether a solo seller in BR can even use a provider; bake it into the filter, not the prose.
- **Cap the questions or lose the user.** The five-question limit is a real UX constraint; order questions so the early ones eliminate the most candidates.

## Origin (reference only)

Repo: https://github.com/Hainrixz/agente-pagokit
Key files: `skills/payment-advisor/SKILL.md` (the wizard: detect → ≤5 questions → filters → score → recommend → handoff), `skills/payment-advisor/data/providers.json` (catalog + score_modifiers + webhook schemes; Stripe & Mercado Pago entries inlined above), `skills/payment-advisor/data/regions.json` / `use_cases.json` / `methods.json`, `skills/payment-advisor/SECURITY_RULES.md`, `agents/integration-specialist.md` (the handoff target). Phase-1 providers: Stripe, Mercado Pago, Wompi, Lemon Squeezy.
