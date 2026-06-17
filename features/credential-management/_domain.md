# Domain: credential-management

Patterns for managing multi-tier authentication in tools that aggregate from heterogeneous sources — keyless public APIs, browser-cookie sessions, and paid API keys — with graceful degradation when credentials are absent.

## What this domain is about

Tools that aggregate from multiple platforms face a credential zoo: some sources are public, some require browser login, some require paid API keys. Credential management in this context is about layering these gracefully: the tool should always work with zero credentials (reduced coverage), work better with browser cookies, and best with API keys — without requiring users to set up everything before getting value.

## Core patterns

- **Three-tier auth**: keyless (always works) → browser cookie (free but fragile) → API key (reliable but paid)
- **Dual env file locations**: project-scoped (`.claude/last30days.env`) takes priority over user-level (`~/.config/`)
- **Preflight source checking**: determine which sources are available before the main pipeline runs
- **Silent degradation**: missing credential = source skipped, not crash
- **Browser-cookie harvesting**: reuse the user's existing browser session instead of asking for tokens; validate the *logged-in marker*, not mere presence
- **Atomic secret writes**: create credential files owner-only (`O_CREAT` + `0o600`) so they're never briefly world-readable — no write-then-chmod race

## Features in this domain

- [[multi-tier-credentials--from-last30days-skill]] — three-tier auth pattern with preflight availability checking
- [[cookie-credential-extraction--from-agent-reach]] — multi-browser cookie harvest (rookiepy→browser_cookie3) driven by declarative per-platform specs, validate-before-save, atomic 0o600 store, and shell-safe best-effort mirrors into upstream tools' credential files
- [[browser-host-api-proxy--from-open-generative-ai]] — bring-your-own-key proxy: same-origin Next.js route forwards browser calls to a gateway (injecting `x-api-key`, dodging CORS), an env switch lets Electron/SSR bypass the proxy, and a global `muapi:auth-required` DOM event drives re-auth on 401/403. Key kept in both localStorage (client) and a cookie (server). Convenience-proxy threat model, *not* a shared-secret boundary.
