# Payment Provider Advisor (pick the right gateway from data, not opinion) — from [PagoKit](https://github.com/Hainrixz/agente-pagokit)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/agente-pagokit · NotebookLM:

## What it does

Before any code is written, PagoKit runs a short wizard that figures out *which* payment gateway you should use. It looks at your project, asks at most five plain-language questions — mainly "where are you (the seller) based, where are your buyers, is this one-time or subscription, do you need PIX/OXXO/etc." — and then recommends a single provider (from Stripe, Mercado Pago, Wompi, Lemon Squeezy in the first release) with three concrete reasons, the actual fee on a typical transaction, how long activation/KYC takes, and the relevant anti-patterns to avoid. It never shows you a numeric score and never makes you read a comparison matrix; it gives you one answer and the reasoning.

## Why it exists

A developer adding payments faces ~30+ gateways, each with different regional availability, currency support, local payment methods, fee structures, KYC requirements, and subscription capabilities. Evaluating them properly takes days, and the wrong pick is expensive to undo once the integration is built. The job-to-be-done is to compress "spend a week comparing gateways" into "answer five questions, get the correct provider for your situation." Geography is the dominant axis: a solo seller in Mexico selling to Mexican buyers wants Mercado Pago (cash vouchers, instant activation), while a US SaaS billing globally wants Stripe — and the *same* product asking the *same* questions should route each correctly.

## How it actually works

The advisor is built on a **data catalog, not hardcoded opinions.** Every provider is a structured record in `providers.json` (plus companion data on regions, special use-cases, and payment methods). A provider record carries everything the decision needs: the countries it serves, the currencies and payment methods it supports, what it *can do* (subscriptions, marketplace payouts, merchant-of-record, installments, cash vouchers, QR), its fee breakdown, its KYC rules (can an individual use it? which countries force a business entity? how many days to activate?), its webhook scheme, known anti-patterns, test cards, and — crucially — a set of **score modifiers**.

The wizard runs in a fixed sequence:

1. **Detect and confirm the project** in the user's own language, in one sentence ("Looks like a Next.js app with Prisma — correct?").
2. **Ask up to five focused questions,** prioritizing seller country, buyer geography, billing recurrence (one-time vs subscription), and required local methods (PIX, OXXO, PSE…). Follow-ups only fire for genuinely ambiguous cases. Five is a hard cap.
3. **Apply hard filters in order** — eliminate any provider that fails: regional availability → currency support → payment-method coverage → must be active (not deprecated/acquired-out) → subscription capability if needed → KYC eligibility for this seller. Anything that fails a filter is out, regardless of how good it otherwise is.
4. **Score the survivors.** Each starts at a base of 5, then the provider's own `score_modifiers` are applied for the matching context — e.g. Stripe gets +3 for `us_saas`, +2 for `eu_subscription`, but −5 for `ios_digital_goods` and −2 for `latam_individual_seller`; Mercado Pago gets +3 for `latam_individual_seller` and +2 for `needs_cash_payment_only` but −3 for `us_saas`. Highest score wins.
5. **Present the recommendation** with three concrete reasons, a *real* fee calculation on a typical transaction (using the provider's actual fee fields), the KYC/activation timeline, the relevant anti-patterns, and a "verified on [date]" disclaimer — because gateway facts go stale.
6. **Hand off to the integration-specialist** with structured parameters (chosen provider, stack, ORM, methods needed) and append the region's legal obligations (GDPR / LGPD / LFPDPPP / CCPA).

## The non-obvious parts

- **Hard filters before soft scoring.** A provider that can't legally serve the seller's country or can't do subscriptions when subscriptions are required is *eliminated*, not just penalized. Scoring only ranks the genuinely-eligible set — so a high "vibes" score can never override a disqualifying fact.
- **Score modifiers live on the provider, keyed by context.** Instead of one big scoring function with branches per provider, each provider declares how much it likes/dislikes each scenario (`us_saas: +3`, `latam_individual_seller: −2`). Adding a provider is adding a JSON row; the engine doesn't change. This is the whole reason the system is maintainable.
- **Freshness is a first-class field.** Every record has `last_verified_at` and `verified_by`, and every recommendation discloses "information verified on [date]." Payment-gateway facts (fees, regional availability, who-acquired-whom) change constantly — Stripe acquired Lemon Squeezy, launched a managed-payments MoR successor — and a stale recommendation is a liability, so the staleness is surfaced rather than hidden.
- **Scores are never shown to the user.** The number is an internal ranking device; exposing it invites "why is it 7 not 8" arguments. The user gets *reasons*, not arithmetic.
- **The five-question cap is a UX guardrail.** More questions = abandonment. The questions are ordered by decision-impact (geography first, because it eliminates the most options) so the cap rarely bites.
- **LATAM is modeled in depth.** Cash vouchers (OXXO, Boleto, PagoFácil), bank rails (PIX, SPEI, PSE), and installments are explicit `supports` fields, because in those markets the *payment method* often decides the provider more than fees do.
- **It refuses to generate code.** The advisor's only output is a decision + a structured handoff; the actual integration is a separate agent. Clean separation between "decide" and "build."

## The playbook (how this drives adoption)

- **Time-to-value is the pitch.** "Days of gateway evaluation → five questions" is the entire value proposition; the advisor *is* the hook that gets a developer to try the tool.
- **Trust through honesty.** Disclosing the verification date and the relevant anti-patterns (instead of overclaiming) is what makes a developer believe the single recommendation enough to act on it.
- **LATAM-first positioning** (Mercado Pago, Wompi, PIX/OXXO/PSE as first-class, bilingual EN/ES throughout) targets an underserved market where most gateway-advice tooling is US-centric.
- **Cloneability:** the engine (filter → score → recommend) is simple; the moat is the *maintained, verified data catalog* — keeping fees, regions, KYC rules, and acquisition status correct across dozens of providers is the real ongoing work.

## Related
- [[secure-payment-webhook--from-pagokit]] — what the advisor hands off to; the chosen provider's webhook scheme (from its data record) drives that integration.
- [[deterministic-security-hooks--from-pagokit]] — sibling PagoKit feature; the hooks police the code that gets generated for the provider this advisor picks.
- [[converter-pipeline--from-markitdown]] — same "data-driven registry + dispatch" shape (sorted converters there, filtered+scored providers here).
- [[ordered-backend-routing--from-agent-reach]] — sibling "pick the right backend from a declarative list" pattern.
