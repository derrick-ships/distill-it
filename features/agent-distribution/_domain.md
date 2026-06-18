# Domain: agent-distribution

Patterns for shipping, installing, and maintaining software *through* an AI agent — where a versioned natural-language runbook is the installer, bounded by explicit safety guardrails, and the same mechanism handles updates and ongoing health.

## What this domain is about

When the user of a tool is (or works through) an AI agent, the natural installer is the agent itself. Instead of a binary or a shell script, you ship a markdown document written as an executable plan: the agent fetches it live and carries out install, environment adaptation, repair, and credential collection — pausing to ask the user only where it must. This domain captures how to make that *safe and reliable*: hard boundaries that define the blast radius, pre-decided branches for known environment failures, explicit user checkpoints, and a "selector/router, never a wrapper" framing so the agent uses upstream tools directly afterward. Distribution, update, and daily maintenance become one pattern: an agent acting on a live, versioned doc.

## Core patterns

- **The doc is the program**: a runbook whose primary reader is an LLM — imperative steps, explicit branches, a clear definition of done
- **Bounded autonomy is the product**: DO-NOT guardrails (no `sudo`, confined to a dedicated dir, never pollute the workspace, escalate-don't-elevate) are what make agent-driven install shippable
- **Branch-on-environment as prose**: enumerate known failure symptoms (PEP 668, Homebrew Python, Windows Store alias) → exact alternative command, so the agent does the detection an installer would hard-code
- **Ask, don't assume**: explicit user checkpoints for choices the agent shouldn't make alone (which features, which credentials); never install everything by default
- **One mechanism, whole lifecycle**: install.md / update.md / a silent-unless-problem daily `watch` are the same "agent reads a live doc and acts" pattern
- **Two readers, one file**: a thin "For Humans" trigger over a long "For AI Agents" spec

## Features in this domain

- [[agent-driven-install--from-agent-reach]] — install.md as an agent-executable runbook: goal + "never a wrapper" framing, hard safety boundaries, artifact-location table, env-branched steps, user checkpoints, and the update/`watch` maintenance loop
- [[self-customizing-crm--from-auto-crm]] — `.claude/commands/*.md` as the *configuration layer* of a product: the agent edits the real Drizzle schema/components to fit the business instead of a settings UI; structural (setup/connect/customize/import) vs operational (add-lead/analyze/briefing/digest) commands, guard-railed by CLAUDE.md/AGENTS.md
