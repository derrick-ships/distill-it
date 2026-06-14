# Domain: credential-management

Patterns for managing multi-tier authentication in tools that aggregate from heterogeneous sources — keyless public APIs, browser-cookie sessions, and paid API keys — with graceful degradation when credentials are absent.

## What this domain is about

Tools that aggregate from multiple platforms face a credential zoo: some sources are public, some require browser login, some require paid API keys. Credential management in this context is about layering these gracefully: the tool should always work with zero credentials (reduced coverage), work better with browser cookies, and best with API keys — without requiring users to set up everything before getting value.

## Core patterns

- **Three-tier auth**: keyless (always works) → browser cookie (free but fragile) → API key (reliable but paid)
- **Dual env file locations**: project-scoped (`.claude/last30days.env`) takes priority over user-level (`~/.config/`)
- **Preflight source checking**: determine which sources are available before the main pipeline runs
- **Silent degradation**: missing credential = source skipped, not crash

## Features in this domain

- [[multi-tier-credentials--from-last30days-skill]] — three-tier auth pattern with preflight availability checking
