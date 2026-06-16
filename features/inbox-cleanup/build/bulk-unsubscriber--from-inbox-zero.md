# Bulk Unsubscriber (build spec) — distilled from inbox-zero

## Summary

Perform a real, server-side one-click unsubscribe from a sender by parsing the RFC 2369 `List-Unsubscribe` header + RFC 8058 one-click POST, fetching it safely (SSRF-guarded, bounded redirects with correct method downgrade), and persisting the sender's status so future mail is auto-handled. Status can also be set manually without any network call. Assume the source repo is gone; everything needed is below.

## Core logic (inlined)

```
unsubscribeSenderAndMark({ emailAccountId, newsletterEmail, unsubscribeLink, listUnsubscribeHeader, logger }):
  sender = extractEmailAddress(newsletterEmail)
  ok = attemptAutomaticUnsubscribe({ unsubscribeLink, listUnsubscribeHeader })
  if ok:
    setSenderStatus({ emailAccountId, newsletterEmail, status: UNSUBSCRIBED })
  log("unsubscribe", { sender, ok })
  return ok

setSenderStatus({ emailAccountId, newsletterEmail, status }):
  upsertSenderRecord(emailAccountId, newsletterEmail, status)   // Newsletter row, unique per (account,email)
```

```
attemptAutomaticUnsubscribe({ unsubscribeLink, listUnsubscribeHeader }):
  url = getHttpUnsubscribeLink(listUnsubscribeHeader) || unsubscribeLink
  // getHttpUnsubscribeLink: List-Unsubscribe may contain "<mailto:...>, <https://...>";
  //   parse out the https URL (ignore mailto for the HTTP path).
  if !url: return false
  if !isSafeExternalHttpUrl(url): return false          // SSRF guard — REQUIRED

  ONE_CLICK_REQUEST_BODY = "List-Unsubscribe=One-Click"
  // try one-click POST first (RFC 8058)
  res = fetchFollowingRedirects(url, {
          method: "POST",
          headers: { "content-type": "application/x-www-form-urlencoded" },
          body: ONE_CLICK_REQUEST_BODY,
        })
  if !res.ok:
    res = fetchFollowingRedirects(url, { method: "GET" })   // fallback
  return res.ok

fetchFollowingRedirects(url, opts):
  followed = 0
  loop:
    r = fetch(url, { ...opts, redirect: "manual" })
    if r.status in {301,302,303,307,308} and followed < 5:
      followed++
      url = r.headers.location
      if r.status in {301,302,303}: opts.method = "GET"; delete opts.body   // method downgrade
      continue
    return r
```

`isSafeExternalHttpUrl(url)` must reject: non-http(s) schemes; hosts resolving to private/loopback/link-local/metadata ranges (127.0.0.0/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fc00::/7); and ideally re-validate after each redirect hop.

## Data contracts

```prisma
model Newsletter {
  id              String  @id @default(cuid())
  email           String                 // the sender address
  name            String?
  status          NewsletterStatus?      // null = undecided
  patternAnalyzed Boolean @default(false)
  lastAnalyzedAt  DateTime?
  emailAccountId  String
  categoryId      String?
  // unique per (emailAccountId, email)
}

enum NewsletterStatus { APPROVED  UNSUBSCRIBED  AUTO_ARCHIVED }
```

Server-action inputs (zod-validated):
```ts
setNewsletterStatusAction: { newsletterEmail: string, status: NewsletterStatus }
unsubscribeSenderAction:   { newsletterEmail: string, unsubscribeLink?: string, listUnsubscribeHeader?: string }
```

Header formats handled:
```
List-Unsubscribe: <mailto:unsub@x.com?subject=unsub>, <https://x.com/u/abc123>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

## Dependencies & assumptions

- **`fetch` with manual redirect handling** (Node 18+ / undici, or any HTTP client where you control redirects).
- **An SSRF URL allow/deny check** — `isSafeExternalHttpUrl`. Do not skip.
- **A relational store** for the `Newsletter` (per-sender status) table, unique on (account, email).
- **Access to the message's `List-Unsubscribe` / `List-Unsubscribe-Post` headers** — supplied by the provider layer ([[email-provider-abstraction--from-inbox-zero]]).
- The `mailto:` unsubscribe path (sending an email to unsubscribe) is NOT part of the HTTP path here; if you want it, send via the provider's send method.

## To port this, you need:
- [ ] A per-sender status table (APPROVED / UNSUBSCRIBED / AUTO_ARCHIVED), unique per account+sender.
- [ ] A header parser that extracts the `https` URL out of `List-Unsubscribe`.
- [ ] An SSRF-safe fetch that does one-click POST → GET fallback, ≤5 redirects, with 301/302/303 method downgrade.
- [ ] Two entry points: perform-network-unsubscribe-then-mark, and set-status-only (manual).
- [ ] (to surface the list) a way to aggregate senders by volume — overlaps with email analytics.

## Gotchas

- **SSRF is the headline risk.** The URL comes from untrusted email. An unguarded server-side fetch lets an attacker probe your internal network. Guard before the first request AND ideally after each redirect.
- **Redirect method downgrade** — keep POST across 307/308 but switch to GET on 301/302/303, dropping the body. Wrong handling = silent unsubscribe failures.
- **Bound the redirects** (≤5) or a malicious sender can loop you.
- **Don't conflate network success with user intent.** Mark the sender's status locally regardless; the user wanting them gone is the durable fact, the remote unsubscribe is best-effort.
- **Senders without the standard** can't be one-click unsubscribed — degrade gracefully to surfacing the link / manual status, don't error.
- **Could not confirm from source:** exact internals of `attemptAutomaticUnsubscribe` / `isSafeExternalHttpUrl` (the file `utils/senders/unsubscribe.ts` was read at the orchestration level; the low-level fetch+guard helpers are reconstructed from the documented behavior — POST-one-click-then-GET, ≤5 redirects, 301/302/303→GET, `isSafeExternalHttpUrl`). Verify the guard's exact deny-list before relying on it.

## Origin (reference only)

Repo: https://github.com/elie222/inbox-zero —
`apps/web/utils/actions/unsubscriber.ts` (server actions `setNewsletterStatusAction`, `unsubscribeSenderAction`),
`apps/web/utils/senders/unsubscribe.ts` (`unsubscribeSenderAndMark`, `setSenderStatus`, `attemptAutomaticUnsubscribe`, `getHttpUnsubscribeLink`, `ONE_CLICK_REQUEST_BODY`),
`isSafeExternalHttpUrl` helper. `Newsletter` model + `NewsletterStatus` enum in `apps/web/prisma/schema.prisma`.
