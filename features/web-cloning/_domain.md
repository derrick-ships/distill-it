# Domain: web-cloning

Reverse-engineering a live website — its visual design, interactions, assets, and layout — into a clean, production-grade codebase by combining browser-based reconnaissance, AI-generated component specifications, and parallel multi-agent code construction.

## What this domain is about

Web cloning is not screen-scraping. It is a full product-reproduction pipeline: you feed it a URL and it outputs a deployable Next.js application that mirrors the original's look, feel, and structure. The key insight is that rendered styles (computed by `getComputedStyle()`) are more reliable than source stylesheets — they reflect the final cascade regardless of preprocessor or framework. AI builders receive exact CSS values, interaction state screenshots, and structured component specs, so they never have to guess.

## Common patterns

- **Reconnaissance first**: capture screenshots at all viewport sizes and all interaction states before writing a single line of code
- **Spec-driven build**: generate a detailed component spec (with exact computed values) before asking AI to write the component
- **Parallel agents**: use git worktrees to let multiple AI agents build different page sections concurrently without merge conflicts
- **Single source of truth**: AGENTS.md as the canonical instruction document, synced to every AI platform

## Features in this domain

- [[website-cloning-pipeline--from-ai-website-cloner-template]] — the full 5-phase pipeline: recon → foundation → component specs → parallel build → assemble & QA
- [[browser-design-token-extraction--from-ai-website-cloner-template]] — browser-based computed-style extraction for pixel-perfect design token capture (in `web-extraction` domain)
- [[component-spec-generation--from-ai-website-cloner-template]] — spec-driven component docs giving AI builders exact CSS values, interaction models, asset paths (in `code-generation` domain)
- [[parallel-worktree-build--from-ai-website-cloner-template]] — multi-agent parallel section builds via git worktrees (in `dev-tooling` domain)
- [[multi-platform-agent-sync--from-ai-website-cloner-template]] — AGENTS.md single source of truth synced to 11+ AI platforms (in `plugin-architecture` domain)

## Cross-domain links

- Reconnaissance feeds [[browser-design-token-extraction--from-ai-website-cloner-template]] (web-extraction)
- Specs drive [[component-spec-generation--from-ai-website-cloner-template]] (code-generation)
- Build uses [[parallel-worktree-build--from-ai-website-cloner-template]] (dev-tooling)
- Platform support via [[multi-platform-agent-sync--from-ai-website-cloner-template]] (plugin-architecture)
