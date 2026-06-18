# Multi-Platform Agent Sync — from [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)

> Domain: [[_domain]] · Source: https://github.com/JCodesMore/ai-website-cloner-template · NotebookLM:

## What it does

This pattern maintains a single canonical instruction document (`AGENTS.md`) that defines the project's rules, conventions, and agent skill definitions. Two sync scripts automatically regenerate the 11+ platform-specific configuration files (CLAUDE.md, GEMINI.md, `.cursor/rules/`, `.continue/` configs, etc.) from that single source. When you update AGENTS.md, one command propagates the change everywhere.

## Why it exists

AI coding agents proliferated fast — Claude Code, Cursor, GitHub Copilot, Gemini CLI, Cline, Windsurf, and more all read their instructions from different files in different formats. Without a sync system, maintaining the same project behavior across tools means manually editing a dozen files and keeping them in sync by hand. They drift. The AGENTS.md pattern treats the instruction set as a first-class artifact with its own source of truth and build process.

## How it actually works

**AGENTS.md** is the source file. It contains all project context: what the project is, naming conventions, code quality rules, the `/clone-website` skill definition, and safety guidelines. It's written in plain Markdown in a format that every AI agent can read directly.

**`scripts/sync-agent-rules.sh`** reads AGENTS.md and generates derivative copies:
- `CLAUDE.md` for Claude Code (same content, Claude-specific preamble)
- `GEMINI.md` for Gemini CLI (same content, Gemini-specific preamble)
- `.cursor/rules/project.mdc` for Cursor
- `.github/copilot-instructions.md` for GitHub Copilot
- `CLINE.md` / `.cline/` for Cline
- `WINDSURF.md` for Windsurf
- And so on for Amazon Q, Augment Code, OpenCode, Codex CLI, Aider

**`scripts/sync-skills.mjs`** regenerates the skill files. The `/clone-website` skill is defined canonically in `.claude/skills/clone-website/SKILL.md`. The sync script reads it and generates equivalent skill configuration in each platform's format:
- `.cursor/rules/clone-website.mdc`
- `.continue/config.json` (commands block)
- Platform-specific command files for each other agent

The scripts use Node.js or bash string templating — no external dependencies. Each generated file carries a `# DO NOT EDIT — generated from AGENTS.md by scripts/sync-agent-rules.sh` header so editors know not to modify the copy directly.

## The non-obvious parts

**Skills vs rules are separate sync paths.** `sync-agent-rules.sh` handles the always-active project context (CLAUDE.md, GEMINI.md, etc.) while `sync-skills.mjs` handles the slash-command skill definitions. They're separate because different platforms represent "always-on instructions" and "user-invocable commands" very differently.

**Generated files should be checked into git.** Counter-intuitively, the generated derivative files (CLAUDE.md, .cursor/rules/, etc.) are committed to the repo, not gitignored. This lets any new contributor or AI agent read them immediately without running a build step. The sync scripts re-generate them on demand; git history shows drift.

**Platform differences are abstracted away.** The main AGENTS.md doesn't need to know about platform-specific syntax (Cursor's `.mdc` frontmatter, Continue's JSON schema, etc.). The sync scripts handle the translation. The rule author thinks in "project conventions," not "Cursor syntax."

**Skill definitions use a compatible subset.** The canonical SKILL.md uses Claude Code's skill syntax (YAML frontmatter + markdown). Other platforms don't have skill systems as rich, so the sync script degrades gracefully: platforms with rich command support get a full equivalent, platforms without it get the skill's instructions injected into the always-on rules file.

## Related

- [[website-cloning-pipeline--from-ai-website-cloner-template]] — the skill this system syncs
- [[skills-system--from-open-design]] — a more elaborate plugin/skill system with SHA-256 digests and 22+ adapters
- [[plugin-ecosystem--from-open-design]] — the 3-tier plugin discovery system that inspired this pattern
- [[agent-driven-install--from-agent-reach]] — related pattern: markdown as the authoritative runbook for agents
