# Domain: permissions

How apps ask for, check, and recover user consent to sensitive capabilities (camera, location, contacts, health, notifications, …) — normalized into one uniform model regardless of the wildly inconsistent native APIs underneath.

## What this domain is about

Every platform exposes a different, inconsistent API for each permission: some answer synchronously, some via callback, some via a delegate you must keep alive; each has its own state enum and its own request method. The work of this domain is *normalization* — collapsing that mess into a single shape so the rest of an app can reason about consent uniformly: one status vocabulary, one request call, one "send the user to Settings" recovery path. It's adjacent to [[privacy]] (protecting data the user has) but distinct: permissions is about the *consent gate* in front of a capability, not about redaction or encryption of data already captured.

## Common patterns

- **Normalized status model**: map every native authorization enum onto a small fixed set (authorized / denied / notDetermined / notSupported); fold non-actionable native states (restricted, unknown) into denied.
- **Abstract base + per-permission subclass**: one contract (`status` + `request`) implemented once per permission, each translating its native API into the shared vocabulary.
- **Configuration as associated data, not new types**: sub-flavored permissions (calendar full/write, location whenInUse/always, notification option sets) carry their config inside an enum case rather than spawning separate permission classes.
- **Uniform denial recovery**: because iOS denials are sticky, every permission exposes the same "open the Settings page" affordance.
- **Async→sync bridging** so status stays a plain readable property even over callback/delegate-only APIs.

## Features in this domain

- [[unified-permission-abstraction--from-permissionskit]] — abstract `Permission` base class normalizing 18 iOS/Apple-platform permissions onto a 4-state status model + uniform `request`/`openSettingPage`, with sub-flavors carried as associated values on a `Kind` enum.

## Cross-domain links

- Mechanism lives in [[infrastructure/async-to-sync-status-bridging--from-permissionskit]] — the DispatchSemaphore/static-anchor bridge that makes the synchronous `status` property possible.
- Distributed via [[infrastructure/modular-permission-packaging--from-permissionskit]] — per-permission modules so apps adopt one permission at a time and avoid referencing sensitive APIs they don't use.
- Adjacent to [[privacy]] — consent gate (this domain) vs. protecting captured data (privacy).
