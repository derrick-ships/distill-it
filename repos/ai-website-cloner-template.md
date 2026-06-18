# ai-website-cloner-template

**Source**: https://github.com/JCodesMore/ai-website-cloner-template  
**Distilled**: 2026-06-18  
**Status**: Distilled

## What it is

A Next.js 16 / React 19 project template that uses AI coding agents to reverse-engineer any website into a clean, production-ready codebase. Give the `/clone-website` command a URL and the agent performs browser-based reconnaissance, extracts computed design tokens, generates component specifications, builds the components (optionally in parallel via git worktrees), and assembles the final application.

## Stack

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript (strict)
- **Styles**: Tailwind CSS v4 with oklch color tokens, shadcn/ui (Radix primitives)
- **Icons**: Lucide React (replaced by extracted SVGs during build)
- **Dev environment**: Docker + Docker Compose, Node.js 24 (enforced via .nvmrc)
- **Deployment**: Vercel-compatible, Docker-ready
- **AI agent support**: Claude Code, Cursor, GitHub Copilot, Gemini CLI, Cline, Windsurf, Amazon Q, Augment Code, Continue, Codex CLI, Aider, OpenCode (12+ platforms)

## Distilled features

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Website Cloning Pipeline | web-cloning | [study](../features/web-cloning/study/website-cloning-pipeline--from-ai-website-cloner-template.md) | [build](../features/web-cloning/build/website-cloning-pipeline--from-ai-website-cloner-template.md) |
| Browser Design Token Extraction | web-extraction | [study](../features/web-extraction/study/browser-design-token-extraction--from-ai-website-cloner-template.md) | [build](../features/web-extraction/build/browser-design-token-extraction--from-ai-website-cloner-template.md) |
| Component Specification Generation | code-generation | [study](../features/code-generation/study/component-spec-generation--from-ai-website-cloner-template.md) | [build](../features/code-generation/build/component-spec-generation--from-ai-website-cloner-template.md) |
| Multi-Platform Agent Sync | plugin-architecture | [study](../features/plugin-architecture/study/multi-platform-agent-sync--from-ai-website-cloner-template.md) | [build](../features/plugin-architecture/build/multi-platform-agent-sync--from-ai-website-cloner-template.md) |
| Parallel Worktree Build | dev-tooling | [study](../features/dev-tooling/study/parallel-worktree-build--from-ai-website-cloner-template.md) | [build](../features/dev-tooling/build/parallel-worktree-build--from-ai-website-cloner-template.md) |

## Key design decisions

1. **Computed styles over source CSS** — `getComputedStyle()` gives post-cascade truth regardless of the target site's framework
2. **Spec-driven construction** — AI builders get structured component specs with exact values, not screenshots alone
3. **AGENTS.md as single source of truth** — one document, sync scripts propagate to 12+ platforms
4. **Worktrees for parallel agents** — isolates concurrent builds to prevent mid-build merge conflicts
5. **oklch color tokens** — Tailwind v4 native; perceptually uniform; avoids the visual drift of hex approximations
