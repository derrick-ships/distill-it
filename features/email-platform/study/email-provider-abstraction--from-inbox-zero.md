# Email Provider Abstraction — from [inbox-zero](https://github.com/elie222/inbox-zero)

> Domain: [[_domain]] · Source: https://github.com/elie222/inbox-zero · NotebookLM: <link once added>

## What it does

It's the single seam between Inbox Zero's features and the two very different email backends it supports — Gmail and Microsoft Outlook/Graph. Every feature (rules engine, drafting, cleanup, analytics) talks to *one* `EmailProvider` interface — "get this message," "archive it," "apply this label," "create a draft," "send" — and never knows or cares which provider is underneath. A factory hands back the right implementation, fully authenticated and rate-limit-checked, on request.

## Why it exists

Gmail and Microsoft Graph are wildly different: different auth, different APIs, different mental models (Gmail has labels, Outlook has folders), different threading rules, different rate limits. If every feature had to branch on "is this Gmail or Outlook?", the codebase would be a maze of conditionals and adding a third provider would be a nightmare. The job-to-be-done is **write each feature once, run it on any provider** — concentrate all the provider-specific ugliness in one swappable adapter layer so the 90% of the app above it stays provider-agnostic.

## How it actually works

This is the classic **adapter + factory** pattern applied to email.

**One interface, two adapters.** There's a `EmailProvider` TypeScript interface listing every operation the app needs. Two classes implement it: `GmailProvider` (wrapping the Gmail API) and `OutlookProvider` (wrapping Microsoft Graph). Each adapter translates the unified calls into its backend's specifics and — crucially — normalizes results into one internal `ParsedMessage` shape so everything upstream sees identical data regardless of source.

**A factory picks the adapter.** `createEmailProvider({ emailAccountId, provider, logger })`:
1. Normalizes the provider name (`toRateLimitProvider`) and validates it (throws on unknown).
2. Checks the account isn't currently rate-limited for that provider (`assertProviderNotRateLimited`) — a guard that fails fast before any API call.
3. Branches: if `provider === "google"`, it gets a Gmail client (`getGmailClientForEmail`) and wraps it in `GmailProvider`; otherwise it gets an Outlook client (`getOutlookClientForEmail`) and wraps it in `OutlookProvider`.
4. Returns the adapter as the unified `EmailProvider`.

**Auth is hidden inside the client getters.** `getGmailClientForEmail` / `getOutlookClientForEmail` are where OAuth lives — they fetch the account's stored tokens and refresh them when expired, returning a ready-to-use authenticated client. The factory and the rest of the app never touch raw tokens; they just ask for a client and get one that works.

**Rate-limiting is first-class.** Because email APIs aggressively rate-limit, the provider name is mapped to a rate-limit identity and checked up front, with a dedicated error type when a provider is throttled — so the app can back off gracefully rather than hammering and getting banned.

## The non-obvious parts

- **Normalization to `ParsedMessage` is the real value.** The interface methods are the obvious part; the quiet, important work is that both adapters emit the *same* message shape (headers, threadId, body, internalDate). That's what lets the rules engine and drafting code be written once.
- **Auth refresh is encapsulated, not sprinkled.** Token fetch/refresh lives entirely in the client getters. No feature ever sees a token. This is what keeps a whole class of "expired token" bugs out of the feature code.
- **Rate-limit check happens before the client is even used.** Failing fast at factory time (not deep inside an API call) makes throttling a clean, catchable condition.
- **Label vs. folder is absorbed by the adapters.** Upstream code says "apply this label / move to this folder" against the interface; each adapter maps that onto Gmail labels or Outlook folders. The impedance mismatch never leaks up.
- **Adding a provider is a contained change.** A new backend = one new adapter implementing the interface + one new client getter + a factory branch. Nothing above the seam changes. That's the whole payoff of the pattern.

## Related

- [[ai-rules-engine--from-inbox-zero]] — its action executor calls this interface to archive/label/draft/send.
- [[ai-reply-drafting--from-inbox-zero]] — writes the finished draft via the provider's draft method.
- [[bulk-unsubscriber--from-inbox-zero]] / [[bulk-archiver--from-inbox-zero]] — read headers and archive through this layer.
- See also: any multi-backend integration (payments, storage, SMS) — the adapter+factory+normalized-DTO shape is identical.
