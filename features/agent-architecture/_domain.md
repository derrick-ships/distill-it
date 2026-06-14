# Domain: agent-architecture

Patterns for structuring AI agent skills: separating prose contracts from executable engines, enforcing output consistency across harnesses, and designing for cross-platform compatibility.

## What this domain is about

Agent architecture covers the structural decisions that determine how an AI skill behaves reliably across different runtimes (Claude Code, Cursor, Copilot, Gemini CLI). The key tension: the LLM is non-deterministic, but users expect consistent output format. This domain captures patterns that constrain the model's behavior through explicit contracts without over-specifying implementation.

## Core patterns

- **Prose/code separation**: SKILL.md (agent contract) vs Engine (Python implementation) — the skill runs everywhere; the engine handles the heavy lifting
- **Output contracts**: Explicit "laws" the model must follow for consistent output format
- **Cross-harness compatibility**: Any feature that works only on one platform is a regression

## Features in this domain

- [[agent-output-contract--from-last30days-skill]] — 5-law output contract pattern for consistent LLM behavior
