# Domain: email-platform

The foundation layer every email feature sits on: a single, provider-agnostic interface that wraps Gmail and Outlook/Microsoft Graph behind one set of methods, plus the OAuth token plumbing that keeps those clients alive.

## What this domain means across repos

Multi-provider email apps face the same problem: Gmail and Microsoft Graph have different APIs, label vs. folder models, and threading semantics. The durable pattern:

1. **A unified `EmailProvider` interface** — one TypeScript type listing every operation the rest of the app needs (get message/thread, archive, label, draft, send, mark read, create label, etc.).
2. **Per-provider adapters** (`GmailProvider`, `OutlookProvider`) that implement that interface against each backend's SDK, normalizing data into one internal `ParsedMessage` shape.
3. **A factory** (`createEmailProvider`) that picks the adapter by provider name, obtains an authenticated client (`getGmailClientForEmail` / `getOutlookClientForEmail`) with token refresh handled internally, and guards against per-provider rate limits before returning.

Everything above this layer (rules engine, drafting, cleanup) is written once against the interface and works on both providers for free.

## Features distilled here

- [[email-provider-abstraction--from-inbox-zero]] — the factory + unified interface + per-provider adapters + OAuth client/token handling.

## Related domains

- [[ai-automation]] — rules and drafting call this interface to act on mail.
- [[inbox-cleanup]] — archive/label operations execute through it.
