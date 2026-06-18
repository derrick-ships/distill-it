# pagokit

**Source:** https://github.com/Hainrixz/agente-pagokit
**Product:** PagoKit — a Claude Code plugin that automates payment-gateway integration. It analyzes your project, asks ≤3–5 questions, recommends the optimal provider for your geography/business model, then generates a complete, production-grade integration (checkout, signed webhooks, idempotency, refunds, customer portal, DB migrations) — all locally, no external API calls. Its differentiator: payment-security rules are enforced by deterministic PostToolUse hooks (Node.js scripts that block insecure writes), not markdown guidelines.
**Stack:** JavaScript (97.6%) + Shell; Node ≥18, zero-dep hooks. Packaged as a Claude Code plugin (`.claude-plugin/`, `commands/`, `skills/`, `agents/`, `hooks/`). Supported stacks: Next.js App Router, Express; ORMs: Prisma, Drizzle, SQLAlchemy; deploy: Vercel, Railway. Phase-1 providers: Stripe, Mercado Pago, Wompi, Lemon Squeezy (Phase 2: Conekta, Culqi, Niubiz, NestJS, FastAPI). Bilingual EN/ES. MIT. Built by Enrique Rocha (tododeia.com).
**Distilled:** 2026-06-18

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Deterministic Security Hooks | agent-guardrails | [study](../features/agent-guardrails/study/deterministic-security-hooks--from-pagokit.md) | [build](../features/agent-guardrails/build/deterministic-security-hooks--from-pagokit.md) |
| Payment Provider Advisor | payments | [study](../features/payments/study/payment-provider-advisor--from-pagokit.md) | [build](../features/payments/build/payment-provider-advisor--from-pagokit.md) |
| Secure Payment Webhook & Idempotency | payments | [study](../features/payments/study/secure-payment-webhook--from-pagokit.md) | [build](../features/payments/build/secure-payment-webhook--from-pagokit.md) |

## Not yet distilled (candidates)

- **Integration-builder template engine** (`skills/integration-builder/templates/`): 47 templates keyed by provider × stack × orm × deploy-target that assemble the generated code. (code-generation; mostly a templating + selection problem — the *secure pattern* it emits is captured in `secure-payment-webhook`.)
- **`integration-specialist` subagent** (`agents/integration-specialist.md`): the subagent that consumes the advisor's handoff and drives generation under the 7 guiding + 5 enforced rules. (agent-architecture.)
- **Doctor / project-analyzer skills** (`skills/doctor`, `skills/project-analyzer`): stack/ORM/deploy detection and a `/pagokit:doctor` health/coverage report. (diagnostics.)
- **Commands layer** (`commands/`): `/pagokit:start`, `/pagokit:test`, `/pagokit:doctor` entry points. (plugin-architecture.)
- **Remaining individual checks** (`no-pii-logs`, `gitignore-check`, `existing-webhook-check`): worked examples of the guardrail `run(ctx)` contract beyond the three inlined in the build doc. (agent-guardrails.)

## Key takeaways

- **Executable policy beats prose policy.** The product's spine is that security rules are Node.js hooks that exit 2 to *block* an insecure write, not markdown the model may ignore. The reusable engine — `PreToolUse`/`PostToolUse`/`Stop` → dispatcher → `run(ctx)->finding|null` checks → exit 2 = block, fail-open on bugs — is domain-agnostic and the highest-value distill here (see agent-guardrails).
- **Providers are data rows, not code branches.** Provider selection is filter→score over a `providers.json` catalog with context-keyed `score_modifiers`; adding a gateway is adding JSON. Hard filters (region/currency/methods/capability/KYC) eliminate; scoring only ranks survivors; the numeric score is never shown.
- **Parse-order is a security property.** The single most-enforced rule: read the raw webhook body before verifying the signature (the HMAC is over the exact bytes), then dedup by event id and bound replay with a ~300s timestamp window. Two distinct idempotency mechanisms guard two distinct failures (double-charge vs. double-fulfill).
- **False-positive engineering is what makes guardrails usable.** Comment/string stripping before regex, a test/fixture allowlist, per-rule `pagokit-ignore` bypass tags, bilingual fix-first messages, and an audit log are the difference between a guardrail you keep and one you disable.
- **LATAM-first, bilingual.** First-class cash vouchers (OXXO/Boleto), bank rails (PIX/SPEI/PSE), installments, Mercado Pago/Wompi, and EN/ES throughout target a market most US-centric payment tooling ignores.
