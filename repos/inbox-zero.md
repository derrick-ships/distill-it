# inbox-zero

**Source:** https://github.com/elie222/inbox-zero
**Product:** Open-source AI email manager — organizes the inbox, pre-drafts replies in the user's voice, blocks cold email, bulk-unsubscribes/archives, and exposes a plain-English rules engine. Web app + Slack/Telegram. Gmail + Outlook.
**Stack:** Next.js, TypeScript, Tailwind + shadcn/ui, Prisma + Postgres, Upstash (jobs/rate-limit), Turborepo monorepo (`apps/web`), Vercel AI SDK for LLM calls.
**Distilled:** 2026-06-15

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| AI Rules Engine | ai-automation | [study](../features/ai-automation/study/ai-rules-engine--from-inbox-zero.md) | [build](../features/ai-automation/build/ai-rules-engine--from-inbox-zero.md) |
| AI Reply Drafting | ai-automation | [study](../features/ai-automation/study/ai-reply-drafting--from-inbox-zero.md) | [build](../features/ai-automation/build/ai-reply-drafting--from-inbox-zero.md) |
| Bulk Unsubscriber | inbox-cleanup | [study](../features/inbox-cleanup/study/bulk-unsubscriber--from-inbox-zero.md) | [build](../features/inbox-cleanup/build/bulk-unsubscriber--from-inbox-zero.md) |
| Bulk Archiver | inbox-cleanup | [study](../features/inbox-cleanup/study/bulk-archiver--from-inbox-zero.md) | [build](../features/inbox-cleanup/build/bulk-archiver--from-inbox-zero.md) |
| Email Provider Abstraction | email-platform | [study](../features/email-platform/study/email-provider-abstraction--from-inbox-zero.md) | [build](../features/email-platform/build/email-provider-abstraction--from-inbox-zero.md) |

## Not yet distilled (candidates)

Reply Zero (needs-reply tracking), Cold Email Blocker, Email Analytics, Meeting Briefs, Smart Filing (Drive/OneDrive attachment saving), Slack & Telegram integration, sender auto-categorization (the LLM categorizer that feeds the bulk archiver).

## Key takeaways

- **The cost moat is the static-then-LLM funnel** in the rules engine — deterministic matching resolves the obvious mail for free; the LLM only sees the ambiguous remainder. This is the most transplantable idea in the repo.
- **Two-stage LLM** (pick the rule, then fill templated action args) keeps each model call small and schema-tight.
- **Learned writing style is a distilled, PII-free summary** of the user's edits, not raw examples — cheap and privacy-safe.
- **Everything sits on one `EmailProvider` adapter+factory seam** so Gmail/Outlook differences never leak into feature code.
- **Cleanup is sender-centric with persisted per-sender status** and risk-tiered bulk actions (only the high-confidence tier is one-click).
