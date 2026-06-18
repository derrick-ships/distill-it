# Domain: dev-tooling

Patterns and infrastructure for developer workflow automation — parallel builds, environment reproducibility, agent-compatible project layouts, and CI/CD scaffolding.

## What this domain is about

Dev tooling features make the development loop faster, safer, or more scalable. They live at the intersection of git workflows, process orchestration, and IDE/agent integration. Unlike infrastructure (which is about hosting), dev-tooling is about the local development experience and how code gets built, tested, and delivered.

## Common patterns

- **Worktree-based parallelism**: run multiple independent development tracks in isolated git worktrees, merge at the end
- **Docker-first reproducibility**: development and production Dockerfiles ship with the template so environment drift never causes bugs
- **Agent-compatible layout**: project structure designed so AI coding agents can navigate, build, and test without human hand-holding

## Features in this domain

- [[parallel-worktree-build--from-ai-website-cloner-template]] — multi-agent parallel section builds via git worktrees; each agent works on a separate branch, no merge conflicts mid-build
