# Multi-Path Authentication — from [openpaper](https://github.com/khoj-ai/openpaper)

> Domain: [[_domain]] · Source: https://github.com/khoj-ai/openpaper · NotebookLM: <link once added>

## What it does

Three ways in: sign in with Google, or get a 6-digit code emailed to you, or connect your Zotero
account. The first two log you in; the Zotero one is different — it doesn't create a login, it *links*
your Zotero library to an account you're already signed into so the app can import your references.

## Why it exists

Lower the friction to a first session (Google = one click; email code = no password to remember), and
unlock the killer import (Zotero) for the researchers who live in it. Three doors, each aimed at a
different user's path of least resistance.

## How it actually works

Sessions are **opaque server-side tokens**, not JWTs. On successful login the server mints a 64-char
random token, stores it in a `sessions` table with a 30-day expiry, and sets it as an httpOnly
`session_token` cookie. Protected routes resolve the current user from either that cookie or an
`Authorization: Bearer` header.

**Google** is plain OAuth2: the client asks the server for an auth URL (with a `state` value), the user
approves at Google, Google redirects back with a `code`, the server swaps it for tokens, fetches the
user's profile, upserts the user, mints a session, and redirects to the app with the cookie set.

**Email code** is three calls: request a code (server generates a 6-digit number, stores it on the user
row with a 10-minute expiry, emails it), optionally set your name, then verify the code (plain equality
+ not-expired check) which mints the session.

**Zotero** is OAuth 1.0a and requires you to already be logged in. You hit "connect," the server gets a
request token from Zotero and stashes it in a pending-tokens table tied to your user, you approve on
zotero.org, Zotero redirects back with a verifier, the server exchanges it for a permanent Zotero API
key, stores the connection, and deletes the pending record. From then on the app can read your Zotero
library (and a daily background sync keeps it fresh).

**Account linking is refused, not merged.** If an email already exists under a different provider, the
flow bounces you with an error rather than merging the two.

## The non-obvious parts

- **Opaque DB tokens, no JWT.** Simpler to reason about and instantly revocable (delete the row), at the
  cost of a DB lookup per request.
- **The OAuth `state` is generated but never verified** on the Google callback — so there's effectively
  no CSRF protection via state. Worth fixing in any port.
- **Verification codes use `random`, not `secrets`** — not cryptographically secure — and are **stored
  in plaintext** on the user row. Combined with no rate limiting, the 6-digit space is brute-forceable.
- **Zotero ≠ login.** Easy to assume "connect Zotero" signs you in; it doesn't. Its callback has no auth
  dependency — identity comes from the pending record created while you *were* authenticated.
- **No provider merge.** One email = one provider, forever, or you're locked out of the other door.
- **A logout bug:** single-device logout reads the token from a not-yet-set response header, so only
  "log out everywhere" actually works.

## Related
- [[pdf-highlights-annotations--from-openpaper]] (Zotero connection feeds the `zotero_annotation_key` import dedupe)
- [[pdf-ingestion-pipeline--from-openpaper]] (Zotero imports use the `skip_metadata_extraction` fast path)
- See also: any session-cookie auth — the twist here is three providers with refuse-don't-merge linking and an OAuth-1.0a side-channel for library access.
