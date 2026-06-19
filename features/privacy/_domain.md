# Domain: privacy

Patterns for protecting user data at every layer — capture-time exclusion, pattern-based secret redaction before storage or AI processing, encryption at rest with OS-managed keys, and audit controls that give users visibility and control over what is retained.

## What this domain is about

Privacy architecture is not a feature you add at the end; it's a set of design decisions made at every integration point where data flows. The key insight is that encryption at rest alone is insufficient — secrets must be intercepted *before* they touch storage or external APIs. This domain covers the mechanisms that make "privacy by default" real: regex-based redaction pipelines, OS clipboard privacy flag respect, capture-time filtering, and layered encryption with keychain-stored keys.

## Common patterns

- **Capture-time exclusion**: filter sensitive data at the moment it's captured (clipboard items with OS privacy flags, password manager content) rather than trying to redact it later
- **Pattern-based redaction**: regex pipelines that detect and strip well-known secret formats (API keys, JWTs, credit cards, env vars) before data is stored or sent to external services
- **AES-256-GCM at rest**: symmetric encryption with keys stored in OS keychains (not config files or env vars)
- **Opt-in cloud vs. local-first**: default all storage to local; any cloud sync requires explicit user opt-in with E2E encryption

## Features in this domain

- [[pattern-based-secret-redaction--from-asyar]] — multi-pattern regex pipeline that intercepts clipboard content, AI context, and user input before storage, redacting API keys, JWTs, credit cards, and other secrets in place; AES-256-GCM encryption at rest with OS keychain key management.

## Cross-domain links

- Feeds [[ai-integration/ai-agent-tool-calling--from-asyar]] — AI context is scrubbed by the redaction pipeline before being sent to any LLM provider
- Related to [[credential-management/multi-tier-credentials--from-last30days-skill]] — a different angle on the same problem (securing credentials used by the system)
