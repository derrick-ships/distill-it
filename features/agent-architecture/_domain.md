# Domain: agent-architecture

Patterns for structuring AI agent skills: separating prose contracts from executable engines, enforcing output consistency across harnesses, and designing for cross-platform compatibility.

## What this domain is about

Agent architecture covers the structural decisions that determine how an AI skill behaves reliably across different runtimes (Claude Code, Cursor, Copilot, Gemini CLI). The key tension: the LLM is non-deterministic, but users expect consistent output format. This domain captures patterns that constrain the model's behavior through explicit contracts without over-specifying implementation.

## Core patterns

- **Prose/code separation**: SKILL.md (agent contract) vs Engine (Python implementation) — the skill runs everywhere; the engine handles the heavy lifting
- **Output contracts**: Explicit "laws" the model must follow for consistent output format
- **Cross-harness compatibility**: Any feature that works only on one platform is a regression
- **Capability routing & resilience**: an agent capability modeled as an ordered list of interchangeable backends with health-gated, automatic fallback — "switching backend" is a data edit, not a code change

## Features in this domain

- [[agent-output-contract--from-last30days-skill]] — 5-law output contract pattern for consistent LLM behavior
- [[ordered-backend-routing--from-agent-reach]] — each capability is a Channel owning an ordered backend list; two-phase health-gated selection (first `ok` wins, then first `warn`) with user-pinnable, unknown-value-ignored overrides
- [[conversation-memory--from-whatsapp-agentkit]] — minimal async per-contact chat memory: one SQL table keyed on phone number, rolling last-N window returned LLM-shaped, SQLite/Postgres swap via one env var
- [[mcp-crm-server--from-auto-crm]] — exposes a whole product (a local SQLite CRM) to an LLM as 10 stdio MCP tools shaped around the domain's nouns/verbs; read-tools pre-aggregate so the model narrates instead of computing, and the no-auth local-trust model rides on stdio being local-only
