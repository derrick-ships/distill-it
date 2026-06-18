# Domain: messaging

Patterns for connecting an app to chat/messaging channels (WhatsApp, SMS, Telegram, etc.) through a provider-agnostic abstraction, so the core logic never depends on which vendor delivers the messages.

## What this domain is about

Messaging integrations are full of vendor-specific ugliness: every provider has its own webhook payload shape, send API, auth scheme, success codes, and verification handshakes. The recurring problem is keeping all of that out of your application's core. This domain captures the adapter/strategy pattern applied to messaging — a single normalized message type, a config-driven factory, and one adapter per provider that translates the vendor's reality into the common contract. Switching or adding a provider becomes a config edit plus one new adapter, not a rewrite.

## Core patterns

- **Normalized message type**: force every provider to emit the same small object (sender, body, message id, is-echo) so downstream code is written once
- **Config-driven factory**: pick the provider from an env var; lazy-import only the chosen adapter
- **Per-provider adapters**: each owns its parsing, auth, endpoint, and success-code quirks behind a shared abstract interface
- **Optional handshakes on the base**: features only some providers need (e.g. Meta's GET verification) live as no-op defaults on the base class so the caller stays branch-free

## Features in this domain

- [[whatsapp-provider-adapter--from-whatsapp-agentkit]] — abstract `ProveedorWhatsApp` + factory + Meta/Twilio adapters normalizing webhooks into a common `MensajeEntrante`; provider chosen via `WHATSAPP_PROVIDER`, core code never branches on vendor
