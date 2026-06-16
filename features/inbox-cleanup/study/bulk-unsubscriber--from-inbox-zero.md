# Bulk Unsubscriber — from [inbox-zero](https://github.com/elie222/inbox-zero)

> Domain: [[_domain]] · Source: https://github.com/elie222/inbox-zero · NotebookLM: <link once added>

## What it does

Shows you a list of every newsletter/marketing sender filling your inbox and lets you unsubscribe from any of them with one click — Inbox Zero actually performs the unsubscribe for you (it doesn't just open the sender's unsubscribe page and make you click through), then records that sender as unsubscribed so it can be auto-archived going forward.

## Why it exists

Unsubscribing is high-friction by design: every newsletter hides its unsubscribe link, and clicking it usually means a page load, sometimes a login, sometimes a "are you sure?" funnel. Multiply that by 50 newsletters and nobody does it. The job-to-be-done is **collapsing unsubscribe to a single click that the software completes end-to-end**, plus remembering the decision so the sender never bothers you again even if the unsubscribe itself is slow to take effect.

## How it actually works

Email has a standard for this that most marketing senders honor: the **`List-Unsubscribe` header**. It contains one or both of a `mailto:` address and an `https://` URL. There's also a companion standard (RFC 8058) — if a sender includes `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, you can unsubscribe with a single HTTP POST, no human interaction required.

The flow:

1. **Find the method.** From the stored email's headers, extract the HTTP unsubscribe URL from the `List-Unsubscribe` header (preferred), falling back to any unsubscribe link found in the body.
2. **Validate the URL.** Before touching it, the URL is checked with a safety guard (`isSafeExternalHttpUrl`) — this prevents the server from being tricked into hitting internal/private addresses (an SSRF defense).
3. **Execute the one-click unsubscribe.** It sends a **POST** with the body `List-Unsubscribe=One-Click` and content-type `application/x-www-form-urlencoded` (the RFC 8058 one-click form). If the POST fails, it falls back to a **GET**. It follows up to 5 redirects, correctly downgrading POST→GET on 301/302/303 (per HTTP semantics) while preserving the method on 307/308.
4. **Record the decision.** If the unsubscribe succeeds, the sender's `Newsletter` record is marked `UNSUBSCRIBED`. The user can also manually set a sender's status (`APPROVED`, `UNSUBSCRIBED`, or `AUTO_ARCHIVED`) without performing a network unsubscribe.

The status tracking is what makes it durable: once a sender is marked unsubscribed (or auto-archive), the system knows to stop surfacing or to auto-clean their future mail, regardless of whether the sender actually honors the unsubscribe.

## The non-obvious parts

- **It genuinely performs the unsubscribe server-side** via the standardized one-click POST — that's the magic, and it only works because of the `List-Unsubscribe`/RFC 8058 standards. Senders who don't implement the standard can't be one-click unsubscribed (fall back to the link/manual status).
- **SSRF is the real risk and they guard it.** Unsubscribe URLs are attacker-controlled (they come from incoming email). Blindly fetching them server-side is an SSRF hole; the `isSafeExternalHttpUrl` check is essential, not optional.
- **Redirect method-downgrade is handled correctly.** Naive HTTP clients keep POSTing across redirects; the RFC says 301/302/303 should become GET. Getting this wrong makes some unsubscribes silently fail.
- **Status is decoupled from the network result.** Marking a sender `AUTO_ARCHIVED` or `UNSUBSCRIBED` is a local decision the system honors even if the actual unsubscribe is unreliable — the user's inbox stays clean either way.
- **It's sender-centric.** The unit is the sender/newsletter, not the message, which is what lets the bulk UI list "who's emailing you" and act per-sender. (The "who's emailing you" volume stats are the sibling analytics feature.)

## Related

- [[bulk-archiver--from-inbox-zero]] — the other half of cleanup; senders marked AUTO_ARCHIVED feed archiving.
- [[ai-rules-engine--from-inbox-zero]] — a NEWSLETTER-type rule can auto-handle these senders going forward.
- [[email-provider-abstraction--from-inbox-zero]] — reading the headers and archiving go through the provider.
- See also: any "do it for me" automation over a web standard; the parse-header → safe-fetch → record-status pattern recurs.
