# Domain: agent-guardrails

**What this domain means:** Mechanisms that constrain what an AI coding agent is *allowed* to produce — not by asking it nicely in a prompt, but by deterministic enforcement that runs outside the model and can block its output. The defining shift is **executable policy over prose policy**: instead of writing "please verify webhook signatures" in a markdown instruction the model may or may not honor, you ship a program (a hook, a linter, a CI gate) that inspects the agent's writes and hard-fails the ones that violate a rule.

This is distinct from [[plugin-architecture]] (how an agent extension is *packaged*) and from [[diagnostics]] (reporting health). Guardrails are about **bounded autonomy**: the agent is free to act, but inside a fence that something other than the agent enforces.

## Recurring ideas across repos studied

- **Deterministic > probabilistic.** Rules that matter (security, money, data loss) are encoded as code that returns deny/warn/pass, not as natural-language guidance the model statistically might follow.
- **Lifecycle interception.** Hooks fire at well-defined points (pre-write, post-write, end-of-turn) so a bad artifact is caught at the moment it's created, before it lands in the repo or runs.
- **Graceful-by-default, deny-on-violation.** The enforcer must never break the agent on its own bugs — internal errors fall through to "allow" — but a confirmed rule violation blocks hard (non-zero exit).
- **Escape hatches with provenance.** A documented per-rule bypass (an inline ignore tag with a stated reason) keeps the gate from becoming a productivity wall, while leaving an audit trail of every deliberate override.
- **Audit trails.** Denials are logged so a human can review what the agent tried to do and why it was stopped.

## Features filed here

| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Deterministic Security Hooks | pagokit | [study](study/deterministic-security-hooks--from-pagokit.md) | [build](build/deterministic-security-hooks--from-pagokit.md) |
| Staged Actions Confirmation Queue | open-carrusel | [study](study/staged-actions-queue--from-open-carrusel.md) | [build](build/staged-actions-queue--from-open-carrusel.md) |

## Related domains
- [[plugin-architecture]] — guardrail hooks are usually shipped *as* part of a plugin; this domain is the enforcement idea, that one is the packaging.
- [[agent-distribution]] — the install runbook's "Boundaries" list is the prose cousin of executable guardrails.
- [[credential-management]] — many guardrail rules exist specifically to keep secrets out of agent-written code.
