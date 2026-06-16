# Email Provider Abstraction (build spec) — distilled from inbox-zero

## Summary

A provider-agnostic email layer: one `EmailProvider` interface, per-backend adapters (`GmailProvider`, `OutlookProvider`) that normalize to a single `ParsedMessage` shape, and a `createEmailProvider` factory that validates the provider, fails fast on rate-limit, obtains an OAuth-authenticated client (token refresh hidden inside the client getter), and returns the adapter. Write features once against the interface; run on any provider. Assume the source repo is gone; everything needed is below.

## Core logic (inlined)

### Factory

```ts
async function createEmailProvider({ emailAccountId, provider, logger }): Promise<EmailProvider> {
  const rlProvider = toRateLimitProvider(provider)        // normalize "google"/"microsoft-entra-id"/etc.
  if (!rlProvider) throw new Error(`Unknown provider: ${provider}`)

  await assertProviderNotRateLimited({ emailAccountId, provider: rlProvider })  // fail fast, throws RateLimitModeError

  if (provider === "google") {
    const client = await getGmailClientForEmail({ emailAccountId })   // OAuth + refresh inside
    return new GmailProvider(client, logger)
  } else {
    const client = await getOutlookClientForEmail({ emailAccountId }) // OAuth + refresh inside
    return new OutlookProvider(client, logger)
  }
}
```

### The unified interface (method names below are the app's needs; exact signatures reconstructed — see gotcha)

```ts
interface EmailProvider {
  // read
  getMessage(messageId): Promise<ParsedMessage>
  getThread(threadId): Promise<ParsedMessage[]>
  getThreads(query): Promise<{ threads, nextPageToken? }>
  getMessagesBatch(ids): Promise<ParsedMessage[]>

  // labels / folders
  getOrCreateLabel(name): Promise<Label>
  labelMessage(messageId, labelId): Promise<void>
  removeLabel(messageId, labelId): Promise<void>
  moveToFolder(messageId, folderId): Promise<void>     // Outlook side; Gmail maps to label

  // state changes
  archiveMessage(messageId): Promise<void>             // Gmail: remove INBOX label; Outlook: move to Archive
  markRead(messageId): Promise<void>
  markSpam(messageId): Promise<void>
  trashMessage(messageId): Promise<void>

  // compose
  draftEmail(args): Promise<{ draftId: string }>
  sendEmail(args): Promise<{ messageId: string }>
  replyToEmail(args): Promise<...>
  forwardEmail(args): Promise<...>

  // watch / sync
  watchEmails(): Promise<{ subscriptionId, expiration }>
  getHistory(startHistoryId): Promise<...>
}
```

### Auth client getter (where OAuth lives)

```ts
async function getGmailClientForEmail({ emailAccountId }) {
  const account = await db.account.find(emailAccountId)       // has access_token, refresh_token, expires_at
  if (isExpired(account.expires_at)) {
    const fresh = await refreshOAuthToken(account.refresh_token, provider="google")
    await saveTokens(account.id, fresh)                       // persist new access_token + expiry
    account.access_token = fresh.access_token
  }
  return new google.gmail({ auth: oauthClientWith(account.access_token) })
}
// getOutlookClientForEmail is the analog against Microsoft Graph + MSAL.
```

### Per-adapter normalization

Each adapter converts backend-native messages into:
```ts
type ParsedMessage = {
  id: string
  threadId: string
  headers: { from: string; to?: string; cc?: string; subject?: string; date?: string;
             "list-unsubscribe"?: string; "list-unsubscribe-post"?: string; [k: string]: string | undefined }
  textPlain?: string
  textHtml?: string
  snippet?: string
  internalDate: string   // epoch ms as string
  labelIds?: string[]
}
```

## Data contracts

```prisma
model EmailAccount {
  id        String @id
  email     String @unique
  accountId String @unique
  account   Account @relation(...)   // holds OAuth tokens
  // watch/sync bookkeeping:
  watchEmailsExpirationDate    DateTime?
  watchEmailsSubscriptionId    String?
  watchEmailsSubscriptionHistory Json?
  lastSyncedHistoryId          String?
  // ... feature flags consumed by higher layers
}
// Account (NextAuth-style) holds: provider, access_token, refresh_token, expires_at, scope, token_type
```

Rate-limit error type: `RateLimitModeError` (thrown by `assertProviderNotRateLimited`), caught upstream to back off.

## Dependencies & assumptions

- **OAuth token store** — an `Account` table with access/refresh tokens + expiry (NextAuth/Auth.js here). Swappable.
- **Provider SDKs** — `googleapis` (Gmail) and Microsoft Graph SDK / MSAL (Outlook). Each adapter depends on one.
- **A rate-limit store** (Upstash/Redis here) keyed by account+provider for `assertProviderNotRateLimited`.
- **Token refresh** — provider OAuth refresh endpoints; `saveTokens` persists the rotated tokens.
- Higher layers depend ONLY on the `EmailProvider` interface + `ParsedMessage`, never on a concrete adapter.

## To port this, you need:
- [ ] A single `EmailProvider` interface covering every mail op your features need.
- [ ] One adapter per backend, each normalizing to a shared `ParsedMessage`.
- [ ] A factory that selects the adapter by provider name and validates unknowns.
- [ ] Client getters that load tokens, refresh-if-expired, persist rotation, and return an authed client — auth must NOT leak above this layer.
- [ ] A pre-flight rate-limit guard with a dedicated catchable error.
- [ ] Mapping of label↔folder semantics inside each adapter.

## Gotchas

- **Normalize aggressively.** If `ParsedMessage` differs subtly between adapters, every upstream feature breaks on one provider. The shared DTO is the contract — test both adapters produce identical shapes.
- **Token refresh races.** Concurrent calls can each try to refresh; ensure `saveTokens` + reuse is safe (single-flight or tolerate rotation) or you'll invalidate each other's refresh tokens.
- **Rate limits are per-provider and harsh.** Check before calling; on throttle, back off — don't retry-storm or the provider bans the account.
- **Label vs folder.** Gmail "archive" = remove INBOX label; Outlook "archive" = move to Archive folder. Hide this in the adapter; never branch upstream.
- **Could not confirm from source:** the EXACT interface method names/signatures and the precise token-refresh code were not read line-by-line (read: `provider.ts` factory + the `email/` dir file list incl. `provider-types.ts`, `google.ts`, `microsoft.ts`, `watch-manager.ts`, `threading.ts`, `rate-limit.ts`; auth helpers `utils/auth/save-tokens.ts`, `cleanup-invalid-tokens.ts`). The method list above is reconstructed from documented usage across the rules/draft/cleanup features — **treat method names as indicative; confirm against `provider-types.ts` if the repo is reachable.**

## Origin (reference only)

Repo: https://github.com/elie222/inbox-zero — `apps/web/utils/email/`:
`provider.ts` (`createEmailProvider`, `toRateLimitProvider`, `assertProviderNotRateLimited`),
`provider-types.ts` (the `EmailProvider` interface), `google.ts` (`GmailProvider`), `microsoft.ts` (`OutlookProvider`),
`types.ts` (`ParsedMessage`), `watch-manager.ts`, `threading.ts`, `rate-limit.ts`, `rate-limit-mode-error.ts`.
Client getters in `apps/web/utils/gmail/` and `apps/web/utils/microsoft/`; token handling in `apps/web/utils/auth/save-tokens.ts`.
`EmailAccount`/`Account` in `apps/web/prisma/schema.prisma`.
